"""Read-only integration coverage inventory; never edits legal data or approves findings.

Writes per-criterion metadata to ignored data/private, not legal text/labels into Git.
Semantic fact/target bindings that cannot be proven from structured catalog stay explicit gaps.
"""

import argparse
import csv
import hashlib
import json
import os
from collections import Counter

from legal_checker.core.config import PROJECT_ROOT, Settings
from legal_checker.core.postgres import connect_postgres
from legal_checker.modules.applicable_law.temporal_resolver import CatalogTemporalResolver
from legal_checker.modules.compliance.numeric_rules import NumericInputError, numeric_kind
from legal_checker.modules.legal_knowledge.repository import canonical
from legal_checker.shared.contracts.document_intelligence import ProfileFields, ProfileSubject


def _fields(node):
    if isinstance(node, dict):
        if isinstance(node.get("field"), str):
            yield node["field"]
        for value in node.values():
            yield from _fields(value)
    elif isinstance(node, list):
        for value in node:
            yield from _fields(value)


def _object(value):
    return json.loads(value) if isinstance(value, str) else value


def inventory(snapshot, dictionary):
    tables = snapshot["tables"]
    versions = {r["requirement_version_id"]: r for r in tables["phien_ban_yeu_cau"]}
    articles = {r["dieu_khoan_id"]: r for r in tables["dieu_khoan_phap_ly"]}
    rules = {}
    for rule in tables["quy_tac_quyet_dinh"]:
        rules.setdefault(rule["tieu_chi_id"], []).append(rule)
    by_family = {}
    for version in versions.values():
        by_family.setdefault(version["requirement_id"], []).append(version)
    resolver = CatalogTemporalResolver()
    marker_gaps = sorted(
        family for family, rows in by_family.items() if resolver.marker_type(family, rows) is None
    )
    scope_gaps = []
    for row in tables["pham_vi_ap_dung"]:
        for name in sorted(set(_fields(_object(row["dieu_kien_json"])))):
            fields = ProfileSubject.model_fields if "." in name else ProfileFields.model_fields
            if name.split(".")[-1] not in fields:
                scope_gaps.append({"scope_id": row["pham_vi_id"], "field": name, "owner": "1+2+3"})
    matrix = []
    for criterion in sorted(tables["tieu_chi_danh_gia"], key=lambda r: r["tieu_chi_id"]):
        key = criterion["tieu_chi_id"]
        version = versions.get(criterion["requirement_version_id"], {})
        numeric, issues = set(), []
        for rule in rules.get(key, []):
            try:
                conditions = _object(rule["dieu_kien_json"])
                if conditions.get("numeric_rule") is not None:
                    numeric.add(numeric_kind(conditions["numeric_rule"]))
            except (ValueError, TypeError, AttributeError, NumericInputError):
                issues.append("UNSUPPORTED_RULE_SHAPE")
        article = articles.get(criterion.get("source_dieu_khoan_id"))
        if not article or article.get("van_ban_id") != version.get("source_van_ban_id"):
            issues.append("LEGAL_SOURCE_OWNERSHIP_REVIEW_REQUIRED")
        family = version.get("requirement_id")
        if family in marker_gaps:
            issues.append("MARKER_POLICY_UNRESOLVED")
        matrix.append(
            {
                "criterion_id": key,
                "requirement_version_id": criterion["requirement_version_id"],
                "requirement_id": family,
                "criterion_type": criterion.get("loai_kiem_tra"),
                "numeric_kinds": sorted(numeric),
                "candidate_fact_fields": sorted(
                    {f for k in numeric for f in dictionary["numeric_fact_groups"].get(k, [])}
                ),
                "binding_status": (
                    "NUMERIC_BRANCH_AND_TARGET_REVIEW_REQUIRED"
                    if numeric
                    else "SEMANTIC_PREDICATE_EVIDENCE_REVIEW_REQUIRED"
                ),
                "source": "C05 + selected C06 + original chunks; external receipts for performance",
                "owners": "2:extract;3:resolve/retrieve;4:verify/reason;5:compose;1:catalog",
                "issues": sorted(set(issues)),
            }
        )
    return {
        "matrix": matrix,
        "scope_gaps": scope_gaps,
        "marker_policy_gaps": marker_gaps,
        "summary": {
            "criteria": len(matrix),
            "families": len(by_family),
            "scope_unmapped_records": len(scope_gaps),
            "scope_unmapped_fields": dict(Counter(r["field"] for r in scope_gaps)),
            "marker_policy_gaps": len(marker_gaps),
            "issue_counts": dict(Counter(code for r in matrix for code in r["issues"])),
            "binding_status": dict(Counter(r["binding_status"] for r in matrix)),
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--knowledge-sha", help="Existing immutable snapshot; default manifest pin")
    parser.add_argument("--output", default="data/private/integration_audit")
    args = parser.parse_args()
    docs = PROJECT_ROOT / "docs/contracts"
    manifest = json.loads((PROJECT_ROOT / "configs/dataset_dev_validation.json").read_text())
    pin = args.knowledge_sha or manifest["knowledge_snapshot_sha256"]
    target = (PROJECT_ROOT / args.output).resolve()
    if not target.is_relative_to((PROJECT_ROOT / "data/private").resolve()):
        parser.error("Audit artifacts must stay under ignored data/private/")
    settings = Settings.from_env()
    with connect_postgres(settings.database_url) as connection:
        connection.execute("SET TRANSACTION READ ONLY")
        row = connection.execute(
            "SELECT content, review_status FROM knowledge.knowledge_snapshots WHERE sha256=%s",
            (pin,),
        ).fetchone()
        if row is None:
            raise ValueError("Pinned snapshot is not installed; update/seed the correct DB first")
        snapshot = row["content"]
    if hashlib.sha256(canonical(snapshot).encode()).hexdigest() != pin:
        raise ValueError("Snapshot checksum differs from requested pin")
    report = inventory(snapshot, json.loads((docs / "data_dictionary.json").read_text()))
    report.update(knowledge_snapshot_sha256=pin, knowledge_review_status=row["review_status"])
    target.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(target, 0o700)
    path = target / "integration_inventory.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    with (target / "criterion_fact_matrix.csv").open("w", newline="") as stream:
        fields = list(report["matrix"][0]) if report["matrix"] else []
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for item in report["matrix"]:
            writer.writerow(
                {
                    k: json.dumps(v, ensure_ascii=False) if isinstance(v, list) else v
                    for k, v in item.items()
                }
            )
    print(json.dumps({"output": str(target), **report["summary"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
