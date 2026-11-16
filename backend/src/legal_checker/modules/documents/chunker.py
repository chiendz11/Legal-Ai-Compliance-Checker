"""Chunk creation with page and character provenance (Phụ lục/Phần/Chương/Điều, rồi khoản).

- ``noi_dung`` luôn là lát cắt nguyên văn của text parser trả về (không strip/sửa),
  để quote/offset ở bước sau khớp tuyệt đối.
- ID tất định theo (hop_dong_id, extraction_version, thu_tu): chạy lại cùng
  version cho cùng ID; đổi tệp/parser/chunker thì đổi version (mục 8.4).
"""

import bisect
import hashlib
import re
from dataclasses import dataclass

from legal_checker.modules.documents.citation_spans import find_citation_spans
from legal_checker.modules.documents.parser import DocumentText
from legal_checker.shared.contracts.document_intelligence import Chunk

CHUNKER_VERSION = "structural-sentences-v2"

# Tiêu đề đứng đầu dòng. Phần/Chương/Điều phải theo sau bởi dấu chấm/hai chấm/gạch
# hoặc hết dòng, nên "Điều 5 của Hợp đồng này" ở đầu dòng không bị bắt.
# "PHỤ LỤC" chỉ nhận dạng chữ in hoa (vd "PHỤ LỤC 1 – ĐẶC ĐIỂM", "PHỤ LỤC THÔNG TIN...").
_HEADING = re.compile(
    r"^[ \t]*(?:"
    r"(?P<phu_luc>PHỤ[ \t]+LỤC(?:[ \t]+(?:SỐ[ \t]+)?(?:\d+|[IVXLC]+)\b)?)"
    r"|(?:"
    r"(?P<phan>(?:PHẦN|Phần)[ \t]+(?:[IVXLC]+|\d+|THỨ[ \t]+\S+))"
    r"|(?P<chuong>(?:CHƯƠNG|Chương)[ \t]+(?:[IVXLC]+|\d+))"
    r"|(?P<dieu>(?:ĐIỀU|Điều)[ \t]+\d+[a-z]?)"
    r")(?=[ \t]*(?:[.:\u2013\u2014-]|\n|$))"
    r")",
    re.MULTILINE,
)
# Dòng mục lục: tiêu đề + dãy chấm dẫn + số trang ở cuối dòng ("ĐIỀU 2. MỤC ĐÍCH.....10").
_TOC_TAIL = re.compile(r"(?:\.{4,}|\u2026{2,})[ \t]*\d{1,4}[ \t]*$")
# Điểm cắt phụ khi một Điều quá dài: dòng bắt đầu "1." / "2)" / "a)" hoặc dòng trống.
_SUB_BREAK = re.compile(
    r"(?m)^(?=[ \t]*(?:\d{1,2}[.)]|\d{1,2}(?:\.\d{1,2})+\.?|[a-zđ]\))[ \t])|\n[ \t]*\n"
)
# Sentence boundaries never split decimals, enumerators or dotted document numbers.
_SENTENCE_END = re.compile(r"[.!?;][\"”’)]*\s+")
_CONTINUATION = re.compile(
    r"(?:trừ\s+(?:trường\s+hợp|khi)|ngoại\s+trừ|với\s+điều\s+kiện|"
    r"tuy\s+nhiên|và\s+với\s+điều\s+kiện)\b",
    re.I,
)
_ABBREVIATIONS = {"tp", "q", "p", "stt", "ts", "ths", "pgs", "gs", "v.v"}


@dataclass(frozen=True)
class ChunkRecord:
    """Một chunk kèm metadata cho bảng doan_hop_dong (C02 Chunk chỉ nhận một phần)."""

    doan_id: str
    hop_dong_id: str
    thu_tu: int
    page_start: int
    page_end: int
    section_path: str | None
    noi_dung: str
    sha256: str
    global_start: int  # vị trí trong text đã ghép của cả tài liệu
    global_end: int
    section_start: int = 0
    section_end: int = 0
    split_reason: str = "STRUCTURAL_ELEMENT"

    def to_contract(self) -> Chunk:
        return Chunk(
            doan_id=self.doan_id,
            hop_dong_id=self.hop_dong_id,
            noi_dung=self.noi_dung,
            page_start=self.page_start,
            page_end=self.page_end,
        )


def extraction_version(source_sha256: str, parser_version: str, *, max_chars: int = 1800) -> str:
    raw = f"{source_sha256}|{parser_version}|{CHUNKER_VERSION}|target-chars={max_chars}"
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


def join_pages(document: DocumentText) -> tuple[str, list[int], list[int]]:
    """Ghép trang bằng '\\n'; trang không đọc được giữ chỗ rỗng để số trang không lệch."""
    parts: list[str] = []
    starts: list[int] = []
    numbers: list[int] = []
    cursor = 0
    for page in sorted(document.pages, key=lambda p: p.page_number):
        if parts:
            parts.append("\n")
            cursor += 1
        text = page.text if page.readable else ""
        starts.append(cursor)
        numbers.append(page.page_number)
        parts.append(text)
        cursor += len(text)
    return "".join(parts), starts, numbers


def _page_at(offset: int, starts: list[int], numbers: list[int]) -> int:
    return numbers[max(bisect.bisect_right(starts, offset) - 1, 0)]


def _line_at(text: str, start: int) -> tuple[str, int]:
    """Trả (dòng bắt đầu từ ``start``, vị trí ký tự xuống dòng kết thúc dòng đó)."""
    end = text.find("\n", start)
    end = len(text) if end == -1 else end
    return text[start:end], end


def _is_toc_entry(text: str, match: re.Match[str]) -> bool:
    """Tiêu đề nằm trong mục lục: dòng (hoặc dòng tiếp theo nếu tên bị xuống dòng)
    kết thúc bằng dãy chấm dẫn và số trang. Bỏ qua để không làm lệch đường dẫn mục."""
    line, end = _line_at(text, match.start())
    if _TOC_TAIL.search(line):
        return True
    if end >= len(text):
        return False
    following, _ = _line_at(text, end + 1)
    return not _HEADING.match(following) and bool(_TOC_TAIL.search(following))


def _sections(text: str) -> list[tuple[int, int, str | None]]:
    sections: list[tuple[int, int, str | None]] = []
    phu_luc = phan = chuong = None
    matches = [m for m in _HEADING.finditer(text) if not _is_toc_entry(text, m)]
    first = matches[0].start() if matches else len(text)
    if text[:first].strip():
        sections.append((0, first, "Mở đầu"))
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        label = " ".join(match.group(0).split())
        if match.group("phu_luc"):
            # Phụ lục bắt đầu một nhánh mới; Điều bên trong (vd Nội quy) nằm dưới phụ lục.
            phu_luc, phan, chuong = label, None, None
            parts = [phu_luc]
        elif match.group("phan"):
            phan, chuong = label, None
            parts = [p for p in (phu_luc, phan) if p]
        elif match.group("chuong"):
            chuong = label
            parts = [p for p in (phu_luc, phan, chuong) if p]
        else:
            parts = [p for p in (phu_luc, phan, chuong, label) if p]
        sections.append((match.start(), end, " > ".join(parts)))
    return sections or [(0, len(text), None)]


def _split_long(
    text: str,
    start: int,
    end: int,
    max_chars: int,
    protected: list[tuple[int, int]] | None = None,
) -> list[tuple[int, int]]:
    """Prefer complete clauses/sentences; size is soft up to two times the target.

    A source citation is atomic. Long unpunctuated input still has a bounded fallback;
    its split_reason exposes this limitation rather than claiming semantic completeness.
    """
    if end - start <= max_chars:
        return [(start, end)]
    protected = protected or []

    def safe(cut):
        return not any(a < cut < b for a, b in protected)

    boundaries = set()
    for match in _SUB_BREAK.finditer(text, start, end):
        cut = match.start()
        if text[start:cut].rstrip().endswith(":") or _CONTINUATION.match(text[cut:end].lstrip()):
            continue
        if safe(cut):
            boundaries.add(cut)
    for match in _SENTENCE_END.finditer(text, start, end):
        cut = match.end()
        before = text[max(start, match.start() - 12) : match.start()]
        word = before.rsplit(None, 1)[-1].lower() if before.strip() else ""
        if word.isdigit() or word in _ABBREVIATIONS:
            continue
        if _CONTINUATION.match(text[cut:end].lstrip()):
            continue
        if safe(cut):
            boundaries.add(cut)
    boundaries.add(end)
    cuts = sorted(boundaries)
    result = []
    a = start
    while a < end:
        if end - a <= max_chars:
            b = end
        else:
            fitting = [x for x in cuts if a < x <= a + max_chars]
            # Avoid separating a tiny heading/introduction from its first clause.
            fitting = [x for x in fitting if x - a >= min(160, max_chars // 3)]
            if fitting:
                b = fitting[-1]
            else:
                following = next((x for x in cuts if x > a), end)
                if following - a <= 2 * max_chars:
                    b = following
                else:
                    limit = min(end, a + 2 * max_chars)
                    spaces = [m.end() for m in re.finditer(r"\s+", text[a:limit])]
                    b = next((a + x for x in reversed(spaces) if safe(a + x)), limit)
                    # Even in a forced split, keep an observed citation in one piece.
                    for lo, hi in protected:
                        if lo < b < hi:
                            b = lo if lo > a else hi
                            break
        if b <= a:
            raise ValueError("Chunker failed to advance")
        result.append((a, b))
        a = b
    return result


def chunk_document(
    document: DocumentText,
    *,
    hop_dong_id: str,
    version: str,
    max_chars: int = 1800,
) -> list[ChunkRecord]:
    if max_chars < 32:
        raise ValueError("max_chars must be at least 32")
    text, starts, numbers = join_pages(document)
    protected = [(s["start"], s["end"]) for s in find_citation_spans(text)]
    chunks: list[ChunkRecord] = []
    for sec_start, sec_end, path in _sections(text):
        pieces = _split_long(text, sec_start, sec_end, max_chars, protected)
        for a, b in pieces:
            body = text[a:b]
            if not body.strip():
                continue
            thu_tu = len(chunks) + 1
            chunks.append(
                ChunkRecord(
                    doan_id=f"{hop_dong_id}_DOAN_{version}_{thu_tu:04d}",
                    hop_dong_id=hop_dong_id,
                    thu_tu=thu_tu,
                    page_start=_page_at(a, starts, numbers),
                    page_end=_page_at(max(b - 1, a), starts, numbers),
                    section_path=path,
                    noi_dung=body,
                    sha256=hashlib.sha256(body.encode("utf-8")).hexdigest(),
                    global_start=a,
                    global_end=b,
                    section_start=sec_start,
                    section_end=sec_end,
                    split_reason=(
                        "STRUCTURAL_ELEMENT"
                        if len(pieces) == 1
                        else "SENTENCE_OR_CLAUSE"
                        if b == sec_end or re.search(r"[.!?;][\"”’)]*\s*$", body)
                        else "BOUNDED_SOURCE_SPLIT"
                    ),
                )
            )
    return chunks
