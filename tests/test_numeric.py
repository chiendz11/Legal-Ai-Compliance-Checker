import pytest

from app.application.pipelines.steps_5_7 import evaluate


def first_payment(request_factory, **facts):
    def mutate(data):
        data["payload"]["observations"][0].update(facts=facts, facts_verified=True)

    return request_factory("PV_GYC062", mutate=mutate)


@pytest.mark.parametrize(
    "included,first,deposit,expected",
    [
        (False, "20", "10", "SATISFIED"),
        (True, "30", "10", "SATISFIED"),
        (False, "30", "10", "VIOLATED"),
        (False, "30.0001", "0", "VIOLATED"),
    ],
)
def test_first_payment_boundary_and_no_double_count(
    knowledge, request_factory, included, first, deposit, expected
):
    request = first_payment(
        request_factory,
        scope="FUTURE_COMMERCIAL",
        contract_price="100",
        first_payment=first,
        deposit=deposit,
        deposit_included_in_first_payment=included,
    )
    result = evaluate(request, knowledge).payload
    assert result.criterion_results[0].finding == expected


@pytest.mark.parametrize("price", ["0", "-1", "NaN", "Infinity"])
def test_invalid_denominator_unknown(knowledge, request_factory, price):
    request = first_payment(
        request_factory,
        scope="FUTURE_COMMERCIAL",
        contract_price=price,
        first_payment="10",
        deposit="0",
        deposit_included_in_first_payment=False,
    )
    assert evaluate(request, knowledge).payload.criterion_results[0].finding == "UNKNOWN"


def test_missing_deposit_inclusion_unknown(knowledge, request_factory):
    request = first_payment(
        request_factory,
        scope="FUTURE_COMMERCIAL",
        contract_price="100",
        first_payment="10",
        deposit="5",
    )
    assert evaluate(request, knowledge).payload.criterion_results[0].finding == "UNKNOWN"


@pytest.mark.parametrize(
    "foreign,amount,expected",
    [
        (False, "70", "SATISFIED"),
        (False, "70.01", "VIOLATED"),
        (True, "50", "SATISFIED"),
        (True, "50.01", "VIOLATED"),
    ],
)
def test_prehandover_seller_specific_threshold(
    knowledge, request_factory, foreign, amount, expected
):
    def mutate(data):
        data["payload"]["observations"][0].update(
            facts_verified=True,
            facts={
                "scope": "FUTURE_COMMERCIAL",
                "contract_price": "100",
                "prehandover_cumulative": amount,
                "foreign_seller_art10_4": foreign,
            },
        )

    request = request_factory("PV_GYC064", mutate=mutate)
    assert evaluate(request, knowledge).payload.criterion_results[0].finding == expected


@pytest.mark.parametrize("days,expected", [(50, "SATISFIED"), (51, "VIOLATED")])
def test_fifty_days_is_submission_deadline(knowledge, request_factory, days, expected):
    def mutate(data):
        data["payload"]["observations"][0].update(
            facts_verified=True,
            facts={
                "deadline_start": "HANDOVER",
                "buyer_voluntarily_self_files": False,
                "application_submission_days": str(days),
            },
        )

    request = request_factory("PV_APT_CERTIFICATE_50D_2024", mutate=mutate)
    assert evaluate(request, knowledge).payload.criterion_results[0].finding == expected


@pytest.mark.parametrize(
    "version_id,facts,expected",
    [
        (
            "PV_GYC065",
            {
                "scope": "FUTURE_COMMERCIAL",
                "contract_price": "100",
                "before_certificate_cumulative": "95",
            },
            "SATISFIED",
        ),
        (
            "PV_GYC065",
            {
                "scope": "FUTURE_COMMERCIAL",
                "contract_price": "100",
                "before_certificate_cumulative": "95.01",
            },
            "VIOLATED",
        ),
        (
            "PV_GYC104",
            {
                "scope": "DEVELOPER_SALE_MULTIPLE_OWNERS_NEW_RULES",
                "maintenance_amount": "2",
                "maintenance_base_price": "100",
                "separate_from_sale_price": True,
            },
            "SATISFIED",
        ),
        (
            "PV_GYC104",
            {
                "scope": "DEVELOPER_SALE_MULTIPLE_OWNERS_NEW_RULES",
                "maintenance_amount": "2",
                "maintenance_base_price": "100",
                "separate_from_sale_price": False,
            },
            "VIOLATED",
        ),
        (
            "PV_GYC154",
            {
                "scope": "NEW_PROJECT",
                "warranty_start": "COMPLETION_AND_ACCEPTANCE_INTO_USE",
                "warranty_months": "60",
            },
            "SATISFIED",
        ),
        (
            "PV_GYC154",
            {
                "scope": "NEW_PROJECT",
                "warranty_start": "COMPLETION_AND_ACCEPTANCE_INTO_USE",
                "warranty_months": "59",
            },
            "VIOLATED",
        ),
    ],
)
def test_remaining_workbook_numeric_rules(knowledge, request_factory, version_id, facts, expected):
    def mutate(data):
        data["payload"]["observations"][0].update(facts_verified=True, facts=facts)

    request = request_factory(version_id, mutate=mutate)
    assert evaluate(request, knowledge).payload.criterion_results[0].finding == expected
