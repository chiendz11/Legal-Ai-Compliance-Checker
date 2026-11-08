"""Backend contract-content attestations unblock grounded findings, and only those."""

from copy import deepcopy

import pytest
from legal_checker.modules.compliance.backend_verification import (
    POLICY,
    contract_content_verifications,
)
from legal_checker.modules.compliance.criterion_reasoner import reason
from legal_checker.modules.compliance.llm_observations import LLMObservationProvider
from legal_checker.shared.contracts.common import Context
from legal_checker.shared.contracts.reasoning import ReasoningRequest
from legal_checker.shared.contracts.temporal import ApplicableRequirement
from test_criterion_reasoner import reasoning_case as reasoning_case
from test_llm_observations import FakeClient, semantic

# The shape every criterion of the reviewed catalogue has.
CATALOGUE_CONDITIONS = {
    "exception_ids": [],
    "optional_choice": False,
    "case_facts_required": True,
    "not_selected_policy": None,
    "scope_missing_policy": "UNKNOWN",
    "criterion_target_only": True,
    "requirement_version_id": "VERSION_1",
    "local_applicability_only": True,
}


@pytest.fixture
def catalogue_case(reasoning_case):
    knowledge, data = reasoning_case
    knowledge.criteria["CRITERION_1"]["dieu_kien"] = deepcopy(CATALOGUE_CONDITIONS)
    return knowledge, data


def attest(knowledge, data):
    request = ReasoningRequest.model_validate(data)
    requirements = [
        ApplicableRequirement.model_validate(r) for r in data["payload"]["requirements"]
    ]
    context = Context.model_validate(request.model_dump(include=set(Context.model_fields)))
    return contract_content_verifications(
        context, request.payload.hop_dong_id, requirements, knowledge
    )


def run(knowledge, data, verifications, finding="SATISFIED"):
    batch = LLMObservationProvider(
        FakeClient([semantic(data, proposed_finding=finding)]),
        automatic_draft_review=True,
        verifications=verifications,
    ).analyze(ReasoningRequest.model_validate(data), knowledge)
    data = deepcopy(data)
    data["payload"]["observations"] = [item.model_dump() for item in batch.observations]
    return reason(ReasoningRequest.model_validate(data), knowledge)[0]


def test_catalogue_criteria_stay_unknown_without_an_attestation(catalogue_case):
    knowledge, data = catalogue_case
    result = run(knowledge, data, [])
    assert result.finding == "UNKNOWN"
    assert "case facts" in (result.uncertainty_reason or "")


@pytest.mark.parametrize("finding", ["SATISFIED", "VIOLATED"])
def test_attested_contract_content_criteria_can_conclude(catalogue_case, finding):
    knowledge, data = catalogue_case
    records = attest(knowledge, data)
    assert [r.tieu_chi_id for r in records] == ["CRITERION_1"]
    assert records[0].verification_reference == f"{POLICY}:{knowledge.sha256}"
    assert records[0].facts["evaluation_target"] == "CONTRACT_CONTENT"
    result = run(knowledge, data, records, finding)
    assert result.finding == finding
    assert result.review_status == "PENDING"  # a machine draft, still awaiting a person


def test_absence_is_never_attested(catalogue_case):
    knowledge, data = catalogue_case
    assert run(knowledge, data, attest(knowledge, data), "MISSING").finding == "UNKNOWN"


@pytest.mark.parametrize("blocker", ["scope", "exception", "optional", "performance", "version"])
def test_no_attestation_when_the_backend_has_not_checked_it(catalogue_case, blocker):
    knowledge, data = catalogue_case
    row = data["payload"]["requirements"][0]
    criterion = knowledge.criteria["CRITERION_1"]
    if blocker == "scope":
        row.update(scope_status="UNKNOWN", applicability_status="UNKNOWN")
    elif blocker == "exception":
        knowledge.tables["ngoai_le_ap_dung"] = [{"requirement_version_id": "VERSION_1"}]
    elif blocker == "optional":
        criterion["dieu_kien"]["optional_choice"] = True
    elif blocker == "performance":
        criterion["loai_kiem_tra"] = "PERFORMANCE_WITH_DOCUMENTS"
    elif blocker == "version":
        row.update(version_status="UNKNOWN", applicability_status="UNKNOWN")
    assert attest(knowledge, data) == []
