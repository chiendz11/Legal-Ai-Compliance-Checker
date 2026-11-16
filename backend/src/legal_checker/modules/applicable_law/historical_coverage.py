"""Recognize a reviewed legacy equivalent, not an invented historical version."""

from legal_checker.modules.applicable_law.catalog_policy import read_policy
from legal_checker.modules.applicable_law.temporal_resolver import as_date, in_force


def historical_exclusion_valid(row, knowledge):
    proof = row.nguon_snapshot_json.get("historical_coverage")
    if not isinstance(proof, dict) or proof.get("kind") != "LEGACY_EQUIVALENT_CONFIRMED":
        return False
    if proof.get("knowledge_sha256") != knowledge.sha256 or not row.moc_ap_dung:
        return False
    versions = [v for v in knowledge.versions.values() if v["requirement_id"] == row.requirement_id]
    legacy = knowledge.versions.get(proof.get("legacy_version_id"))
    if not versions or not legacy or not in_force(legacy, row.moc_ap_dung):
        return False
    for version in versions:
        policy = read_policy(version)
        if (
            not policy
            or policy.historical_equivalent_family_id != legacy["requirement_id"]
            or not policy.historical_basis_article_ids
            or not set(policy.historical_basis_article_ids) <= knowledge.articles.keys()
            or not as_date(version.get("hieu_luc_tu"))
            or row.moc_ap_dung >= as_date(version["hieu_luc_tu"])
        ):
            return False
    return (
        proof.get("legacy_requirement_id") == legacy["requirement_id"]
        and proof.get("legacy_scope_status") == "MATCH"
        and proof.get("legacy_version_status") == "RESOLVED"
    )


def resolve_historical_branches(rows, knowledge):
    by_family = {r.requirement_id: r for r in rows}
    result = []
    for row in rows:
        if row.applicability_status != "UNKNOWN" or not row.moc_ap_dung:
            result.append(row)
            continue
        versions = [
            v for v in knowledge.versions.values() if v["requirement_id"] == row.requirement_id
        ]
        try:
            policies = [read_policy(v) for v in versions]
        except (ValueError, TypeError):
            result.append(row)
            continue
        names = {p.historical_equivalent_family_id for p in policies if p}
        if (
            not versions
            or len(policies) != len([p for p in policies if p])
            or len(names) != 1
            or None in names
        ):
            result.append(row)
            continue
        legacy = by_family.get(next(iter(names)))
        if not legacy or not legacy.confirmed:
            result.append(row)
            continue
        updated = row.model_copy(deep=True)
        updated.nguon_snapshot_json["historical_coverage"] = {
            "kind": "LEGACY_EQUIVALENT_CONFIRMED",
            "knowledge_sha256": knowledge.sha256,
            "legacy_requirement_id": legacy.requirement_id,
            "legacy_version_id": legacy.requirement_version_id,
            "legacy_scope_status": legacy.scope_status,
            "legacy_version_status": legacy.version_status,
        }
        if historical_exclusion_valid(updated, knowledge):
            updated.applicability_status = "NOT_APPLICABLE"
            updated.requirement_version_id = None
            updated.nguon_snapshot_json["candidate_version_only"] = False
            updated.reason["version"] = (
                "Modern source branch not in force; historical obligation evaluated by "
                + legacy.requirement_id
                + "/"
                + legacy.requirement_version_id
            )
            updated.reason["summary"] = "NOT_APPLICABLE: " + updated.reason["version"]
            result.append(updated)
        else:
            result.append(row)
    return result
