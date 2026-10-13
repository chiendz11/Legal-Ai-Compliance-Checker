from legal_checker.modules.compliance.numeric_rules import numeric_finding
from legal_checker.shared.contracts.reasoning import Observation


def observation(**facts):
    return Observation(
        tieu_chi_id="TEST", giai_thich="Historical specification", facts=facts, facts_verified=True
    )


def test_historical_first_payment_does_not_assume_deposit_treatment():
    rule = {"first_payment_lte_ratio": 0.3, "denominator": "contract_price"}
    facts = {"contract_price": "100", "first_payment": "30", "deposit": "0"}
    assert numeric_finding("TEST", rule, observation(**facts))[0] == "SATISFIED"
    assert (
        numeric_finding("TEST", rule, observation(**{**facts, "first_payment": "31"}))[0]
        == "VIOLATED"
    )
    assert numeric_finding("TEST", rule, observation(**{**facts, "deposit": "1"}))[0] == "UNKNOWN"
    del facts["deposit"]
    assert numeric_finding("TEST", rule, observation(**facts))[0] == "UNKNOWN"


def test_historical_foreign_seller_uses_its_own_classification():
    rule = {"prehandover_cumulative_lte_ratio": 0.7, "foreign_invested_seller_lte_ratio": 0.5}
    facts = {
        "contract_price": "100",
        "prehandover_cumulative": "51",
        "foreign_invested_seller": True,
    }
    assert numeric_finding("TEST", rule, observation(**facts))[0] == "VIOLATED"
    facts["foreign_invested_seller"] = False
    assert numeric_finding("TEST", rule, observation(**facts))[0] == "SATISFIED"
    facts["foreign_invested_seller"] = None
    assert numeric_finding("TEST", rule, observation(**facts))[0] == "UNKNOWN"


def test_historical_maintenance_base_and_price_treatment_need_resolution():
    rule = {
        "maintenance_ratio": 0.02,
        "included_in_sale_payment": True,
        "denominator": "apartment_value",
    }
    facts = {"apartment_value": "100", "maintenance_amount": "2", "included_in_sale_payment": True}
    assert numeric_finding("TEST", rule, observation(**facts))[0] == "UNKNOWN"
    facts["maintenance_base_definition_resolved"] = True
    assert numeric_finding("TEST", rule, observation(**facts))[0] == "SATISFIED"
    facts["included_in_sale_payment"] = None
    assert numeric_finding("TEST", rule, observation(**facts))[0] == "UNKNOWN"
