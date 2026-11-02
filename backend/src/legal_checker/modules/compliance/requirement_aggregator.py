"""Pure C08 aggregation over a complete, pinned C05/C07 checklist.

AGG_CAN_HO_V1 is an explicitly supported policy, not a majority vote. Unknown
policy content is a knowledge gap. Snapshots preserve draft/verification flags.
"""

import json
from collections import Counter
from copy import deepcopy
from typing import Any

from legal_checker.modules.compliance.decision_rules import parse_json_object
from legal_checker.modules.legal_knowledge.models import KnowledgeSnapshot
from legal_checker.shared.contracts.aggregation import RequirementResult
from legal_checker.shared.contracts.common import Context, RequirementStatus
from legal_checker.shared.contracts.reasoning import CriterionResult
from legal_checker.shared.contracts.temporal import ApplicableRequirement
from legal_checker.shared.ids import stable_id
from legal_checker.shared.validation import validate_context, validate_requirements

POLICY_ID = "AGG_CAN_HO_V1"
POLICY_PRIORITY = [
    "SCOPE_OR_VERSION_UNRESOLVED=INSUFFICIENT",
    "PROVEN_VIOLATION=NON_COMPLIANT_WITH_COVERAGE_FLAG",
    "UNKNOWN=INSUFFICIENT",
    "ALL_MISSING=NON_COMPLIANT",
    "MIXED_SATISFIED_MISSING=PARTIAL",
    "ALL_SATISFIED=COMPLIANT",
]
POLICY_CONDITIONS = {
    "COMPLIANT": (
        "all applicable mandatory criteria SATISFIED and no unresolved scope/version/evidence"
    ),
    "INSUFFICIENT": (
        "scope/version unresolved OR no applicable evaluated criterion OR any remaining UNKNOWN "
        "without already-proven violation"
    ),
    "NON_COMPLIANT": (
        "any applicable mandatory criterion VIOLATED; or all applicable mandatory criteria "
        "MISSING with verified absence"
    ),
    "PARTIAL": ("at least one SATISFIED and at least one verified MISSING; no VIOLATED/UNKNOWN"),
    "excluded": "NOT_APPLICABLE excluded with reason; REVIEW_REQUIRED is not a criterion finding",
}


def _json_value(value: Any) -> Any:
    if isinstance(value, str):
        return json.loads(value)
    return value


def _policy_issues(policy_id: str | None, policy: dict[str, Any] | None) -> list[str]:
    if policy is None:
        return ["KNOWLEDGE_GAP: aggregation policy is missing"]
    if not isinstance(policy, dict):
        return ["KNOWLEDGE_GAP: aggregation policy is not an object"]
    if policy_id != POLICY_ID or policy.get("quy_tac_tong_hop_id") != POLICY_ID:
        return [f"UNSUPPORTED_POLICY: {policy_id}"]
    issues = []
    if not isinstance(policy.get("rule_version"), str) or not policy["rule_version"].strip():
        issues.append("KNOWLEDGE_GAP: aggregation rule_version is missing")
    try:
        conditions = parse_json_object(policy.get("dieu_kien_json"))
        priority = _json_value(policy.get("thu_tu_uu_tien_json"))
    except (ValueError, TypeError):
        return [*issues, "UNSUPPORTED_POLICY: malformed aggregation JSON"]
    # Stored contract: natural-language policy plus ordered named clauses.
    # Interpret only the registered specification, never arbitrary policy prose.
    if conditions != POLICY_CONDITIONS:
        issues.append("UNSUPPORTED_POLICY: AGG_CAN_HO_V1 conditions differ from its specification")
    if priority != POLICY_PRIORITY:
        issues.append("CONFLICTING_POLICY: AGG_CAN_HO_V1 priority differs from its specification")
    if policy.get("trang_thai") != "ENGINE_POLICY":
        issues.append("UNSUPPORTED_POLICY: aggregation policy is not ENGINE_POLICY")
    return issues


def _rule_version(policy: dict[str, Any] | None, request: Context) -> str:
    """Use deployment metadata for a policy gap without inventing a policy version."""
    value = policy.get("rule_version") if isinstance(policy, dict) else None
    return value.strip() if isinstance(value, str) and value.strip() else request.rule_version


def requirement_exclusion_reason(
    requirement: ApplicableRequirement, knowledge: KnowledgeSnapshot
) -> str | None:
    """C05 exclusion needs resolved ownership, usable knowledge and a stated reason."""
    version = knowledge.versions.get(requirement.requirement_version_id)
    if (
        requirement.applicability_status != "NOT_APPLICABLE"
        or requirement.scope_status != "NO_MATCH"
        or requirement.version_status != "RESOLVED"
        or not version
        or version.get("requirement_id") != requirement.requirement_id
    ):
        return None
    policy_id = version.get("quy_tac_tong_hop_id")
    if _policy_issues(policy_id, knowledge.aggregations.get(policy_id)):
        return None
    expected = knowledge.criteria_for(requirement.requirement_version_id)
    expected_ids = [item.get("tieu_chi_id") for item in expected]
    if (
        not expected
        or len(expected_ids) != len(set(expected_ids))
        or any(
            not item.get("tieu_chi_id")
            or item != knowledge.criteria.get(item["tieu_chi_id"])
            or item.get("requirement_version_id") != requirement.requirement_version_id
            or type(item.get("bat_buoc")) is not bool
            for item in expected
        )
    ):
        return None
    explanation = "; ".join(value for value in requirement.reason.values() if value.strip())
    return "C05 NOT_APPLICABLE: " + explanation if explanation else None


def excluded_requirement_ids(
    request: Context,
    knowledge: KnowledgeSnapshot,
    requirements: list[ApplicableRequirement],
) -> list[str]:
    """Shared exclusion rule for C08 and workflow output membership."""
    validate_context(request, knowledge)
    validate_requirements(request, requirements, knowledge)
    return [
        requirement.yeu_cau_ca_id
        for requirement in requirements
        if requirement_exclusion_reason(requirement, knowledge)
    ]


def _group_results(
    request: Context,
    knowledge: KnowledgeSnapshot,
    criteria: list[CriterionResult],
    requirements: list[ApplicableRequirement],
) -> dict[str, dict[str, CriterionResult]]:
    requirements_by_id = {item.yeu_cau_ca_id: item for item in requirements}
    grouped: dict[str, dict[str, CriterionResult]] = {key: {} for key in requirements_by_id}
    result_ids = set()
    expected_contract = getattr(getattr(request, "payload", None), "hop_dong_id", None)
    for original in criteria:
        result = CriterionResult.model_validate(original.model_dump())
        requirement = requirements_by_id.get(result.yeu_cau_ca_id)
        criterion = knowledge.criteria.get(result.tieu_chi_id)
        if (
            not requirement
            or not criterion
            or result.ca_id != request.ca_id
            or result.lan_chay_id != request.run_id
            or criterion.get("requirement_version_id") != requirement.requirement_version_id
            or requirement.version_status != "RESOLVED"
        ):
            raise ValueError("C08 criterion case/run/requirement/version ownership mismatch")
        if result.ket_qua_id in result_ids or result.tieu_chi_id in grouped[result.yeu_cau_ca_id]:
            raise ValueError("C08 duplicate criterion finding or result ID")
        snapshot = result.tieu_chi_snapshot_json
        if any(snapshot.get(key) != value for key, value in criterion.items()) or (
            snapshot.get("knowledge_snapshot_sha256") != request.knowledge_snapshot_sha256
        ):
            raise ValueError("C08 criterion snapshot differs from pinned knowledge")
        context = snapshot.get("context")
        expected_context = request.model_dump(
            mode="json", include=set(Context.model_fields) - {"trace_id"}
        )
        if not isinstance(context, dict) or any(
            context.get(key) != value for key, value in expected_context.items()
        ):
            raise ValueError("C08 criterion context differs from the pinned case/run/deployment")
        contract = snapshot.get("hop_dong_id")
        if not isinstance(contract, str) or not contract.strip():
            raise ValueError("C08 criterion snapshot is missing contract ownership")
        if expected_contract is not None and contract != expected_contract:
            raise ValueError("C08 criterion contract differs from the pinned contract")
        # A Context-only caller has no contract DTO; still reject a mixed contract
        # batch instead of treating case/run membership as sufficient ownership.
        expected_contract = contract
        if result.mandatory != (criterion.get("bat_buoc") is True):
            raise ValueError("C08 mandatory flag differs from pinned criterion")
        result_ids.add(result.ket_qua_id)
        grouped[result.yeu_cau_ca_id][result.tieu_chi_id] = result
    return grouped


def _valid_local_exclusion(result: CriterionResult) -> bool:
    """C07 local exclusions need review gates and attributable support, not a flag."""
    return (
        result.excluded
        and result.finding == "UNKNOWN"
        and bool(result.exclusion_reason and result.exclusion_reason.strip())
        and result.gates.reliable()
        and bool(result.evidence or result.external_evidence)
        and all(evidence.verified for evidence in result.external_evidence)
        and bool(result.legal_basis_ids)
    )


def _status(findings: Counter, blockers: list[str]) -> tuple[RequirementStatus, str]:
    if blockers:
        return "INSUFFICIENT", "; ".join(blockers)
    if findings["VIOLATED"]:
        return "NON_COMPLIANT", "At least one applicable mandatory criterion is VIOLATED"
    if findings["UNKNOWN"]:
        return "INSUFFICIENT", "At least one applicable mandatory criterion remains UNKNOWN"
    if findings["MISSING"] and not findings["SATISFIED"]:
        return "NON_COMPLIANT", "All applicable mandatory criteria are verified MISSING"
    if findings["SATISFIED"] and findings["MISSING"]:
        return "PARTIAL", "Applicable mandatory criteria contain SATISFIED and verified MISSING"
    return "COMPLIANT", "All applicable mandatory criteria are SATISFIED"


def aggregate(
    request: Context,
    knowledge: KnowledgeSnapshot,
    criteria: list[CriterionResult],
    requirements: list[ApplicableRequirement],
) -> list[RequirementResult]:
    """Aggregate by C05 instance, retaining gaps and excluding only justified C05.

    Missing C07 precedes even a proven violation. UNKNOWN counts represent actual
    C07 UNKNOWN findings; absent findings have separate snapshot IDs. Overall
    coverage includes evidence gates; finding coverage only measures membership.
    """
    validate_context(request, knowledge)
    validate_requirements(request, requirements, knowledge)
    grouped = _group_results(request, knowledge, criteria, requirements)
    outputs = []
    for requirement in requirements:
        if requirement_exclusion_reason(requirement, knowledge):
            continue
        version = knowledge.versions.get(requirement.requirement_version_id)
        expected = (
            knowledge.criteria_for(requirement.requirement_version_id)
            if requirement.requirement_version_id and requirement.version_status == "RESOLVED"
            else []
        )
        expected_ids = [item["tieu_chi_id"] for item in expected]
        if len(expected_ids) != len(set(expected_ids)) or any(
            item != knowledge.criteria.get(item["tieu_chi_id"])
            or item.get("requirement_version_id") != requirement.requirement_version_id
            for item in expected
        ):
            raise ValueError("C08 expected checklist contains duplicate or foreign criteria")
        results = grouped[requirement.yeu_cau_ca_id]
        if set(results) - set(expected_ids):
            raise ValueError("C08 result is outside the expected version checklist")
        policy_id = version.get("quy_tac_tong_hop_id") if version else None
        policy = knowledge.aggregations.get(policy_id)
        blockers = _policy_issues(policy_id, policy)
        if not requirement.confirmed:
            blockers.append("C05 scope/version/applicability is not confirmed")
        if not version or requirement.version_status != "RESOLVED":
            blockers.append("KNOWLEDGE_GAP: requirement version is unresolved")
        if not expected:
            blockers.append("KNOWLEDGE_GAP: no criteria in the resolved requirement version")
        missing_ids = sorted(set(expected_ids) - set(results))
        if missing_ids:
            blockers.append("Missing C07 findings: " + ", ".join(missing_ids))
        if any(type(row.get("bat_buoc")) is not bool for row in expected):
            blockers.append("KNOWLEDGE_GAP: mandatory policy is not boolean")
        local_excluded = {
            key: result.exclusion_reason
            for key, result in results.items()
            if requirement.confirmed and _valid_local_exclusion(result)
        }
        invalid_exclusions = [
            key for key, result in results.items() if result.excluded and key not in local_excluded
        ]
        if invalid_exclusions:
            blockers.append(
                "Invalid criterion exclusions: " + ", ".join(sorted(invalid_exclusions))
            )
        applicable_ids = [
            row["tieu_chi_id"]
            for row in expected
            if row.get("bat_buoc") is True and row["tieu_chi_id"] not in local_excluded
        ]
        evaluated = [results[key] for key in applicable_ids if key in results]
        if not applicable_ids:
            blockers.append("No applicable mandatory criterion remains for aggregation")
        findings = Counter(result.finding for result in evaluated)
        status, explanation = _status(findings, blockers)
        finding_coverage = bool(expected) and not missing_ids
        evidence_coverage = bool(evaluated) and all(
            result.gates.coverage_complete for result in evaluated
        )
        coverage = (
            not blockers and finding_coverage and evidence_coverage and not findings["UNKNOWN"]
        )
        snapshot = {
            "applicable_requirement": requirement.model_dump(mode="json"),
            "requirement_version": deepcopy(version),
            "aggregation_policy": deepcopy(policy),
            "aggregation_policy_id": policy_id,
            "knowledge_snapshot_sha256": request.knowledge_snapshot_sha256,
            "run_id": request.run_id,
            "phien_ban_id": request.phien_ban_id,
            "expected_criterion_ids": expected_ids,
            "applicable_mandatory_criterion_ids": applicable_ids,
            "evaluated_criterion_result_ids": [result.ket_qua_id for result in evaluated],
            "missing_criterion_ids": missing_ids,
            "excluded_criteria": local_excluded,
            "optional_criterion_ids": [
                row["tieu_chi_id"] for row in expected if row.get("bat_buoc") is False
            ],
            "finding_counts": {
                finding: findings[finding]
                for finding in ("SATISFIED", "VIOLATED", "MISSING", "UNKNOWN")
            },
            "finding_coverage_complete": finding_coverage,
            "evidence_coverage_complete": evidence_coverage,
            "diagnostics": blockers,
        }
        outputs.append(
            RequirementResult(
                tuan_thu_id=stable_id(request, "C08", requirement.yeu_cau_ca_id),
                yeu_cau_ca_id=requirement.yeu_cau_ca_id,
                status=status,
                so_tieu_chi_ap_dung=len(applicable_ids),
                so_tieu_chi_da_danh_gia=len(evaluated),
                so_unknown=findings["UNKNOWN"],
                rule_version=_rule_version(policy, request),
                giai_thich=explanation,
                requirement_snapshot_json=snapshot,
                coverage_complete=coverage,
            )
        )
    return outputs
