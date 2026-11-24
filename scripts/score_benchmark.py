"""Score saved predictions against R14 without sending answers to the application or an LLM."""

import argparse
import json
import re
import sqlite3
import statistics
import unicodedata
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path

from scripts.run_benchmark import read_json, write_json

NO_PREDICTION = "NO_PREDICTION"
C07_LABELS = ["SATISFIED", "VIOLATED", "MISSING", "UNKNOWN"]
C09_LABELS = ["VALID", "STALE", "INVALID", "UNKNOWN"]
FACT_FIELDS = {
    "area_net_m2": "dien_tich",
    "area_gross_m2": "gross_area_m2",
    "warranty_months": "warranty_months",
    "land_area_m2": "land_area_m2",
    "maintenance_percent": "maintenance_percent",
    "ma_can_ho": "ma_can_ho",
    "project_name": "project_name",
    "ten_ben_ban": "ten_ben_ban",
    "ten_ben_mua": "ten_ben_mua",
    "maintenance_account_number": "maintenance_account_number",
}


def normalized(value):
    return " ".join(unicodedata.normalize("NFC", value).casefold().split())


def scalar_equal(field, expected, actual):
    if expected is None or actual is None:
        return expected is actual
    if field in {
        "area_net_m2",
        "area_gross_m2",
        "warranty_months",
        "land_area_m2",
        "maintenance_percent",
    }:
        try:
            return Decimal(str(expected)) == Decimal(str(actual))
        except InvalidOperation:
            return False
    return (
        isinstance(expected, str)
        and isinstance(actual, str)
        and normalized(expected) == normalized(actual)
    )


def compare(key, expected, actual):
    return {"target": key, "gold": expected, "prediction": actual, "match": expected == actual}


def gold_version_key(row):
    return row["requirement_id"], row["requirement_version_id"]


def c06_witnesses(db, case_id, prediction, k):
    chunks = {row["doan_id"]: row for row in prediction["chunks"]}
    texts = {key: normalized(row["noi_dung"]) for key, row in chunks.items()}
    ranks = defaultdict(list)
    for row in prediction["retrieval"]:
        if row["giai_doan"] == "FINAL" and row["duoc_chon"]:
            ranks[row["tieu_chi_id"]].append(row)
    rows = db.execute(
        "SELECT payload_json FROM benchmark_answers "
        "WHERE case_id=? AND layer='RETRIEVAL_JUDGED_POOL'",
        (case_id,),
    )
    results = []
    for (payload,) in rows:
        witness = json.loads(payload)
        if witness["relevance"] != 2:
            continue
        source = witness["evidence"]
        if isinstance(source, dict):
            source = [source]
        hits = []
        for row in ranks[witness["criterion_id"]]:
            chunk = chunks[row["doan_id"]]
            text = texts[row["doan_id"]]
            if any(
                chunk["page_start"] <= span["page"] <= chunk["page_end"]
                and len(normalized(span["quote"])) >= 12
                and normalized(span["quote"]) in text
                for span in source
            ):
                hits.append(row["thu_hang"])
        best = min(hits, default=None)
        results.append(
            {
                "target": witness["criterion_id"],
                "page": [s["page"] for s in source],
                "best_rank": best,
                "match": best is not None and best <= k,
            }
        )
    return results


def c09_occurrences(gold, prediction):
    citations = prediction["extracted_citations"]
    findings = {row["vien_dan_id"]: row for row in prediction["citation_findings"]}

    # Pair exact normalized text and overlapping source pages one-to-one.
    # Ambiguous pairs and spacing/punctuation variants remain unmatched.
    def norm(text):
        return re.sub(r"\s+", "", normalized(text))

    def candidates(expected):
        pages = {span["page"] for span in expected["evidence"]}
        return [
            c["vien_dan_id"]
            for c in citations
            if norm(c["raw_text"]) == norm(expected["raw_text"])
            and any(
                pos["page_start"] <= page <= pos["page_end"]
                for pos in c["evidence"]
                for page in pages
            )
        ]

    expected = gold["citations"]
    pairs = [candidates(row) for row in expected]
    uses = Counter(cid for matches in pairs for cid in matches)
    results = []
    for row, matches in zip(expected, pairs, strict=True):
        unique = len(matches) == 1 and uses[matches[0]] == 1
        finding = findings.get(matches[0]) if unique else None
        result = compare(
            row["citation_id"], row["status"], finding["status"] if finding else NO_PREDICTION
        )
        result["occurrence_matched"] = unique
        results.append(result)
    return results


def score_case(db, receipt, gold, prediction, reports, k):
    expected_scope = {row["requirement_id"]: row for row in gold["requirements"]}
    scope = {row["requirement_id"]: row for row in prediction["requirements"]}
    owners = {row["yeu_cau_ca_id"]: gold_version_key(row) for row in scope.values()}
    result = prediction["evaluation"]["payload"]
    criteria = {
        (owners[r["yeu_cau_ca_id"]], r["tieu_chi_id"]): r for r in result["criterion_results"]
    }
    aggregated = {owners[row["yeu_cau_ca_id"]]: row for row in result["requirement_results"]}
    facts = {row["ten_truong"]: row for row in prediction["contract_profile"]["facts"]}
    c02, c07, c08 = [], [], []
    for row in gold["facts"]:
        key = row["field"]
        if key not in FACT_FIELDS or row["status"] != "KNOWN" or row["value"] is None:
            continue
        actual = facts.get(FACT_FIELDS[key], {}).get("gia_tri_chuan_json")
        c02.append(
            {
                "target": key,
                "match": scalar_equal(key, row["value"], actual),
                "available": actual is not None,
            }
        )
    for row in gold["criteria"]:
        if row["annotation_quality"] != "GOLD" or row["disposition"] != "ASSESSED":
            continue
        candidate = criteria.get((gold_version_key(row), row["criterion_id"]))
        label = candidate["finding"] if candidate and not candidate["excluded"] else NO_PREDICTION
        item = compare(row["criterion_id"], row["finding"], label)
        item["diagnostic"] = candidate.get("uncertainty_reason") if candidate else "NO_CRITERION"
        item["model"] = candidate.get("model_version") if candidate else None
        c07.append(item)
    for row in gold["requirements_aggregated"]:
        if row["disposition"] == "ASSESSED":
            c08.append(
                compare(
                    row["requirement_id"],
                    row["status"],
                    aggregated.get(gold_version_key(row), {}).get("status", NO_PREDICTION),
                )
            )
    report = reports[0]["report"]
    risks = {row["ket_qua_rui_ro_id"] for row in result["risks"]}
    checks = {
        "initial_draft": report["report_status"] == "DRAFT",
        "source_hash": report["report_json"]["case"]["source"]["sha256"]
        == receipt["source_sha256"],
        "knowledge_hash": report["report_json"]["audit"]["context"]["knowledge_snapshot_sha256"]
        == receipt["knowledge_snapshot_sha256"],
        "recommendation_risk_links": all(
            r["ket_qua_rui_ro_id"] in risks for r in result["recommendations"]
        ),
        "reports_bound_to_run": all(r["run_id"] == receipt["run_id"] for r in reports),
    }
    return {
        "C02_known_scalar_subset": c02,
        "C05_scope_status": [
            compare(key, row["scope_status"], scope.get(key, {}).get("scope_status", NO_PREDICTION))
            for key, row in expected_scope.items()
        ],
        "C05_applicability_and_version": [
            compare(
                key,
                [row["applicability_status"], row["requirement_version_id"]],
                [scope[key]["applicability_status"], scope[key]["requirement_version_id"]]
                if key in scope
                else NO_PREDICTION,
            )
            for key, row in expected_scope.items()
        ],
        "C06_strict_witness_hits": c06_witnesses(db, receipt["case_id"], prediction, k),
        "C07_assessed": c07,
        "C08_assessed": c08,
        "C09_occurrences": c09_occurrences(gold, prediction),
        "C13_integrity": checks,
        "runtime_diagnostics": dict(
            Counter(r["code"] for r in result["diagnostics"] if "code" in r)
        ),
        "report_id": report["bao_cao_id"],
    }


def classification(rows, labels):
    matrix = Counter((r["gold"], r["prediction"]) for r in rows)
    per_class = {}
    for label in labels:
        tp = matrix[label, label]
        fp = sum(n for (g, p), n in matrix.items() if g != label and p == label)
        fn = sum(n for (g, p), n in matrix.items() if g == label and p != label)
        per_class[label] = {
            "support": tp + fn,
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "precision": tp / (tp + fp) if tp + fp else 0,
            "recall": tp / (tp + fn) if tp + fn else 0,
            "f1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0,
        }
    supported = [row["f1"] for row in per_class.values() if row["support"]]
    return {
        "macro_f1": statistics.mean(supported) if supported else None,
        "per_class": per_class,
        "matrix": {g: {p: matrix[g, p] for p in labels + [NO_PREDICTION]} for g in labels},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--gold", required=True, type=Path, help="Extracted R14 TEAM or evaluator package"
    )
    parser.add_argument("--predictions", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("-k", type=int, default=5)
    args = parser.parse_args()
    if args.k < 1:
        parser.error("-k must be positive")
    gate = read_json(args.gold / "FULL_RELEASE_GATE.json")
    if not gate["full_e2e_gold_ready"]:
        parser.error("Full Gold release gate did not pass")
    summary = read_json(args.predictions / "runs.json")
    plan = read_json(args.predictions / "plan.json")
    coverage = read_json(args.gold / "GOLD_COVERAGE.json")
    if (
        len(set(plan["cases"])) != len(plan["cases"])
        or [r["case_id"] for r in summary] != plan["cases"]
    ):
        parser.error("Run receipts do not match the frozen plan")
    split = plan["split"]
    if split not in coverage["split_counts"]:
        parser.error(f"The selected Gold package does not contain answers for {split}")
    database = args.gold / "gold_master.sqlite"
    if not database.is_file() and split in {"DEV", "VALIDATION"}:
        database = args.gold / "gold_dev_validation.sqlite"
    if not database.is_file():
        parser.error(f"Missing Gold SQLite database: {database}")
    db_uri = database.resolve().as_uri() + "?mode=ro&immutable=1"
    cases, merged = {}, defaultdict(list)
    with sqlite3.connect(db_uri, uri=True) as db:
        for row in summary:
            if row["status"] != "COMPLETED":
                continue
            case_id = row["case_id"]
            binding = db.execute(
                "SELECT split,source_sha256,knowledge_sha256 FROM cases WHERE case_id=?", (case_id,)
            ).fetchone()
            if (
                binding != (plan["split"], row["source_sha256"], row["knowledge_snapshot_sha256"])
                or row["module_source"] != "MODULES"
            ):
                raise ValueError(f"Gold/inference binding mismatch: {case_id}")
            path = args.predictions / case_id
            prediction = read_json(path / "prediction.json")
            if (
                prediction["context"]["run_id"] != row["run_id"]
                or prediction["case"]["source"]["sha256"] != binding[1]
                or prediction["context"]["knowledge_snapshot_sha256"] != binding[2]
            ):
                raise ValueError(f"Prediction mismatch: {case_id}")
            gold = read_json(args.gold / "cases" / f"{case_id}.json")
            if (gold["case_id"], gold["source_sha256"], gold["knowledge_snapshot_sha256"]) != (
                case_id,
                binding[1],
                binding[2],
            ):
                raise ValueError(f"Gold case payload mismatch: {case_id}")
            scored = score_case(
                db,
                row,
                gold,
                prediction,
                read_json(path / "reports.json"),
                args.k,
            )
            cases[case_id] = scored
            for key, values in scored.items():
                if isinstance(values, list):
                    merged[key].extend(values)
    metrics = {
        key: {"matched": sum(r["match"] for r in rows), "targets": len(rows)}
        for key, rows in merged.items()
    }
    if cases:
        metrics["C07_assessed"].update(classification(merged["C07_assessed"], C07_LABELS))
        matched = [r for r in merged["C09_occurrences"] if r["occurrence_matched"]]
        metrics["C09_occurrences"]["exact_occurrence_pairs"] = len(matched)
        metrics["C09_occurrences"]["status_on_exact_pairs"] = classification(matched, C09_LABELS)
        reciprocal_ranks = []
        for case in cases.values():
            queries = defaultdict(int)
            for row in case["C06_strict_witness_hits"]:
                rank = 1 / row["best_rank"] if row["match"] else 0
                queries[row["target"]] = max(queries[row["target"]], rank)
            reciprocal_ranks.extend(queries.values())
        metrics["C06_strict_witness_hits"].update(
            k=args.k,
            queries=len(reciprocal_ranks),
            queries_with_hit=sum(rank > 0 for rank in reciprocal_ranks),
            mrr_at_k=statistics.mean(reciprocal_ranks) if reciprocal_ranks else None,
        )
    output = {
        "split": plan["split"],
        "gold_release": args.gold.resolve().name,
        "gold_knowledge_sha256": coverage["knowledge_snapshot_sha256"],
        "gold_policy_sha256": coverage["evaluation_policy_snapshot_sha256"],
        "planned": len(summary),
        "completed": len(cases),
        "runs": summary,
        "metrics": metrics,
        "cases": cases,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_json(args.output, output)
    print(f"{len(cases)}/{len(summary)} completed and scored -> {args.output}")
    for key, metric in metrics.items():
        print(f"{key}: {metric['matched']}/{metric['targets']}")
    if len(cases) != len(summary):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
