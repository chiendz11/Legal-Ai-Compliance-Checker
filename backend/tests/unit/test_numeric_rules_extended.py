"""Synthetic boundary/uncertainty tests for the remaining pinned numeric schemas."""

from copy import deepcopy

import pytest

from legal_checker.modules.compliance.numeric_rules import (
    NumericInputError,
    evaluate_numeric,
    numeric_kind,
)

SELLER_FACT = "ho_so_hop_dong.ben_ban_co_von_nuoc_ngoai"
EXTENDED_CASES = [
    (
        {
            "denominator": "sale_price",
            "deposit_lte_ratio": "0.05",
            "eligible_before_collection": True,
        },
        {
            "deposit": "50",
            "deposit_unit": "VND",
            "sale_price": "1000",
            "sale_price_unit": "VND",
            "eligible_before_collection": True,
        },
        "deposit",
        ("49.99", "50", "50.01"),
        (True, True, False),
    ),
    (
        {
            "denominator": "contract_price",
            "deposit_inclusion": "EXPERT_REVIEW_REQUIRED",
            "first_payment_lte_ratio": "0.3",
            "scope": "FUTURE_FORMED_KDBDS_2014",
        },
        {
            "numeric_scope": "FUTURE_FORMED_KDBDS_2014",
            "contract_price": "1000",
            "contract_price_unit": "VND",
            "first_payment_excluding_deposit": "250",
            "first_payment_excluding_deposit_unit": "VND",
            "deposit": "50",
            "deposit_unit": "VND",
            "deposit_inclusion_reviewed": True,
            "deposit_inclusion_review_reference": "memory://expert/deposit-review",
            "deposit_included_in_first_payment": True,
        },
        "first_payment_excluding_deposit",
        ("249.99", "250", "250.01"),
        (True, True, False),
    ),
    (
        {
            "denominator": "contract_price",
            "foreign_invested_seller_lte_ratio": "0.5",
            "prehandover_cumulative_lte_ratio": "0.7",
            "scope": "FUTURE_FORMED_KDBDS_2014",
            "seller_fact": SELLER_FACT,
            "seller_fact_unresolved": "UNKNOWN",
        },
        {
            "numeric_scope": "FUTURE_FORMED_KDBDS_2014",
            "contract_price": "1000",
            "contract_price_unit": "VND",
            "cumulative_payment": "700",
            "cumulative_payment_unit": "VND",
            "before_handover": True,
            SELLER_FACT: False,
        },
        "cumulative_payment",
        ("699.99", "700", "700.01"),
        (True, True, False),
    ),
    (
        {
            "before_certificate_cumulative_lte_ratio": "0.95",
            "denominator": "contract_price",
            "scope": "FUTURE_FORMED_KDBDS_2014",
        },
        {
            "numeric_scope": "FUTURE_FORMED_KDBDS_2014",
            "contract_price": "1000",
            "contract_price_unit": "VND",
            "cumulative_payment": "950",
            "cumulative_payment_unit": "VND",
            "before_certificate": True,
        },
        "cumulative_payment",
        ("949.99", "950", "950.01"),
        (True, True, False),
    ),
    (
        {
            "denominator": "apartment_value",
            "denominator_definition": "EXPERT_REVIEW_REQUIRED",
            "included_in_sale_payment": True,
            "maintenance_ratio": "0.02",
            "scope": "DEVELOPER_SALE_MULTI_OWNER_NHAO_2014",
        },
        {
            "numeric_scope": "DEVELOPER_SALE_MULTI_OWNER_NHAO_2014",
            "maintenance_amount": "20",
            "maintenance_amount_unit": "VND",
            "apartment_value": "1000",
            "apartment_value_unit": "VND",
            "denominator_definition_reviewed": True,
            "denominator_definition_review_reference": "memory://expert/base-review",
            "included_in_sale_payment": True,
        },
        "maintenance_amount",
        ("19.99", "20", "20.01"),
        (False, True, False),
    ),
    (
        {
            "scope": "APARTMENT_NEW_BUILD_NHAO_2014",
            "start": "COMPLETION_AND_ACCEPTANCE_INTO_USE",
            "warranty_min_months": "60",
        },
        {
            "numeric_scope": "APARTMENT_NEW_BUILD_NHAO_2014",
            "warranty_months": "60",
            "warranty_unit": "MONTH",
            "warranty_start": "COMPLETION_AND_ACCEPTANCE_INTO_USE",
        },
        "warranty_months",
        ("59", "60", "61"),
        (False, True, True),
    ),
]


@pytest.mark.parametrize("rule,facts,field,values,expected", EXTENDED_CASES)
def test_below_equal_above_for_each_extended_schema(rule, facts, field, values, expected):
    before = deepcopy((rule, facts))
    assert numeric_kind(rule) in rule
    for value, outcome in zip(values, expected, strict=True):
        assert evaluate_numeric(rule, {**facts, field: value}, facts_verified=True) is outcome
    assert (rule, facts) == before


@pytest.mark.parametrize("rule,facts,field,values,expected", EXTENDED_CASES)
def test_every_extended_fact_is_required_and_unknown_stays_unknown(
    rule, facts, field, values, expected
):
    with pytest.raises(NumericInputError, match="unverified"):
        evaluate_numeric(rule, facts, facts_verified=False)
    for key in facts:
        incomplete = {name: value for name, value in facts.items() if name != key}
        with pytest.raises(NumericInputError):
            evaluate_numeric(rule, incomplete, facts_verified=True)


@pytest.mark.parametrize("rule,facts,field,values,expected", EXTENDED_CASES)
@pytest.mark.parametrize("bad", [None, True, False, "NaN", "Infinity", "-1", [], "1e1000"])
def test_extended_numeric_values_are_finite_numbers(rule, facts, field, values, expected, bad):
    with pytest.raises(NumericInputError):
        evaluate_numeric(rule, {**facts, field: bad}, facts_verified=True)


@pytest.mark.parametrize(
    "index,field", [(0, "sale_price"), (1, "contract_price"), (4, "apartment_value")]
)
@pytest.mark.parametrize("bad", [None, "0", "-1", True, "NaN"])
def test_extended_denominators_are_positive(index, field, bad):
    rule, facts, *_ = EXTENDED_CASES[index]
    with pytest.raises(NumericInputError):
        evaluate_numeric(rule, {**facts, field: bad}, facts_verified=True)


@pytest.mark.parametrize(
    "index,field,bad",
    [
        (0, "eligible_before_collection", None),
        (0, "eligible_before_collection", "true"),
        (0, "sale_price_unit", "USD"),
        (1, "deposit_inclusion_reviewed", False),
        (1, "deposit_inclusion_review_reference", " "),
        (1, "deposit_inclusion_review_reference", True),
        (1, "deposit_included_in_first_payment", None),
        (1, "deposit_included_in_first_payment", "false"),
        (2, SELLER_FACT, None),
        (2, SELLER_FACT, "false"),
        (2, SELLER_FACT, 0),
        (2, "before_handover", False),
        (3, "before_certificate", False),
        (4, "denominator_definition_reviewed", False),
        (4, "denominator_definition_review_reference", ""),
        (4, "included_in_sale_payment", None),
        (4, "apartment_value_unit", []),
        (5, "warranty_start", "HANDOVER"),
        (5, "warranty_unit", "DAY"),
    ],
)
def test_unresolved_review_units_and_branches_are_rejected(index, field, bad):
    rule, facts, *_ = EXTENDED_CASES[index]
    with pytest.raises(NumericInputError):
        evaluate_numeric(rule, {**facts, field: bad}, facts_verified=True)


def test_deposit_eligibility_is_not_ignored_even_below_cap():
    rule, facts, *_ = EXTENDED_CASES[0]
    assert not evaluate_numeric(
        rule, {**facts, "deposit": "1", "eligible_before_collection": False}, facts_verified=True
    )


@pytest.mark.parametrize("value,expected", [("299.99", True), ("300", True), ("300.01", False)])
def test_expert_can_explicitly_exclude_deposit_but_numeric_code_does_not_decide(value, expected):
    rule, facts, *_ = EXTENDED_CASES[1]
    assert (
        evaluate_numeric(
            rule,
            {
                **facts,
                "first_payment_excluding_deposit": value,
                "deposit_included_in_first_payment": False,
            },
            facts_verified=True,
        )
        is expected
    )
    assert not evaluate_numeric(
        rule, {**facts, "first_payment_excluding_deposit": "300"}, facts_verified=True
    )


@pytest.mark.parametrize("amount,expected", [("499.99", True), ("500", True), ("500.01", False)])
def test_2014_foreign_seller_branch_boundary(amount, expected):
    rule, facts, *_ = EXTENDED_CASES[2]
    assert (
        evaluate_numeric(
            rule, {**facts, "cumulative_payment": amount, SELLER_FACT: True}, facts_verified=True
        )
        is expected
    )


def test_foreign_seller_fact_uses_exact_pinned_key_without_invented_default():
    rule, facts, *_ = EXTENDED_CASES[2]
    facts = {key: value for key, value in facts.items() if key != SELLER_FACT}
    facts["foreign_seller_art10_4"] = False
    with pytest.raises(NumericInputError, match=SELLER_FACT):
        evaluate_numeric(rule, facts, facts_verified=True)


def test_2014_maintenance_preserves_included_in_sale_payment_condition():
    rule, facts, *_ = EXTENDED_CASES[4]
    assert not evaluate_numeric(
        rule, {**facts, "included_in_sale_payment": False}, facts_verified=True
    )


@pytest.mark.parametrize(
    "index,changes",
    [
        (0, {"eligible_before_collection": False}),
        (0, {"denominator": "contract_price"}),
        (0, {"deposit_lte_ratio": True}),
        (0, {"deposit_lte_ratio": "5"}),
        (1, {"deposit_inclusion": "AUTO_INCLUDE"}),
        (1, {"scope": []}),
        (2, {"seller_fact": "foreign_seller_art10_4"}),
        (2, {"seller_fact_unresolved": "FALSE"}),
        (2, {"scope": "FUTURE_COMMERCIAL"}),
        (2, {"foreign_invested_seller_lte_ratio": "50"}),
        (4, {"denominator_definition": "IGNORE"}),
        (4, {"included_in_sale_payment": False}),
        (4, {"denominator": "contract_price"}),
        (5, {"start": "HANDOVER"}),
    ],
)
def test_no_numeric_rule_condition_is_silently_ignored(index, changes):
    rule, *_ = EXTENDED_CASES[index]
    with pytest.raises(NumericInputError):
        numeric_kind({**rule, **changes})


@pytest.mark.parametrize("rule,facts,field,values,expected", EXTENDED_CASES)
def test_extra_conditions_or_mismatched_scope_are_explicitly_unsupported(
    rule, facts, field, values, expected
):
    with pytest.raises(NumericInputError, match="Unsupported"):
        numeric_kind({**rule, "new_condition": True})
    if "scope" in rule:
        with pytest.raises(NumericInputError, match="numeric_scope"):
            evaluate_numeric(
                rule, {**facts, "numeric_scope": "WRONG_LEGAL_SCOPE"}, facts_verified=True
            )


def test_extended_thresholds_come_from_rule_instead_of_sample_values():
    rule, facts, *_ = EXTENDED_CASES[0]
    assert not evaluate_numeric(rule, {**facts, "deposit": "60"}, facts_verified=True)
    assert evaluate_numeric(
        {**rule, "deposit_lte_ratio": "0.07"}, {**facts, "deposit": "60"}, facts_verified=True
    )


@pytest.mark.parametrize("facts", [None, [], "not-a-mapping", True])
def test_invalid_fact_container_remains_numeric_uncertainty(facts):
    rule, *_ = EXTENDED_CASES[0]
    with pytest.raises(NumericInputError, match="mapping"):
        evaluate_numeric(rule, facts, facts_verified=True)
