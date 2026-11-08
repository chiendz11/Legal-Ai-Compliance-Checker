"""The C07 call budget goes to backend-verified criteria first and may run concurrently."""

import threading
from copy import deepcopy

import pytest
from legal_checker.modules.compliance.llm_observations import LLMObservationProvider
from legal_checker.shared.contracts.reasoning import ReasoningRequest
from test_criterion_reasoner import reasoning_case as reasoning_case
from test_llm_observations import FakeClient, prior_verification, semantic


def two_criteria(knowledge, data):
    """Add CRITERION_2 with its own chunk and C06 selection to the one-criterion fixture."""
    second = deepcopy(knowledge.criteria["CRITERION_1"])
    second.update(tieu_chi_id="CRITERION_2", thu_tu=2)
    knowledge.criteria["CRITERION_2"] = second
    knowledge.tables["tieu_chi_danh_gia"].append(second)
    for finding in ("SATISFIED", "VIOLATED", "MISSING", "UNKNOWN"):
        rule = deepcopy(knowledge.decision("CRITERION_1", finding))
        rule.update(tieu_chi_id="CRITERION_2", quy_tac_id="RULE_2_" + finding)
        knowledge.tables["quy_tac_quyet_dinh"].append(rule)
    chunk = deepcopy(data["payload"]["chunks"][0])
    chunk.update(doan_id="CHUNK_2", noi_dung="Second criterion evidence only.")
    data["payload"]["chunks"].append(chunk)
    retrieval = deepcopy(data["payload"]["retrieval"][0])
    retrieval.update(truy_xuat_id="C06_2", tieu_chi_id="CRITERION_2", doan_id="CHUNK_2")
    data["payload"]["retrieval"].append(retrieval)
    return semantic(
        data,
        tieu_chi_id="CRITERION_2",
        evidence=[{"doan_id": "CHUNK_2", "trich_dan": chunk["noi_dung"], "ky_tu_bat_dau": None}],
    )


class ByCriterionClient(FakeClient):
    """Answers by the criterion in the payload, so call order does not matter."""

    def __init__(self, proposals, barrier=None):
        super().__init__([])
        self.proposals = proposals
        self.barrier = barrier
        self.lock = threading.Lock()

    def complete(self, context, **kwargs):
        if self.barrier is not None:
            self.barrier.wait(timeout=5)  # both calls must be in flight at once
        criterion = kwargs["payload"]["criterion"]["tieu_chi_id"]
        with self.lock:
            self.responses = iter([self.proposals[criterion]])
            return super().complete(context, **kwargs)


def test_verified_criteria_get_the_budget_first(reasoning_case):
    knowledge, data = reasoning_case
    proposal_2 = two_criteria(knowledge, data)
    request = ReasoningRequest.model_validate(data)
    client = FakeClient([proposal_2])
    batch = LLMObservationProvider(
        client,
        max_calls=1,
        verifications=[
            prior_verification(request).model_copy(update={"tieu_chi_id": "CRITERION_2"})
        ],
    ).analyze(request, knowledge)
    assert [kw["payload"]["criterion"]["tieu_chi_id"] for _, kw in client.calls] == ["CRITERION_2"]
    # Records keep checklist order; the unverified criterion is the one left over.
    assert [a.tieu_chi_id for a in batch.analyses] == ["CRITERION_1", "CRITERION_2"]
    assert batch.analyses[0].error_code == "CALL_LIMIT"
    assert batch.analyses[1].origin == "OPENAI"


def test_parallel_calls_give_the_same_records_as_sequential(reasoning_case):
    knowledge, data = reasoning_case
    proposal_2 = two_criteria(knowledge, data)
    request = ReasoningRequest.model_validate(data)
    proposals = {"CRITERION_1": semantic(data), "CRITERION_2": proposal_2}
    sequential = LLMObservationProvider(ByCriterionClient(proposals), max_calls=2).analyze(
        request, knowledge
    )
    parallel_client = ByCriterionClient(proposals, barrier=threading.Barrier(2))
    parallel = LLMObservationProvider(parallel_client, max_calls=2, max_parallel_calls=4).analyze(
        request, knowledge
    )
    assert len(parallel_client.calls) == 2
    assert [a.model_dump() for a in parallel.analyses] == [
        a.model_dump() for a in sequential.analyses
    ]


@pytest.mark.parametrize("value", [0, -1, 1.5])
def test_parallel_setting_must_be_a_positive_integer(value):
    with pytest.raises(ValueError):
        LLMObservationProvider(max_parallel_calls=value)
