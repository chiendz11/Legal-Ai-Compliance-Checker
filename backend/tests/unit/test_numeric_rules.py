"""Numeric schema boundary tests, using synthetic amounts, not expected seed outputs."""

from copy import deepcopy
from decimal import Decimal

import pytest
from legal_checker.modules.compliance.numeric_rules import (
    NumericInputError,
    evaluate_numeric,
    numeric_kind,
)

NUMERIC_CASES = [
    (
        {
            "denominator": "contract_price",
            "first_payment_including_deposit_lte_ratio": "0.3",
            "scope": "FUTURE_COMMERCIAL",
        },
        {
            "numeric_scope": "FUTURE_COMMERCIAL",
            "contract_price": "1000",
            "contract_price_unit": "VND",
            "first_payment_excluding_deposit": "250",
            "first_payment_excluding_deposit_unit": "VND",
            "deposit": "50",
            "deposit_unit": "VND",
        },
        "first_payment_excluding_deposit",
        ("249.99", "250", "250.01"),
        (True, True, False),
    ),
    (
        {
            "denominator": "contract_price",
            "prehandover_cumulative_lte_ratio": "0.7",
            "foreign_seller_art10_4_lte_ratio": "0.5",
            "scope": "FUTURE_COMMERCIAL",
        },
        {
            "numeric_scope": "FUTURE_COMMERCIAL",
            "contract_price": "1000",
            "contract_price_unit": "VND",
            "cumulative_payment": "700",
            "cumulative_payment_unit": "VND",
            "before_handover": True,
            "foreign_seller_art10_4": False,
        },
        "cumulative_payment",
        ("699.99", "700", "700.01"),
        (True, True, False),
    ),
    (
        {
            "denominator": "contract_price",
            "before_certificate_cumulative_lte_ratio": "0.95",
            "scope": "FUTURE_COMMERCIAL",
        },
        {
            "numeric_scope": "FUTURE_COMMERCIAL",
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
            "maintenance_ratio": "0.02",
            "scope": "DEVELOPER_SALE_MULTIPLE_OWNERS_NEW_RULES",
            "separate_from_sale_price": True,
        },
        {
            "numeric_scope": "DEVELOPER_SALE_MULTIPLE_OWNERS_NEW_RULES",
            "maintenance_amount": "20",
            "maintenance_amount_unit": "VND",
            "maintenance_base": "1000",
            "maintenance_base_unit": "VND",
            "maintenance_base_kind": "APARTMENT_OR_SOLD_AREA_VALUE",
            "separate_from_sale_price": True,
        },
        "maintenance_amount",
        ("19.99", "20", "20.01"),
        (False, True, False),
    ),
    (
        {
            "scope": "NEW_PROJECT",
            "start": "COMPLETION_AND_ACCEPTANCE_INTO_USE",
            "warranty_min_months": 60,
        },
        {
            "numeric_scope": "NEW_PROJECT",
            "warranty_months": "60",
            "warranty_unit": "MONTH",
            "warranty_start": "COMPLETION_AND_ACCEPTANCE_INTO_USE",
        },
        "warranty_months",
        ("59", "60", "61"),
        (False, True, True),
    ),
    (
        {
            "application_submission_max_days": 50,
            "exception": "BUYER_VOLUNTARILY_SELF_FILES",
            "not_certificate_issuance_deadline": True,
            "start": "HANDOVER",
        },
        {
            "submission_elapsed_days": "50",
            "submission_unit": "DAY",
            "submission_start": "HANDOVER",
            "submission_event": "APPLICATION_SUBMISSION",
            "buyer_voluntarily_self_files": False,
            "application_submitted": True,
        },
        "submission_elapsed_days",
        ("49", "50", "51"),
        (True, True, False),
    ),
]


@pytest.mark.parametrize("rule,facts,field,values,expected", NUMERIC_CASES)
def test_below_equal_above_for_every_supported_schema(rule, facts, field, values, expected):
    original = deepcopy((rule, facts))
    for value, outcome in zip(values, expected, strict=True):
        assert evaluate_numeric(rule, {**facts, field: value}, facts_verified=True) is outcome
    assert (rule, facts) == original


@pytest.mark.parametrize("rule,facts,field,values,expected", NUMERIC_CASES)
def test_every_required_fact_and_verification_is_required(rule, facts, field, values, expected):
    with pytest.raises(NumericInputError, match="unverified"):
        evaluate_numeric(rule, facts, facts_verified=False)
    for required in facts:
        incomplete = {key: value for key, value in facts.items() if key != required}
        with pytest.raises(NumericInputError):
            evaluate_numeric(rule, incomplete, facts_verified=True)


@pytest.mark.parametrize(
    "value", [None, True, False, "NaN", "Infinity", "-Infinity", "-1", [], "bad", "1e1000"]
)
def test_no_null_bool_nonfinite_negative_or_unbounded_numbers(value):
    rule, facts, field, _, _ = NUMERIC_CASES[0]
    with pytest.raises(NumericInputError):
        evaluate_numeric(rule, {**facts, field: value}, facts_verified=True)


@pytest.mark.parametrize("denominator", [None, "0", "-1", True, "NaN"])
@pytest.mark.parametrize("index,field", [(0, "contract_price"), (3, "maintenance_base")])
def test_denominator_must_be_positive(index, field, denominator):
    rule, facts, *_ = NUMERIC_CASES[index]
    with pytest.raises(NumericInputError):
        evaluate_numeric(rule, {**facts, field: denominator}, facts_verified=True)


@pytest.mark.parametrize(
    "index,field,value",
    [
        (0, "deposit_unit", "USD"),
        (0, "contract_price_unit", "PERCENT"),
        (1, "before_handover", False),
        (1, "foreign_seller_art10_4", "false"),
        (2, "before_certificate", False),
        (3, "maintenance_base_kind", "UNRESOLVED"),
        (4, "warranty_unit", "YEAR"),
        (4, "warranty_start", "PURCHASE"),
        (5, "submission_event", "CERTIFICATE_ISSUANCE"),
        (5, "buyer_voluntarily_self_files", True),
        (5, "application_submitted", False),
    ],
)
def test_wrong_units_or_unresolved_branch_is_unknown(index, field, value):
    rule, facts, *_ = NUMERIC_CASES[index]
    with pytest.raises(NumericInputError):
        evaluate_numeric(rule, {**facts, field: value}, facts_verified=True)


@pytest.mark.parametrize("amount,expected", [("499.99", True), ("500", True), ("500.01", False)])
def test_foreign_seller_branch_has_its_own_boundary(amount, expected):
    rule, facts, *_ = NUMERIC_CASES[1]
    assert (
        evaluate_numeric(
            rule,
            {**facts, "foreign_seller_art10_4": True, "cumulative_payment": amount},
            facts_verified=True,
        )
        is expected
    )


def test_threshold_is_taken_from_pinned_rule_and_not_hardcoded():
    rule, facts, *_ = NUMERIC_CASES[0]
    assert evaluate_numeric(
        {**rule, "first_payment_including_deposit_lte_ratio": "0.4"},
        {**facts, "first_payment_excluding_deposit": "350"},
        facts_verified=True,
    )


def test_comparison_does_not_round_at_decimal_context_boundary():
    rule, facts, *_ = NUMERIC_CASES[0]
    value = Decimal("250.0000000000000000000000000000001")
    assert not evaluate_numeric(
        rule, {**facts, "first_payment_excluding_deposit": value}, facts_verified=True
    )


@pytest.mark.parametrize(
    "change",
    [
        {"extra": True},
        {"denominator": "unknown"},
        {"first_payment_including_deposit_lte_ratio": True},
        {"first_payment_including_deposit_lte_ratio": "NaN"},
        {"first_payment_including_deposit_lte_ratio": "30"},
        {"scope": "OTHER_LAW"},
    ],
)
def test_unsupported_schema_condition_or_threshold_is_explicit(change):
    with pytest.raises(NumericInputError):
        numeric_kind({**NUMERIC_CASES[0][0], **change})


def test_expert_review_variant_is_not_treated_as_simple_ratio():
    rule = {
        "denominator": "contract_price",
        "deposit_inclusion": "EXPERT_REVIEW_REQUIRED",
        "first_payment_lte_ratio": 0.3,
        "scope": "FUTURE_FORMED_KDBDS_2014",
    }
    assert numeric_kind(rule) == "first_payment_lte_ratio"
    facts = {
        "numeric_scope": "FUTURE_FORMED_KDBDS_2014",
        "contract_price": "1000",
        "contract_price_unit": "VND",
        "first_payment_excluding_deposit": "250",
        "first_payment_excluding_deposit_unit": "VND",
        "deposit": "50",
        "deposit_unit": "VND",
    }
    with pytest.raises(NumericInputError, match="deposit_inclusion_reviewed"):
        evaluate_numeric(rule, facts, facts_verified=True)
