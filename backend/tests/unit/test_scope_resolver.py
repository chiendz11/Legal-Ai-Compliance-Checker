from types import SimpleNamespace

import pytest
from legal_checker.modules.applicable_law.scope_resolver import CatalogScopeResolver
from legal_checker.shared.contracts.common import Context
from legal_checker.shared.contracts.document_intelligence import (
    ContractProfile,
    ExtractedFact,
    ProfileFields,
    ProfileSubject,
)

CONTEXT = Context(
    ca_id="CA_T1",
    phien_ban_id="V_TEST",
    rule_version="R_TEST",
    legal_knowledge_version="K_TEST",
    knowledge_snapshot_sha256="0" * 64,
    run_id="CA_T1_B_DEV_001",
    trace_id="CA_T1_TRACE",
)
TYPES = [
    {"loai_hop_dong_id": "MB_HOP_DONG_MUA_BAN", "loai_cha_id": None},
    {"loai_hop_dong_id": "MB_BAT_DONG_SAN", "loai_cha_id": "MB_HOP_DONG_MUA_BAN"},
    {"loai_hop_dong_id": "MB_CAN_HO_CHUNG_CU", "loai_cha_id": "MB_BAT_DONG_SAN"},
]


def knowledge(clauses, mode="ALL_MANDATORY"):
    families = {c["requirement_id"] for c in clauses} | {"FAM_X"}
    return SimpleNamespace(
        tables={
            "loai_hop_dong": TYPES,
            "yeu_cau_phap_ly": [
                {"requirement_id": f, "che_do_ket_hop": mode} for f in sorted(families)
            ],
            "pham_vi_ap_dung": clauses,
        }
    )


def clause(conditions, group="G1", pham_vi_id="PV1", requirement_id="FAM_X", evidence=False):
    return {
        "pham_vi_id": pham_vi_id,
        "requirement_id": requirement_id,
        "nhom_phien_ban": group,
        "dieu_kien_json": {
            "all": [{"field": f, "op": op, "value": v} for f, op, v in conditions],
            "missing_policy": "UNKNOWN",
            "scope_confirmed_requires_validated_facts": evidence,
        },
    }


def profile(subjects=(), facts=(), **fields):
    return ContractProfile(
        hop_dong_id="HD_T1",
        profile=ProfileFields(**fields),
        subjects=[
            ProfileSubject(chu_the_id=f"S{i}", vai_tro=role, la_chu_the_kinh_doanh=value)
            for i, (role, value) in enumerate(subjects)
        ],
        facts=[
            ExtractedFact(
                trich_xuat_id=f"F{i}",
                ten_truong=f"profile.{name}",
                trang_thai="EXTRACTED",
                phuong_phap="TEST",
                evidence_ids=["E1"],
            )
            for i, name in enumerate(facts)
        ],
    )


def resolve(clauses, contract_profile, mode="ALL_MANDATORY"):
    results = CatalogScopeResolver(["FAM_X"]).resolve(
        CONTEXT, contract_profile, knowledge(clauses, mode)
    )
    assert len(results) == 1
    return results[0]


def test_missing_fact_is_unknown_not_no_match():
    result = resolve(
        [clause([("che_do_giao_dich", "EQ", "KINH_DOANH_BDS")])],
        profile(),
    )
    assert result.scope_status == "UNKNOWN"
    assert "che_do_giao_dich" in result.scope_reason


def test_descendant_contract_type_matches():
    result = resolve(
        [clause([("loai_hop_dong_id", "IS_OR_DESCENDANT_OF", "MB_BAT_DONG_SAN")])],
        profile(loai_hop_dong_id="MB_CAN_HO_CHUNG_CU"),
    )
    assert result.scope_status == "MATCH"
    assert result.yeu_cau_ca_id == "CA_T1_FAM_X"
    assert result.nhom_phien_ban == "G1"


def test_parent_type_is_not_descendant_of_child():
    result = resolve(
        [clause([("loai_hop_dong_id", "IS_OR_DESCENDANT_OF", "MB_CAN_HO_CHUNG_CU")])],
        profile(loai_hop_dong_id="MB_BAT_DONG_SAN"),
    )
    assert result.scope_status == "NO_MATCH"


def test_type_outside_catalog_is_unknown():
    result = resolve(
        [clause([("loai_hop_dong_id", "IS_OR_DESCENDANT_OF", "MB_BAT_DONG_SAN")])],
        profile(loai_hop_dong_id="LOAI_LA"),
    )
    assert result.scope_status == "UNKNOWN"


def test_profile_boolean_matches_catalog_co_and_json_false():
    result = resolve(
        [clause([("la_hop_dong_theo_mau", "EQ", "CO"), ("la_nha_o_xa_hoi", "EQ", False)])],
        profile(la_hop_dong_theo_mau=True, la_nha_o_xa_hoi=False),
    )
    assert result.scope_status == "MATCH"


def test_subject_field_uses_role_prefix():
    conditions = [("BEN_BAN.la_chu_the_kinh_doanh", "EQ", "CO")]
    assert (
        resolve([clause(conditions)], profile(subjects=[("BEN_BAN", True)])).scope_status == "MATCH"
    )
    assert (
        resolve([clause(conditions)], profile(subjects=[("BEN_BAN", None)])).scope_status
        == "UNKNOWN"
    )
    assert resolve([clause(conditions)], profile()).scope_status == "UNKNOWN"


def test_false_beats_unknown_inside_a_clause():
    result = resolve(
        [clause([("che_do_giao_dich", "EQ", "KINH_DOANH_BDS"), ("doi_tuong", "EQ", "NHA_O")])],
        profile(doi_tuong="DAT"),
    )
    assert result.scope_status == "NO_MATCH"


def test_grouped_mode_matches_if_any_group_matches():
    clauses = [
        clause([("doi_tuong", "EQ", "DAT")], group="G1", pham_vi_id="PV1"),
        clause([("doi_tuong", "EQ", "NHA_O")], group="G2", pham_vi_id="PV2"),
    ]
    mode = "THEO_NHOM_PHIEN_BAN_KHONG_LOAI_TRU_NGUON_DONG_THOI"
    result = resolve(clauses, profile(doi_tuong="NHA_O"), mode)
    assert result.scope_status == "MATCH"
    assert result.nhom_phien_ban == "G2"
    assert result.dieu_kien_snapshot_json["group_status"] == {"G1": "NO_MATCH", "G2": "MATCH"}


def test_all_mandatory_needs_every_clause():
    clauses = [
        clause([("doi_tuong", "EQ", "NHA_O")], pham_vi_id="PV1"),
        clause([("linh_vuc", "EQ", "NHA_O")], pham_vi_id="PV2"),
    ]
    assert resolve(clauses, profile(doi_tuong="NHA_O")).scope_status == "UNKNOWN"


def test_validated_facts_policy_requires_evidence():
    conditions = [("doi_tuong", "EQ", "NHA_O")]
    no_source = resolve([clause(conditions, evidence=True)], profile(doi_tuong="NHA_O"))
    assert no_source.scope_status == "UNKNOWN"
    with_source = resolve(
        [clause(conditions, evidence=True)], profile(facts=["doi_tuong"], doi_tuong="NHA_O")
    )
    assert with_source.scope_status == "MATCH"


def test_party_capacity_pending_caps_type_only_clause():
    type_only = clause([("loai_hop_dong_id", "IS_OR_DESCENDANT_OF", "MB_BAT_DONG_SAN")])
    type_only["loai_chu_the"] = "CAN_XAC_MINH_TU_CACH_CAC_BEN"
    result = resolve([type_only], profile(loai_hop_dong_id="MB_CAN_HO_CHUNG_CU"))
    assert result.scope_status == "UNKNOWN"
    assert "CAN_XAC_MINH_TU_CACH_CAC_BEN" in result.scope_reason

    with_party = clause(
        [
            ("loai_hop_dong_id", "IS_OR_DESCENDANT_OF", "MB_BAT_DONG_SAN"),
            ("BEN_BAN.la_chu_the_kinh_doanh", "EQ", "CO"),
        ]
    )
    with_party["loai_chu_the"] = "CAN_XAC_MINH_TU_CACH_CAC_BEN"
    contract = profile(subjects=[("BEN_BAN", True)], loai_hop_dong_id="MB_CAN_HO_CHUNG_CU")
    assert resolve([with_party], contract).scope_status == "MATCH"


def test_developer_new_build_confirms_housing_group_capacity():
    housing = clause([("loai_hop_dong_id", "IS_OR_DESCENDANT_OF", "MB_BAT_DONG_SAN")], group="NHAO")
    housing["loai_chu_the"] = "CAN_XAC_MINH_TU_CACH_CAC_BEN"
    fields = {"loai_hop_dong_id": "MB_CAN_HO_CHUNG_CU", "la_nha_xay_moi": True}

    developer = resolve([housing], profile(ben_ban_la_chu_dau_tu=True, **fields))
    assert developer.scope_status == "MATCH"
    assert "team policy" in developer.scope_reason

    unknown = resolve([housing], profile(**fields))
    assert unknown.scope_status == "UNKNOWN"

    # The policy only confirms; a non-developer seller is not turned into NO_MATCH.
    resale = resolve([housing], profile(ben_ban_la_chu_dau_tu=False, **fields))
    assert resale.scope_status == "UNKNOWN"

    disabled = CatalogScopeResolver(["FAM_X"], party_capacity_checks={}).resolve(
        CONTEXT, profile(ben_ban_la_chu_dau_tu=True, **fields), knowledge([housing])
    )
    assert disabled[0].scope_status == "UNKNOWN"


def test_evidenced_social_housing_excludes_commercial_family():
    payment = clause([("loai_hop_dong_id", "IS_OR_DESCENDANT_OF", "MB_BAT_DONG_SAN")])
    fields = {"loai_hop_dong_id": "MB_CAN_HO_CHUNG_CU", "la_nha_o_xa_hoi": True}

    def run(contract, commercial_only=("FAM_X",)):
        resolver = CatalogScopeResolver(["FAM_X"], commercial_only_requirements=commercial_only)
        return resolver.resolve(CONTEXT, contract, knowledge([payment]))[0]

    excluded = run(profile(facts=["la_nha_o_xa_hoi"], **fields))
    assert excluded.scope_status == "NO_MATCH"
    assert excluded.nhom_phien_ban is None
    assert excluded.dieu_kien_snapshot_json["exclusion"]["status_before_exclusion"] == "MATCH"

    # No source evidence or an unknown value leaves the catalog result untouched.
    assert run(profile(**fields)).scope_status == "MATCH"
    unknown = {"loai_hop_dong_id": "MB_CAN_HO_CHUNG_CU"}
    assert run(profile(facts=["la_nha_o_xa_hoi"], **unknown)).scope_status == "MATCH"
    # Families outside the commercial-only list are not affected.
    assert run(profile(facts=["la_nha_o_xa_hoi"], **fields), ()).scope_status == "MATCH"


def test_family_without_clauses_is_unknown():
    assert resolve([], profile()).scope_status == "UNKNOWN"


def test_unsupported_operator_fails_loudly():
    with pytest.raises(ValueError, match="Unsupported scope operator"):
        resolve([clause([("doi_tuong", "IN", "NHA_O")])], profile(doi_tuong="NHA_O"))


def test_snapshots_keep_reference_shape():
    result = resolve([clause([("doi_tuong", "EQ", "NHA_O")])], profile(doi_tuong="NHA_O"))
    assert {"human_verified", "profile"} <= result.profile_snapshot_json.keys()
    assert result.profile_snapshot_json["profile"]["doi_tuong"] == "NHA_O"
    assert {"checklist_exhaustive", "unprovided_event_date_is_not_signing_date"} <= (
        result.dieu_kien_snapshot_json.keys()
    )
