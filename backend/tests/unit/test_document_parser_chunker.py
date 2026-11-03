"""Group A step 2: PDF text reader and structural chunker, without DB or network."""

import hashlib

import pytest
from legal_checker.modules.documents.chunker import chunk_document, extraction_version
from legal_checker.modules.documents.parser import (
    DocumentPage,
    DocumentText,
    PdfTextReader,
    UnsupportedDocumentError,
    _drop_repeated_copies,
)


def _document(*texts: str, unreadable: tuple[int, ...] = ()) -> DocumentText:
    pages = tuple(
        DocumentPage(number, text, "TEXT", number not in unreadable)
        for number, text in enumerate(texts, start=1)
    )
    return DocumentText("a" * 64, pages)


def _paths(document: DocumentText) -> list[str | None]:
    return [c.section_path for c in chunk_document(document, hop_dong_id="HD", version="v")]


# ---------------------------------------------------------------- parser


def _minimal_pdf(pages: list[str]) -> bytes:
    """PDF tối giản dựng tay (Helvetica, ASCII) để test không cần thư viện tạo PDF."""
    objects = ["<< /Type /Catalog /Pages 2 0 R >>"]
    kids = " ".join(f"{4 + 2 * i} 0 R" for i in range(len(pages)))
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>")
    objects.append("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    for i, text in enumerate(pages):
        lines = "".join(f"({line}) Tj 0 -16 Td " for line in text.split("\n"))
        stream = f"BT /F1 12 Tf 50 750 Td {lines}ET"
        objects.append(
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 3 0 R >> >> /Contents {5 + 2 * i} 0 R >>"
        )
        objects.append(f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream")
    out = b"%PDF-1.4\n"
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n{body}\nendobj\n".encode()
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    out += "".join(f"{offset:010d} 00000 n \n" for offset in offsets).encode()
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n".encode()
    out += f"startxref\n{xref}\n%%EOF".encode()
    return out


def test_pdf_reader_keeps_pages_hash_and_marks_unreadable_pages():
    content = _minimal_pdf(
        [
            "HOP DONG MUA BAN\nDieu 1. Doi tuong hop dong ban can ho so 12A",
            "",
            "Dieu 2. Gia ban\nCan cu Nghi dinh 95/2024/ND-CP ve nha o",
        ]
    )
    reader = PdfTextReader()
    document = reader.extract(content, "application/pdf")
    assert document.source_sha256 == hashlib.sha256(content).hexdigest()
    assert [p.page_number for p in document.pages] == [1, 2, 3]
    assert [p.readable for p in document.pages] == [True, False, True]
    assert "95/2024/ND-CP" in document.pages[2].text
    assert reader.parser_version and reader.parser_version.startswith("pypdf-")


def test_pdf_reader_rejects_other_mime_types():
    with pytest.raises(UnsupportedDocumentError):
        PdfTextReader().extract(b"%PDF-1.4", "application/msword")


def test_repeated_form_copies_are_reduced_to_one():
    page = "PHỤ LỤC I:\nDANH MỤC PHẦN SỞ HỮU CHUNG\nTrang 26\n"  # trang ngắn
    extra = "Số hợp đồng: TEST-062/2023/HDMB\n"
    assert _drop_repeated_copies(page * 2 + extra, 2) == page + extra
    assert _drop_repeated_copies(page * 3 + extra, 3) == page + extra


def test_text_that_does_not_repeat_is_kept_unchanged():
    text = "ĐIỀU 1. ĐỊNH NGHĨA\n" + "nội dung khác nhau " * 10
    assert _drop_repeated_copies(text, 2) == text
    assert _drop_repeated_copies(text, 1) == text


# ---------------------------------------------------------------- chunker

CONTRACT = """HỢP ĐỒNG MUA BÁN CĂN HỘ
Căn cứ Bộ luật Dân sự số 91/2015/QH13;
ĐIỀU 1: GIẢI THÍCH TỪ NGỮ
1. Căn hộ là căn hộ số 12A.
Điều 5 của Hợp đồng này nằm đầu dòng nhưng không phải tiêu đề.
ĐIỀU 2. GIÁ BÁN
Giá bán là 2.000.000.000 đồng.
"""
APPENDIX = """PHỤ LỤC 1 – ĐẶC ĐIỂM CĂN HỘ
I. ĐẶC ĐIỂM
PHỤ LỤC 8
NỘI QUY QUẢN LÝ SỬ DỤNG NHÀ CHUNG CƯ
ĐIỀU 1. PHẠM VI ÁP DỤNG
Bản nội quy này áp dụng cho Nhà chung cư.
PHỤ LỤC THÔNG TIN GIAO DỊCH
Số hợp đồng: TEST-070/2017/HDMB
"""


def test_chunks_follow_articles_and_appendices():
    assert _paths(_document(CONTRACT, APPENDIX)) == [
        "Mở đầu",
        "ĐIỀU 1",
        "ĐIỀU 2",
        "PHỤ LỤC 1",
        "PHỤ LỤC 8",
        "PHỤ LỤC 8 > ĐIỀU 1",
        "PHỤ LỤC",
    ]


def test_chunks_are_exact_slices_with_pages_and_hashes():
    document = _document(CONTRACT, APPENDIX)
    full = CONTRACT + "\n" + APPENDIX
    chunks = chunk_document(document, hop_dong_id="HD", version="v")
    for chunk in chunks:
        assert full[chunk.global_start : chunk.global_end] == chunk.noi_dung
        assert chunk.sha256 == hashlib.sha256(chunk.noi_dung.encode()).hexdigest()
        assert chunk.to_contract().noi_dung == chunk.noi_dung
    by_path = {c.section_path: c for c in chunks}
    assert by_path["ĐIỀU 2"].page_start == 1
    assert by_path["PHỤ LỤC 1"].page_start == 2


def test_table_of_contents_does_not_create_sections():
    toc = """MỤC LỤC
ĐIỀU 1. GIẢI THÍCH TỪ NGỮ.............................. 3
ĐIỀU 2. GIÁ BÁN.......................................10
PHỤ LỤC 7. DANH SÁCH CÁC HẠNG MỤC CHO DỊCH VỤ QUẢN LÝ
TÒA NHÀ ..............................................57
"""
    paths = _paths(_document(toc, CONTRACT))
    assert paths == ["Mở đầu", "ĐIỀU 1", "ĐIỀU 2"]  # ĐIỀU 2 không bị gán vào PHỤ LỤC 7


def test_unreadable_page_is_skipped_but_page_numbers_stay_correct():
    document = _document(CONTRACT, "■■■ trang lỗi ■■■", APPENDIX, unreadable=(2,))
    chunks = chunk_document(document, hop_dong_id="HD", version="v")
    assert all("■" not in c.noi_dung for c in chunks)
    assert {c.section_path: c for c in chunks}["PHỤ LỤC 1"].page_start == 3


def test_long_article_is_split_at_clause_boundaries():
    body = "ĐIỀU 9. DÀI\n" + "".join(f"{i}. " + "nội dung " * 30 + "\n" for i in range(1, 8))
    chunks = chunk_document(_document(body), hop_dong_id="HD", version="v", max_chars=600)
    assert len(chunks) > 1
    assert all(len(c.noi_dung) <= 600 for c in chunks)
    assert "".join(c.noi_dung for c in chunks) == body


def test_rerun_gives_same_ids_and_new_version_gives_new_ids():
    document = _document(CONTRACT, APPENDIX)
    version = extraction_version("a" * 64, "pypdf-test")
    first = [c.doan_id for c in chunk_document(document, hop_dong_id="HD", version=version)]
    again = [c.doan_id for c in chunk_document(document, hop_dong_id="HD", version=version)]
    other = extraction_version("b" * 64, "pypdf-test")
    changed = [c.doan_id for c in chunk_document(document, hop_dong_id="HD", version=other)]
    assert first == again
    assert set(first).isdisjoint(changed)
