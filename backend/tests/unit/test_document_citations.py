"""Group A step 2: C03 extraction of contract-authored legal citations."""

from datetime import date

from legal_checker.modules.documents.chunker import chunk_document
from legal_checker.modules.documents.citation_extractor import extract_citations
from legal_checker.modules.documents.parser import DocumentPage, DocumentText
from legal_checker.shared.contracts.assessment import AssessmentCase, SourceDocument
from legal_checker.shared.contracts.common import DeploymentPin
from legal_checker.shared.contracts.document_intelligence import (
    ContractProfile,
    DocumentIntelligenceResult,
    ProfileFields,
)
from legal_checker.workflows.handoffs import validate_document

HD = "HD_TEST"


def _citations(*pages: str):
    document = DocumentText(
        "a" * 64, tuple(DocumentPage(i, t, "TEXT", True) for i, t in enumerate(pages, 1))
    )
    chunks = chunk_document(document, hop_dong_id=HD, version="v")
    return chunks, extract_citations(chunks, version="v")


def _by_so_hieu(records):
    return {r.so_hieu: r for r in records if r.so_hieu}


def test_number_and_name_are_merged_into_one_citation():
    _, records = _citations(
        "Căn cứ Bộ luật dân sự số 91/2015/QH13;\n"
        "Căn cứ Luật Kinh Doanh Bất Động Sản số 66/2014/QH13 ngày 25/11/2014;\n"
        "Căn cứ Nghị định số 99/2015/NĐ-CP;\n"
        "Căn cứ Thông tư 02/2016/TT-BXD;\n"
    )
    by_so = _by_so_hieu(records)
    assert set(by_so) == {"91/2015/QH13", "66/2014/QH13", "99/2015/NĐ-CP", "02/2016/TT-BXD"}
    assert (by_so["91/2015/QH13"].loai_van_ban, by_so["91/2015/QH13"].ten_van_ban) == (
        "Bộ luật",
        "Bộ luật dân sự",
    )
    assert by_so["66/2014/QH13"].ten_van_ban == "Luật Kinh Doanh Bất Động Sản"
    assert by_so["99/2015/NĐ-CP"].loai_van_ban == "Nghị định"
    assert by_so["02/2016/TT-BXD"].loai_van_ban == "Thông tư"
    assert all(r.status == "EXTRACTED" and r.nam for r in by_so.values())


def test_contract_numbers_and_generic_law_phrases_are_not_citations():
    _, records = _citations(
        "Hợp đồng số TEST-070/2017/HDMB.\n"
        "Các Bên tuân thủ pháp Luật Việt Nam và quy định của pháp luật hiện hành.\n"
        "Luật sư của Bên Mua có mặt.\n"
    )
    assert records == []


def test_name_stops_before_the_rest_of_the_sentence():
    _, records = _citations("Theo quy định của Luật Nhà ở và theo thỏa thuận của các Bên.\n")
    (record,) = records
    assert (record.ten_van_ban, record.status, record.nam) == ("Luật Nhà ở", "AMBIGUOUS", None)


def test_law_with_year_and_article_reference():
    _, records = _citations(
        "Theo Khoản 1 Điều 55 của Luật Kinh doanh bất động sản 2014, Bên Bán bảo lãnh.\n"
    )
    (record,) = records
    assert record.ten_van_ban == "Luật Kinh doanh bất động sản"
    assert (record.nam, record.dieu, record.khoan, record.status) == (2014, "55", "1", "EXTRACTED")
    assert record.raw_text.startswith("Khoản 1 Điều 55")


def test_name_wrapped_onto_next_line_is_kept_whole():
    _, records = _citations("Căn cứ Luật Kinh\nDoanh Bất Động Sản số 66/2014/QH13;\n")
    (record,) = records
    assert record.ten_van_ban == "Luật Kinh Doanh Bất Động Sản"


def test_repeated_mentions_are_grouped_with_exact_quotes():
    chunks, records = _citations(
        "ĐIỀU 1. CĂN CỨ\nTheo Luật Nhà ở.\nĐIỀU 2. BẢO TRÌ\nTheo Luật Nhà ở.\n"
    )
    (record,) = records
    assert len(record.mentions) == 2
    text = {c.doan_id: c.noi_dung for c in chunks}
    assert all(text[m.doan_id][m.start : m.end] == m.quote for m in record.mentions)
    assert len(record.to_contract().evidence) == 2


def test_unknown_future_document_is_still_extracted():
    _, records = _citations("Theo Nghị định 999/2099/NĐ-CP.\n")
    (record,) = records
    assert (record.so_hieu, record.status) == ("999/2099/NĐ-CP", "EXTRACTED")


def test_output_validates_as_document_intelligence_result():
    chunks, records = _citations(
        "Căn cứ Bộ luật dân sự số 91/2015/QH13;\nĐIỀU 1. GIÁ\nTheo Luật Nhà ở.\n"
    )
    case = AssessmentCase(
        ca_id="CA_TEST",
        hop_dong_id=HD,
        source=SourceDocument(
            tep_id="TEP", object_uri="x://HD.pdf", mime_type="application/pdf", sha256="a" * 64
        ),
        assessment_context={"ngay_danh_gia": date(2026, 11, 2)},
        deployment=DeploymentPin(phien_ban_id="P", rule_version="R", legal_knowledge_version="L"),
        tenant_id="T",
        created_by="dev",
    )
    result = DocumentIntelligenceResult(
        contract_profile=ContractProfile(hop_dong_id=HD, profile=ProfileFields()),
        chunks=[c.to_contract() for c in chunks],
        citations=[r.to_contract() for r in records],
    )
    validate_document(case, result)
