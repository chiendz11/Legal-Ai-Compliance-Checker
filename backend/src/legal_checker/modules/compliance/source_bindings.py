"""Narrow, source-backed bindings for draft clauses, not human approval or receipts."""

import re
from datetime import date
from decimal import localcontext

from legal_checker.modules.compliance.decision_rules import load_decision_rule
from legal_checker.modules.compliance.numeric_rules import NumericInputError, number
from legal_checker.modules.retrieval.fact_evidence import fold


def bind_maintenance_ratio(record, criterion, sources, knowledge):
    if (
        criterion["tieu_chi_id"] != "TC_PV_HYC049_02"
        or record.facts.get("assessment_mode") != "DRAFT_REVIEW"
    ):
        return
    required = {
        "gia_ban",
        "maintenance_amount",
        "maintenance_percent",
        "maintenance_base_reference",
    }
    if (
        not required <= sources.keys()
        or sources["maintenance_base_reference"][0] != "STATED_SALE_PRICE"
    ):
        record.facts["numeric_binding_issue"] = (
            "Explicit same-basis maintenance denominator not established"
        )
        return
    price = sources["gia_ban"][0]
    if not isinstance(price, dict) or price.get("don_vi") not in {"VND", "USD", "EUR"}:
        return
    unit = price["don_vi"]
    amount_quotes = " ".join(e.trich_dan for e in sources["maintenance_amount"][1])
    if not re.search(rf"\b{unit}\b", amount_quotes, re.I):
        return
    _, conditions, issues = load_decision_rule(criterion["tieu_chi_id"], "SATISFIED", knowledge)
    numeric = conditions.get("numeric_rule") or {}
    if issues or numeric.get("denominator") != "apartment_value":
        return
    try:
        base = number(price.get("so_tien"), "declared apartment value", positive=True)
        amount = number(sources["maintenance_amount"][0], "maintenance amount")
        percent = number(sources["maintenance_percent"][0], "stated maintenance percent")
    except NumericInputError:
        record.facts["numeric_binding_issue"] = "Invalid source-backed maintenance numbers"
        return
    with localcontext() as arithmetic:
        arithmetic.prec = 400
        conflicting = amount * 100 != base * percent
    if conflicting:
        record.gates.evidence_conflict = True
        record.facts["numeric_binding_issue"] = "Stated maintenance percentage and amount conflict"
        return
    reference = "BACKEND_STATED_CONTRACT_RATIO_V1:" + record.facts["contract_source_sha256"]
    record.facts.update(
        numeric_scope=numeric["scope"],
        numeric_target="MAINTENANCE_RATIO",
        numeric_target_reviewed=True,
        numeric_target_review_reference=reference,
        denominator_definition_reviewed=True,
        denominator_definition_review_reference=reference,
        denominator_definition_scope="STATED_CONTRACT_VALUE_ONLY",
        apartment_value=str(base),
        apartment_value_unit=unit,
        maintenance_amount=str(amount),
        maintenance_amount_unit=unit,
        numeric_binding_authority="BACKEND_SOURCE_CHECK_DRAFT_ONLY",
    )


def penalty_special_law_binding(record, criterion, requirement, profile, knowledge, exceptions):
    """Resolve the registered Article 418 effect for a consumer apartment draft.

    The related 2014 real-estate law expressly keeps agreed penalties/compensation
    in Article 16(2). This does not apply a commercial-law 8% cap or attest payment.
    Other regimes keep the exception unresolved instead of borrowing this branch.
    """
    if (
        record.facts.get("assessment_mode") != "DRAFT_REVIEW"
        or criterion["tieu_chi_id"] != "TC_PV_DS418_02"
        or len(exceptions) != 1
    ):
        return False
    item = exceptions[0]
    if (
        item.get("ngoai_le_id") != "EX_DS418_SPECIAL"
        or item.get("tac_dong") != "RESOLVE_SPECIAL_LAW"
    ):
        return False
    p = profile.profile
    if not (
        p.ben_ban_la_chu_dau_tu is True
        and p.ben_mua_la_ca_nhan is True
        and p.muc_dich_giao_dich == "TIEU_DUNG_KHONG_THUONG_MAI"
        and p.doi_tuong == "NHA_O"
        and requirement.confirmed
    ):
        return False
    article = knowledge.articles.get("ART_VBPL010_16", {})
    law = knowledge.documents.get(article.get("van_ban_id"), {})
    day = requirement.moc_ap_dung
    if not (
        law.get("so_hieu") == "66/2014/QH13"
        and article.get("trang_thai_xac_minh") in {"HUMAN_VERIFIED", "VERIFIED", "SOURCE_CHECKED"}
        and law.get("hieu_luc_tu")
        and day
        and date.fromisoformat(str(law["hieu_luc_tu"])[:10]) <= day
        and (not law.get("hieu_luc_den") or day < date.fromisoformat(str(law["hieu_luc_den"])[:10]))
    ):
        return False
    text = fold(article.get("noi_dung_nguon") or article.get("noi_dung") or "")
    if not all(word in text for word in ("phat", "boi thuong", "cac ben thoa thuan")):
        return False
    record.facts.update(
        {
            "legal.article_418_applies": True,
            "legal.related_law_has_penalty_rule": True,
            "legal.related_law_source_ids": "ART_VBPL010_16",
            "exception_effect": "RESOLVE_SPECIAL_LAW_AGREED_PENALTY",
            "exception_binding_reference": "CC418_RE2014_16_CONSUMER_DRAFT_V1:" + knowledge.sha256,
        }
    )
    return True
