"""Criterion-specific proof policies; backend review facts never infer real performance."""

import json
from copy import deepcopy

import pytest
from test_c07_findings import register_external
from test_criterion_reasoner import assert_unknown, only_result
from test_criterion_reasoner import reasoning_case as reasoning_case


def configure(knowledge, data, criterion_type, finding="SATISFIED"):
    """Create a reviewed synthetic proposal scoped to the tested proof category."""
    knowledge.criteria["CRITERION_1"]["loai_kiem_tra"] = criterion_type
    observation = data["payload"]["observations"][0]
    observation["proposed_finding"] = finding
    if criterion_type == "PERFORMANCE_OR_CONDITIONAL":
        observation.update(
            facts={"evaluation_target": "PERFORMANCE", "condition_triggered": True},
            facts_verified=True,
        )
        register_external(data)
    elif criterion_type == "DOI_CHIEU_CO_DIEU_KIEN":
        observation.update(
            facts={"evaluation_target": "CONTRACT_CONTENT", "condition_triggered": True},
            facts_verified=True,
        )
    elif criterion_type == "CONTRACT_CLAUSE_AND_PERFORMANCE":
        observation.update(facts={"evaluation_target": "CONTRACT_CONTENT"}, facts_verified=True)
        for result in ("SATISFIED", "VIOLATED", "UNKNOWN", "MISSING"):
            knowledge.decision("CRITERION_1", result)["dieu_kien_json"].update(
                conclusion_scope_required=True, performance_requires_receipt_evidence=True
            )
    elif criterion_type == "PROHIBITED_CLAUSE" and finding == "SATISFIED":
        observation["gates"].update(coverage_complete=True, absence_verified=True)
    return observation


@pytest.mark.parametrize(
    "criterion_type",
    [
        "PERFORMANCE_OR_CONDITIONAL",
        "DOI_CHIEU_CO_DIEU_KIEN",
        "PROHIBITED_CLAUSE",
        "CONTRACT_CLAUSE_AND_PERFORMANCE",
    ],
)
@pytest.mark.parametrize("finding", ["SATISFIED", "VIOLATED"])
def test_reviewed_type_specific_proposals_have_positive_paths(
    reasoning_case, criterion_type, finding
):
    knowledge, data = reasoning_case
    configure(knowledge, data, criterion_type, finding)
    before = deepcopy((data, vars(knowledge)))
    result = only_result(knowledge, data)
    assert result.finding == finding
    assert result.review_status == "PENDING"
    assert result.pham_vi_ket_luan == "CURRENT_CRITERION"
    assert (data, vars(knowledge)) == before
    if criterion_type != "PROHIBITED_CLAUSE":
        assert "Conclusion target:" in result.giai_thich


@pytest.mark.parametrize(
    "criterion_type",
    [
        "PERFORMANCE_OR_CONDITIONAL",
        "DOI_CHIEU_CO_DIEU_KIEN",
        "CONTRACT_CLAUSE_AND_PERFORMANCE",
    ],
)
@pytest.mark.parametrize("target", [None, True, "ENTIRE_CONTRACT", "UNKNOWN"])
def test_scoped_types_require_explicit_verified_target(reasoning_case, criterion_type, target):
    knowledge, data = reasoning_case
    observation = configure(knowledge, data, criterion_type)
    if target is None:
        observation["facts"].pop("evaluation_target")
    else:
        observation["facts"]["evaluation_target"] = target
    assert_unknown(only_result(knowledge, data), "evaluation_target")


@pytest.mark.parametrize("criterion_type", ["PERFORMANCE_OR_CONDITIONAL", "DOI_CHIEU_CO_DIEU_KIEN"])
@pytest.mark.parametrize("trigger", [None, False, "true", "false", "1"])
def test_conditional_criterion_does_not_assume_trigger(reasoning_case, criterion_type, trigger):
    knowledge, data = reasoning_case
    observation = configure(knowledge, data, criterion_type)
    if trigger is None:
        observation["facts"].pop("condition_triggered")
    else:
        observation["facts"]["condition_triggered"] = trigger
    result = only_result(knowledge, data)
    assert_unknown(result, "condition_triggered")
    assert not result.excluded


@pytest.mark.parametrize(
    "criterion_type",
    [
        "PERFORMANCE_OR_CONDITIONAL",
        "DOI_CHIEU_CO_DIEU_KIEN",
        "CONTRACT_CLAUSE_AND_PERFORMANCE",
    ],
)
def test_scoped_facts_need_backend_verification(reasoning_case, criterion_type):
    knowledge, data = reasoning_case
    configure(knowledge, data, criterion_type)["facts_verified"] = False
    assert_unknown(only_result(knowledge, data), "verified", "evaluation_target")


def test_conditional_contract_promise_cannot_prove_performance_satisfied(reasoning_case):
    knowledge, data = reasoning_case
    observation = configure(knowledge, data, "PERFORMANCE_OR_CONDITIONAL")
    observation["facts"]["evaluation_target"] = "CONTRACT_CONTENT"
    observation["external_evidence"] = []
    assert_unknown(only_result(knowledge, data), "promise")


def test_conditional_contrary_clause_can_prove_only_contract_violation(reasoning_case):
    knowledge, data = reasoning_case
    observation = configure(knowledge, data, "PERFORMANCE_OR_CONDITIONAL", "VIOLATED")
    observation["facts"]["evaluation_target"] = "CONTRACT_CONTENT"
    observation["external_evidence"] = []
    result = only_result(knowledge, data)
    assert result.finding == "VIOLATED"
    assert "CONTRACT_CONTENT" in result.giai_thich


@pytest.mark.parametrize(
    "criterion_type",
    [
        "PERFORMANCE_OR_CONDITIONAL",
        "DOI_CHIEU_CO_DIEU_KIEN",
        "CONTRACT_CLAUSE_AND_PERFORMANCE",
    ],
)
def test_actual_performance_always_needs_registered_external_proof(reasoning_case, criterion_type):
    knowledge, data = reasoning_case
    observation = configure(knowledge, data, criterion_type)
    observation["facts"]["evaluation_target"] = "PERFORMANCE"
    observation["external_evidence"] = []
    assert_unknown(only_result(knowledge, data), "external evidence")


@pytest.mark.parametrize(
    "criterion_type", ["DOI_CHIEU_CO_DIEU_KIEN", "CONTRACT_CLAUSE_AND_PERFORMANCE"]
)
def test_registered_receipt_supports_performance_without_fake_contract_quote(
    reasoning_case, criterion_type
):
    knowledge, data = reasoning_case
    observation = configure(knowledge, data, criterion_type)
    observation["facts"]["evaluation_target"] = "PERFORMANCE"
    observation["evidence"] = []
    data["payload"]["retrieval"] = []
    register_external(data)
    result = only_result(knowledge, data)
    assert result.finding == "SATISFIED" and not result.evidence
    assert "PERFORMANCE" in result.giai_thich


def test_hybrid_contract_conclusion_does_not_claim_payment_was_performed(reasoning_case):
    knowledge, data = reasoning_case
    configure(knowledge, data, "CONTRACT_CLAUSE_AND_PERFORMANCE")
    result = only_result(knowledge, data)
    assert result.finding == "SATISFIED"
    assert "CONTRACT_CONTENT" in result.giai_thich
    assert not result.external_evidence


@pytest.mark.parametrize(
    "flag", ["conclusion_scope_required", "performance_requires_receipt_evidence"]
)
@pytest.mark.parametrize("value", ["true", 1, None, []])
def test_hybrid_policy_flags_are_strict_booleans(reasoning_case, flag, value):
    knowledge, data = reasoning_case
    configure(knowledge, data, "CONTRACT_CLAUSE_AND_PERFORMANCE")
    knowledge.decision("CRITERION_1", "SATISFIED")["dieu_kien_json"][flag] = value
    assert_unknown(only_result(knowledge, data), "condition")


@pytest.mark.parametrize("gate", ["coverage_complete", "absence_verified"])
def test_prohibited_absence_needs_full_document_coverage(reasoning_case, gate):
    knowledge, data = reasoning_case
    configure(knowledge, data, "PROHIBITED_CLAUSE")["gates"][gate] = False
    assert_unknown(only_result(knowledge, data), gate)


@pytest.mark.parametrize("flag", ["all_pages_readable", "all_related_documents_received"])
def test_prohibited_absence_cannot_skip_ocr_or_annexes(reasoning_case, flag):
    knowledge, data = reasoning_case
    configure(knowledge, data, "PROHIBITED_CLAUSE")[flag] = False
    assert_unknown(only_result(knowledge, data), flag)


def test_prohibited_absence_can_use_registered_review_manifest_not_fake_quote(reasoning_case):
    knowledge, data = reasoning_case
    observation = configure(knowledge, data, "PROHIBITED_CLAUSE")
    observation["evidence"] = []
    data["payload"]["retrieval"] = []
    register_external(data)
    data["payload"]["external_evidence_registry"][0]["object_uri"] = "memory://review-manifest"
    observation["external_evidence"][0]["object_uri"] = "memory://review-manifest"
    result = only_result(knowledge, data)
    assert result.finding == "SATISFIED" and not result.evidence
    assert result.external_evidence[0].object_uri == "memory://review-manifest"


def test_prohibited_violation_needs_actual_contract_clause(reasoning_case):
    knowledge, data = reasoning_case
    configure(knowledge, data, "PROHIBITED_CLAUSE", "VIOLATED")["evidence"] = []
    register_external(data)
    assert_unknown(only_result(knowledge, data), "actual contract clause")


@pytest.mark.parametrize(
    "criterion_type",
    [
        "PERFORMANCE_OR_CONDITIONAL",
        "DOI_CHIEU_CO_DIEU_KIEN",
        "PROHIBITED_CLAUSE",
        "CONTRACT_CLAUSE_AND_PERFORMANCE",
    ],
)
def test_extended_types_never_invent_missing_contract_content(reasoning_case, criterion_type):
    knowledge, data = reasoning_case
    configure(knowledge, data, criterion_type, "MISSING")
    data["payload"]["observations"][0]["gates"].update(
        coverage_complete=True, absence_verified=True
    )
    assert_unknown(only_result(knowledge, data), "mandatory contract content")


def optional_case(knowledge, data, choice):
    """Use a pinned optional-selection policy with independent reviewed choice fact."""
    knowledge.criteria["CRITERION_1"]["dieu_kien"] = {
        "optional_choice": True,
        "not_selected_policy": "NOT_APPLICABLE",
        "scope_missing_policy": "UNKNOWN",
        "criterion_target_only": True,
        "requirement_version_id": "VERSION_1",
    }
    knowledge.decision("CRITERION_1", "SATISFIED")["dieu_kien_json"]["gate"][
        "optional_choice_confirmed"
    ] = True
    observation = data["payload"]["observations"][0]
    observation.update(facts={"optional_choice_confirmed": choice}, facts_verified=True)
    return observation


@pytest.mark.parametrize("json_text", [False, True])
def test_verified_selected_optional_mechanism_is_evaluated(reasoning_case, json_text):
    knowledge, data = reasoning_case
    optional_case(knowledge, data, True)
    if json_text:
        knowledge.criteria["CRITERION_1"]["dieu_kien"] = json.dumps(
            knowledge.criteria["CRITERION_1"]["dieu_kien"]
        )
    assert only_result(knowledge, data).finding == "SATISFIED"


def test_verified_not_selected_optional_mechanism_is_excluded_by_pinned_policy(reasoning_case):
    knowledge, data = reasoning_case
    optional_case(knowledge, data, False)
    result = only_result(knowledge, data)
    assert_unknown(result)
    assert result.excluded
    assert "not selected" in result.exclusion_reason


@pytest.mark.parametrize("choice", [None, "true", "false", "1"])
def test_optional_choice_is_not_assumed_from_unresolved_values(reasoning_case, choice):
    knowledge, data = reasoning_case
    optional_case(knowledge, data, choice)
    result = only_result(knowledge, data)
    assert_unknown(result, "optional")
    assert not result.excluded


def test_unverified_optional_nonselection_cannot_hide_criterion(reasoning_case):
    knowledge, data = reasoning_case
    optional_case(knowledge, data, False)["facts_verified"] = False
    assert not only_result(knowledge, data).excluded


@pytest.mark.parametrize("policy", [None, "UNKNOWN", "OTHER_POLICY", {}])
def test_optional_nonselection_requires_exact_pinned_exclusion_policy(reasoning_case, policy):
    knowledge, data = reasoning_case
    optional_case(knowledge, data, False)
    knowledge.criteria["CRITERION_1"]["dieu_kien"]["not_selected_policy"] = policy
    result = only_result(knowledge, data)
    assert_unknown(result)
    assert not result.excluded


@pytest.mark.parametrize(
    "condition",
    [
        None,
        "[]",
        '{"optional_choice":true,"optional_choice":false}',
        {"optional_choice": "true"},
        {"scope_missing_policy": "SATISFIED"},
        {"criterion_target_only": False},
        {"exception_ids": "not-a-list"},
        {"requirement_version_id": "FOREIGN_VERSION"},
        {"local_applicability_only": False},
        {"unknown_condition": True},
    ],
)
def test_malformed_or_unsupported_criterion_conditions_are_not_ignored(reasoning_case, condition):
    knowledge, data = reasoning_case
    knowledge.criteria["CRITERION_1"]["dieu_kien"] = condition
    assert_unknown(only_result(knowledge, data), "criterion")


def test_future_unknown_criterion_type_stays_explicitly_unsupported(reasoning_case):
    knowledge, data = reasoning_case
    knowledge.criteria["CRITERION_1"]["loai_kiem_tra"] = "FUTURE_TYPE_NOT_IMPLEMENTED"
    assert_unknown(only_result(knowledge, data), "unsupported criterion type")


@pytest.mark.parametrize("criterion_type", ["CONTRACT_CONTENT", "NOI_DUNG_BAT_BUOC"])
@pytest.mark.parametrize("finding", ["SATISFIED", "VIOLATED"])
def test_external_receipt_cannot_replace_contract_text(reasoning_case, criterion_type, finding):
    knowledge, data = reasoning_case
    knowledge.criteria["CRITERION_1"]["loai_kiem_tra"] = criterion_type
    observation = data["payload"]["observations"][0]
    observation.update(proposed_finding=finding, evidence=[])
    data["payload"]["retrieval"] = []
    register_external(data)
    assert_unknown(only_result(knowledge, data), "contract evidence")
