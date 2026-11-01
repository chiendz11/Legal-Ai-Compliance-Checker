from datetime import date
from types import SimpleNamespace

from legal_checker.modules.applicable_law.temporal_resolver import CatalogTemporalResolver
from legal_checker.shared.contracts.common import Context
from legal_checker.shared.contracts.document_intelligence import (
    ContractProfile,
    ProfileFields,
    ProfileTimeMarker,
)
from legal_checker.shared.contracts.scope import ScopeResolution

CONTEXT = Context(
    ca_id="CA_T1",
    phien_ban_id="V_TEST",
    rule_version="R_TEST",
    legal_knowledge_version="K_TEST",
    knowledge_snapshot_sha256="0" * 64,
    run_id="CA_T1_B_DEV_001",
    trace_id="CA_T1_TRACE",
)
SIGNING_RULE = "NGAY_XAC_LAP_HOAC_SU_DUNG_MAU"


def version(version_id, start, end=None, group="G1", marker=SIGNING_RULE, family="FAM_X"):
    return {
        "requirement_version_id": version_id,
        "requirement_id": family,
        "nhom_phien_ban": group,
        "hieu_luc_tu": start,
        "hieu_luc_den": end,
        "loai_moc_ap_dung": marker,
        "source_van_ban_id": "VB1",
        "dieu_khoan_id": "ART1",
        "can_xac_minh_chuyen_tiep": True,
        "quy_tac_chuyen_tiep": "transition text",
    }


def knowledge(*versions):
    return SimpleNamespace(
        sha256="a" * 64, versions={v["requirement_version_id"]: v for v in versions}
    )


def scope(status="MATCH", groups=None, family="FAM_X"):
    return ScopeResolution(
        yeu_cau_ca_id=f"CA_T1_{family}",
        ca_id="CA_T1",
        requirement_id=family,
        nhom_phien_ban="G1",
        scope_status=status,
        profile_snapshot_json={"human_verified": False, "profile": {}},
        dieu_kien_snapshot_json={
            "checklist_exhaustive": False,
            "group_status": groups if groups is not None else {"G1": status},
        },
        scope_reason=f"{status}: test",
    )


def profile(**dates):
    return ContractProfile(
        hop_dong_id="HD_T1",
        profile=ProfileFields(),
        time_markers=[
            ProfileTimeMarker(
                moc_id=f"HD_T1_{kind}", loai_moc=kind, ngay=day, trang_thai="EXTRACTED"
            )
            for kind, day in dates.items()
        ],
    )


def resolve(scope_item, contract, versions):
    [result] = CatalogTemporalResolver().resolve(CONTEXT, contract, [scope_item], versions)
    return result


TWO_VERSIONS = knowledge(
    version("PV_OLD", "2015-07-01", "2024-08-01", marker="CHUA_XAC_MINH"),
    version("PV_NEW", "2024-08-01"),
)


def test_signing_date_selects_version_and_confirms():
    result = resolve(scope(), profile(SIGNING=date(2017, 2, 16)), TWO_VERSIONS)
    assert (result.version_status, result.applicability_status) == ("RESOLVED", "CONFIRMED")
    assert result.requirement_version_id == "PV_OLD"
    assert result.loai_moc == "SIGNING"
    assert result.moc_id == "HD_T1_SIGNING"
    assert result.nguon_snapshot_json["candidate_version_only"] is False


def test_interval_is_half_open_at_both_boundaries():
    on_start = resolve(scope(), profile(SIGNING=date(2024, 8, 1)), TWO_VERSIONS)
    assert on_start.requirement_version_id == "PV_NEW"
    day_before = resolve(scope(), profile(SIGNING=date(2024, 7, 31)), TWO_VERSIONS)
    assert day_before.requirement_version_id == "PV_OLD"


def test_unknown_date_stays_unknown_with_only_a_candidate_pointer():
    result = resolve(scope(), profile(SIGNING=None), TWO_VERSIONS)
    assert (result.version_status, result.applicability_status) == ("UNKNOWN", "UNKNOWN")
    # Pointer for loading criteria, explicitly flagged as not resolved.
    assert result.requirement_version_id == "PV_NEW"
    assert result.nguon_snapshot_json["candidate_version_only"] is True
    assert result.nguon_snapshot_json["candidate_version_ids"] == ["PV_OLD", "PV_NEW"]


def test_date_before_catalog_coverage_of_a_version_chain_is_unknown():
    result = resolve(scope(), profile(SIGNING=date(2015, 3, 25)), TWO_VERSIONS)
    assert (result.version_status, result.applicability_status) == ("UNKNOWN", "UNKNOWN")
    assert "before catalog coverage" in result.reason["version"]


def test_event_rule_never_falls_back_to_signing_date():
    rule = "NGAY_THOA_THUAN_VA_NGAY_THU_TIEN"
    versions = knowledge(version("PV_PAY", "2015-07-01", marker=rule))
    result = resolve(scope(), profile(SIGNING=date(2020, 1, 1), COLLECTION=None), versions)
    assert result.loai_moc == "COLLECTION"
    assert result.moc_ap_dung is None
    assert result.version_status == "UNKNOWN"
    # A single candidate is kept as an unconfirmed pointer for retrieval/compliance.
    assert result.requirement_version_id == "PV_PAY"
    assert result.nguon_snapshot_json["candidate_version_only"] is True


def test_family_event_policy_selects_specific_collection_marker():
    rule = "NGAY_THOA_THUAN_VA_NGAY_THU_TIEN"
    versions = knowledge(version("PV_CERT", "2015-07-01", marker=rule, family="FAM_PRE_CERT_CAP"))
    contract = profile(COLLECTION=date(2020, 1, 1), PRE_CERTIFICATE_COLLECTION=date(2020, 5, 1))
    result = resolve(scope(family="FAM_PRE_CERT_CAP"), contract, versions)
    assert result.loai_moc == "PRE_CERTIFICATE_COLLECTION"
    assert result.moc_ap_dung == date(2020, 5, 1)


def test_requirement_not_yet_in_force_is_not_applicable():
    versions = knowledge(version("PV_2024", "2024-08-01"))
    result = resolve(scope(), profile(SIGNING=date(2017, 2, 16)), versions)
    assert result.applicability_status == "NOT_APPLICABLE"
    assert result.requirement_version_id is None


def test_overlapping_versions_stay_unknown():
    versions = knowledge(
        version("PV_A", "2015-01-01", group="G1"), version("PV_B", "2016-01-01", group="G1")
    )
    result = resolve(scope(), profile(SIGNING=date(2020, 1, 1)), versions)
    assert (result.version_status, result.applicability_status) == ("UNKNOWN", "UNKNOWN")
    assert result.nguon_snapshot_json["candidate_version_only"] is True
    assert "2 versions in force" in result.reason["version"]


def test_overlap_is_resolved_by_the_only_matching_scope_group():
    versions = knowledge(
        version("PV_A", "2015-01-01", group="G1"), version("PV_B", "2015-01-01", group="G2")
    )
    item = scope(groups={"G1": "UNKNOWN", "G2": "MATCH"})
    result = resolve(item, profile(SIGNING=date(2020, 1, 1)), versions)
    assert result.requirement_version_id == "PV_B"
    assert result.applicability_status == "CONFIRMED"


def test_version_of_unknown_scope_group_is_resolved_but_not_confirmed():
    versions = knowledge(version("PV_A", "2015-01-01"))
    result = resolve(scope("UNKNOWN"), profile(SIGNING=date(2020, 1, 1)), versions)
    assert (result.version_status, result.applicability_status) == ("RESOLVED", "UNKNOWN")


def test_no_match_scope_is_not_applicable_and_scope_fields_are_kept():
    item = scope("NO_MATCH")
    result = resolve(item, profile(SIGNING=date(2020, 1, 1)), TWO_VERSIONS)
    assert result.applicability_status == "NOT_APPLICABLE"
    assert result.requirement_version_id is None
    # Every scope-owned field checked by workflows.handoffs.validate_legal is copied.
    assert (
        result.yeu_cau_ca_id,
        result.requirement_id,
        result.scope_status,
        result.nhom_phien_ban,
    ) == (item.yeu_cau_ca_id, item.requirement_id, item.scope_status, item.nhom_phien_ban)
    assert result.dieu_kien_snapshot_json == item.dieu_kien_snapshot_json
