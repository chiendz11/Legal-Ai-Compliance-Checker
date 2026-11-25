"""Group A step 1: OCR fills in scanned pages; text-layer pages are never re-read."""

import io

import pytest
from legal_checker.core.config import Settings
from legal_checker.modules.documents import ocr
from legal_checker.modules.documents.chunker import chunk_document
from legal_checker.modules.documents.ocr import OcrUnavailableError, build_ocr_engine
from legal_checker.modules.documents.parser import PdfTextReader
from unit.test_document_parser_chunker import _minimal_pdf

pytest.importorskip("pypdfium2")

TEXT_PAGE = "HOP DONG MUA BAN\nDieu 1. Doi tuong hop dong ban can ho so 12A"
OCR_TEXT = "HỢP ĐỒNG MUA BÁN CĂN HỘ\nĐiều 2. Giá bán căn hộ là 2.000.000.000 đồng\n"


class FakeOcr:
    version = "fake-ocr-1"

    def __init__(self, text=OCR_TEXT):
        self.text = text
        self.images: list[bytes] = []

    def recognize(self, png: bytes) -> str:
        self.images.append(png)
        return self.text


def test_only_scanned_pages_are_ocred_and_marked():
    engine = FakeOcr()
    reader = PdfTextReader(engine)
    document = reader.extract(_minimal_pdf([TEXT_PAGE, ""]), "application/pdf")
    first, second = document.pages
    assert (first.method, first.readable) == ("TEXT", True)
    assert "HOP DONG MUA BAN" in first.text
    assert (second.method, second.readable) == ("OCR", True)
    assert second.text == OCR_TEXT.strip("\n")
    assert len(engine.images) == 1 and engine.images[0].startswith(b"\x89PNG")
    assert reader.parser_version.endswith("+fake-ocr-1")
    chunks = chunk_document(document, hop_dong_id="HD", version="v")
    assert any("Giá bán căn hộ" in c.noi_dung and c.page_start == 2 for c in chunks)


def test_without_engine_or_scanned_pages_nothing_changes():
    plain = PdfTextReader()
    scanned = plain.extract(_minimal_pdf([""]), "application/pdf").pages[0]
    assert (scanned.method, scanned.readable) == ("TEXT", False)
    engine = FakeOcr()
    reader = PdfTextReader(engine)
    reader.extract(_minimal_pdf([TEXT_PAGE]), "application/pdf")
    assert engine.images == []
    assert "+" not in reader.parser_version  # same extraction IDs as before OCR existed


def test_ocr_output_that_is_still_unreadable_stays_unreadable_and_page_limit_holds():
    engine = FakeOcr(text="  \n")
    reader = PdfTextReader(engine, max_ocr_pages=2)
    pages = reader.extract(_minimal_pdf(["", "", ""]), "application/pdf").pages
    assert [(p.method, p.readable) for p in pages] == [
        ("OCR", False),
        ("OCR", False),
        ("TEXT", False),
    ]
    assert len(engine.images) == 2


def test_engine_selection(monkeypatch):
    assert build_ocr_engine("off") is None
    with pytest.raises(ValueError, match="DOCUMENT_OCR"):
        build_ocr_engine("cloud")
    monkeypatch.setattr(ocr, "_candidates", lambda command: [])
    assert build_ocr_engine("auto") is None  # missing Tesseract: keep the old behaviour
    with pytest.raises(OcrUnavailableError, match="Tesseract is not installed"):
        build_ocr_engine("tesseract")


def _real_engine():
    settings = Settings.from_env()
    engine = build_ocr_engine(
        "auto", command=settings.tesseract_cmd, tessdata_dir=settings.tessdata_dir
    )
    if engine is None:
        pytest.skip("Tesseract with Vietnamese data is not installed")
    return engine


def _scanned_pdf(lines: list[str]) -> bytes:
    """Image-only PDF (no text layer), like a phone scan of a printed contract."""
    from PIL import Image, ImageDraw, ImageFont

    font = None
    for name in ("arial.ttf", "DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        try:
            font = ImageFont.truetype(name, 40)
            break
        except OSError:
            continue
    if font is None:
        pytest.skip("No Unicode TTF font to draw Vietnamese text")
    image = Image.new("L", (1700, 2200), 255)
    draw = ImageDraw.Draw(image)
    for i, line in enumerate(lines):
        draw.text((120, 150 + 70 * i), line, font=font, fill=0)
    buffer = io.BytesIO()
    image.save(buffer, format="PDF", resolution=200)
    return buffer.getvalue()


def test_tesseract_reads_a_vietnamese_scan():
    engine = _real_engine()
    content = _scanned_pdf(
        [
            "HỢP ĐỒNG MUA BÁN CĂN HỘ CHUNG CƯ",
            "Hôm nay, ngày 01 tháng 11 năm 2026, tại Hà Nội",
            "Điều 2. Giá bán căn hộ là 3.200.000.000 đồng",
        ]
    )
    reader = PdfTextReader(engine)
    (page,) = reader.extract(content, "application/pdf").pages
    assert (page.method, page.readable) == ("OCR", True)
    text = " ".join(page.text.split())
    for expected in ("HỢP ĐỒNG MUA BÁN", "ngày 01 tháng 11 năm 2026", "Điều 2", "3.200.000.000"):
        assert expected in text, (expected, text)
    assert reader.parser_version.split("+")[1].startswith("tesseract-")
