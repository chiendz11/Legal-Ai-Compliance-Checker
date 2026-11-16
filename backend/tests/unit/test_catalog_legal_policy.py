"""Legal regime boundaries differ from evidence that an obligation was performed."""

from datetime import date
from types import SimpleNamespace

import pytest
from legal_checker.modules.applicable_law.catalog_policy import (
    ELIGIBILITY_FACT,
    LegalVersionPolicy,
)
from legal_checker.modules.applicable_law.scope_resolver import get_field
from legal_checker.modules.applicable_law.temporal_resolver import CatalogTemporalResolver
from legal_checker.shared.contracts.common import Context
from legal_checker.shared.contracts.document_intelligence import (
    ContractProfile,
    ExtractedFact,
    ProfileEvidence,
    ProfileFields,
    ProfileTimeMarker,
)
from legal_checker.shared.contracts.scope import ScopeResolution


def resolve(
    day,
    *,
    eligibility="absent",
    ready=True,
    marker="SIGNING",
    transition="KDBDS_83",
    article="ART1",
    groups=None,
):
    context = Context(
        ca_id="CA",
        phien_ban_id="DEPLOY",
        rule_version="RULE",
        legal_knowledge_version="K",
        knowledge_snapshot_sha256="a" * 64,
        run_id="RUN",
        trace_id="TRACE",
    )
    policy = LegalVersionPolicy(
        policy_id="LEGAL_VERSION_POLICY_V1",
        review_scope="CONTRACT_AT_CONCLUSION",
        selection_marker=marker,
        performance_events=["COLLECTION"],
        transition=transition,
        grandfathering="SALE_PROCEDURE_ONLY",
        source_article_ids=[article],
        source_urls=["https://vanban.chinhphu.vn/"],
        criteria_ready=ready,
        notes="Reviewed policy",
    )
    versions = [
        dict(
            requirement_version_id=vid,
            requirement_id="FAM",
            nhom_phien_ban="G",
            hieu_luc_tu=start,
            hieu_luc_den=end,
            loai_moc_ap_dung=marker,
            quy_tac_chuyen_tiep=policy.model_dump_json(),
        )
        for vid, start, end in [("OLD", "2015-07-01", "2024-08-01"), ("NEW", "2024-08-01", None)]
    ]
    profile = ContractProfile(
        hop_dong_id="HD",
        profile=ProfileFields(tinh_trang_tai_san="HINH_THANH_TRONG_TUONG_LAI"),
        time_markers=[
            ProfileTimeMarker(moc_id="SIGN", loai_moc="SIGNING", ngay=day, trang_thai="EXTRACTED")
        ],
    )
    if eligibility != "absent":
        profile.evidence = [
            ProfileEvidence(
                bang_chung_id="E",
                doan_id="D",
                trich_dan="source",
                ky_tu_bat_dau=0,
                ky_tu_ket_thuc=6,
            )
        ]
        profile.facts = [
            ExtractedFact(
                trich_xuat_id="F",
                ten_truong=ELIGIBILITY_FACT,
                gia_tri_chuan_json=eligibility,
                trang_thai="HUMAN_VERIFIED",
                phuong_phap="REVIEW",
                human_verified=True,
                evidence_ids=["E"],
            )
        ]
    scope = ScopeResolution(
        yeu_cau_ca_id="YC",
        ca_id="CA",
        requirement_id="FAM",
        scope_status="MATCH",
        scope_reason="MATCH",
        dieu_kien_snapshot_json={"group_status": groups or {"G": "MATCH"}},
    )

    def run():
        return CatalogTemporalResolver().resolve(
            context,
            profile,
            [scope],
            SimpleNamespace(
                sha256="a" * 64, versions={r["requirement_version_id"]: r for r in versions}
            ),
        )[0]

    return run, profile, versions


def test_old_contract_keeps_signing_regime_without_receipt_date():
    run, _, _ = resolve(date(2024, 7, 31))
    result = run()
    assert result.confirmed and result.requirement_version_id == "OLD"
    assert result.loai_moc == "SIGNING"


def test_new_future_sale_needs_explicit_grandfathering_fact():
    run, _, _ = resolve(date(2024, 8, 1))
    result = run()
    assert not result.confirmed and result.version_status == "UNKNOWN"
    assert ELIGIBILITY_FACT in result.reason["version"]


@pytest.mark.parametrize(
    "eligible,version,basis", [(False, "NEW", "2024-08-01"), (True, "OLD", "2024-07-31")]
)
def test_article_83_5_selects_new_or_grandfathered_regime(eligible, version, basis):
    run, _, _ = resolve(date(2024, 8, 1), eligibility=eligible)
    result = run()
    assert result.confirmed and result.requirement_version_id == version
    assert result.moc_ap_dung == date(2024, 8, 1)
    assert result.nguon_snapshot_json["regime_selection_date"] == basis


@pytest.mark.parametrize("defect", ["unreviewed", "missing_evidence", "conflict", "string_bool"])
def test_unsupported_transition_proof_never_becomes_false(defect):
    run, profile, _ = resolve(date(2024, 8, 1), eligibility=False)
    if defect == "unreviewed":
        profile.facts[0].human_verified = False
    elif defect == "missing_evidence":
        profile.evidence = []
    elif defect == "string_bool":
        profile.facts[0].gia_tri_chuan_json = "false"
    else:
        profile.facts.append(
            profile.facts[0].model_copy(update={"trich_xuat_id": "F2", "gia_tri_chuan_json": True})
        )
    assert run().version_status == "UNKNOWN"


def test_article_6_disclosure_is_not_grandfathered():
    run, _, _ = resolve(date(2024, 8, 1), article="ART_VBPL005_6")
    assert run().requirement_version_id == "NEW"


def test_article_83_sale_procedure_does_not_choose_all_old_contract_terms():
    import json

    run, _, versions = resolve(date(2024, 8, 1), eligibility=True)
    for version in versions:
        policy = json.loads(version["quy_tac_chuyen_tiep"])
        policy["grandfathering"] = "CASE_REVIEW"
        version["quy_tac_chuyen_tiep"] = json.dumps(policy)
    assert run().version_status == "UNKNOWN"
    assert "does not automatically select every old rule" in run().reason["version"]


def test_social_housing_transition_cannot_be_proven_by_signing_date_alone():
    run, profile, _ = resolve(date(2024, 8, 1), transition="HOUSING_198")
    profile.profile.la_nha_o_xa_hoi = True
    assert run().version_status == "UNKNOWN"
    assert "housing_social_process_before_20240801" in run().reason["version"]


def test_template_use_is_not_implicitly_signing_date():
    run, _, _ = resolve(date(2024, 8, 1), marker="TEMPLATE_USE", transition="CONSUMER_80")
    result = run()
    assert not result.confirmed and result.loai_moc == "TEMPLATE_USE"
    assert "0 TEMPLATE_USE" in result.reason["version"]


def test_criterionless_catalog_version_is_not_executable():
    run, _, _ = resolve(date(2024, 7, 31), ready=False)
    assert run().version_status == "UNKNOWN"
    assert "no approved executable criteria" in run().reason["version"]


def test_unresolved_concurrent_source_cannot_disappear_by_picking_one_match():
    run, _, versions = resolve(
        date(2024, 8, 1), eligibility=False, groups={"G": "MATCH", "G2": "UNKNOWN"}
    )
    versions[0]["hieu_luc_den"] = None
    versions[1]["nhom_phien_ban"] = "G2"
    assert run().version_status == "UNKNOWN"
    assert "2 versions in force" in run().reason["version"]


def test_unknown_policy_version_fails_closed():
    run, _, versions = resolve(date(2024, 7, 31))
    versions[0]["quy_tac_chuyen_tiep"] = '{"policy_id":"FUTURE_V2"}'
    assert run().version_status == "UNKNOWN"


@pytest.mark.parametrize("name", ["la_giao_dich_dien_tu", "co_thoa_thuan_trong_tai"])
def test_optional_scope_properties_stay_unknown_until_produced(name):
    profile = ContractProfile(hop_dong_id="HD", profile=ProfileFields())
    assert get_field(profile, name).value is None
    setattr(profile.profile, name, False)
    assert get_field(profile, name).value is None
    profile.facts = [
        ExtractedFact(
            trich_xuat_id="F",
            ten_truong=f"profile.{name}",
            gia_tri_chuan_json=False,
            trang_thai="EXTRACTED",
            phuong_phap="LABEL_REGEX",
            evidence_ids=["E"],
        )
    ]
    profile.evidence = [
        ProfileEvidence(
            bang_chung_id="E",
            doan_id="D",
            trich_dan="source",
            ky_tu_bat_dau=0,
            ky_tu_ket_thuc=6,
        )
    ]
    assert get_field(profile, name).value == "KHONG"
    profile.facts.append(
        profile.facts[0].model_copy(update={"trich_xuat_id": "F2", "gia_tri_chuan_json": True})
    )
    assert get_field(profile, name).value is None
