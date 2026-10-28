"""Allowlisted numeric schemas from the catalog; all thresholds come from the rule.

Facts use explicit units and branch markers (see compliance/README.md). A numeric
comparison is only one part of a predicate; the reviewed proposal must agree too.
No text matching, Python expressions, NULL coercion, or automatic unit conversion.
"""

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation, localcontext
from typing import Any


class NumericInputError(ValueError):
    """Incomplete, unsupported or unsafe numeric input must leave C07 UNKNOWN."""


SCHEMAS = {
    "deposit_lte_ratio": {"denominator", "deposit_lte_ratio", "eligible_before_collection"},
    "first_payment_including_deposit_lte_ratio": {
        "denominator",
        "first_payment_including_deposit_lte_ratio",
        "scope",
    },
    "prehandover_cumulative_lte_ratio": {
        "denominator",
        "prehandover_cumulative_lte_ratio",
        "foreign_seller_art10_4_lte_ratio",
        "scope",
    },
    "before_certificate_cumulative_lte_ratio": {
        "denominator",
        "before_certificate_cumulative_lte_ratio",
        "scope",
    },
    "maintenance_ratio": {"maintenance_ratio", "scope", "separate_from_sale_price"},
    "warranty_min_months": {"warranty_min_months", "scope", "start"},
    "application_submission_max_days": {
        "application_submission_max_days",
        "exception",
        "not_certificate_issuance_deadline",
        "start",
    },
    "first_payment_lte_ratio": {
        "denominator",
        "deposit_inclusion",
        "first_payment_lte_ratio",
        "scope",
    },
}

# The 2014 variants carry additional constraints. Recognizing the whole shape is
# essential: merely matching a threshold key would silently ignore those clauses.
LEGACY_SCHEMAS = (
    (
        "prehandover_cumulative_lte_ratio",
        {
            "denominator",
            "foreign_invested_seller_lte_ratio",
            "prehandover_cumulative_lte_ratio",
            "scope",
            "seller_fact",
            "seller_fact_unresolved",
        },
    ),
    (
        "maintenance_ratio",
        {
            "denominator",
            "denominator_definition",
            "included_in_sale_payment",
            "maintenance_ratio",
            "scope",
        },
    ),
)


def number(value: Any, label: str, *, positive: bool = False) -> Decimal:
    """Parse a finite, nonnegative Decimal; bool and missing values are not numbers."""
    if (
        value is None
        or isinstance(value, bool)
        or not isinstance(value, (str, int, float, Decimal))
    ):
        raise NumericInputError(f"Missing or invalid numeric fact: {label}")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise NumericInputError(f"Invalid numeric fact: {label}") from exc
    if not result.is_finite() or result < 0 or (positive and result <= 0):
        raise NumericInputError(f"Non-finite, negative or invalid denominator: {label}")
    # Bound arithmetic resources and avoid ambient Decimal precision rounding.
    if len(result.as_tuple().digits) > 80 or abs(result.as_tuple().exponent) > 80:
        raise NumericInputError(f"Unsupported numeric magnitude/precision: {label}")
    return result


def numeric_kind(rule: Any) -> str:
    """Validate the whole numeric schema before using any one of its conditions."""
    if not isinstance(rule, dict):
        raise NumericInputError("numeric_rule must be an object")
    matches = [key for key, fields in (*SCHEMAS.items(), *LEGACY_SCHEMAS) if set(rule) == fields]
    if len(matches) != 1:
        raise NumericInputError("Unsupported numeric_rule schema or extra conditions")
    kind = matches[0]
    threshold = number(rule[kind], kind)
    if kind.endswith("ratio") and threshold > 1:
        raise NumericInputError("Numeric ratio threshold must use fraction units [0, 1]")
    denominator = {
        "deposit_lte_ratio": "sale_price",
        "first_payment_including_deposit_lte_ratio": "contract_price",
        "first_payment_lte_ratio": "contract_price",
        "prehandover_cumulative_lte_ratio": "contract_price",
        "before_certificate_cumulative_lte_ratio": "contract_price",
        "maintenance_ratio": "apartment_value",
    }
    if "denominator" in rule and rule["denominator"] != denominator[kind]:
        raise NumericInputError("Unsupported numeric denominator")
    foreign_key = (
        "foreign_seller_art10_4_lte_ratio"
        if "foreign_seller_art10_4_lte_ratio" in rule
        else "foreign_invested_seller_lte_ratio"
    )
    if foreign_key in rule:
        foreign = number(rule[foreign_key], "foreign seller threshold")
        if foreign > 1:
            raise NumericInputError("Foreign seller threshold must be a fraction [0, 1]")
    scopes = {
        "first_payment_including_deposit_lte_ratio": {"FUTURE_COMMERCIAL"},
        "first_payment_lte_ratio": {"FUTURE_FORMED_KDBDS_2014"},
        "prehandover_cumulative_lte_ratio": {
            "FUTURE_FORMED_KDBDS_2014" if "seller_fact" in rule else "FUTURE_COMMERCIAL"
        },
        "before_certificate_cumulative_lte_ratio": {
            "FUTURE_COMMERCIAL",
            "FUTURE_FORMED_KDBDS_2014",
        },
        "maintenance_ratio": {
            "DEVELOPER_SALE_MULTI_OWNER_NHAO_2014"
            if "denominator_definition" in rule
            else "DEVELOPER_SALE_MULTIPLE_OWNERS_NEW_RULES"
        },
        "warranty_min_months": {"NEW_PROJECT", "APARTMENT_NEW_BUILD_NHAO_2014"},
    }
    if kind in scopes:
        scope = rule.get("scope")
        if not isinstance(scope, str) or scope not in scopes[kind]:
            raise NumericInputError("Unsupported numeric scope")
    if kind == "deposit_lte_ratio" and rule["eligible_before_collection"] is not True:
        raise NumericInputError("Unsupported eligible_before_collection condition")
    if kind == "first_payment_lte_ratio" and rule["deposit_inclusion"] != "EXPERT_REVIEW_REQUIRED":
        raise NumericInputError("Unsupported deposit inclusion policy")
    if "seller_fact" in rule and (
        rule["seller_fact"] != "ho_so_hop_dong.ben_ban_co_von_nuoc_ngoai"
        or rule["seller_fact_unresolved"] != "UNKNOWN"
    ):
        raise NumericInputError("Unsupported seller fact policy")
    if "denominator_definition" in rule and (
        rule["denominator_definition"] != "EXPERT_REVIEW_REQUIRED"
        or rule["included_in_sale_payment"] is not True
    ):
        raise NumericInputError("Unsupported maintenance denominator/payment policy")
    if "separate_from_sale_price" in rule and rule["separate_from_sale_price"] is not True:
        raise NumericInputError("Unsupported separate_from_sale_price condition")
    if kind == "warranty_min_months":
        if rule["start"] != "COMPLETION_AND_ACCEPTANCE_INTO_USE":
            raise NumericInputError("Unsupported warranty start")
    if kind == "application_submission_max_days" and (
        rule["start"] != "HANDOVER"
        or rule["exception"] != "BUYER_VOLUNTARILY_SELF_FILES"
        or rule["not_certificate_issuance_deadline"] is not True
    ):
        raise NumericInputError("Unsupported submission deadline conditions")
    return kind


def _equals(facts, key, expected):
    value = facts.get(key)
    if value != expected or (isinstance(expected, bool) and type(value) is not bool):
        raise NumericInputError(f"Unresolved numeric branch/unit: {key} must be {expected}")


def _same_currency(facts, *names):
    units = [facts.get(f"{name}_unit") for name in names]
    if (
        any(not isinstance(unit, str) or unit not in {"VND", "USD", "EUR"} for unit in units)
        or len(set(units)) != 1
    ):
        raise NumericInputError("Missing, unsupported or mismatched currency units")


def _boolean(facts, key):
    """Require an explicit verified boolean, preserving unresolved facts as unknown."""
    value = facts.get(key)
    if type(value) is not bool:
        raise NumericInputError(f"Unresolved numeric branch: {key}")
    return value


def _expert_review(facts, subject):
    """Require a separate expert decision/reference already attested by the backend.

    facts_verified belongs to the trusted adapter. These fields describe the
    decision and its reference; numeric code cannot authenticate the reviewer.
    """
    _equals(facts, f"{subject}_reviewed", True)
    reference = facts.get(f"{subject}_review_reference")
    if not isinstance(reference, str) or not reference.strip():
        raise NumericInputError(f"Missing expert review reference: {subject}")


def evaluate_numeric(rule: dict, facts: Mapping, *, facts_verified: bool) -> bool:
    """Return whether the numeric constraint holds, or raise NumericInputError.

    Values are compared by cross multiplication instead of rounded division. A
    false result proves only the numeric constraint fails, not the whole legal case.
    """
    kind = numeric_kind(rule)
    if facts_verified is not True:
        raise NumericInputError("Numeric facts are unverified")
    if not isinstance(facts, Mapping):
        raise NumericInputError("Numeric facts must be a mapping")
    if "scope" in rule:
        _equals(facts, "numeric_scope", rule["scope"])
    threshold = number(rule[kind], kind)
    with localcontext() as context:
        context.prec = 400
        if kind == "deposit_lte_ratio":
            _same_currency(facts, "deposit", "sale_price")
            deposit = number(facts.get("deposit"), "deposit")
            price = number(facts.get("sale_price"), "sale_price", positive=True)
            eligible = _boolean(facts, "eligible_before_collection")
            return deposit <= price * threshold and eligible is rule["eligible_before_collection"]
        if kind == "maintenance_ratio" and "denominator_definition" in rule:
            _expert_review(facts, "denominator_definition")
            _same_currency(facts, "maintenance_amount", "apartment_value")
            base = number(facts.get("apartment_value"), "apartment_value", positive=True)
            amount = number(facts.get("maintenance_amount"), "maintenance_amount")
            included = _boolean(facts, "included_in_sale_payment")
            return amount == base * threshold and included is rule["included_in_sale_payment"]
        if "denominator" in rule:
            denominator = number(facts.get("contract_price"), "contract_price", positive=True)
            if kind in {"first_payment_including_deposit_lte_ratio", "first_payment_lte_ratio"}:
                names = ("first_payment_excluding_deposit", "deposit", "contract_price")
                _same_currency(facts, *names)
                deposit = number(facts.get("deposit"), "deposit")
                amount = number(facts.get(names[0]), names[0])
                include_deposit = True
                if kind == "first_payment_lte_ratio":
                    _expert_review(facts, "deposit_inclusion")
                    include_deposit = _boolean(facts, "deposit_included_in_first_payment")
                if include_deposit:
                    amount += deposit
            else:
                _same_currency(facts, "cumulative_payment", "contract_price")
                amount = number(facts.get("cumulative_payment"), "cumulative_payment")
                if kind == "prehandover_cumulative_lte_ratio":
                    _equals(facts, "before_handover", True)
                    foreign_fact = rule.get("seller_fact", "foreign_seller_art10_4")
                    foreign = _boolean(facts, foreign_fact)
                    if foreign:
                        threshold_key = (
                            "foreign_invested_seller_lte_ratio"
                            if "seller_fact" in rule
                            else "foreign_seller_art10_4_lte_ratio"
                        )
                        threshold = number(rule[threshold_key], "foreign limit")
                else:
                    _equals(facts, "before_certificate", True)
            return amount <= denominator * threshold
        if kind == "maintenance_ratio":
            _same_currency(facts, "maintenance_amount", "maintenance_base")
            base = number(facts.get("maintenance_base"), "maintenance_base", positive=True)
            amount = number(facts.get("maintenance_amount"), "maintenance_amount")
            _equals(facts, "maintenance_base_kind", "APARTMENT_OR_SOLD_AREA_VALUE")
            separate = facts.get("separate_from_sale_price")
            if type(separate) is not bool:
                raise NumericInputError("Unresolved numeric fact: separate_from_sale_price")
            return amount == base * threshold and separate is rule["separate_from_sale_price"]
        if kind == "warranty_min_months":
            _equals(facts, "warranty_unit", "MONTH")
            _equals(facts, "warranty_start", rule["start"])
            return number(facts.get("warranty_months"), "warranty_months") >= threshold
        _equals(facts, "submission_unit", "DAY")
        _equals(facts, "submission_start", rule["start"])
        _equals(facts, "submission_event", "APPLICATION_SUBMISSION")
        _equals(facts, "buyer_voluntarily_self_files", False)
        _equals(facts, "application_submitted", True)
        return number(facts.get("submission_elapsed_days"), "submission_elapsed_days") <= threshold


def evaluate_numeric_for_criterion(rule: dict, facts: Mapping, *, facts_verified: bool) -> bool:
    """Evaluate a pinned constraint only within an independently reviewed proposition.

    The catalog reuses some group-level numeric objects for different criteria.
    Comparing the whole object would make an eligibility breach a cap breach, or
    a payment-inclusion breach a ratio breach. The engine cannot derive the target
    from a criterion ID or predicate keywords. A trusted backend review must bind
    one allowlisted target to the current criterion (its context/digest is checked
    by reviewed_observations). Standalone evaluate_numeric keeps whole-rule semantics.
    """
    kind = numeric_kind(rule)
    shared_deposit = kind == "deposit_lte_ratio"
    shared_maintenance = kind == "maintenance_ratio" and "denominator_definition" in rule
    if not (shared_deposit or shared_maintenance):
        return evaluate_numeric(rule, facts, facts_verified=facts_verified)
    if facts_verified is not True or not isinstance(facts, Mapping):
        raise NumericInputError("Current-criterion numeric facts/target are unverified")
    _expert_review(facts, "numeric_target")
    target = facts.get("numeric_target")
    allowed = (
        {"ALL_CONSTRAINTS", "DEPOSIT_CAP", "DEPOSIT_ELIGIBILITY", "DEPOSIT_PRICE"}
        if shared_deposit
        else {"ALL_CONSTRAINTS", "MAINTENANCE_RATIO", "MAINTENANCE_PAYMENT_INCLUSION"}
    )
    if not isinstance(target, str) or target not in allowed:
        raise NumericInputError("Unsupported current-criterion numeric_target")
    if target == "ALL_CONSTRAINTS":
        return evaluate_numeric(rule, facts, facts_verified=facts_verified)
    if target == "DEPOSIT_ELIGIBILITY":
        return _boolean(facts, "eligible_before_collection") is rule["eligible_before_collection"]
    if target == "DEPOSIT_PRICE":
        return _boolean(facts, "sale_price_stated_in_agreement")
    if "scope" in rule:
        _equals(facts, "numeric_scope", rule["scope"])
    if target == "MAINTENANCE_PAYMENT_INCLUSION":
        return _boolean(facts, "included_in_sale_payment") is rule["included_in_sale_payment"]
    with localcontext() as context:
        context.prec = 400
        if target == "DEPOSIT_CAP":
            _same_currency(facts, "deposit", "sale_price")
            deposit = number(facts.get("deposit"), "deposit")
            price = number(facts.get("sale_price"), "sale_price", positive=True)
            return deposit <= price * number(rule[kind], kind)
        _expert_review(facts, "denominator_definition")
        _same_currency(facts, "maintenance_amount", "apartment_value")
        amount = number(facts.get("maintenance_amount"), "maintenance_amount")
        base = number(facts.get("apartment_value"), "apartment_value", positive=True)
        return amount == base * number(rule[kind], kind)
