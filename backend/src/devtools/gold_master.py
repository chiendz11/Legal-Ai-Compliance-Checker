"""Materialize one scoped answer registry without manufacturing legal judgments.

The SQLite database is an evaluator artifact, not the application's runtime DB.
Full-case answers and narrowly scoped observations keep different question scopes.
"""

import argparse
import hashlib
import json
import re
import shutil
import sqlite3
from collections import Counter
from pathlib import Path

from devtools.gold_answers import (
    GoldCase,
    GoldError,
    _artifact_spans_match,
    canonical_sha,
    check_full_gold_coverage,
    validate_gold_case,
    validate_literal_gold,
)

LAYERS = (
    "FACTS",
    "SCOPE_TEMPORAL",
    "CRITERIA",
    "CITATION_OCCURRENCES",
    "RETRIEVAL_JUDGED_POOL",
    "AGGREGATION",
    "RISKS",
    "RECOMMENDATION_ASSERTIONS",
    "REVIEW_POLICY",
    "REPORT_ASSERTIONS",
)
SCOPED_LAYERS = ("APPENDIX_LITERALS", "NUMBERED_MENTIONS", "CATALOG_IDENTITY")
FULL_SCOPE = "PROVIDED_PDF_AND_PINNED_KNOWLEDGE:DRAFT_REVIEW"

SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE metadata(key TEXT PRIMARY KEY, value_json TEXT NOT NULL);
CREATE TABLE cases(
 case_id TEXT PRIMARY KEY, contract_id TEXT UNIQUE NOT NULL, group_id TEXT NOT NULL,
 split TEXT NOT NULL CHECK(split IN ('DEV','VALIDATION','TEST')),
 source_sha256 TEXT NOT NULL, page_count INTEGER NOT NULL,
 knowledge_sha256 TEXT NOT NULL, policy_sha256 TEXT NOT NULL,
 full_case_status TEXT NOT NULL CHECK(full_case_status IN
 ('ADJUDICATED','PENDING_ADJUDICATION')));
CREATE TABLE layer_coverage(
 case_id TEXT NOT NULL REFERENCES cases(case_id), layer TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN
 ('ADJUDICATED','SCOPED_ONLY','PENDING_ADJUDICATION')),
 scope TEXT NOT NULL, answer_count INTEGER NOT NULL, reason TEXT NOT NULL,
 PRIMARY KEY(case_id, layer));
CREATE TABLE answers(
 answer_id TEXT PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(case_id),
 layer TEXT NOT NULL, question_scope TEXT NOT NULL, target_id TEXT NOT NULL,
 annotation_status TEXT NOT NULL CHECK(annotation_status IN
 ('ADJUDICATED','PENDING_ADJUDICATION')),
 scoreable INTEGER NOT NULL CHECK(scoreable IN (0,1)),
 payload_json TEXT NOT NULL, payload_sha256 TEXT NOT NULL,
 origin_json TEXT NOT NULL,
 UNIQUE(case_id, layer, question_scope, target_id),
 CHECK(scoreable=0 OR annotation_status='ADJUDICATED'));
CREATE TABLE evidence(
 answer_id TEXT NOT NULL REFERENCES answers(answer_id), ordinal INTEGER NOT NULL,
 source_sha256 TEXT NOT NULL, source_ref TEXT NOT NULL, page INTEGER NOT NULL,
 start_offset INTEGER NOT NULL, end_offset INTEGER NOT NULL, quote TEXT NOT NULL,
 PRIMARY KEY(answer_id,ordinal));
CREATE TABLE proposals(
 proposal_id TEXT PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(case_id),
 original_path TEXT NOT NULL, annotation_status TEXT NOT NULL
 CHECK(annotation_status='PENDING_RECONCILIATION'), payload_json TEXT NOT NULL);
CREATE VIEW benchmark_answers AS
 SELECT a.*,c.split,c.group_id,c.source_sha256,c.knowledge_sha256,c.policy_sha256
 FROM answers a JOIN cases c USING(case_id) WHERE a.scoreable=1;
CREATE VIEW dev_validation_answers AS
 SELECT * FROM benchmark_answers WHERE split IN ('DEV','VALIDATION');
CREATE VIEW test_answers_evaluator_only AS
 SELECT * FROM benchmark_answers WHERE split='TEST';
CREATE VIEW criterion_finding_answers AS
 SELECT * FROM benchmark_answers WHERE layer='CRITERIA'
 AND json_extract(payload_json,'$.disposition')='ASSESSED';
CREATE VIEW pending_work AS
 SELECT * FROM layer_coverage WHERE status='PENDING_ADJUDICATION';
"""


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def save(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def dumps(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def spans(value):
    """Distinct source spans, including nested controls and context witnesses."""
    result = {}

    def visit(item):
        if isinstance(item, dict):
            if {"source_sha256", "ref", "page", "start", "end", "quote"} <= item.keys():
                result[(item["ref"], item["start"], item["end"])] = item
            for v in item.values():
                visit(v)
        elif isinstance(item, list):
            for v in item:
                visit(v)

    visit(value)
    return list(result.values())


def target_key(layer, row, ordinal):
    if layer in {"FACTS", "APPENDIX_LITERALS"}:
        return row["field"]
    if layer in {"SCOPE_TEMPORAL", "AGGREGATION"}:
        return dumps([row["requirement_id"], row.get("requirement_version_id")])
    if layer == "CRITERIA":
        return row["criterion_id"]
    if layer == "CITATION_OCCURRENCES":
        return row["citation_id"]
    if layer == "RETRIEVAL_JUDGED_POOL":
        return row["criterion_id"] + ":" + row["source_ref"]
    if layer == "RISKS":
        return row["semantic_key"]
    if layer == "RECOMMENDATION_ASSERTIONS":
        return row["source_risk_key"] + ":" + row["template_id"]
    if layer in {"NUMBERED_MENTIONS", "CATALOG_IDENTITY"}:
        e = row["evidence"]
        return f"{e['ref']}:{e['start']}:{e['end']}:{row['number']}"
    return str(ordinal)


def insert_answer(db, *, case, layer, scope, row, origin, adjudicated=True):
    """No upsert: conflicting answers cannot silently replace one another."""
    if not _artifact_spans_match(row, case["source"]):
        raise GoldError("Master source witness mismatch: " + case["case_id"])
    key = target_key(layer, row, origin.get("ordinal", 0))
    ident = canonical_sha([case["case_id"], layer, scope, key])
    db.execute(
        "INSERT INTO answers VALUES(?,?,?,?,?,?,?,?,?,?)",
        (
            ident,
            case["case_id"],
            layer,
            scope,
            key,
            "ADJUDICATED" if adjudicated else "PENDING_ADJUDICATION",
            int(adjudicated),
            dumps(row),
            canonical_sha(row),
            dumps(origin),
        ),
    )
    for n, e in enumerate(spans(row)):
        db.execute(
            "INSERT INTO evidence VALUES(?,?,?,?,?,?,?,?)",
            (
                ident,
                n,
                e["source_sha256"],
                e["ref"],
                e["page"],
                e["start"],
                e["end"],
                e["quote"],
            ),
        )


def check_literal(row):
    """Appendix absence is never promoted into full-document absence."""
    if row.get("scope") != "SYNTHETIC_TRANSACTION_APPENDIX_ONLY":
        raise GoldError("Literal import must preserve its appendix-only question scope")
    if row.get("whole_document_absence_claim") is not False:
        raise GoldError("Scoped literals cannot assert whole-document absence")
    if row.get("annotation_quality") != "GOLD":
        raise GoldError("Unadjudicated scoped literal cannot be imported as Gold")
    if row.get("status") not in {"KNOWN", "CONFLICT", "NOT_PROVIDED_IN_AUTHORED_APPENDIX"}:
        raise GoldError("Unrecognized scoped literal annotation status")


def normalized_number(value):
    """Only a declared document-type spelling alias, without changing the quote."""
    return re.sub(r"/ND(?=-CP$)", "/NĐ", str(value or "").strip().upper())


def check_identity(row, snapshot, *, snapshot_sha=None):
    """Check exact-number identity only; this never assigns a C09 verdict."""
    if (
        row.get("temporal_and_domain_gold") is not False
        or row.get("overall_c09_status") != "UNJUDGED"
    ):
        raise GoldError("Catalog number identity is not citation temporal/domain validity")
    if row.get("knowledge_snapshot_sha256") != (snapshot_sha or canonical_sha(snapshot)):
        raise GoldError("Identity belongs to another knowledge revision")
    identity = row.get("identity")
    if identity not in {"MATCH", "NO_MATCH_IN_PINNED_CATALOG"}:
        return False
    if row.get("annotation_quality") != "GOLD":
        raise GoldError("Unadjudicated identity cannot be imported as Gold")
    number = normalized_number(row["number"])
    matches = [
        d
        for d in snapshot["tables"]["van_ban_phap_ly"]
        if normalized_number(d.get("so_hieu")) == number
    ]
    if identity == "NO_MATCH_IN_PINNED_CATALOG":
        if (
            matches
            or row.get("document_id") is not None
            or row.get("catalog_record_sha256") is not None
            or row.get("catalog_candidate_ids") != []
            or row.get("exhaustive_catalog_membership_check") is not True
            or row.get("real_world_existence_claim") is not False
            or not row.get("reason")
        ):
            raise GoldError("A negative catalog answer needs a checked empty catalog match")
        return True
    doc = next(
        (
            d
            for d in snapshot["tables"]["van_ban_phap_ly"]
            if d["van_ban_id"] == row.get("document_id")
        ),
        None,
    )
    if not doc or canonical_sha(doc) != row.get("catalog_record_sha256"):
        raise GoldError("Catalog identity record changed")
    if len(matches) != 1 or matches[0]["van_ban_id"] != row["document_id"]:
        raise GoldError("Exact number does not uniquely identify the asserted document")
    return True


def build_master(
    *,
    full_release,
    literal_root,
    identity_root,
    sources_root,
    pdf_root,
    snapshot_path,
    public_inputs_root,
    output,
):
    """Combine validated independent answers, keeping unresolved work unscored."""
    if output.exists():
        raise GoldError("Master output must be new; preserve earlier revisions")
    snapshot = load(snapshot_path)
    kb_sha = canonical_sha(snapshot)
    policy = load(full_release / "POLICY_SNAPSHOT.json")
    policy_sha = canonical_sha(policy)
    upstream_index = load(full_release / "SOURCE_INDEX.json")
    index = [
        {
            **r,
            "pdf_path": "sources/pdf/" + r["contract_id"] + ".pdf",
            "text_path": "sources/text/" + r["contract_id"] + ".json",
            "intake_path": "public_inputs/" + r["case_id"] + ".json",
        }
        for r in upstream_index
    ]
    if len(index) != 360 or len({r["case_id"] for r in index}) != 360:
        raise GoldError("Gold Master must preserve the 360-case source denominator")
    grouped = {}
    for r in index:
        if r["split"] not in {"DEV", "VALIDATION", "TEST"}:
            raise GoldError("Unknown split")
        if r["group_id"] in grouped and grouped[r["group_id"]] != r["split"]:
            raise GoldError("Source-group leakage across DEV/VALIDATION/TEST")
        grouped[r["group_id"]] = r["split"]
    artifacts = {}
    for p in sorted((full_release / "artifacts").glob("*/*.json")):
        a = load(p)
        key = a["case_id"] + ":" + a["layer"]
        if key in artifacts:
            raise GoldError("Duplicate full-case artifact")
        artifacts[key] = a
    sources, answers = {}, {}
    # Establish every byte/source/knowledge pin before writing a new release.
    for r in index:
        cid, hid = r["case_id"], r["contract_id"]
        source = load(sources_root / (hid + ".json"))
        observed = hashlib.sha256((pdf_root / (hid + ".pdf")).read_bytes()).hexdigest()
        if (
            source["case_id"] != cid
            or source["source_sha256"] != r["source_sha256"]
            or observed != r["source_sha256"]
        ):
            raise GoldError("Master source PDF/index/text mismatch: " + cid)
        sources[cid] = source
        p = full_release / "cases" / (cid + ".json")
        if p.exists():
            answer = load(p)
            validate_gold_case(GoldCase.model_validate(answer), source, snapshot)
            answers[cid] = answer
        literal = load(literal_root / "literal_gold" / (cid + ".json"))
        validate_literal_gold(literal, source)
    gate = check_full_gold_coverage(sources, answers, snapshot, artifacts=artifacts)
    if any(e.get("case_id") in answers for e in gate["errors"] if isinstance(e, dict)):
        raise GoldError("A supposedly completed case fails its layer checks")
    # Recheck each completed case; global errors also include legitimately pending cases.
    for cid, answer in answers.items():
        one = check_full_gold_coverage(
            {cid: sources[cid]}, {cid: answer}, snapshot, artifacts=artifacts
        )
        if one["errors"]:
            raise GoldError("Invalid full-case materialization: " + cid)
    output.mkdir(parents=True)
    try:
        with sqlite3.connect(output / "gold_master.sqlite") as db:
            db.executescript(SCHEMA)
            for r in index:
                cid = r["case_id"]
                completed = cid in answers
                source = sources[cid]
                case = {**r, "source": source}
                db.execute(
                    "INSERT INTO cases VALUES(?,?,?,?,?,?,?,?,?)",
                    (
                        cid,
                        r["contract_id"],
                        r["group_id"],
                        r["split"],
                        r["source_sha256"],
                        source["page_count"],
                        kb_sha,
                        policy_sha,
                        "ADJUDICATED" if completed else "PENDING_ADJUDICATION",
                    ),
                )
                for layer in LAYERS:
                    a = artifacts.get(cid + ":" + layer) if completed else None
                    rows = a["judgments"] if a else []
                    for n, row in enumerate(rows):
                        insert_answer(
                            db,
                            case=case,
                            layer=layer,
                            scope=FULL_SCOPE,
                            row=row,
                            origin={
                                "kind": "BOUND_FULL_CASE_ARTIFACT",
                                "artifact_sha256": canonical_sha(a),
                                "ordinal": n,
                            },
                        )
                    db.execute(
                        "INSERT INTO layer_coverage VALUES(?,?,?,?,?,?)",
                        (
                            cid,
                            layer,
                            "ADJUDICATED" if completed else "PENDING_ADJUDICATION",
                            FULL_SCOPE,
                            len(rows),
                            "Bound source-adjudicated artifact; retrieval is a bounded judged pool"
                            if completed
                            else (
                                "Whole-case source adjudication not completed; "
                                "no legal UNKNOWN answer manufactured"
                            ),
                        ),
                    )
                literal = load(literal_root / "literal_gold" / (cid + ".json"))
                if (
                    literal["source_sha256"] != r["source_sha256"]
                    or literal["case_id"] != cid
                    or literal["knowledge_snapshot_sha256"] != kb_sha
                    or literal.get("production_outputs_used") is not False
                    or literal.get("full_document_profile_gold") is not False
                    or literal.get("quality") != "SCOPED_GOLD"
                    or literal.get("scope") != "APPENDIX_LITERALS_AND_NUMBERED_MENTIONS"
                ):
                    raise GoldError("Scoped literal source/quality pin mismatch: " + cid)
                for n, row in enumerate(literal["fields"]):
                    check_literal(row)
                    insert_answer(
                        db,
                        case=case,
                        layer="APPENDIX_LITERALS",
                        scope=row["scope"],
                        row=row,
                        origin={
                            "kind": "SCOPED_SOURCE_LITERAL",
                            "artifact_sha256": canonical_sha(literal),
                            "ordinal": n,
                            "original_path": "imports/literal_gold/" + cid + ".json",
                        },
                    )
                for n, row in enumerate(literal["numbered_mentions"]):
                    if (
                        row.get("identity_or_validity_claim") is not False
                        or row.get("scope") != "NUMBERED_MENTION_ONLY"
                        or row.get("annotation_quality") != "GOLD"
                    ):
                        raise GoldError("Numbered mention cannot be promoted to legal validation")
                    insert_answer(
                        db,
                        case=case,
                        layer="NUMBERED_MENTIONS",
                        scope="DECLARED_NUMBER_PATTERNS_ONLY",
                        row=row,
                        origin={
                            "kind": "SCOPED_LITERAL_OCCURRENCE",
                            "artifact_sha256": canonical_sha(literal),
                            "ordinal": n,
                        },
                    )
                identities = load(identity_root / "catalog_identity" / (cid + ".json"))
                save(output / "imports" / "literal_gold" / (cid + ".json"), literal)
                save(output / "imports" / "catalog_identity" / (cid + ".json"), identities)
                for n, row in enumerate(identities):
                    if row["case_id"] != cid or row.get("production_outputs_used") is not False:
                        raise GoldError("Invalid identity provenance")
                    ready = check_identity(row, snapshot, snapshot_sha=kb_sha)
                    insert_answer(
                        db,
                        case=case,
                        layer="CATALOG_IDENTITY",
                        scope="EXACT_NUMBER_TO_PINNED_CATALOG_IDENTITY_ONLY",
                        row=row,
                        adjudicated=ready,
                        origin={
                            "kind": "SCOPED_IDENTITY_ONLY",
                            "ordinal": n,
                            "number_alias_policy": "UPPERCASE_AND_ND_TO_NĐ_DOCUMENT_TYPE_ONLY",
                            "source_quote_preserved": True,
                            "original_path": "imports/catalog_identity/" + cid + ".json",
                        },
                    )
                for layer in SCOPED_LAYERS:
                    count = db.execute(
                        "SELECT count(*) FROM answers WHERE case_id=? AND layer=? AND scoreable=1",
                        (cid, layer),
                    ).fetchone()[0]
                    db.execute(
                        "INSERT INTO layer_coverage VALUES(?,?,?,?,?,?)",
                        (
                            cid,
                            layer,
                            "SCOPED_ONLY",
                            layer,
                            count,
                            "This bounded scope does not complete its full-document/E2E layer",
                        ),
                    )
                # Legacy partial verdicts/presence pools are retained for reconciliation,
                # never silently imported as current C05/C07/C09 Gold.
                for folder in ("cases", "evidence_components", "derived_assertions"):
                    old = identity_root / folder / (cid + ".json")
                    if old.is_file():
                        data = load(old)
                        db.execute(
                            "INSERT INTO proposals VALUES(?,?,?,?,?)",
                            (
                                canonical_sha([cid, folder]),
                                cid,
                                folder + "/" + old.name,
                                "PENDING_RECONCILIATION",
                                dumps(data),
                            ),
                        )
                intake = load(public_inputs_root / (cid + ".json"))
                if (
                    intake["context"]["ca_id"] != cid
                    or intake["context"]["knowledge_snapshot_sha256"] != kb_sha
                    or intake["case"]["source"]["sha256"] != r["source_sha256"]
                ):
                    raise GoldError("Public input belongs to another case/source/knowledge")
                save(output / "public_inputs" / (cid + ".json"), intake)
                for source_path, target in (
                    (pdf_root / (r["contract_id"] + ".pdf"), output / r["pdf_path"]),
                    (sources_root / (r["contract_id"] + ".json"), output / r["text_path"]),
                ):
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source_path, target)
                if completed:
                    save(output / "cases" / (cid + ".json"), answers[cid])
                    for layer in LAYERS:
                        save(
                            output / "artifacts" / cid / (layer + ".json"),
                            artifacts[cid + ":" + layer],
                        )
            counts = dict(db.execute("SELECT layer,count(*) FROM benchmark_answers GROUP BY layer"))
            pending_targets = db.execute(
                "SELECT count(*) FROM answers WHERE annotation_status='PENDING_ADJUDICATION'"
            ).fetchone()[0]
            pending_layers = db.execute("SELECT count(*) FROM pending_work").fetchone()[0]
            finding_targets = db.execute(
                "SELECT count(*) FROM criterion_finding_answers"
            ).fetchone()[0]
            integrity = db.execute("PRAGMA integrity_check").fetchone()[0]
            if integrity != "ok" or db.execute("PRAGMA foreign_key_check").fetchall():
                raise GoldError("Gold Master relational integrity check failed")
            coverage = dict(
                format="GOLD_MASTER_V1",
                release_status=(
                    "GOLD" if gate["full_e2e_gold_ready"] else "PARTIAL_SOURCE_ADJUDICATED"
                ),
                registered_cases=len(index),
                complete_authored_cases=len(answers),
                pending_cases=len(index) - len(answers),
                full_e2e_gold_ready=gate["full_e2e_gold_ready"],
                pending_full_layer_units=pending_layers,
                pending_scoped_identity_targets=pending_targets,
                criterion_finding_metric_targets=finding_targets,
                scoreable_answer_counts=counts,
                split_counts=dict(Counter(r["split"] for r in index)),
                source_group_count=len(grouped),
                knowledge_snapshot_sha256=kb_sha,
                evaluation_policy_snapshot_sha256=policy_sha,
                adjudicator_type="AI_SOURCE_ADJUDICATED",
                human_legal_signoff=False,
                production_outputs_used=False,
                external_or_local_model_calls=0,
                source_relevance_pool_scope=(
                    "BOUNDED_MANUALLY_JUDGED_SOURCE_BLOCK_POOLS; OUTSIDE_POOL_UNJUDGED"
                ),
                semantic_legal_quality_automatically_proven=False,
                scoped_answers_do_not_complete_cases=True,
                missing_work_is_not_legal_unknown=True,
            )
            for k, v in coverage.items():
                db.execute("INSERT INTO metadata VALUES(?,?)", (k, dumps(v)))
            for split in ("DEV", "VALIDATION", "TEST"):
                rows = [r for r in index if r["split"] == split]
                save(
                    output / "views" / (split + ".json"),
                    dict(
                        case_ids=[r["case_id"] for r in rows],
                        database="../gold_master.sqlite",
                        query="SELECT * FROM benchmark_answers WHERE split = ?",
                        parameters=[split],
                        evaluator_only=split == "TEST",
                        contains_copied_answers=False,
                    ),
                )
            with (output / "answers.jsonl").open("w", encoding="utf-8") as stream:
                cols = [r[1] for r in db.execute("PRAGMA table_info(answers)")]
                for row in db.execute("SELECT * FROM answers ORDER BY case_id,layer,target_id"):
                    rec = dict(zip(cols, row, strict=True))
                    rec["payload"] = json.loads(rec.pop("payload_json"))
                    rec["origin"] = json.loads(rec.pop("origin_json"))
                    stream.write(dumps(rec) + "\n")
        save(output / "SOURCE_INDEX.json", index)
        save(output / "UPSTREAM_SOURCE_INDEX.json", upstream_index)
        save(output / "knowledge_snapshot.json", snapshot)
        save(output / "POLICY_SNAPSHOT.json", policy)
        save(output / "GOLD_COVERAGE.json", coverage)
        save(output / "FULL_RELEASE_GATE.json", gate)
        save(
            output / "PENDING_ADJUDICATION.json",
            [
                dict(
                    case_id=r["case_id"],
                    split=r["split"],
                    group_id=r["group_id"],
                    status="PENDING_ADJUDICATION",
                )
                for r in index
                if r["case_id"] not in answers
            ],
        )
        save(
            output / "VALIDATION.json",
            dict(
                status="PASS",
                source_pins_checked=len(index),
                full_cases_checked=len(answers),
                sqlite_integrity=integrity,
                full_e2e_gold_ready=gate["full_e2e_gold_ready"],
                scope=(
                    "Byte pins, ownership, scoped imports, unique keys, splits and receipts; "
                    "not proof of legal correctness"
                ),
            ),
        )
        save(
            output / "PACKAGE_HASHES.json",
            {
                str(p.relative_to(output)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted(output.rglob("*"))
                if p.is_file() and p.name != "PACKAGE_HASHES.json"
            },
        )
        return coverage
    except BaseException:
        # Only this invocation's newly created directory is removed.
        shutil.rmtree(output)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    names = (
        "full-release",
        "literal-root",
        "identity-root",
        "sources-root",
        "pdf-root",
        "snapshot",
        "public-inputs-root",
        "output",
    )
    for name in names:
        parser.add_argument("--" + name, type=Path, required=True)
    args = vars(parser.parse_args())
    args["snapshot_path"] = args.pop("snapshot")
    print(json.dumps(build_master(**args), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
