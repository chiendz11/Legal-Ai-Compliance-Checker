"""Group A step 2: C02 profile extraction with evidence, conflicts and unknowns."""

import json
from datetime import date
from decimal import Decimal

from legal_checker.modules.documents.chunker import chunk_document
from legal_checker.modules.documents.parser import DocumentPage, DocumentText
from legal_checker.modules.documents.profile_extractor import extract_profile
from legal_checker.shared.contracts.assessment import AssessmentCase, SourceDocument
from legal_checker.shared.contracts.common import DeploymentPin
from legal_checker.shared.contracts.document_intelligence import DocumentIntelligenceResult
from legal_checker.workflows.handoffs import validate_document

HD = "HD_TEST"

BODY = """CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM
HỢP ĐỒNG MUA BÁN CĂN HỘ CHUNG CƯ
Căn cứ Luật Kinh doanh Bất động sản số 66/2014/QH13;
Căn cứ các quy định hiện hành khác của pháp luật Việt Nam;
BÊN BÁN NHÀ Ở (sau đây gọi tắt là Bên Bán):
TỔNG CÔNG TY CỔ PHẦN THƯƠNG MẠI XÂY DỰNG
Mã số doanh nghiệp: 0100203476
ĐIỀU 1. GIẢI THÍCH TỪ NGỮ
1. “Chủ đầu tư”, “Bên Bán” là Tổng Công ty Cổ phần Thương mại Xây dựng.
ĐIỀU 2. ĐẶC ĐIỂM CĂN HỘ
Bảo lãnh trong trường hợp bán nhà ở hình thành trong tương lai.
3. Mục đích sử dụng Căn hộ: Dùng để ở.
"""
APPENDIX = """PHỤ LỤC THÔNG TIN GIAO DỊCH
Ngày giao kết: 2017-02-16
Họ tên bên mua: Phan Gia Trâm
Căn hộ: TEST-A3-121
Diện tích sử dụng: 62.4 m²
Giá bán căn hộ theo phạm vi thuế/phí: 1.996.800.000 VND
Ngày bàn giao dự kiến: 2017-12-30
"""


def _profile(*pages: str):
    document = DocumentText(
        "a" * 64, tuple(DocumentPage(i, t, "TEXT", True) for i, t in enumerate(pages, 1))
    )
    chunks = chunk_document(document, hop_dong_id=HD, version="v")
    return chunks, extract_profile(chunks, hop_dong_id=HD, version="v")


def _facts(profile):
    return {f.ten_truong: f for f in profile.facts}


def _validate(chunks, profile):
    case = AssessmentCase(
        ca_id="CA_TEST",
        hop_dong_id=HD,
        source=SourceDocument(
            tep_id="TEP", object_uri="x://HD.pdf", mime_type="application/pdf", sha256="a" * 64
        ),
        assessment_context={"ngay_danh_gia": date(2026, 11, 3)},
        deployment=DeploymentPin(phien_ban_id="P", rule_version="R", legal_knowledge_version="L"),
        tenant_id="T",
        created_by="dev",
    )
    validate_document(
        case,
        DocumentIntelligenceResult(
            contract_profile=profile, chunks=[c.to_contract() for c in chunks], citations=[]
        ),
    )


def test_full_contract_profile_matches_expected_values():
    chunks, result = _profile(BODY, APPENDIX)
    p = result.profile
    assert (p.ngay_giao_ket, p.do_chinh_xac_ngay, p.loai_moc_ap_dung) == (
        date(2017, 2, 16),
        "DAY",
        "NGAY_GIAO_KET",
    )
    assert p.ngay_ban_giao_du_kien == date(2017, 12, 30)
    assert (p.gia_tri_hop_dong, p.don_vi_tien) == (Decimal("1996800000"), "VND")
    assert (p.loai_hop_dong_id, p.doi_tuong, p.he_phap_luat) == (
        "MB_CAN_HO_CHUNG_CU",
        "NHA_O",
        "VIET_NAM",
    )
    assert (p.tinh_trang_tai_san, p.che_do_giao_dich, p.muc_dich_su_dung_can_ho) == (
        "HINH_THANH_TRONG_TUONG_LAI",
        "KINH_DOANH_BDS",
        "DE_O",
    )
    assert (p.ben_ban_la_ca_nhan, p.ben_mua_la_ca_nhan, p.ben_ban_la_chu_dau_tu) == (
        False,
        True,
        True,
    )
    assert p.quan_he_chu_the == "DOANH_NGHIEP_VA_CA_NHAN"
    assert p.ben_ban_co_von_nuoc_ngoai is None  # không có bằng chứng thì không đoán
    assert {(s.vai_tro, s.ten_chu_the) for s in result.subjects} == {
        ("BEN_BAN", "TỔNG CÔNG TY CỔ PHẦN THƯƠNG MẠI XÂY DỰNG"),
        ("BEN_MUA", "Phan Gia Trâm"),
    }
    signing = next(m for m in result.time_markers if m.loai_moc == "SIGNING")
    assert (signing.ngay, signing.duoc_dung_phan_giai) == (date(2017, 2, 16), True)
    _validate(chunks, result)
    json.dumps(result.model_dump(mode="json"))  # ghi được vào cột JSON


def test_every_fact_points_to_an_exact_quote():
    chunks, result = _profile(BODY, APPENDIX)
    text = {c.doan_id: c.noi_dung for c in chunks}
    for evidence in result.evidence:
        quote = text[evidence.doan_id][evidence.ky_tu_bat_dau : evidence.ky_tu_ket_thuc]
        assert quote == evidence.trich_dan
    assert _facts(result)["profile.ngay_giao_ket"].gia_tri_raw == "Ngày giao kết: 2017-02-16"
    assert all(not f.human_verified for f in result.facts)


def test_blank_template_fields_stay_unknown():
    chunks, result = _profile(
        "HỢP ĐỒNG MUA BÁN CĂN HỘ\nNgày giao kết: ……………\nHọ tên bên mua: ..............\n"
    )
    assert result.profile.ngay_giao_ket is None
    assert result.subjects == []
    signing = next(m for m in result.time_markers if m.loai_moc == "SIGNING")
    assert (signing.trang_thai, signing.duoc_dung_phan_giai) == ("UNKNOWN", False)
    _validate(chunks, result)


def test_year_only_signing_date_is_not_turned_into_a_full_date():
    chunks, result = _profile("HỢP ĐỒNG MUA BÁN CĂN HỘ\nNgày ký (năm): 2023\n")
    p = result.profile
    assert p.ngay_giao_ket is None
    assert (p.ngay_giao_ket_raw, p.do_chinh_xac_ngay) == ("2023", "YEAR")
    _validate(chunks, result)


def test_different_prices_are_kept_as_conflict():
    chunks, result = _profile(APPENDIX, "PHỤ LỤC 3\nGiá bán căn hộ: 2.100.000.000 VND\n")
    assert result.profile.gia_tri_hop_dong is None
    fact = _facts(result)["gia_ban"]
    assert fact.trang_thai == "CONFLICT"
    assert len(fact.gia_tri_chuan_json) == 2 and len(fact.evidence_ids) == 2
    _validate(chunks, result)


def test_wrapped_overlay_text_is_not_a_conflict():
    _, result = _profile(APPENDIX, "Họ tên bên mua: Phan\nGia Trâm\n")
    fact = _facts(result)["ten_ben_mua"]
    assert (fact.trang_thai, fact.gia_tri_chuan_json) == ("EXTRACTED", "Phan Gia Trâm")


def test_land_use_purpose_is_not_apartment_purpose():
    _, result = _profile("6. Mục đích sử dụng:\nĐất ở (xây dựng chung cư): 8.368,5 m2\n")
    assert result.profile.muc_dich_su_dung_can_ho is None
