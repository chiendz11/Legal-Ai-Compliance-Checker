from datetime import date
from types import SimpleNamespace

import pytest
from legal_checker.modules.citation_validation.normalizer import number_key
from legal_checker.modules.citation_validation.service import CatalogCitationValidator
from legal_checker.shared.contracts.citation import (
    CitationExtraction,
    CitationExtractionMetadata,
    CitationNormalization,
    CitationPosition,
)
from legal_checker.shared.contracts.common import Context
from legal_checker.shared.contracts.document_intelligence import (
    ContractProfile,
    ProfileFields,
    ProfileTimeMarker,
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
VERIFIED = {"identity_verified": True, "temporal_verified": True, "domain_verified": True}
DOCUMENTS = {
    "LNO_2014": {
        "van_ban_id": "LNO_2014",
        "ten_van_ban": "Luật Nhà ở",
        "so_hieu": "65/2014/QH13",
        "so_hieu_chuan": "65/2014/QH13",
        "linh_vuc": "NHAO_2014",
        "hieu_luc_tu": "2015-07-01",
        "hieu_luc_den": "2024-08-01",
        "trang_thai": "HISTORICAL",
        "van_ban_thay_the_id": "LNO_2023",
        **VERIFIED,
    },
    "LNO_2023": {
        "van_ban_id": "LNO_2023",
        "ten_van_ban": "Luật Nhà ở",
        "so_hieu": "27/2023/QH15",
        "so_hieu_chuan": "27/2023/QH15",
        "linh_vuc": "NHAO_2024",
        "hieu_luc_tu": "2024-08-01",
        "hieu_luc_den": None,
        "trang_thai": "CURRENT",
        "van_ban_thay_the_id": None,
        "identity_verified": True,
        "temporal_verified": False,
        "domain_verified": True,
    },
    "ND_NOXH": {
        "van_ban_id": "ND_NOXH",
        "ten_van_ban": "Nghị định về nhà ở xã hội",
        "so_hieu": "100/2024/NĐ-CP",
        "so_hieu_chuan": "100/2024/NĐ-CP",
        "linh_vuc": "NOXH",
        "hieu_luc_tu": "2024-08-01",
        "trang_thai": "CURRENT",
        **VERIFIED,
    },
    "TT_OLD": {
        "van_ban_id": "TT_OLD",
        "ten_van_ban": "Thông tư quy chế quản lý",
        "so_hieu": "02/2016/TT-BXD",
        "so_hieu_chuan": "02/2016/TT-BXD",
        "linh_vuc": "NHAO_2014_QUAN_LY_NCC",
        "hieu_luc_tu": "2016-04-02",
        "trang_thai": "HISTORICAL",
        **VERIFIED,
    },
}
RELATIONS = [
    {
        "van_ban_nguon_id": "LNO_2023",
        "van_ban_dich_id": "LNO_2014",
        "loai_quan_he": "THAY_THE",
        "moc_hieu_luc": "2024-08-01",
    },
    {
        "van_ban_nguon_id": "TT_AMEND",
        "van_ban_dich_id": "TT_OLD",
        "loai_quan_he": "SUA_DOI_MOT_PHAN",
        "moc_hieu_luc": "2017-02-01",
    },
]
KNOWLEDGE = SimpleNamespace(
    documents=DOCUMENTS,
    tables={
        "quan_he_van_ban": RELATIONS,
        "loai_hop_dong": [
            {"loai_hop_dong_id": "MB_CAN_HO_CHUNG_CU", "legal_domain": "REAL_ESTATE_HOUSING"}
        ],
    },
)


def citation(number=None, title=None, status="EXTRACTED", vien_dan_id="HD_T1_LS2_CIT_00001"):
    return CitationExtraction(
        vien_dan_id=vien_dan_id,
        hop_dong_id="HD_T1",
        raw_text=f"Căn cứ {title or ''} {number or ''}",
        normalized=CitationNormalization(so_hieu=number, ten_van_ban=title),
        extraction=CitationExtractionMetadata(status=status),
        evidence=[CitationPosition(doan_id="HD_T1_C1", page_start=1, page_end=1)],
    )


def profile(signed=date(2020, 1, 1), social=None):
    return ContractProfile(
        hop_dong_id="HD_T1",
        profile=ProfileFields(loai_hop_dong_id="MB_CAN_HO_CHUNG_CU", la_nha_o_xa_hoi=social),
        time_markers=[
            ProfileTimeMarker(
                moc_id="HD_T1_SIGNING", loai_moc="SIGNING", ngay=signed, trang_thai="EXTRACTED"
            )
        ],
    )


def validate(item, contract=None):
    [finding] = CatalogCitationValidator().validate(
        CONTEXT, contract or profile(), [item], KNOWLEDGE
    )
    return finding


def test_number_key_ignores_diacritics_case_and_spaces():
    assert number_key("99/2015/NĐ-CP") == number_key("99 / 2015 / nd-cp") == "99/2015/ND-CP"


def test_valid_at_signing_stays_valid_after_later_replacement():
    finding = validate(citation("65/2014/QH13", "Luật Nhà ở"), profile(date(2020, 1, 1)))
    assert (finding.status, finding.reason_code) == ("VALID", "IN_FORCE_AT_DATE")
    assert finding.normalized_van_ban_id == "LNO_2014"
    assert finding.domain_status == "MATCH"
    # Current status is reported separately and does not change the historical result.
    assert finding.current_status == "HISTORICAL"
    assert finding.replacement_van_ban_id == "LNO_2023"
    assert finding.finding_verified is True
    assert finding.finding_id == "CA_T1_LS2_CIT_FIND_00001"
    assert finding.relevant_date == date(2020, 1, 1)


def test_replaced_before_signing_is_stale():
    finding = validate(citation("65/2014/QH13", "Luật Nhà ở"), profile(date(2025, 1, 1)))
    assert (finding.status, finding.reason_code) == ("STALE", "REPLACED_BEFORE_DATE")


def test_not_yet_in_force_at_signing_is_invalid():
    finding = validate(citation("27/2023/QH15", "Luật Nhà ở"), profile(date(2020, 1, 1)))
    assert (finding.status, finding.reason_code) == ("INVALID", "NOT_YET_IN_FORCE_AT_DATE")


def test_partial_amendment_does_not_make_a_document_stale():
    assert validate(citation("02/2016/TT-BXD"), profile(date(2020, 1, 1))).status == "VALID"


def test_name_without_number_is_unknown_with_candidates():
    finding = validate(citation(title="Luật\n   nhà ở", status="AMBIGUOUS"))
    assert (finding.status, finding.reason_code) == (
        "UNKNOWN",
        "NAME_ONLY_VERSION_IDENTITY_AMBIGUOUS",
    )
    assert finding.normalized_van_ban_id is None
    candidates = finding.source_snapshot_json["checks"]["identity"]["candidates"]
    assert candidates == ["LNO_2014", "LNO_2023"]


def test_number_outside_catalog_is_unknown_not_invalid():
    finding = validate(citation("45/2013/QH13", "Luật Đất đai"))
    assert (finding.status, finding.reason_code) == ("UNKNOWN", "NUMBER_NOT_IN_CATALOG")


def test_number_cited_with_another_law_name_is_invalid():
    finding = validate(citation("65/2014/QH13", "Luật Kinh doanh bất động sản"))
    assert (finding.status, finding.reason_code) == ("INVALID", "NUMBER_TITLE_MISMATCH")


def test_short_form_of_the_law_name_is_not_a_mismatch():
    documents = {
        "BVNTD": {
            **DOCUMENTS["LNO_2014"],
            "van_ban_id": "BVNTD",
            "ten_van_ban": "Luật Bảo vệ quyền lợi người tiêu dùng",
            "so_hieu": "59/2010/QH12",
            "so_hieu_chuan": "59/2010/QH12",
            "linh_vuc": "BVNTD_2010",
        }
    }
    knowledge = SimpleNamespace(documents=documents, tables=KNOWLEDGE.tables)
    [finding] = CatalogCitationValidator().validate(
        CONTEXT, profile(), [citation("59/2010/QH12", "Luật Bảo vệ người tiêu dùng")], knowledge
    )
    assert finding.status == "VALID"


def test_social_housing_decree_depends_on_contract_social_housing_status():
    item = citation("100/2024/NĐ-CP")
    mismatch = validate(item, profile(date(2025, 1, 1), social=False))
    assert (mismatch.status, mismatch.reason_code, mismatch.domain_status) == (
        "INVALID",
        "DOMAIN_MISMATCH",
        "MISMATCH",
    )
    assert validate(item, profile(date(2025, 1, 1), social=True)).status == "VALID"
    unknown = validate(item, profile(date(2025, 1, 1), social=None))
    assert (unknown.status, unknown.domain_status) == ("VALID", "UNKNOWN")


def test_unknown_signing_date_is_unknown():
    finding = validate(citation("65/2014/QH13", "Luật Nhà ở"), profile(signed=None))
    assert (finding.status, finding.reason_code) == ("UNKNOWN", "RELEVANT_DATE_UNKNOWN")


def test_finding_is_unverified_without_verified_catalog_metadata():
    finding = validate(citation("27/2023/QH15", "Luật Nhà ở"), profile(date(2025, 1, 1)))
    assert finding.status == "VALID"
    assert finding.finding_verified is False


def test_citations_of_another_contract_are_rejected():
    other = citation("65/2014/QH13").model_copy(update={"hop_dong_id": "HD_OTHER"})
    with pytest.raises(ValueError, match="another contract"):
        CatalogCitationValidator().validate(CONTEXT, profile(), [other], KNOWLEDGE)
