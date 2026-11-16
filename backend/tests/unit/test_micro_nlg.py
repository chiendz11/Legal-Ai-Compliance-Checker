"""Numeric presentation must preserve uncertainty, units, provenance and stored findings."""

from copy import deepcopy
from decimal import Decimal
from types import SimpleNamespace

import pytest
from legal_checker.modules.compliance.micro_nlg import (
    _extract_dict_string,
    numeric_explanation,
    synthesize_criterion_explanation,
)


@pytest.mark.parametrize("finding", ["UNKNOWN", "MISSING", "UNSUPPORTED"])
@pytest.mark.parametrize(
    "rule,facts",
    [
        ({"warranty_min_months": 60}, {}),
        ({"maintenance_ratio": "0.025"}, {"maintenance_amount": "1250000"}),
        ({"deposit_lte_ratio": "0.04"}, {"deposit": "25000000"}),
    ],
)
def test_nondecisive_numeric_findings_never_become_compliance(finding, rule, facts):
    criterion = SimpleNamespace(
        finding=finding,
        giai_thich=f"Backend đối chiếu bằng Decimal. Rule={rule!r}; dữ kiện={facts!r}",
        uncertainty_reason="Thiếu dữ kiện",
        model_version="BACKEND_NUMERIC_V1",
        prompt_version="TEST",
    )
    before = deepcopy(vars(criterion))
    text, traces = synthesize_criterion_explanation(criterion)
    assert "đáp ứng" not in text
    assert "36" not in text
    assert "Decimal" not in text
    assert any(criterion.giai_thich in item for item in traces)
    assert vars(criterion) == before


@pytest.mark.parametrize("value", [None, "", True, "NaN", "Infinity", "-1", "1e999"])
def test_missing_or_invalid_numbers_are_not_replaced_with_defaults(value):
    text = numeric_explanation(
        {"warranty_min_months": "72"}, {"warranty_months": value}, "SATISFIED"
    )
    assert "36 tháng" not in text and "60 tháng" not in text
    assert "Chưa đủ dữ liệu cấu trúc" in text


@pytest.mark.parametrize("finding", ["SATISFIED", "VIOLATED"])
def test_absent_threshold_is_not_replaced_with_a_legal_constant(finding):
    text = numeric_explanation({}, {"warranty_months": "36"}, finding)
    assert "60" not in text
    assert "5%" not in text
    assert "2%" not in text


def test_known_warranty_preserves_actual_rule_threshold_and_finding():
    text = numeric_explanation(
        {"warranty_min_months": "72"}, {"warranty_months": Decimal("48")}, "VIOLATED"
    )
    assert "48 tháng" in text and "72 tháng" in text
    assert "không đáp ứng" in text
    inconsistent = numeric_explanation(
        {"warranty_min_months": "72"}, {"warranty_months": "48"}, "SATISFIED"
    )
    assert "không nhất quán" in inconsistent


@pytest.mark.parametrize(
    "rule,facts,amount,percent",
    [
        ({"maintenance_ratio": "0.025"}, {"maintenance_amount": "1250000"}, "1250000", "2.500"),
        ({"deposit_lte_ratio": "0.04"}, {"deposit": "25000000"}, "25000000", "4.00"),
    ],
)
def test_money_is_not_rendered_as_a_percentage_and_rules_are_not_hardcoded(
    rule, facts, amount, percent
):
    text = numeric_explanation(rule, facts, "VIOLATED")
    assert amount + " VND" in text
    assert amount + "%" not in text
    assert percent + "%" in text
    assert "không đáp ứng" in text


@pytest.mark.parametrize(
    "raw,expected",
    [
        (
            'Rule={"text": "value } with brace", "limit": 72}; trailing',
            {"text": "value } with brace", "limit": 72},
        ),
        ("Rule={'limit': '72', 'value': None}; trailing", {"limit": "72", "value": None}),
        ("Rule={'value': Decimal('36')}", None),
        ("Rule={'value': __import__('os').getcwd()}", None),
        ('Rule={"limit":', None),
    ],
)
def test_legacy_audit_parser_accepts_only_data_literals(raw, expected):
    assert _extract_dict_string(raw, "Rule=") == expected
