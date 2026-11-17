"""Backend admissibility review for machine DRAFT findings, never human approval.

Quote matching proves attribution, not legal truth. Only an explicitly reviewed
catalog can authorize a grounded content proposal; numeric facts, local conditions,
exceptions, absence and performance still need independent backend attestations.
"""

from legal_checker.modules.compliance.criterion_reasoner import (
    CONTENT_TYPES,
    SUPPORTED_TYPES,
    _legal_basis,
)
from legal_checker.modules.compliance.decision_rules import load_decision_rule, parse_json_object
from legal_checker.modules.compliance.reviewed_observations import BackendReview, proposal_digest
from legal_checker.modules.compliance.subject_grounding import subject_supported
from legal_checker.shared.contracts.common import Context
from legal_checker.shared.contracts.reasoning import Gates

POLICY = "C07_GROUNDED_DRAFT_V1"


def automatic_review(
    proposal, request, knowledge, *, verification=None, unresolved_provider_conditions=False
):
    """Derive gates from backend inputs; never copy gates/facts from an AI response.

    This is a machine review of admissibility for a draft. Human publication review
    remains PENDING. Unreviewed knowledge and unsupported proof obligations fail closed.
    """
    criterion = knowledge.criteria[proposal.tieu_chi_id]
    requirement = next(
        r
        for r in request.payload.requirements
        if r.requirement_version_id == criterion["requirement_version_id"]
    )
    version = knowledge.versions[criterion["requirement_version_id"]]
    rule, conditions, issues = load_decision_rule(
        proposal.tieu_chi_id, proposal.proposed_finding, knowledge
    )
    try:
        applicability = parse_json_object(criterion.get("dieu_kien", {}))
    except ValueError:
        applicability, issues = {}, [*issues, "invalid applicability"]
    exceptions = [
        row
        for row in knowledge.tables.get("ngoai_le_ap_dung", [])
        if row.get("tieu_chi_id") == proposal.tieu_chi_id
        or (
            not row.get("tieu_chi_id")
            and row.get("requirement_version_id") == requirement.requirement_version_id
        )
    ]
    # Existing independent attestations may supply facts; their context was checked
    # by LLMObservationProvider. CandidateFact from an AI is never promoted here.
    gates = verification.gates.model_copy(deep=True) if verification else Gates()
    synthetic = bool(
        verification
        and verification.verification_reference.startswith("SYNTHETIC_SCENARIO_V1:")
        and verification.facts_verified
        and verification.facts.get("synthetic_evaluation") is True
    )
    source_checked_draft = bool(
        verification
        and verification.verification_reference.startswith("C02_DRAFT_CONTENT_V2:")
        and verification.facts_verified
        and verification.facts.get("assessment_mode") == "DRAFT_REVIEW"
        and verification.facts.get("assessment_policy_id") == "DRAFT_CONTENT_REVIEW_V1"
        and verification.facts.get("evaluation_target") == "CONTRACT_CONTENT"
        and getattr(knowledge, "review_status", None) in {"HUMAN_VERIFIED", "SOURCE_CHECKED"}
    )
    gates.scope_confirmed = requirement.confirmed
    gates.version_resolved = requirement.version_status == "RESOLVED"
    gates.source_verified = bool(_legal_basis(criterion, knowledge)) and (
        gates.source_verified
        or (
            criterion.get("human_verified") is True
            and criterion.get("trang_thai_nguon") == "VERIFIED"
            and version.get("trang_thai_ra_soat") == "HUMAN_VERIFIED"
        )
    )
    # Exact quote and C06 membership have already been validated by the adapter.
    registered = {
        row.bang_chung_id
        for row in request.payload.external_evidence_registry
        if row.verified and row.tieu_chi_id == proposal.tieu_chi_id
    }
    gates.evidence_validated = bool(proposal.evidence or proposal.external_evidence) and all(
        row.bang_chung_id in registered for row in proposal.external_evidence
    )
    fdr_rows = [
        r
        for r in request.payload.retrieval
        if r.yeu_cau_ca_id == requirement.yeu_cau_ca_id
        and r.tieu_chi_id == proposal.tieu_chi_id
        and r.giai_doan == "FINAL"
        and (
            r.scores.get("full_document_review") is not None
            or r.retrieval_version.startswith("FULL_DOCUMENT_REVIEW")
        )
    ]
    if (
        not gates.absence_verified
        and verification
        and criterion.get("loai_kiem_tra") == "PROHIBITED_CLAUSE"
        and proposal.proposed_finding == "SATISFIED"
        and not issues
        and not unresolved_provider_conditions
        and gates.coverage_complete
        and gates.evidence_validated
        and verification.all_pages_readable
        and verification.all_related_documents_received
        and verification.facts.get("document_review_complete") is True
        and verification.facts.get("document_review_non_candidates_absent") is True
        and verification.facts.get("content_subject_validated") is not False
        and bool(fdr_rows)
        and all(r.duoc_chon for r in fdr_rows)
    ):
        gates.absence_verified = True
    if not verification:
        gates.exceptions_resolved = not exceptions and not applicability.get("exception_ids")
    local = (
        verification.local_applicability
        if verification
        else (
            "UNKNOWN"
            if any(applicability.get(k) for k in ("optional_choice", "case_facts_required"))
            else "MATCH"
        )
    )
    # An unqualified semantic CONTENT draft is allowed only with the verified
    # catalog above. Complex/numeric predicates are still checked by reason().
    supported = criterion.get("loai_kiem_tra") in (
        SUPPORTED_TYPES if verification and verification.facts_verified else CONTENT_TYPES
    )
    numeric = conditions.get("numeric_rule") is not None
    absence_predicate = bool(
        verification
        and proposal.proposed_finding == "MISSING"
        and criterion.get("loai_kiem_tra") in CONTENT_TYPES
        and criterion.get("bat_buoc") is True
        and criterion.get("noi_dung_bat_buoc_trong_hd") is True
        and verification.mandatory_confirmed
        and verification.all_pages_readable
        and verification.all_related_documents_received
        and gates.missing_allowed()
    )
    predicate = bool(
        (proposal.proposed_finding in {"SATISFIED", "VIOLATED"} or absence_predicate)
        and not issues
        and not unresolved_provider_conditions
        and (
            proposal.proposed_finding != "VIOLATED"
            or subject_supported(
                proposal.tieu_chi_id, " ".join(e.trich_dan for e in proposal.evidence)
            )
        )
        and (
            verification is None or verification.facts.get("content_subject_validated") is not False
        )
        and (
            rule.get("human_verified") is True
            or synthetic
            or (source_checked_draft and rule.get("trang_thai") == "SOURCE_CHECKED")
        )
        and supported
        and gates.reliable()
        and local == "MATCH"
        and (not numeric or (verification and verification.facts_verified))
    )
    values = {}
    if verification:
        for name in (
            "mandatory_confirmed",
            "all_pages_readable",
            "all_related_documents_received",
            "template_field_unfilled",
            "facts",
            "facts_verified",
        ):
            values[name] = getattr(verification, name)
    return BackendReview(
        **{name: getattr(request, name) for name in Context.model_fields},
        hop_dong_id=request.payload.hop_dong_id,
        yeu_cau_ca_id=requirement.yeu_cau_ca_id,
        tieu_chi_id=proposal.tieu_chi_id,
        proposal_sha256=proposal_digest(proposal),
        verification_reference=POLICY + ":" + request.knowledge_snapshot_sha256,
        predicate_verified=predicate,
        gates=gates,
        local_applicability=local,
        exclusion_reason=(
            str(verification.facts["local_non_applicability_reason"])
            if source_checked_draft
            and local == "NO_MATCH"
            and verification.facts.get("local_condition_policy") == "DRAFT_LOCAL_CONDITIONS_V1"
            and verification.facts.get("condition_review_sha256")
            and verification.facts.get("document_review_complete") is True
            and verification.facts.get("local_non_applicability_reason")
            else str(verification.facts.get("synthetic_non_applicability_reason"))
            if synthetic
            and local == "NO_MATCH"
            and verification.facts.get("synthetic_non_applicability_reason")
            else None
        ),
        **values,
    )
