"""Package independently authored Gold; never manufacture answers from predictions."""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from devtools.gold_answers import (
    GoldCase,
    GoldError,
    canonical_sha,
    check_full_gold_coverage,
    validate_gold_case,
)


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save(path: Path, value: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_gold_release(
    *,
    curated_root: Path,
    sources_root: Path,
    pdf_root: Path,
    snapshot_path: Path,
    source_index_path: Path,
    output: Path,
    expected_case_count: int = 360,
) -> dict:
    """Publish verified authored cases, preserving the full source denominator."""
    if output.exists() and any(output.iterdir()):
        raise GoldError("Output must be a new empty directory; preserve previous release")
    snapshot = load(snapshot_path)
    snapshot_sha = canonical_sha(snapshot)
    index = load(source_index_path)
    items = index["items"] if isinstance(index, dict) else index
    ids = [r["case_id"] for r in items]
    if not ids or len(ids) != len(set(ids)):
        raise GoldError("Source index must register unique expected cases")
    if len(ids) != expected_case_count:
        raise GoldError("Source index cannot shrink the registered release denominator")
    policy_path = curated_root / "POLICY_SNAPSHOT.json"
    if not policy_path.is_file():
        raise GoldError("Authored answers must pin the evaluation/review/citation policies")
    policy_snapshot = load(policy_path)
    sources, source_checks = {}, []
    for item in items:
        cid = item["case_id"]
        hid = item.get("contract_id") or item.get("hop_dong_id")
        if not hid:
            raise GoldError("Missing registered contract identity")
        source = load(sources_root / (hid + ".json"))
        observed = hashlib.sha256((pdf_root / (hid + ".pdf")).read_bytes()).hexdigest()
        registered = item.get("source_sha256") or item.get("pdf_sha256")
        if (
            source["case_id"] != cid
            or source["source_sha256"] != observed
            or registered != observed
        ):
            raise GoldError("Source PDF/index/text identity mismatch: " + cid)
        sources[cid] = source
        source_checks.append({"case_id": cid, "source_sha256": observed, "status": "PASS"})

    answers, artifacts, paths, validations = {}, {}, {}, []
    for path in sorted((curated_root / "artifacts").glob("*/*.json")):
        artifact = load(path)
        ident = artifact["case_id"] + ":" + artifact["layer"]
        if ident in artifacts or artifact["case_id"] not in sources:
            raise GoldError("Duplicate/unregistered adjudication artifact")
        artifacts[ident], paths[ident] = artifact, path.relative_to(curated_root)
    for path in sorted((curated_root / "cases").glob("CA360_*.json")):
        answer = load(path)
        cid = answer["case_id"]
        if cid not in sources or path.stem != cid or cid in answers:
            raise GoldError("Duplicate/unregistered authored case")
        validations.append(
            validate_gold_case(GoldCase.model_validate(answer), sources[cid], snapshot)
        )
        single = check_full_gold_coverage(
            {cid: sources[cid]}, {cid: answer}, snapshot, artifacts=artifacts
        )
        if single["errors"]:
            raise GoldError(
                "Authored case failed layer checks: " + cid + " " + str(single["errors"][:3])
            )
        answers[cid] = answer

    gate = check_full_gold_coverage(sources, answers, snapshot, artifacts=artifacts)
    counts = Counter(r["finding"] for a in answers.values() for r in a["criteria"])
    dispositions = Counter(r["disposition"] for a in answers.values() for r in a["criteria"])
    pending = [
        {
            "case_id": cid,
            "status": "PENDING_ADJUDICATION",
            "reason": "FULL_CASE_SOURCE_ADJUDICATION_NOT_COMPLETED",
        }
        for cid in sorted(set(sources) - set(answers))
    ]
    coverage = {
        "release_status": "GOLD" if gate["full_e2e_gold_ready"] else "PARTIAL_SOURCE_ADJUDICATED",
        "full_e2e_gold_ready": gate["full_e2e_gold_ready"],
        "registered_cases": len(sources),
        "source_pdf_checks": len(source_checks),
        "complete_authored_cases": len(answers),
        "pending_cases": len(pending),
        "criterion_findings": dict(counts),
        "criterion_dispositions": dict(dispositions),
        "knowledge_snapshot_sha256": snapshot_sha,
        "evaluation_policy_snapshot_sha256": canonical_sha(policy_snapshot),
        "adjudicator_type": "AI_SOURCE_ADJUDICATED",
        "human_legal_signoff": False,
        "production_outputs_used": False,
        "external_or_local_model_calls": 0,
        "semantic_legal_quality_automatically_proven": False,
        "source_relevance_pool_scope": (
            "BOUNDED_MANUALLY_JUDGED_SOURCE_BLOCK_POOLS; OUTSIDE_POOL_UNJUDGED"
        ),
        "missing_cases_are_not_legal_unknowns": True,
    }
    # All checks precede writes. Do not silently replace a previous release.
    for cid, answer in answers.items():
        save(output / "cases" / (cid + ".json"), answer)
    for ident, artifact in artifacts.items():
        save(output / paths[ident], artifact)
    save(output / "SOURCE_INDEX.json", items)
    save(output / "POLICY_SNAPSHOT.json", policy_snapshot)
    save(output / "SOURCE_CHECKS.json", source_checks)
    save(output / "GOLD_COVERAGE.json", coverage)
    save(output / "FULL_RELEASE_GATE.json", gate)
    save(output / "PENDING_ADJUDICATION.json", pending)
    save(
        output / "VALIDATION.json",
        {
            "status": "PASS",
            "scope": "SOURCE_PINS_EXACT_QUOTES_OWNERSHIP_AND_ARTIFACT_BINDING_FOR_AUTHORED_CASES",
            "case_validations": validations,
            "full_e2e_gold_ready": gate["full_e2e_gold_ready"],
            "all_360_semantically_adjudicated": not pending,
            "semantic_legal_quality_automatically_proven": False,
        },
    )
    save(
        output / "AUTHORING_POLICY.json",
        {
            "authoring_mode": "DIRECT_ASSISTANT_SOURCE_ADJUDICATION",
            "adjudicator_type": "AI_SOURCE_ADJUDICATED",
            "knowledge_snapshot_sha256": snapshot_sha,
            "owner_accepted_ai_curation": True,
            "forbid_external_llm_calls": True,
            "forbid_local_model_calls": True,
            "human_legal_signoff": False,
            "production_outputs_used": False,
            "full_e2e_gold_ready": gate["full_e2e_gold_ready"],
            "scope": (
                "Authored cases and targets only; missing annotation is pending, not legal UNKNOWN"
            ),
        },
    )
    save(
        output / "PACKAGE_HASHES.json",
        {
            str(path.relative_to(output)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(output.rglob("*.json"))
            if path.name != "PACKAGE_HASHES.json"
        },
    )
    return coverage


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("curated-root", "sources-root", "pdf-root", "snapshot", "source-index", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    coverage = build_gold_release(
        curated_root=args.curated_root,
        sources_root=args.sources_root,
        pdf_root=args.pdf_root,
        snapshot_path=args.snapshot,
        source_index_path=args.source_index,
        output=args.output,
    )
    print(json.dumps(coverage, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
