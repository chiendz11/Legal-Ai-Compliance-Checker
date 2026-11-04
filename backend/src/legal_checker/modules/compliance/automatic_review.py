"""Backend admissibility review for machine DRAFT findings, never human approval.

Quote matching proves attribution, not legal truth. Only an explicitly reviewed
catalog can authorize a grounded content proposal; numeric facts, local conditions,
exceptions, absence and performance still need independent backend attestations.
"""

from legal_checker.modules.compliance.criterion_reasoner import CONTENT_TYPES, _legal_basis
from legal_checker.modules.compliance.decision_rules import load_decision_rule, parse_json_object
from legal_checker.modules.compliance.reviewed_observations import BackendReview, proposal_digest
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
    gates.evidence_validated = bool(proposal.evidence) and not proposal.external_evidence
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
    supported = criterion.get("loai_kiem_tra") in CONTENT_TYPES
    numeric = conditions.get("numeric_rule") is not None
    predicate = bool(
        proposal.proposed_finding in {"SATISFIED", "VIOLATED"}
        and not issues
        and not unresolved_provider_conditions
        and rule.get("human_verified") is True
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
        **values,
    )
