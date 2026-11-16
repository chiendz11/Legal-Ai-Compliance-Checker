"""An adverse opinion without supporting quotes must not become a legal risk."""

import pytest
from legal_checker.modules.compliance.llm_observations import LLMObservationProvider
from legal_checker.shared.contracts.reasoning import ReasoningRequest
from test_criterion_reasoner import reasoning_case as reasoning_case
from test_llm_observations import FakeClient, semantic


@pytest.mark.parametrize("verdict", ["UNSUPPORTED", "UNCERTAIN"])
def test_adverse_recheck_rejects_opinion_without_turning_it_positive(reasoning_case, verdict):
    knowledge, data = reasoning_case
    client = FakeClient(
        [
            semantic(data, proposed_finding="VIOLATED"),
            {
                "verdict": verdict,
                "supporting_quote_ids": [],
                "explanation": "The actual quote does not establish the alleged prohibited act.",
            },
        ]
    )
    batch = LLMObservationProvider(client, verify_adverse_evidence=True).analyze(
        ReasoningRequest.model_validate(data), knowledge
    )
    result = batch.analyses[0]
    assert result.error_code == "ADVERSE_EVIDENCE_NOT_SUPPORTED"
    assert result.observation.proposed_finding == "UNKNOWN"
    assert result.proposal.proposed_finding == "VIOLATED"  # Raw opinion retained for review.
    assert result.adverse_evidence_review["verdict"] == verdict
    assert len(client.calls) == 2


@pytest.mark.parametrize("ids", [[], ["FOREIGN"], ["E1", "E1"]])
def test_supported_response_requires_real_unique_quote_ids(reasoning_case, ids):
    knowledge, data = reasoning_case
    client = FakeClient(
        [
            semantic(data, proposed_finding="VIOLATED"),
            {
                "verdict": "SUPPORTED",
                "supporting_quote_ids": ids,
                "explanation": "Claimed support.",
            },
        ]
    )
    batch = LLMObservationProvider(client, verify_adverse_evidence=True).analyze(
        ReasoningRequest.model_validate(data), knowledge
    )
    assert batch.analyses[0].error_code == "INVALID_ADVERSE_EVIDENCE_CHECK"
    assert batch.observations[0].proposed_finding == "UNKNOWN"


def test_support_check_cannot_approve_backend_gates(reasoning_case):
    knowledge, data = reasoning_case
    client = FakeClient(
        [
            semantic(data, proposed_finding="VIOLATED"),
            {
                "verdict": "SUPPORTED",
                "supporting_quote_ids": ["E1"],
                "explanation": "Offline synthetic quote/predicate agreement.",
            },
        ]
    )
    batch = LLMObservationProvider(client, verify_adverse_evidence=True).analyze(
        ReasoningRequest.model_validate(data), knowledge
    )
    result = batch.analyses[0]
    assert result.error_code is None
    assert result.adverse_evidence_review["verdict"] == "SUPPORTED"
    assert result.observation.proposed_finding == "UNKNOWN"  # No trusted backend review.
    assert not result.observation.gates.source_verified
    assert len(result.adverse_evidence_review["input_sha256"]) == 64
