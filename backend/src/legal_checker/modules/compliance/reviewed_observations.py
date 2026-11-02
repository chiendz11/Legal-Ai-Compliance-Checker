"""Separate untrusted semantic proposals from context-bound backend review records.

The caller supplies review/registry records from trusted application storage or a
human review step. This module verifies their linkage; it cannot authenticate a
reviewer or download/hash documents. Never deserialize these records from LLM text.
"""

import hashlib
import json
from decimal import Decimal
from typing import Literal

from pydantic import Field

from legal_checker.modules.compliance.grounding_validator import validate_criteria
from legal_checker.modules.legal_knowledge.models import KnowledgeSnapshot
from legal_checker.shared.contracts.common import Context
from legal_checker.shared.contracts.reasoning import Gates, Observation, ReasoningRequest


class BackendReview(Context):
    """Trusted review of the exact proposal in this case/run/snapshot, defaulting unknown."""

    hop_dong_id: str
    yeu_cau_ca_id: str
    tieu_chi_id: str
    proposal_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    verification_reference: str = Field(min_length=1)
    predicate_verified: bool = Field(default=False, strict=True)
    gates: Gates = Field(default_factory=Gates)
    local_applicability: Literal["MATCH", "NO_MATCH", "UNKNOWN"] = "UNKNOWN"
    exclusion_reason: str | None = None
    mandatory_confirmed: bool = False
    all_pages_readable: bool = False
    all_related_documents_received: bool = False
    template_field_unfilled: bool = False
    facts: dict[str, Decimal | bool | str | None] = Field(default_factory=dict)
    facts_verified: bool = False


def proposal_digest(proposal: Observation) -> str:
    """Bind review to exact proposal contents, including evidence offsets and facts."""
    data = json.dumps(proposal.model_dump(mode="json"), sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def build_verified_observation(
    proposal: Observation,
    review: BackendReview | None,
    request: ReasoningRequest,
    knowledge: KnowledgeSnapshot,
) -> Observation:
    """Discard all provider verification claims, then apply a separate backend review.

    No review means conservative UNKNOWN verification, even if the provider claimed
    every gate. Exact evidence and metadata survive; structural checks can only
    demote the backend's flags. A registry entry is required for external evidence.
    """
    proposal = Observation.model_validate(proposal.model_dump())
    # Construct a fresh DTO: no provider gates, scope, absence, facts or exclusions
    # are inherited. Model/prompt metadata describe the semantic proposal itself.
    output = Observation(
        tieu_chi_id=proposal.tieu_chi_id,
        proposed_finding=proposal.proposed_finding,
        giai_thich=proposal.giai_thich,
        evidence=[item.model_copy(deep=True) for item in proposal.evidence],
        external_evidence=[item.model_copy(deep=True) for item in proposal.external_evidence],
        model_version=proposal.model_version,
        prompt_version=proposal.prompt_version,
    )
    if review is not None:
        review = BackendReview.model_validate(review.model_dump())
        for key in (
            "ca_id",
            "phien_ban_id",
            "run_id",
            "rule_version",
            "legal_knowledge_version",
            "knowledge_snapshot_sha256",
        ):
            if getattr(review, key) != getattr(request, key):
                raise ValueError(f"Backend review context mismatch: {key}")
        if (
            review.hop_dong_id != request.payload.hop_dong_id
            or review.tieu_chi_id != proposal.tieu_chi_id
            or review.proposal_sha256 != proposal_digest(proposal)
        ):
            raise ValueError("Backend review proposal/contract/criterion digest mismatch")
        criterion = knowledge.criteria.get(proposal.tieu_chi_id)
        requirement = next(
            (
                item
                for item in request.payload.requirements
                if item.yeu_cau_ca_id == review.yeu_cau_ca_id
            ),
            None,
        )
        if (
            not criterion
            or not requirement
            or (requirement.requirement_version_id != criterion["requirement_version_id"])
        ):
            raise ValueError("Backend review requirement/criterion ownership mismatch")
        for name in (
            "gates",
            "local_applicability",
            "exclusion_reason",
            "mandatory_confirmed",
            "all_pages_readable",
            "all_related_documents_received",
            "template_field_unfilled",
            "facts",
            "facts_verified",
        ):
            # Dump/validate below makes a deep copy of all review values.
            setattr(output, name, getattr(review, name))
        if not review.predicate_verified:
            output.proposed_finding = "UNKNOWN"
            output.giai_thich = "Semantic predicate has not been reviewed: " + proposal.giai_thich
    else:
        output.proposed_finding = "UNKNOWN"
        output.giai_thich = "Missing backend review of provider proposal: " + proposal.giai_thich
    output = Observation.model_validate(output.model_dump())
    registry = {
        (entry.tieu_chi_id, entry.bang_chung_id): entry
        for entry in request.payload.external_evidence_registry
    }
    for evidence in output.external_evidence:
        entry = registry.get((output.tieu_chi_id, evidence.bang_chung_id))
        evidence.verified = bool(entry and entry.verified)
    data = request.model_dump()
    data["payload"]["observations"] = [output.model_dump()]
    issues = validate_criteria(ReasoningRequest.model_validate(data), knowledge)
    if issues[output.tieu_chi_id]:
        output.gates.evidence_validated = False
    return output
