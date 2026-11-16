"""Group A step 2: PDF text reader and structural chunker, without DB or network."""

import hashlib

import pytest
from legal_checker.modules.documents.chunker import chunk_document, extraction_version
from legal_checker.modules.documents.parser import (
    DOCX_MIME as DOCX,
)
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


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def docx_document(body: str) -> bytes:
    """A DOCX with the given w:body XML (only document.xml is needed to read the text)."""
    import io
    import zipfile

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(
            "word/document.xml",
            f'<w:document xmlns:w="{W_NS}"><w:body>{body}</w:body></w:document>',
        )
    return buffer.getvalue()


def para(*runs: str) -> str:
    return (
        "<w:p>"
        + "".join(f"<w:r><w:t xml:space='preserve'>{r}</w:t></w:r>" for r in runs)
        + "</w:p>"
    )


def test_docx_reader_reads_paragraphs_tables_and_page_breaks_in_order():
    body = (
        para("HỢP ĐỒNG MUA BÁN ", "CĂN HỘ CHUNG CƯ")
        + "<w:p><w:r><w:t>Điều 1.</w:t><w:tab/><w:t>Đối tượng</w:t></w:r></w:p>"
        + "<w:tbl><w:tr><w:tc>"
        + para("Giá bán")
        + "</w:tc><w:tc>"
        + para("2.000.000.000 đồng")
        + "</w:tc></w:tr></w:tbl>"
        + "<w:p><w:r><w:br w:type='page'/>"
        + "<w:t>Điều 2. Bàn giao căn hộ cho bên mua</w:t></w:r></w:p>"
        + "<w:p><w:r><w:delText>đã xóa</w:delText></w:r></w:p>"
        + "<w:sdt><w:sdtContent>"
        + para("Phụ lục 01 kèm theo hợp đồng")
        + "</w:sdtContent></w:sdt>"
    )
    content = docx_document(body)
    reader = PdfTextReader()
    document = reader.extract(content, DOCX)
    assert reader.parser_version == "docx-xml-1"
    assert document.source_sha256 == hashlib.sha256(content).hexdigest()
    assert [p.page_number for p in document.pages] == [1, 2]
    first, second = (p.text for p in document.pages)
    assert first.startswith("HỢP ĐỒNG MUA BÁN CĂN HỘ CHUNG CƯ\nĐiều 1.\tĐối tượng\n")
    assert "Giá bán\t2.000.000.000 đồng" in first
    assert second.startswith("Điều 2. Bàn giao căn hộ")
    assert "Phụ lục 01" in second and "đã xóa" not in second
    assert all(p.method == "TEXT" and p.readable for p in document.pages)


def test_docx_nested_table_is_read_once():
    inner = "<w:tbl><w:tr><w:tc>" + para("ô lồng bên trong") + "</w:tc></w:tr></w:tbl>"
    body = "<w:tbl><w:tr><w:tc>" + para("ô ngoài") + inner + "</w:tc></w:tr></w:tbl>"
    text = PdfTextReader().extract(docx_document(body), DOCX).pages[0].text
    assert text.count("ô lồng bên trong") == 1 and "ô ngoài" in text


@pytest.mark.parametrize(
    "content", [b"not a zip", docx_document("")[:30], b"PK\x05\x06" + b"\0" * 18]
)
def test_docx_reader_rejects_broken_files(content):
    with pytest.raises(UnsupportedDocumentError, match="Not a readable DOCX"):
        PdfTextReader().extract(content, DOCX)


def test_docx_reader_refuses_an_oversized_body(monkeypatch):
    from legal_checker.modules.documents import parser

    monkeypatch.setattr(parser, "MAX_DOCX_XML_BYTES", 10)
    with pytest.raises(UnsupportedDocumentError, match="too large"):
        PdfTextReader().extract(docx_document(para("x" * 50)), DOCX)


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
