"""Storage and PDF/DOCX/OCR adapters preserve page text and source hashes."""

import hashlib
import io
import logging
import unicodedata
from dataclasses import dataclass
from typing import Literal, Protocol

from legal_checker.modules.documents.ocr import DEFAULT_MAX_PAGES, OcrEngine, render_pages


@dataclass(frozen=True)
class DocumentPage:
    page_number: int
    text: str
    method: Literal["TEXT", "OCR"]
    readable: bool


@dataclass(frozen=True)
class DocumentText:
    source_sha256: str
    pages: tuple[DocumentPage, ...]


class DocumentReader(Protocol):
    def extract(self, content: bytes, mime_type: str) -> DocumentText: ...


class UnsupportedDocumentError(ValueError):
    """MIME type has no reader, or the bytes are not a readable file of that type."""


PDF_MIME = "application/pdf"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
DOCX_READER_VERSION = "docx-xml-1"
# document.xml of a long contract is a few MB; more than this is a zip bomb, not a contract.
MAX_DOCX_XML_BYTES = 64 * 1024 * 1024
_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _docx_paragraph(paragraph, pages: list[list[str]]) -> None:
    """Text of one w:p in reading order; an explicit page break starts a new page."""
    parts: list[str] = []
    for node in paragraph.iter():
        tag = node.tag
        if tag == _W + "t":
            parts.append(node.text or "")
        elif tag == _W + "tab":
            parts.append("\t")
        elif tag in (_W + "br", _W + "cr"):
            if node.get(_W + "type") == "page":
                pages[-1].append("".join(parts))
                pages.append([])
                parts = []
            else:
                parts.append("\n")
        elif tag == _W + "noBreakHyphen":
            parts.append("-")
    pages[-1].append("".join(parts))


def _docx_block(element, pages: list[list[str]]) -> None:
    """Body content in document order: paragraphs, tables (row by row), content controls."""
    for child in element:
        tag = child.tag
        if tag == _W + "p":
            _docx_paragraph(child, pages)
        elif tag == _W + "tbl":
            # Direct rows/cells only: a nested table is read once, through its cell's paragraphs.
            for row in child.findall(_W + "tr"):
                cells = []
                for cell in row.findall(_W + "tc"):
                    lines: list[list[str]] = [[]]
                    for paragraph in cell.iter(_W + "p"):
                        _docx_paragraph(paragraph, lines)
                    cells.append(" ".join(t for page in lines for t in page if t.strip()))
                pages[-1].append("\t".join(cells))
        elif tag in (_W + "sdt", _W + "sdtContent", _W + "customXml", _W + "smartTag"):
            _docx_block(child, pages)


def _raw_docx_pages(content: bytes) -> list[str]:
    """Body text of a DOCX (headers, footers and comments are not contract content)."""
    import zipfile
    from xml.etree import ElementTree

    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            info = archive.getinfo("word/document.xml")
            if info.file_size > MAX_DOCX_XML_BYTES:
                raise UnsupportedDocumentError("DOCX body is too large to be a contract")
            xml = archive.read(info)
        root = ElementTree.fromstring(xml)
    except (zipfile.BadZipFile, KeyError, ElementTree.ParseError) as error:
        raise UnsupportedDocumentError(f"Not a readable DOCX file: {error}") from error
    body = root.find(_W + "body")
    pages: list[list[str]] = [[]]
    if body is not None:
        _docx_block(body, pages)
    return ["\n".join(lines) for lines in pages]


# Trang có ít hơn ngưỡng này ký tự (bỏ khoảng trắng) coi như không đọc được:
# thường là trang scan cần OCR. Trang vẫn được giữ với readable=False.
MIN_READABLE_CHARS = 20
# Font lỗi khiến parser trả "■" hoặc "\ufffd" thay cho chữ có dấu.
# Quá ngưỡng này thì coi trang là không đọc được, không dùng làm evidence.
MAX_GARBLED_RATIO = 0.02
_GARBLED = ("\u25a0", "\ufffd")


def _normalize(text: str) -> str:
    # NFC một lần tại đây: mọi offset/quote phía sau đều tính trên text đã chuẩn hóa.
    return unicodedata.normalize("NFC", text.replace("\r\n", "\n").replace("\r", "\n"))


def _repeated_form_copies(page) -> int:
    """Số Form XObject trên trang cùng vẽ lại một nội dung con.

    Một số PDF (vd bộ dataset khi chèn thông tin giữa trang) chia trang thành nhiều
    khung; mỗi khung chứa *toàn bộ* trang gốc nhưng chỉ hiện phần trong ranh giới (BBox).
    pypdf bỏ qua BBox nên đọc text của trang gốc một lần cho mỗi khung.
    """
    resources = page.get("/Resources")
    xobjects = resources.get_object().get("/XObject") if resources else None
    if not xobjects:
        return 1
    targets: list[int] = []
    for ref in xobjects.get_object().values():
        form = ref.get_object()
        if form.get("/Subtype") != "/Form" or "/Resources" not in form:
            continue
        inner = form["/Resources"].get_object().get("/XObject")
        if inner and len(inner.get_object()) == 1:
            (target,) = inner.get_object().values()
            targets.append(getattr(target, "idnum", id(target)))
    return max((targets.count(t) for t in set(targets)), default=1)


def _drop_repeated_copies(text: str, copies: int) -> str:
    """Bỏ các bản lặp liền nhau ở đầu text: [T, T, ..., T, phần thêm] → [T, phần thêm]."""
    if copies < 2 or not text:
        return text
    # Mẫu dò phải ngắn hơn một bản sao (trang có thể rất ngắn); mỗi vị trí ứng viên
    # đều được kiểm tra lại toàn bộ các bản sao nên mẫu ngắn không gây cắt nhầm.
    probe = text[: min(16, len(text) // copies)]

    period = text.find(probe, 1)
    while period > 0:
        if all(text[i * period : (i + 1) * period] == text[:period] for i in range(copies)):
            return text[:period] + text[copies * period :]
        period = text.find(probe, period + 1)
    return text  # không khớp mẫu lặp: giữ nguyên, không đoán


def _raw_pdf_pages(content: bytes) -> tuple[str, list[str]]:
    """Trả (tên parser + version, text thô từng trang)."""
    from pypdf import PdfReader
    from pypdf import __version__ as pypdf_version

    # pypdf ghi rất nhiều cảnh báo "Skipping broken line" khi bảng font hơi lỗi,
    # dù vẫn đọc được chữ. Chỉ giữ mức ERROR trong lúc đọc, xong thì trả lại như cũ.
    logger = logging.getLogger("pypdf")
    previous_level = logger.level
    logger.setLevel(logging.ERROR)
    try:
        reader = PdfReader(io.BytesIO(content))
        pages = [
            _drop_repeated_copies(page.extract_text() or "", _repeated_form_copies(page))
            for page in reader.pages
        ]
    finally:
        logger.setLevel(previous_level)
    return f"pypdf-{pypdf_version}", pages


def _is_readable(text: str) -> bool:
    visible = "".join(text.split())
    garbled = sum(visible.count(ch) for ch in _GARBLED)
    return len(visible) >= MIN_READABLE_CHARS and garbled <= MAX_GARBLED_RATIO * len(visible)


class PdfTextReader:
    """DocumentReader cho PDF và DOCX. PDF: trang có lớp chữ đọc bằng pypdf; trang scan được
    OCR khi có ``ocr`` (không có thì giữ readable=False như trước). DOCX: đọc thân văn bản
    (đoạn, bảng) theo thứ tự; DOCX không có trang, chỉ ngắt trang tường minh mới tách trang."""

    def __init__(self, ocr: OcrEngine | None = None, *, max_ocr_pages: int = DEFAULT_MAX_PAGES):
        self.ocr = ocr
        self.max_ocr_pages = max_ocr_pages
        self.parser_version: str | None = None

    def extract(self, content: bytes, mime_type: str) -> DocumentText:
        mime = mime_type.partition(";")[0].strip().lower()
        if mime == DOCX_MIME:
            self.parser_version = DOCX_READER_VERSION
            pages = tuple(
                DocumentPage(number, text, "TEXT", _is_readable(text))
                for number, text in enumerate(
                    (_normalize(raw) for raw in _raw_docx_pages(content)), start=1
                )
            )
            return DocumentText(hashlib.sha256(content).hexdigest(), pages)
        if mime != PDF_MIME:
            raise UnsupportedDocumentError(f"No reader for MIME type {mime_type!r}")
        self.parser_version, raw_pages = _raw_pdf_pages(content)
        pages = []
        for number, raw in enumerate(raw_pages, start=1):
            text = _normalize(raw)
            pages.append(DocumentPage(number, text, "TEXT", _is_readable(text)))
        scanned = [p.page_number for p in pages if not p.readable][: self.max_ocr_pages]
        if self.ocr is not None and scanned:
            for number, png in render_pages(content, scanned):
                text = _normalize(self.ocr.recognize(png)).strip("\n")
                pages[number - 1] = DocumentPage(number, text, "OCR", _is_readable(text))
            # Kết quả phụ thuộc engine OCR → version trích xuất (và mọi ID) đổi theo.
            self.parser_version += f"+{self.ocr.version}"
        return DocumentText(hashlib.sha256(content).hexdigest(), tuple(pages))
