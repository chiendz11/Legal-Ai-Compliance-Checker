"""Group A step 2: C02 profile extraction with evidence, conflicts and unknowns."""

import json
from datetime import date
from decimal import Decimal

import pytest
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


def test_seller_name_after_label_prefix_is_found():
    _, result = _profile(
        "BÊN BÁN NHÀ Ở (sau đây gọi tắt là Bên Bán)3:\n"
        "- Công ty: CÔNG TY CỔ PHẦN PHÁT TRIỂN ĐÔ THỊ QUỐC TẾ VIỆT NAM  \n"
        "(viết tắt là “VIDC”)\n",
        "BÊN BÁN NHÀ Ở (BÊN BÁN)\nTên Công ty: Công ty Cổ phần HBI\n",
    )
    (seller,) = [s for s in result.subjects if s.vai_tro == "BEN_BAN"]
    assert seller.ten_chu_the == "CÔNG TY CỔ PHẦN PHÁT TRIỂN ĐÔ THỊ QUỐC TẾ VIỆT NAM"
    assert result.profile.ben_ban_la_ca_nhan is False


def test_seller_heading_with_roman_numeral_or_name_on_same_line():
    _, roman = _profile(
        "I. BÊN BÁN CĂN HỘ CHUNG CƯ (sau đây gọi tắt là “Bên Bán”):\n"
        "CÔNG TY CỔ PHẦN TRUNG THỦY LANCASTER \n"
        "Giấy chứng nhận đăng ký doanh nghiệp số: 0312586710\n"
    )
    _, same_line = _profile(
        "BÊN BÁN: CÔNG TY CỔ PHẦN BẤT ĐỘNG SẢN ĐẦU TƯ VÀ PHÁT TRIỂN CAO ỐC  \n"
        "THIÊN LONG\n"
        "Giấy chứng nhận ĐKDN : 3703021584\n"
    )
    assert [s.ten_chu_the for s in roman.subjects] == ["CÔNG TY CỔ PHẦN TRUNG THỦY LANCASTER"]
    assert [s.ten_chu_the for s in same_line.subjects] == [
        "CÔNG TY CỔ PHẦN BẤT ĐỘNG SẢN ĐẦU TƯ VÀ PHÁT TRIỂN CAO ỐC THIÊN LONG"
    ]


def test_seller_heading_after_party_letter_and_title_case_company():
    _, letter = _profile(
        "I. BÊN A: BÊN BÁN NHÀ Ở (sau đây gọi tắt là Bên Bán): \nCÔNG TY CỔ PHẦN THÀNH PHỐ XANH  \n"
    )
    _, title_case = _profile(
        "I. BÊN BÁN CĂN HỘ CHUNG CƯ (sau đây gọi tắt là Bên bán):\n"
        "- Tên tổ chức, cá nhân: Công Ty TNHH Đầu Tư Xây Dựng Minh Hưng.\n"
    )
    assert [s.ten_chu_the for s in letter.subjects] == ["CÔNG TY CỔ PHẦN THÀNH PHỐ XANH"]
    assert [s.ten_chu_the for s in title_case.subjects] == [
        "Công Ty TNHH Đầu Tư Xây Dựng Minh Hưng."
    ]


SELLER = "I. BÊN BÁN CĂN HỘ (“Bên Bán”):\nCÔNG TY CỔ PHẦN ĐẦU TƯ BẤT ĐỘNG SẢN SIC\n"


@pytest.mark.parametrize(
    "text",
    [
        "“Nhà Chung Cư” là nhà chung cư nơi có Căn Hộ do Bên Bán làm chủ đầu tư.",
        "“Dự Án” là dự án do Công ty Cổ phần Đầu Tư Bất  \nĐộng Sản SIC là chủ đầu tư.",
    ],
)
def test_seller_is_investor_when_the_contract_says_so(text):
    _, result = _profile(SELLER + text)
    assert result.profile.ben_ban_la_chu_dau_tu is True
    assert _facts(result)["profile.ben_ban_la_chu_dau_tu"].evidence_ids


def test_another_company_as_investor_says_nothing_about_the_seller():
    _, result = _profile(SELLER + "“Dự Án” do Công ty Cổ phần Khác Hẳn làm chủ đầu tư.")
    assert result.profile.ben_ban_la_chu_dau_tu is None


def test_social_housing_title_and_home_purpose_variants():
    _, social = _profile("HỢP ĐỒNG MUA BÁN NHÀ Ở XÃ HỘI\nCĂN HỘ CHUNG CƯ CÔNG ĐOÀN\n")
    assert social.profile.la_nha_o_xa_hoi is True
    for line in (
        "Mục đích sử dụng Căn Hộ: chỉ dùng để ở.",
        "e) Mục đích sử dụng Căn Hộ: Dùng làm nhà ở.",
    ):
        _, result = _profile(line)
        assert result.profile.muc_dich_su_dung_can_ho == "DE_O"


def _signing(result):
    return next(m for m in result.time_markers if m.loai_moc == "SIGNING")


def test_signing_date_is_read_from_the_opening_sentence():
    chunks, result = _profile(
        "HỢP ĐỒNG MUA BÁN CĂN HỘ CHUNG CƯ\n"
        "Hôm nay, ngày 01 tháng 11 năm 2026, tại Hà Nội, chúng tôi gồm:\n"
    )
    p = result.profile
    assert (p.ngay_giao_ket, p.do_chinh_xac_ngay, p.loai_moc_ap_dung) == (
        date(2026, 11, 1),
        "DAY",
        "NGAY_GIAO_KET",
    )
    assert p.ngay_giao_ket_raw == "ngày 01 tháng 11 năm 2026"
    fact = _facts(result)["profile.ngay_giao_ket"]
    assert (fact.trang_thai, fact.phuong_phap) == ("EXTRACTED", "PHRASE_REGEX")
    assert fact.gia_tri_raw == "Hôm nay, ngày 01 tháng 11 năm 2026"
    assert (_signing(result).ngay, _signing(result).duoc_dung_phan_giai) == (
        date(2026, 11, 1),
        True,
    )
    _validate(chunks, result)


def test_signing_sentence_variants():
    cases = {
        "Hôm nay là ngày 5/3/2024 tại TP. Hồ Chí Minh": date(2024, 3, 5),
        "Hợp đồng này được lập vào ngày 12 tháng 7 năm 2023": date(2023, 7, 12),
        "Hợp đồng này được ký kết ngày 20\ntháng 01 năm 2022, gồm 10 điều": date(2022, 1, 20),
    }
    for text, expected in cases.items():
        assert _profile(f"HỢP ĐỒNG\n{text}\n")[1].profile.ngay_giao_ket == expected, text


def test_dates_that_are_not_the_signing_sentence_are_ignored():
    for text in (
        "Hà Nội, ngày 01 tháng 11 năm 2026",  # ngày soạn thảo ở đầu văn bản
        "theo Hợp đồng góp vốn được ký ngày 10 tháng 5 năm 2020",  # hợp đồng khác
        "Hôm nay, ngày ..... tháng ..... năm 20.....",  # mẫu trống
        "Hôm nay, ngày 31 tháng 02 năm 2026",  # ngày không tồn tại
    ):
        chunks, result = _profile(f"HỢP ĐỒNG MUA BÁN CĂN HỘ\n{text}\n")
        assert result.profile.ngay_giao_ket is None, text
        assert _signing(result).duoc_dung_phan_giai is False
        _validate(chunks, result)


def test_signing_sentence_agrees_with_label_or_is_a_conflict():
    same = "Hôm nay, ngày 16 tháng 02 năm 2017, tại Hà Nội"
    _, agree = _profile(BODY + same, APPENDIX)
    assert agree.profile.ngay_giao_ket == date(2017, 2, 16)
    assert _facts(agree)["ngay_giao_ket"].evidence_ids[1:]  # nhãn + câu đều là bằng chứng

    _, conflict = _profile(BODY + "Hôm nay, ngày 20 tháng 3 năm 2018", APPENDIX)
    assert conflict.profile.ngay_giao_ket is None
    fact = _facts(conflict)["ngay_giao_ket"]
    assert fact.trang_thai == "CONFLICT"
    assert fact.gia_tri_chuan_json == ["2017-02-16", "2018-03-20"]
    assert _signing(conflict).duoc_dung_phan_giai is False
