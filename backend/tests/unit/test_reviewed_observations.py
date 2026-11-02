"""Provider claims never manufacture backend verification or external provenance."""

from copy import deepcopy

import pytest
from legal_checker.modules.compliance.criterion_reasoner import reason
from legal_checker.modules.compliance.reviewed_observations import (
    BackendReview,
    build_verified_observation,
    proposal_digest,
)
from legal_checker.shared.contracts.reasoning import Observation, ReasoningRequest
from test_c07_findings import register_external
from test_criterion_reasoner import reasoning_case as reasoning_case


def make_review(request, proposal):
    context = {
        key: getattr(request, key)
        for key in (
            "ca_id",
            "phien_ban_id",
            "rule_version",
            "legal_knowledge_version",
            "knowledge_snapshot_sha256",
            "run_id",
            "trace_id",
        )
    }
    return BackendReview(
        **context,
        hop_dong_id=request.payload.hop_dong_id,
        yeu_cau_ca_id="CASE_REQUIREMENT_1",
        tieu_chi_id="CRITERION_1",
        proposal_sha256=proposal_digest(proposal),
        verification_reference="memory://review/1",
        predicate_verified=True,
        gates={
            "evidence_validated": True,
            "source_verified": True,
            "scope_confirmed": True,
            "version_resolved": True,
            "exceptions_resolved": True,
        },
        local_applicability="MATCH",
    )


def test_llm_self_asserted_flags_are_discarded_without_backend_review(reasoning_case):
    knowledge, data = reasoning_case
    register_external(data)
    data["payload"]["external_evidence_registry"] = []
    proposal = Observation.model_validate(data["payload"]["observations"][0])
    proposal.gates.coverage_complete = True
    proposal.gates.absence_verified = True
    proposal.facts_verified = True
    proposal.facts = {"made_up": "1"}
    before = proposal.model_dump()
    request = ReasoningRequest.model_validate(data)
    result = build_verified_observation(proposal, None, request, knowledge)
    assert result.proposed_finding == "UNKNOWN"
    assert not result.gates.reliable()
    assert not result.gates.source_verified
    assert not result.gates.absence_verified
    assert result.local_applicability == "UNKNOWN"
    assert not result.mandatory_confirmed
    assert not result.facts_verified and result.facts == {}
    assert not result.external_evidence[0].verified
    assert proposal.model_dump() == before


def test_backend_review_is_independent_and_does_not_mutate_inputs(reasoning_case):
    knowledge, data = reasoning_case
    request = ReasoningRequest.model_validate(data)
    proposal = request.payload.observations[0]
    review = make_review(request, proposal)
    before = deepcopy((request.model_dump(), review.model_dump()))
    result = build_verified_observation(proposal, review, request, knowledge)
    request_data = request.model_dump()
    request_data["payload"]["observations"] = [result.model_dump()]
    assert (
        reason(ReasoningRequest.model_validate(request_data), knowledge)[0].finding == "SATISFIED"
    )
    result.gates.source_verified = False
    assert (request.model_dump(), review.model_dump()) == before


@pytest.mark.parametrize(
    "field,value",
    [
        ("ca_id", "OTHER_CASE"),
        ("run_id", "OTHER_RUN"),
        ("phien_ban_id", "OTHER_DEPLOYMENT"),
        ("knowledge_snapshot_sha256", "f" * 64),
        ("tieu_chi_id", "OTHER_CRITERION"),
        ("yeu_cau_ca_id", "OTHER_REQUIREMENT"),
        ("hop_dong_id", "OTHER_CONTRACT"),
        ("proposal_sha256", "f" * 64),
    ],
)
def test_backend_review_must_bind_exact_context_and_proposal(reasoning_case, field, value):
    knowledge, data = reasoning_case
    request = ReasoningRequest.model_validate(data)
    proposal = request.payload.observations[0]
    review = make_review(request, proposal).model_copy(update={field: value})
    with pytest.raises(ValueError, match="Backend review"):
        build_verified_observation(proposal, review, request, knowledge)


def test_proposal_changed_after_review_cannot_reuse_flags(reasoning_case):
    knowledge, data = reasoning_case
    request = ReasoningRequest.model_validate(data)
    proposal = request.payload.observations[0]
    review = make_review(request, proposal)
    proposal.proposed_finding = "VIOLATED"
    with pytest.raises(ValueError, match="digest"):
        build_verified_observation(proposal, review, request, knowledge)


def test_unreviewed_predicate_remains_unknown_even_with_backend_gates(reasoning_case):
    knowledge, data = reasoning_case
    request = ReasoningRequest.model_validate(data)
    proposal = request.payload.observations[0]
    review = make_review(request, proposal)
    review.predicate_verified = False
    result = build_verified_observation(proposal, review, request, knowledge)
    assert result.proposed_finding == "UNKNOWN"


def test_external_verification_comes_from_registered_source_not_proposal(reasoning_case):
    knowledge, data = reasoning_case
    register_external(data)
    data["payload"]["observations"][0]["external_evidence"][0]["verified"] = False
    request = ReasoningRequest.model_validate(data)
    proposal = request.payload.observations[0]
    review = make_review(request, proposal)
    result = build_verified_observation(proposal, review, request, knowledge)
    assert result.external_evidence[0].verified
    data["payload"]["external_evidence_registry"][0]["verified"] = False
    result = build_verified_observation(
        proposal, review, ReasoningRequest.model_validate(data), knowledge
    )
    assert not result.external_evidence[0].verified
    assert not result.gates.evidence_validated
