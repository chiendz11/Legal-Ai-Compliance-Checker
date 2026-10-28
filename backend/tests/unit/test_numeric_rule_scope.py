"""Shared group numeric objects cannot decide an unrelated criterion proposition."""

from copy import deepcopy

import pytest
from test_criterion_reasoner import assert_unknown, only_result
from test_criterion_reasoner import reasoning_case as reasoning_case
from test_numeric_rules_extended import EXTENDED_CASES

from legal_checker.modules.compliance.numeric_rules import (
    NumericInputError,
    evaluate_numeric,
    evaluate_numeric_for_criterion,
)


def scope(target):
    """Independent review binding; these flags must never come from model output."""
    return {
        "numeric_target": target,
        "numeric_target_reviewed": True,
        "numeric_target_review_reference": "memory://review/current-proposition",
    }


def test_deposit_cap_does_not_claim_a_separate_eligibility_breach():
    rule, facts, *_ = EXTENDED_CASES[0]
    facts = {**facts, "eligible_before_collection": False, **scope("DEPOSIT_CAP")}
    assert not evaluate_numeric(rule, facts, facts_verified=True)
    assert evaluate_numeric_for_criterion(rule, facts, facts_verified=True)


def test_deposit_eligibility_does_not_claim_a_separate_amount_breach():
    rule, facts, *_ = EXTENDED_CASES[0]
    facts = {**facts, "deposit": "60", **scope("DEPOSIT_ELIGIBILITY")}
    assert not evaluate_numeric(rule, facts, facts_verified=True)
    assert evaluate_numeric_for_criterion(rule, facts, facts_verified=True)


def test_deposit_price_statement_does_not_require_other_criteria_facts():
    rule, *_ = EXTENDED_CASES[0]
    facts = {"sale_price_stated_in_agreement": True, **scope("DEPOSIT_PRICE")}
    assert evaluate_numeric_for_criterion(rule, facts, facts_verified=True)
    facts["sale_price_stated_in_agreement"] = False
    assert not evaluate_numeric_for_criterion(rule, facts, facts_verified=True)


def test_maintenance_ratio_does_not_decide_payment_inclusion():
    rule, facts, *_ = EXTENDED_CASES[4]
    facts = {**facts, "included_in_sale_payment": False, **scope("MAINTENANCE_RATIO")}
    assert not evaluate_numeric(rule, facts, facts_verified=True)
    assert evaluate_numeric_for_criterion(rule, facts, facts_verified=True)


def test_maintenance_inclusion_does_not_decide_rate_or_denominator():
    rule, facts, *_ = EXTENDED_CASES[4]
    scoped = {
        "numeric_scope": facts["numeric_scope"],
        "included_in_sale_payment": True,
        **scope("MAINTENANCE_PAYMENT_INCLUSION"),
    }
    assert evaluate_numeric_for_criterion(rule, scoped, facts_verified=True)


@pytest.mark.parametrize("index", [0, 4])
def test_whole_rule_is_evaluated_only_when_explicitly_in_current_proposition(index):
    rule, facts, *_ = EXTENDED_CASES[index]
    facts = {**facts, **scope("ALL_CONSTRAINTS")}
    assert evaluate_numeric_for_criterion(rule, facts, facts_verified=True) is evaluate_numeric(
        rule, facts, facts_verified=True
    )


@pytest.mark.parametrize("index", [0, 4])
@pytest.mark.parametrize(
    "change",
    [
        {"numeric_target": None},
        {"numeric_target": "UNREVIEWED_PROPOSITION"},
        {"numeric_target_reviewed": False},
        {"numeric_target_reviewed": "true"},
        {"numeric_target_review_reference": " "},
    ],
)
def test_ambiguous_numeric_target_cannot_be_inferred(index, change):
    rule, facts, *_ = EXTENDED_CASES[index]
    with pytest.raises(NumericInputError):
        evaluate_numeric_for_criterion(
            rule, {**facts, **scope("ALL_CONSTRAINTS"), **change}, facts_verified=True
        )


def test_engine_requires_backend_numeric_target_for_shared_schema(reasoning_case):
    knowledge, data = reasoning_case
    rule, facts, *_ = EXTENDED_CASES[0]
    knowledge.decision("CRITERION_1", "SATISFIED")["dieu_kien_json"]["numeric_rule"] = rule
    observation = data["payload"]["observations"][0]
    observation.update(facts=facts, facts_verified=True)
    assert_unknown(only_result(knowledge, data), "numeric_target")
    observation["facts"] = {**facts, "eligible_before_collection": False, **scope("DEPOSIT_CAP")}
    before = deepcopy((data, vars(knowledge)))
    result = only_result(knowledge, data)
    assert result.finding == "SATISFIED"
    assert (data, vars(knowledge)) == before


@pytest.mark.parametrize("facts,verified", [({}, True), ({"present": True}, False)])
def test_required_case_facts_are_not_satisfied_by_empty_or_unverified_data(
    reasoning_case, facts, verified
):
    knowledge, data = reasoning_case
    knowledge.criteria["CRITERION_1"]["dieu_kien"] = {"case_facts_required": True}
    data["payload"]["observations"][0].update(facts=facts, facts_verified=verified)
    assert_unknown(only_result(knowledge, data), "case facts")


def test_malformed_local_policy_cannot_hide_criterion_by_optional_exclusion(reasoning_case):
    knowledge, data = reasoning_case
    knowledge.criteria["CRITERION_1"]["dieu_kien"] = {
        "optional_choice": True,
        "not_selected_policy": "NOT_APPLICABLE",
        "unrecognized_exception_policy": True,
    }
    data["payload"]["observations"][0].update(
        facts={"optional_choice_confirmed": False}, facts_verified=True
    )
    result = only_result(knowledge, data)
    assert_unknown(result, "unsupported criterion")
    assert not result.excluded


def test_unresolved_exception_reference_stays_unknown(reasoning_case):
    knowledge, data = reasoning_case
    knowledge.criteria["CRITERION_1"]["dieu_kien"] = {"exception_ids": ["MISSING_EXCEPTION"]}
    assert_unknown(only_result(knowledge, data), "exception")


def test_exception_owned_by_another_version_cannot_be_used(reasoning_case):
    knowledge, data = reasoning_case
    knowledge.criteria["CRITERION_1"]["dieu_kien"] = {"exception_ids": ["FOREIGN_EXCEPTION"]}
    knowledge.tables["ngoai_le_ap_dung"] = [
        {"ngoai_le_id": "FOREIGN_EXCEPTION", "requirement_version_id": "OTHER_VERSION"}
    ]
    assert_unknown(only_result(knowledge, data), "exception")
