"""Storage and PDF/DOCX/OCR adapters preserve page text and source hashes."""

import hashlib
import io
import logging
import unicodedata
from dataclasses import dataclass
from typing import Literal, Protocol


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
    """MIME type has no reader yet (DOCX/OCR are planned)."""


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
    """DocumentReader cho PDF có text layer. Chưa OCR: trang scan có readable=False."""

    def __init__(self) -> None:
        self.parser_version: str | None = None

    def extract(self, content: bytes, mime_type: str) -> DocumentText:
        if mime_type.partition(";")[0].strip().lower() != "application/pdf":
            raise UnsupportedDocumentError(f"No reader for MIME type {mime_type!r}")
        self.parser_version, raw_pages = _raw_pdf_pages(content)
        pages = []
        for number, raw in enumerate(raw_pages, start=1):
            text = _normalize(raw)
            pages.append(DocumentPage(number, text, "TEXT", _is_readable(text)))
        return DocumentText(hashlib.sha256(content).hexdigest(), tuple(pages))
