"""Pure C07 engine for backend-reviewed proposals and pinned numeric constraints.

Semantic predicates belong to an ObservationProvider. No predicate is executed or
interpreted by keyword. Verification flags belong to the trusted backend adapter;
use reviewed_observations for untrusted provider output, never forward LLM gates.
"""

from copy import deepcopy
from typing import Any

from legal_checker.modules.compliance.decision_rules import load_decision_rule, parse_json_object
from legal_checker.modules.compliance.grounding_validator import validate_criteria
from legal_checker.modules.compliance.numeric_rules import (
    NumericInputError,
    evaluate_numeric_for_criterion,
    numeric_kind,
)
from legal_checker.modules.legal_knowledge.models import KnowledgeSnapshot
from legal_checker.shared.contracts.common import Context
from legal_checker.shared.contracts.reasoning import (
    CriterionResult,
    Gates,
    Observation,
    ReasoningRequest,
)
from legal_checker.shared.contracts.temporal import ApplicableRequirement
from legal_checker.shared.ids import stable_id

CONTENT_TYPES = {"CONTRACT_CONTENT", "NOI_DUNG_BAT_BUOC"}
SCOPED_TYPES = {
    "PERFORMANCE_OR_CONDITIONAL",
    "DOI_CHIEU_CO_DIEU_KIEN",
    "CONTRACT_CLAUSE_AND_PERFORMANCE",
}
SUPPORTED_TYPES = (
    CONTENT_TYPES
    | SCOPED_TYPES
    | {
        "PERFORMANCE_WITH_DOCUMENTS",
        "PROHIBITED_CLAUSE",
    }
)
MISSING_POLICIES = {
    "MISSING_CHI_KHI_NOI_DUNG_BAT_BUOC_VA_DA_KIEM_TRA_TOAN_BO",
    "MISSING_ONLY_AFTER_FULL_DOCUMENT_AND_ANNEX_REVIEW",
}


def _legal_basis(criterion: dict[str, Any], knowledge: KnowledgeSnapshot) -> list[str]:
    """Check direct source ownership without equating availability with verification."""
    version_id = criterion["requirement_version_id"]
    version = knowledge.versions[version_id]
    article_id = criterion.get("source_dieu_khoan_id")
    document_id = version.get("source_van_ban_id")
    article = knowledge.articles.get(article_id)
    if (
        not article
        or document_id not in knowledge.documents
        or article.get("van_ban_id") != document_id
    ):
        return []
    try:
        basis = knowledge.legal_basis(criterion)
    except (KeyError, ValueError):
        return []
    expected = [version_id, article_id, document_id]
    return expected if set(expected).issubset(basis) else []


def _rule_gate_issues(conditions, gates, observation, basis, mandatory, unresolved):
    """Evaluate only named boolean gates; an unknown condition never silently passes."""
    actual = {
        **gates.model_dump(),
        "source_available": bool(basis),
        "no_unresolved_conflict": not gates.evidence_conflict,
        "facts_verified": observation.facts_verified,
        "all_pages_readable": observation.all_pages_readable,
        "all_related_documents_received": observation.all_related_documents_received,
        "template_field_unfilled": observation.template_field_unfilled,
        "mandatory_contract_content": mandatory,
        "criterion_content_absent": gates.absence_verified,
        "any_unresolved_fact": unresolved,
        "optional_choice_confirmed": (
            observation.facts_verified
            and observation.facts.get("optional_choice_confirmed") is True
        ),
    }
    issues = []
    for name, expected in conditions.get("gate", {}).items():
        if name not in actual or type(expected) is not bool:
            issues.append(f"Unsupported decision rule gate: {name}")
        elif actual[name] is not expected:
            issues.append(f"Decision rule gate not met: {name}")
    return issues


def _exclusion(requirement, observation, gates, applicability, policy_resolved):
    """Retain a justified non-applicability as UNKNOWN/excluded, never a fifth finding."""
    if (
        requirement.applicability_status == "NOT_APPLICABLE"
        and requirement.scope_status == "NO_MATCH"
        and requirement.version_status == "RESOLVED"
    ):
        explanation = "; ".join(value for value in requirement.reason.values() if value.strip())
        if explanation:
            return "C05 NOT_APPLICABLE: " + explanation
    if not policy_resolved:
        # A missing rule, unsupported policy or unresolved fact cannot disappear
        # from C08 coverage through a local exclusion. C05 above is resolver-owned.
        return None
    if (
        requirement.confirmed
        and observation
        and observation.facts_verified
        and observation.facts.get("optional_choice_confirmed") is False
        and applicability.get("optional_choice") is True
        and applicability.get("not_selected_policy") == "NOT_APPLICABLE"
        and gates.reliable()
        and (observation.evidence or observation.external_evidence)
    ):
        return "Optional mechanism verified as not selected; pinned policy NOT_APPLICABLE"
    if (
        requirement.confirmed
        and observation
        and observation.local_applicability == "NO_MATCH"
        and observation.exclusion_reason
        and gates.reliable()
        and (observation.evidence or observation.external_evidence)
    ):
        return "Criterion local NO_MATCH: " + observation.exclusion_reason
    return None


def _applicability(criterion, knowledge):
    """Interpret structural local-criterion policies, never natural-language scope text."""
    try:
        applicability = parse_json_object(criterion.get("dieu_kien", {}))
    except (TypeError, ValueError):
        return {}, ["Invalid criterion applicability JSON"]
    issues = []
    supported = {
        "exception_ids",
        "optional_choice",
        "case_facts_required",
        "not_selected_policy",
        "scope_missing_policy",
        "criterion_target_only",
        "requirement_version_id",
        "local_applicability_only",
    }
    if set(applicability) - supported:
        issues.append("Unsupported criterion applicability conditions")
    for key in ("optional_choice", "case_facts_required", "local_applicability_only"):
        if key in applicability and type(applicability[key]) is not bool:
            issues.append(f"Invalid criterion applicability flag: {key}")
    if applicability.get("criterion_target_only", True) is not True:
        issues.append("Criterion applicability must target only the current criterion")
    if applicability.get("local_applicability_only", True) is not True:
        issues.append("Unsupported non-local criterion applicability")
    exception_ids = applicability.get("exception_ids", [])
    if not isinstance(exception_ids, list) or any(
        not isinstance(value, str) or not value for value in exception_ids
    ):
        issues.append("Invalid criterion exception_ids")
    else:
        known_exceptions = {
            row.get("ngoai_le_id")
            for row in getattr(knowledge, "tables", {}).get("ngoai_le_ap_dung", [])
            if row.get("requirement_version_id") in (None, criterion["requirement_version_id"])
            and row.get("tieu_chi_id") in (None, criterion["tieu_chi_id"])
        }
        if any(exception_id not in known_exceptions for exception_id in exception_ids):
            issues.append("Criterion refers to an unresolved or foreign exception")
    if applicability.get("not_selected_policy") not in (None, "NOT_APPLICABLE"):
        issues.append("Unsupported criterion not_selected_policy")
    if applicability.get("scope_missing_policy", "UNKNOWN") != "UNKNOWN":
        issues.append("Unsupported criterion scope_missing_policy")
    declared_version = applicability.get("requirement_version_id")
    if declared_version is not None and declared_version != criterion["requirement_version_id"]:
        issues.append("Criterion applicability requirement version mismatch")
    return applicability, issues


def _type_issues(criterion_type, proposal, observation, gates, request, conditions):
    """Apply structural proof policies for supported criterion types.

    Backend-reviewed `evaluation_target` separates a contract clause from actual
    performance. A provider's opinion or a promise is never a receipt substitute.
    """
    if proposal not in {"SATISFIED", "VIOLATED"}:
        return []
    issues = []
    if criterion_type in CONTENT_TYPES and not observation.evidence:
        gates.evidence_validated = False
        issues.append("Contract-content criterion requires attributable contract evidence")
    target = observation.facts.get("evaluation_target")
    needs_target = (
        criterion_type in SCOPED_TYPES or conditions.get("conclusion_scope_required") is True
    )
    if needs_target and (
        not observation.facts_verified or target not in {"CONTRACT_CONTENT", "PERFORMANCE"}
    ):
        issues.append("A verified evaluation_target CONTRACT_CONTENT/PERFORMANCE is required")
    if criterion_type in {"PERFORMANCE_OR_CONDITIONAL", "DOI_CHIEU_CO_DIEU_KIEN"}:
        if (
            not observation.facts_verified
            or observation.facts.get("condition_triggered") is not True
        ):
            issues.append("Current-criterion condition_triggered is unresolved or not confirmed")
    if needs_target and target == "CONTRACT_CONTENT" and not observation.evidence:
        issues.append("Contract-content target requires attributable contract evidence")
    if (
        criterion_type == "PERFORMANCE_OR_CONDITIONAL"
        and proposal == "SATISFIED"
        and target == "CONTRACT_CONTENT"
    ):
        issues.append("A contract promise cannot establish performance SATISFIED")
    needs_external = (
        criterion_type == "PERFORMANCE_WITH_DOCUMENTS"
        or (needs_target and target == "PERFORMANCE")
        or (
            conditions.get("performance_requires_receipt_evidence") is True
            and target == "PERFORMANCE"
        )
    )
    if needs_external and not observation.external_evidence:
        gates.evidence_validated = False
        issues.append(
            "Performance requires registered external evidence; contract promises are insufficient"
        )
    if criterion_type == "PROHIBITED_CLAUSE":
        if proposal == "SATISFIED":
            for key in ("coverage_complete", "absence_verified"):
                if not getattr(gates, key):
                    issues.append(f"PROHIBITED_CLAUSE SATISFIED requires {key}")
            for key in ("all_pages_readable", "all_related_documents_received"):
                if not getattr(observation, key):
                    issues.append(f"PROHIBITED_CLAUSE SATISFIED requires {key}")
            if not request.payload.chunks:
                issues.append("PROHIBITED_CLAUSE requires the reviewed contract document set")
        elif not observation.evidence:
            issues.append("PROHIBITED_CLAUSE VIOLATED requires the actual contract clause")
    return issues


def _missing_issues(criterion, observation, gates, request):
    """An absence assertion needs a reviewed document set, not a fabricated quote."""
    issues = []
    if criterion.get("loai_kiem_tra") not in CONTENT_TYPES:
        issues.append("MISSING is only supported for mandatory contract content")
    if criterion.get("missing_policy") not in MISSING_POLICIES:
        issues.append("Missing policy does not permit MISSING or is unsupported")
    if not (
        criterion.get("bat_buoc") is True
        and criterion.get("noi_dung_bat_buoc_trong_hd") is True
        and observation.mandatory_confirmed
    ):
        issues.append("Mandatory contract content/applicability is not confirmed")
    for name in ("coverage_complete", "absence_verified"):
        if not getattr(gates, name):
            issues.append(f"MISSING requires {name}")
    for name in ("all_pages_readable", "all_related_documents_received"):
        if not getattr(observation, name):
            issues.append(f"MISSING requires {name}")
    if not request.payload.chunks:
        issues.append("MISSING requires the reviewed contract document set")
    return issues


def _evaluate(
    request: ReasoningRequest,
    knowledge: KnowledgeSnapshot,
    requirement: ApplicableRequirement,
    criterion: dict[str, Any],
    observation: Observation | None,
    grounding_issues: list[str],
) -> CriterionResult:
    """Check one proposal without modifying the request, catalog or verification state."""
    criterion_id = criterion["tieu_chi_id"]
    proposal = observation.proposed_finding if observation else "UNKNOWN"
    rule, conditions, issues = load_decision_rule(criterion_id, proposal, knowledge)
    applicability, applicability_issues = _applicability(criterion, knowledge)
    issues.extend(applicability_issues)
    exclusion_policy_resolved = not issues
    issues.extend(grounding_issues)
    basis = _legal_basis(criterion, knowledge)
    gates = observation.gates.model_copy(deep=True) if observation else Gates()
    gates.scope_confirmed = gates.scope_confirmed and requirement.scope_status == "MATCH"
    gates.version_resolved = gates.version_resolved and requirement.version_status == "RESOLVED"
    gates.source_verified = gates.source_verified and bool(basis)
    if grounding_issues or observation is None:
        gates.evidence_validated = False
    if proposal in {"SATISFIED", "VIOLATED"} and observation:
        if not (observation.evidence or observation.external_evidence):
            gates.evidence_validated = False
            issues.append("A content finding requires attributable evidence")
    if not requirement.confirmed:
        issues.append("Requirement applicability/scope/version is not confirmed")
    criterion_type = criterion.get("loai_kiem_tra")
    if criterion_type not in SUPPORTED_TYPES:
        exclusion_policy_resolved = False
        issues.append(f"Unsupported criterion type: {criterion_type}")
    if not basis:
        exclusion_policy_resolved = False
        issues.append("Missing or inconsistent legal basis/source provenance")
    mandatory = bool(
        criterion.get("bat_buoc") is True
        and criterion.get("noi_dung_bat_buoc_trong_hd") is True
        and observation
        and observation.mandatory_confirmed
    )
    numeric = conditions.get("numeric_rule")
    if numeric is not None:
        try:
            numeric_kind(numeric)
        except NumericInputError as exc:
            exclusion_policy_resolved = False
            issues.append(str(exc))
    if observation is None:
        issues.append("Missing observation for the criterion")
    else:
        if proposal == "UNKNOWN":
            issues.append(f"Provider uncertainty: {observation.giai_thich}")
        if observation.local_applicability != "MATCH":
            issues.append("Criterion local_applicability is not MATCH")
        if observation.template_field_unfilled:
            issues.append("A required current-criterion template field is unfilled")
        if observation.facts and (
            not observation.facts_verified or any(v is None for v in observation.facts.values())
        ):
            exclusion_policy_resolved = False
            issues.append("Current-criterion facts are unresolved or unverified")
        if applicability.get("case_facts_required") is True and (
            not observation.facts_verified or not observation.facts
        ):
            exclusion_policy_resolved = False
            issues.append("Criterion requires verified current-criterion case facts")
        if proposal == "MISSING":
            issues.extend(_missing_issues(criterion, observation, gates, request))
        issues.extend(
            _type_issues(criterion_type, proposal, observation, gates, request, conditions)
        )
        if applicability.get("optional_choice") is True:
            if (
                not observation.facts_verified
                or observation.facts.get("optional_choice_confirmed") is not True
            ):
                issues.append("Optional criterion choice is unresolved or verified as not selected")
        if conditions.get("performance_requires_receipt_evidence") is True and not conditions.get(
            "conclusion_scope_required"
        ):
            issues.append("Receipt-evidence rule requires an explicit conclusion scope policy")
        if proposal in {"SATISFIED", "VIOLATED"} and numeric is not None:
            try:
                holds = evaluate_numeric_for_criterion(
                    numeric, observation.facts, facts_verified=observation.facts_verified
                )
                if holds != (proposal == "SATISFIED"):
                    issues.append("Numeric evaluation disagrees with the proposed finding")
            except NumericInputError as exc:
                exclusion_policy_resolved = False
                issues.append(str(exc))
        if isinstance(conditions.get("gate"), dict):
            issues.extend(
                _rule_gate_issues(
                    conditions,
                    gates,
                    observation,
                    basis,
                    mandatory,
                    bool(issues) or not gates.reliable(),
                )
            )
    for name in (
        "evidence_validated",
        "source_verified",
        "scope_confirmed",
        "version_resolved",
        "exceptions_resolved",
    ):
        if not getattr(gates, name):
            issues.append(f"Unresolved gate: {name}")
    if gates.evidence_conflict:
        issues.append("Unresolved evidence_conflict")
    exclusion_reason = _exclusion(
        requirement, observation, gates, applicability, exclusion_policy_resolved
    )
    if exclusion_reason:
        issues.append("Excluded by applicability policy: " + exclusion_reason)
    uncertainty = "; ".join(dict.fromkeys(issues)) if issues else None
    snapshot = deepcopy(criterion)
    snapshot["knowledge_snapshot_sha256"] = request.knowledge_snapshot_sha256
    snapshot["context"] = request.model_dump(mode="json", include=set(Context.model_fields))
    snapshot["hop_dong_id"] = request.payload.hop_dong_id
    if rule is not None:
        snapshot["decision_rule_snapshot_json"] = deepcopy(rule)
    explanation = (
        f"Cannot accept a finding: {uncertainty}" if uncertainty else observation.giai_thich
    )
    if (
        observation
        and observation.facts_verified
        and observation.facts.get("evaluation_target") in {"CONTRACT_CONTENT", "PERFORMANCE"}
        and (criterion_type in SCOPED_TYPES or conditions.get("conclusion_scope_required") is True)
    ):
        explanation = (
            f"Conclusion target: {observation.facts['evaluation_target']}; "
            "only the current criterion. " + explanation
        )
    return CriterionResult(
        ket_qua_id=stable_id(request, "C07", f"{requirement.yeu_cau_ca_id}/{criterion_id}"),
        ca_id=request.ca_id,
        yeu_cau_ca_id=requirement.yeu_cau_ca_id,
        tieu_chi_id=criterion_id,
        finding="UNKNOWN" if uncertainty else proposal,
        giai_thich=explanation,
        gates=gates,
        uncertainty_reason=uncertainty,
        evidence=[e.model_copy(deep=True) for e in observation.evidence] if observation else [],
        external_evidence=(
            [e.model_copy(deep=True) for e in observation.external_evidence] if observation else []
        ),
        legal_basis_ids=basis,
        tieu_chi_snapshot_json=snapshot,
        model_version=observation.model_version if observation else "NO_OBSERVATION",
        prompt_version=observation.prompt_version if observation else "NOT_USED",
        lan_chay_id=request.run_id,
        mandatory=criterion.get("bat_buoc") is True,
        excluded=bool(exclusion_reason),
        exclusion_reason=exclusion_reason,
    )


def reason(request: ReasoningRequest, knowledge: KnowledgeSnapshot) -> list[CriterionResult]:
    """Return C07 for the resolved checklist; malformed identity/quotes raise ValueError.

    Missing facts/verification/rules produce UNKNOWN. An unresolved C05 version
    produces no criterion findings, including when it retains a candidate version
    ID. C08 must retain that requirement and explain the incomplete resolution.
    """
    request = ReasoningRequest.model_validate(request.model_dump())
    grounding = validate_criteria(request, knowledge, complete=True)
    observations = {item.tieu_chi_id: item for item in request.payload.observations}
    results = []
    for requirement in request.payload.requirements:
        if requirement.version_status != "RESOLVED" or requirement.requirement_version_id is None:
            continue
        for criterion in knowledge.criteria_for(requirement.requirement_version_id):
            criterion_id = criterion["tieu_chi_id"]
            results.append(
                _evaluate(
                    request,
                    knowledge,
                    requirement,
                    criterion,
                    observations.get(criterion_id),
                    grounding[criterion_id],
                )
            )
    return results
