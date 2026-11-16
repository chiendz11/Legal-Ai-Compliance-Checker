"""Versioned catalog metadata for reviewing a contract at its conclusion.

The legal-regime date and the evidence of later performance are different inputs.
Legacy prose stays readable; only the explicitly versioned JSON activates this policy.
"""

import json
from datetime import date, timedelta
from typing import Literal

from pydantic import ConfigDict, Field

from legal_checker.shared.contracts.common import Model
from legal_checker.shared.contracts.document_intelligence import ContractProfile

POLICY_ID = "LEGAL_VERSION_POLICY_V1"
MARKERS = frozenset({"SIGNING", "TEMPLATE_USE", "DEPOSIT_AGREEMENT", "COLLECTION"})
ELIGIBILITY_FACT = "transition.future_sale_eligible_before_20240801"
SOCIAL_TRANSITION_FACT = "transition.housing_social_process_before_20240801"
CUTOFF = date(2024, 8, 1)


class LegalVersionPolicy(Model):
    model_config = ConfigDict(extra="forbid")

    policy_id: Literal["LEGAL_VERSION_POLICY_V1"]
    review_scope: Literal["CONTRACT_AT_CONCLUSION"]
    selection_marker: Literal["SIGNING", "TEMPLATE_USE", "DEPOSIT_AGREEMENT", "COLLECTION"]
    performance_events: list[str] = Field(default_factory=list)
    transition: Literal["KDBDS_83", "CONSUMER_80", "HOUSING_198", "CIVIL_688", "SOURCE_INTERVAL"]
    grandfathering: Literal["NONE", "SALE_PROCEDURE_ONLY", "CASE_REVIEW"] = "NONE"
    source_article_ids: list[str] = Field(min_length=1)
    source_urls: list[str] = Field(min_length=1)
    criteria_ready: bool
    notes: str = Field(min_length=1)
    historical_equivalent_family_id: str | None = None
    historical_basis_article_ids: list[str] = Field(default_factory=list)


def read_policy(version: dict) -> LegalVersionPolicy | None:
    value = version.get("quy_tac_chuyen_tiep")
    if not isinstance(value, str) or not value.lstrip().startswith("{"):
        return None
    parsed = json.loads(value)
    # JSON with an unknown policy id is not a legacy prose rule.
    return LegalVersionPolicy.model_validate(parsed)


def verified_boolean(profile: ContractProfile, name: str) -> bool | None:
    """Accept one evidenced, reviewed C02 fact; conflict/unknown never becomes False."""
    facts = [f for f in profile.facts if f.ten_truong == name]
    evidence_ids = {e.bang_chung_id for e in profile.evidence}
    if not facts or any(
        type(f.gia_tri_chuan_json) is not bool
        or not f.human_verified
        or not f.evidence_ids
        or not set(f.evidence_ids) <= evidence_ids
        or f.trang_thai not in {"EXTRACTED", "VERIFIED", "HUMAN_VERIFIED"}
        for f in facts
    ):
        return None
    values = {f.gia_tri_chuan_json for f in facts}
    return values.pop() if len(values) == 1 else None


def selection_date(
    profile: ContractProfile, day: date, policies: list[LegalVersionPolicy]
) -> tuple[date, str | None]:
    """Apply the documented Article 83(5) grandfathering guard, not a date fallback.

    Article 83(9) keeps the regime of an earlier concluded contract. Later amendments,
    ongoing consumer transactions and project-specific housing transitions need separate
    assessments; this policy does not certify them from a signing date alone.
    """
    if (
        day >= CUTOFF
        and any(p.transition == "HOUSING_198" for p in policies)
        and profile.profile.la_nha_o_xa_hoi is True
    ):
        prior_process = verified_boolean(profile, SOCIAL_TRANSITION_FACT)
        if prior_process is None:
            return day, f"transition fact required: {SOCIAL_TRANSITION_FACT} (Article 198(5)(e))"
        if prior_process:
            return day, "Article 198(5)(e): prior social-housing process needs case-specific review"
    if (
        day < CUTOFF
        or not any(p.transition == "KDBDS_83" for p in policies)
        or profile.profile.tinh_trang_tai_san != "HINH_THANH_TRONG_TUONG_LAI"
    ):
        return day, None
    # Article 6 disclosure is expressly subject to the new law, even for old eligible stock.
    if all("ART_VBPL005_6" in p.source_article_ids for p in policies):
        return day, None
    eligible = verified_boolean(profile, ELIGIBILITY_FACT)
    if eligible is None:
        return day, f"transition fact required: {ELIGIBILITY_FACT} (Article 83(5))"
    if eligible and not all(p.grandfathering == "SALE_PROCEDURE_ONLY" for p in policies):
        return day, (
            "Article 83(5) eligible stock: separate case review required for contract terms; "
            "sale-procedure grandfathering does not automatically select every old rule"
        )
    return (CUTOFF - timedelta(days=1), None) if eligible else (day, None)
