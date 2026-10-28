"""Regression tests for unresolved C05 and exclusions that would hide knowledge gaps."""

from copy import deepcopy

import pytest
from legal_checker.modules.compliance.criterion_reasoner import reason
from legal_checker.modules.compliance.llm_observations import LLMObservationProvider
from legal_checker.modules.compliance.run_c07 import run_assessment
from legal_checker.shared.contracts.common import Context
from legal_checker.shared.contracts.reasoning import ReasoningRequest
from test_c07_extended_types import optional_case
from test_criterion_reasoner import assert_unknown, only_result
from test_criterion_reasoner import reasoning_case as reasoning_case
from test_llm_observations import FakeClient
from test_numeric_rules_extended import EXTENDED_CASES


def test_candidate_version_does_not_become_a_resolved_checklist(reasoning_case):
    knowledge, data = reasoning_case
    data["payload"]["requirements"][0].update(
        version_status="UNKNOWN", applicability_status="UNKNOWN"
    )
    request = ReasoningRequest.model_validate(data)
    before = request.model_dump()
    client = FakeClient([])
    provider = LLMObservationProvider(client)

    assert reason(request, knowledge) == []
    batch = provider.analyze(request, knowledge)
    assert batch.observations == batch.analyses == []
    run = run_assessment(request, knowledge, provider=provider)
    assert run.results == []
    assert run.request.payload.requirements == request.payload.requirements
    assert request.model_dump() == before
    assert client.calls == []


def test_new_c07_snapshot_identifies_the_exact_pinned_knowledge(reasoning_case):
    knowledge, data = reasoning_case
    before = deepcopy(knowledge.criteria)
    result = only_result(knowledge, data)
    assert result.tieu_chi_snapshot_json["knowledge_snapshot_sha256"] == knowledge.sha256
    assert knowledge.criteria == before


def test_c07_snapshot_preserves_full_context_and_contract_without_mutation(reasoning_case):
    knowledge, data = reasoning_case
    before = deepcopy(data)
    request = ReasoningRequest.model_validate(data)
    result = reason(request, knowledge)[0]
    assert result.tieu_chi_snapshot_json["context"] == request.model_dump(
        mode="json", include=set(Context.model_fields)
    )
    assert result.tieu_chi_snapshot_json["hop_dong_id"] == request.payload.hop_dong_id
    result.tieu_chi_snapshot_json["context"]["run_id"] = "MUTATED_OUTPUT"
    assert request.run_id == before["run_id"]
    assert data == before


@pytest.mark.parametrize("key", ["quy_tac_id", "rule_version"])
@pytest.mark.parametrize("value", [None, "", "   ", 1])
def test_rule_identity_and_version_must_be_present(reasoning_case, key, value):
    knowledge, data = reasoning_case
    knowledge.decision("CRITERION_1", "SATISFIED")[key] = value
    result = only_result(knowledge, data)
    assert_unknown(result, key)


@pytest.mark.parametrize("status", ["DISABLED", "INACTIVE", "RETIRED", "DELETED"])
def test_disabled_catalog_row_cannot_be_enabled_by_its_json(reasoning_case, status):
    knowledge, data = reasoning_case
    rule = knowledge.decision("CRITERION_1", "SATISFIED")
    rule["trang_thai"] = status
    assert rule["dieu_kien_json"]["enabled"] is True
    assert_unknown(only_result(knowledge, data), "disabled")


@pytest.mark.parametrize("exclusion", ["local", "optional"])
@pytest.mark.parametrize(
    "gap",
    [
        "missing-rule",
        "ambiguous-rule",
        "disabled-rule",
        "unsupported-type",
        "unsupported-numeric",
        "unsupported-conditions",
        "unsupported-gate",
        "nonboolean-gate",
        "contradictory-receipt-policy",
        "unsupported-numeric-target",
        "invalid-numeric-fact",
        "unverified-fact",
        "null-fact",
        "required-facts",
    ],
)
def test_exclusion_cannot_conceal_an_unresolved_policy_or_fact(reasoning_case, exclusion, gap):
    knowledge, data = reasoning_case
    observation = data["payload"]["observations"][0]
    if exclusion == "optional":
        optional_case(knowledge, data, False)
    else:
        observation.update(local_applicability="NO_MATCH", exclusion_reason="Reviewed branch")
    rule = knowledge.decision("CRITERION_1", "SATISFIED")
    if gap == "missing-rule":
        knowledge.tables["quy_tac_quyet_dinh"].remove(rule)
    elif gap == "ambiguous-rule":
        knowledge.tables["quy_tac_quyet_dinh"].append(deepcopy(rule))
    elif gap == "disabled-rule":
        rule["dieu_kien_json"]["enabled"] = False
    elif gap == "unsupported-type":
        knowledge.criteria["CRITERION_1"]["loai_kiem_tra"] = "UNSUPPORTED"
    elif gap == "unsupported-numeric":
        rule["dieu_kien_json"]["numeric_rule"] = {"unsupported_amount": 100}
    elif gap == "unsupported-conditions":
        rule["dieu_kien_json"]["new_condition"] = True
    elif gap == "unsupported-gate":
        rule["dieu_kien_json"]["gate"]["future_unsupported_gate"] = True
    elif gap == "nonboolean-gate":
        rule["dieu_kien_json"]["gate"]["optional_choice_confirmed"] = "false"
    elif gap == "contradictory-receipt-policy":
        rule["dieu_kien_json"].update(
            performance_requires_receipt_evidence=True, conclusion_scope_required=False
        )
    elif gap in {"unsupported-numeric-target", "invalid-numeric-fact"}:
        numeric_rule, facts, *_ = deepcopy(EXTENDED_CASES[0])
        rule["dieu_kien_json"]["numeric_rule"] = numeric_rule
        observation.setdefault("facts", {}).update(
            **facts,
            numeric_target="DEPOSIT_CAP",
            numeric_target_reviewed=True,
            numeric_target_review_reference="memory://backend/numeric-target",
        )
        observation["facts_verified"] = True
        if gap == "unsupported-numeric-target":
            observation["facts"]["numeric_target"] = "UNSUPPORTED_TARGET"
        else:
            observation["facts"]["deposit"] = "garbage"
    elif gap == "unverified-fact":
        observation["facts"] = {"scope": "candidate"}
        observation["facts_verified"] = False
    elif gap == "null-fact":
        observation.setdefault("facts", {})["scope"] = None
        observation["facts_verified"] = True
    elif gap == "required-facts":
        knowledge.criteria["CRITERION_1"].setdefault("dieu_kien", {})["case_facts_required"] = True
        observation["facts"] = {}
        observation["facts_verified"] = False

    result = only_result(knowledge, data)
    assert_unknown(result)
    assert not result.excluded
    assert result.exclusion_reason is None
