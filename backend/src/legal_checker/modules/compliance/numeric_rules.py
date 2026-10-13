from decimal import Decimal, InvalidOperation

from legal_checker.shared.contracts.reasoning import Observation


def numeric_finding(criterion_id: str, rule: dict, observation: Observation):
    """Use Decimal and explicit, verified fields; absent values never become zero."""
    facts = observation.facts
    if not observation.facts_verified:
        return "UNKNOWN", "Numeric facts have not been verified"
    if facts.get("scope") != rule.get("scope") and rule.get("scope"):
        return "UNKNOWN", "Numeric scope is unresolved"

    def amount(name):
        v = facts.get(name)
        if v is None or isinstance(v, bool):
            raise ValueError(f"Missing numeric fact: {name}")
        d = Decimal(str(v))
        if not d.is_finite() or d < 0:
            raise ValueError(f"Invalid numeric fact: {name}")
        return d

    def ratio(numerator, denominator):
        den = amount(denominator)
        if den <= 0:
            raise ValueError("Denominator must be positive")
        return numerator / den

    try:
        if "first_payment_including_deposit_lte_ratio" in rule:
            first = amount("first_payment")
            deposit = amount("deposit")
            included = facts.get("deposit_included_in_first_payment")
            if type(included) is not bool:
                raise ValueError("Deposit inclusion must be explicitly known")
            value = ratio(first + (Decimal(0) if included else deposit), "contract_price")
            passed = value <= Decimal(str(rule["first_payment_including_deposit_lte_ratio"]))
        elif "first_payment_lte_ratio" in rule:
            # The historical knowledge leaves inclusion of a deposit for expert review.
            # A zero-deposit scenario has no inclusion ambiguity; never assume absent = zero.
            if amount("deposit") != 0:
                raise ValueError("Historical deposit inclusion requires separate legal review")
            value = ratio(amount("first_payment"), rule.get("denominator", "contract_price"))
            passed = value <= Decimal(str(rule["first_payment_lte_ratio"]))
        elif "prehandover_cumulative_lte_ratio" in rule:
            modern = "foreign_seller_art10_4_lte_ratio" in rule
            foreign = facts.get("foreign_seller_art10_4" if modern else "foreign_invested_seller")
            if type(foreign) is not bool:
                raise ValueError("Seller classification is unresolved")
            value = ratio(amount("prehandover_cumulative"), "contract_price")
            foreign_key = (
                "foreign_seller_art10_4_lte_ratio"
                if modern
                else "foreign_invested_seller_lte_ratio"
            )
            limit = rule[foreign_key if foreign else "prehandover_cumulative_lte_ratio"]
            passed = value <= Decimal(str(limit))
        elif "before_certificate_cumulative_lte_ratio" in rule:
            value = ratio(amount("before_certificate_cumulative"), "contract_price")
            passed = value <= Decimal(str(rule["before_certificate_cumulative_lte_ratio"]))
        elif "maintenance_ratio" in rule:
            historical = rule.get("included_in_sale_payment") is True
            base = (
                rule.get("denominator", "maintenance_base_price")
                if historical
                else "maintenance_base_price"
            )
            value = ratio(amount("maintenance_amount"), base)
            treatment = facts.get(
                "included_in_sale_payment" if historical else "separate_from_sale_price"
            )
            if type(treatment) is not bool:
                raise ValueError("Maintenance price treatment is unknown")
            if historical and facts.get("maintenance_base_definition_resolved") is not True:
                raise ValueError(
                    "Historical maintenance denominator requires separate legal review"
                )
            passed = value == Decimal(str(rule["maintenance_ratio"])) and treatment
        elif "warranty_min_months" in rule:
            if facts.get("warranty_start") != rule["start"]:
                raise ValueError("Warranty starting event is not resolved")
            value = amount("warranty_months")
            passed = value >= Decimal(str(rule["warranty_min_months"]))
        elif "application_submission_max_days" in rule:
            if facts.get("deadline_start") != rule["start"]:
                raise ValueError("Deadline starting event is not resolved")
            if facts.get("buyer_voluntarily_self_files") is not False:
                raise ValueError("Self-filing exception must be resolved upstream")
            value = amount("application_submission_days")
            passed = value <= Decimal(str(rule["application_submission_max_days"]))
        elif "deposit_lte_ratio" in rule:
            if criterion_id.endswith("DEPOSIT_CAP"):
                value = ratio(amount("deposit"), "sale_price")
                passed = value <= Decimal(str(rule["deposit_lte_ratio"]))
            elif criterion_id.endswith("DEPOSIT_ELIGIBLE"):
                value = facts.get("eligible_before_collection")
                if type(value) is not bool:
                    raise ValueError("Collection eligibility is unresolved")
                passed = value
            elif criterion_id.endswith("DEPOSIT_PRICE"):
                value = facts.get("sale_price_agreed")
                if type(value) is not bool:
                    raise ValueError("Agreed sale price is unresolved")
                passed = value
            else:
                raise ValueError("Unsupported deposit criterion")
        else:
            raise ValueError("Unsupported numeric rule")
    except (ValueError, InvalidOperation) as exc:
        return "UNKNOWN", str(exc)
    return ("SATISFIED" if passed else "VIOLATED"), f"Verified numeric check: {value}"
