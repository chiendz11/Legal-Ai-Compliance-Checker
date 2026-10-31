"""Read pinned decision rules as data, never as executable predicate text."""

import json
from copy import deepcopy
from decimal import Decimal
from math import isfinite
from typing import Any

from legal_checker.modules.legal_knowledge.models import KnowledgeSnapshot
from legal_checker.shared.contracts.reasoning import Gates

SUPPORTED_RULE_GATES = set(Gates.model_fields) | {
    "source_available",
    "no_unresolved_conflict",
    "facts_verified",
    "all_pages_readable",
    "all_related_documents_received",
    "template_field_unfilled",
    "mandatory_contract_content",
    "criterion_content_absent",
    "any_unresolved_fact",
    "optional_choice_confirmed",
}


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError(f"Non-finite JSON constant: {value}")


def _finite(value):
    if isinstance(value, dict):
        return all(isinstance(k, str) and _finite(v) for k, v in value.items())
    if isinstance(value, list):
        return all(_finite(v) for v in value)
    if isinstance(value, Decimal):
        return value.is_finite()
    if isinstance(value, float):
        return isfinite(value)
    return value is None or isinstance(value, (str, int, bool))


def parse_json_object(value: Any) -> dict[str, Any]:
    """Decode a finite JSON object without duplicate keys; copy caller-owned data."""
    if isinstance(value, str):
        value = json.loads(
            value,
            parse_float=Decimal,
            parse_constant=_reject_constant,
            object_pairs_hook=_object,
        )
    if not isinstance(value, dict) or not _finite(value):
        raise ValueError("Expected a finite JSON object")
    return deepcopy(value)


def load_decision_rule(
    criterion_id: str, finding: str, knowledge: KnowledgeSnapshot
) -> tuple[dict[str, Any] | None, dict[str, Any], list[str]]:
    """Return the exact attempted rule and explicit issues for unsupported conditions."""
    try:
        rule = knowledge.decision(criterion_id, finding)
    except (KeyError, ValueError):
        return None, {}, [f"Missing or ambiguous {finding} decision rule"]
    if (
        not isinstance(rule, dict)
        or rule.get("tieu_chi_id") != criterion_id
        or rule.get("finding") != finding
    ):
        return None, {}, [f"{finding} decision rule identity mismatch"]
    try:
        conditions = parse_json_object(rule["dieu_kien_json"])
    except (KeyError, TypeError, ValueError):
        return rule, {}, ["Invalid decision rule JSON"]
    issues = []
    for key in ("quy_tac_id", "rule_version"):
        if not isinstance(rule.get(key), str) or not rule[key].strip():
            issues.append(f"Missing decision rule {key}")
    if rule.get("trang_thai") in {"DISABLED", "INACTIVE", "RETIRED", "DELETED"}:
        issues.append(f"{finding} decision rule is disabled")
    allowed = {
        "enabled",
        "gate",
        "predicate",
        "numeric_rule",
        "scope_of_facts",
        "criterion_target_only",
        "template_output",
        "human_approval_required_for_final",
        "conclusion_scope_required",
        "performance_requires_receipt_evidence",
    }
    if set(conditions) - allowed:
        issues.append("Unsupported decision rule conditions")
    if conditions.get("enabled") is not True:
        issues.append(f"{finding} decision rule is disabled")
    if not isinstance(conditions.get("predicate"), str) or not conditions["predicate"].strip():
        issues.append("Missing decision rule predicate")
    if conditions.get("scope_of_facts", "CURRENT_CRITERION") != "CURRENT_CRITERION":
        issues.append("Unsupported rule scope_of_facts")
    if conditions.get("criterion_target_only", True) is not True:
        issues.append("Rule must target only the current criterion")
    if conditions.get("template_output", "DRAFT") != "DRAFT":
        issues.append("Unsupported rule template_output")
    if type(conditions.get("human_approval_required_for_final", True)) is not bool:
        issues.append("Invalid human_approval_required_for_final")
    for key in ("conclusion_scope_required", "performance_requires_receipt_evidence"):
        if key in conditions and type(conditions[key]) is not bool:
            issues.append(f"Invalid decision rule condition: {key}")
    if conditions.get("performance_requires_receipt_evidence") is True and not conditions.get(
        "conclusion_scope_required"
    ):
        issues.append("Receipt-evidence rule requires an explicit conclusion scope policy")
    if not isinstance(conditions.get("gate"), dict):
        issues.append("Invalid decision rule gate object")
    else:
        for name, expected in conditions["gate"].items():
            if name not in SUPPORTED_RULE_GATES or type(expected) is not bool:
                issues.append(f"Unsupported decision rule gate: {name}")
    return rule, conditions, issues
