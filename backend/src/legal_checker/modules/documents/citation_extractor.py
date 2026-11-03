"""C03 extraction of contract-authored legal citations (regex, chưa dùng LLM).

- EXTRACTED: có số hiệu văn bản pháp luật (vd 91/2015/QH13) hoặc (Bộ) luật kèm năm.
- AMBIGUOUS: chỉ có tên văn bản, không số hiệu/năm (vd "theo Luật Nhà ở").
- Không kiểm tra hiệu lực (việc của bước 3B): "Nghị định 999/2099/NĐ-CP" vẫn được trích.
- Cùng một văn bản + điều/khoản nêu nhiều lần → 1 citation với nhiều vị trí.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass, field

from legal_checker.modules.documents.chunker import ChunkRecord
from legal_checker.shared.contracts.citation import (
    CitationExtraction,
    CitationExtractionMetadata,
    CitationNormalization,
    CitationPosition,
)

EXTRACTOR_VERSION = "regex-v3"

# Số hiệu văn bản pháp luật: chỉ nhận ký hiệu loại văn bản đã biết, để không bắt nhầm
# số hợp đồng ("070/2017/HDMB"). Vd 91/2015/QH13, 99/2015/NĐ-CP, 02/2016/TT-BXD.
# PDF có thể xuống dòng ngay sau dấu gạch ("99/2015/NĐ-\nCP"): số hiệu chuẩn hóa bỏ khoảng trắng.
_SO_HIEU = re.compile(
    r"\b\d{1,4}/\d{4}/"
    r"(?:QH\d{1,2}|UBTVQH\d{0,2}|(?:NĐ|ND|TTLT|TT|QĐ|QD|NQ|PL|CT)"
    r"(?:-[ \t]*\n?[ \t]*[A-Za-zĐđ0-9]+)*)"
    r"(?![A-Za-zĐđ0-9])"
)
_SUFFIX_LOAI = (
    ("UBTVQH", "Nghị quyết"),
    ("QH", "Luật"),
    ("NĐ", "Nghị định"),
    ("ND", "Nghị định"),
    ("TTLT", "Thông tư liên tịch"),
    ("TT", "Thông tư"),
    ("QĐ", "Quyết định"),
    ("QD", "Quyết định"),
    ("NQ", "Nghị quyết"),
    ("PL", "Pháp lệnh"),
    ("CT", "Chỉ thị"),
)
# Loại văn bản viết hoa chữ đầu ("Luật", "Bộ luật"/"Bộ Luật", "Nghị định"/"Nghị Định"...).
# "luật"/"nghị định" viết thường thường là cách nói chung ("theo quy định của pháp luật").
_LOAI = re.compile(
    r"(?<![A-Za-zÀ-ỹ])(?P<loai>Bộ [Ll]uật|Luật|Nghị [Đđ]ịnh|Thông [Tt]ư liên tịch|"
    r"Thông [Tt]ư|Nghị [Qq]uyết|Quyết [Đđ]ịnh|Pháp [Ll]ệnh)(?![A-Za-zÀ-ỹ])"
)
_LOAI_CHUAN = {
    "bộ luật": "Bộ luật",
    "luật": "Luật",
    "nghị định": "Nghị định",
    "thông tư liên tịch": "Thông tư liên tịch",
    "thông tư": "Thông tư",
    "nghị quyết": "Nghị quyết",
    "quyết định": "Quyết định",
    "pháp lệnh": "Pháp lệnh",
}
# Từ báo hiệu tên văn bản đã kết thúc ("Luật Nhà ở | và theo thỏa thuận").
_STOP_WORDS = frozenset(
    "và để khi về mà thì theo của tại trong đối với như sau trước hiện có được cho các "
    "này đó nêu dựa vào thực phải từ bằng hoặc nhưng do ngày số năm quy đã sẽ nghĩa là "
    "trên dưới hướng liên gồm bao chưa không nếu đến tới cùng hay ra "
    # Đầu dòng tiếp theo là mục mới, không phải phần tên bị xuống dòng.
    "điều khoản điểm bên trang chương mục phụ".split()
)
# Sau "pháp" là cách nói chung ("pháp Luật Việt Nam"), sau "Luật" mà là "sư" là luật sư.
_GENERIC_BEFORE = re.compile(r"pháp[ \t]*$", re.IGNORECASE)
_NOT_A_NAME = frozenset({"sư", "này", "đó", "trên", "nêu", "hiện"})
_MAX_NAME_WORDS = 8
# Tên có thể bị xuống dòng trong PDF ("Luật Kinh\nDoanh Bất Động Sản"): cho phép 1 lần "\n".
_WORD = re.compile(r"(?:[ \t]+|[ \t]*\n[ \t]*)(?P<word>[^\s,.;:()\[\]\"“”‘’]+)")
# Năm sau tên: "Luật Nhà ở 2014", "... năm 2014", "... ngày 25 tháng 11 năm 2014",
# "... ngày 25/11/2014".
_NAM_SAU_TEN = re.compile(
    r"[ \t]+(?:năm[ \t]+|ngày[ \t]+\d{1,2}(?:[ \t]+tháng[ \t]+\d{1,2}[ \t]+năm[ \t]+|/\d{1,2}/))?"
    r"(?P<nam>(?:19|20)\d{2})(?!\d)"
)
_GAP_TO_SO_HIEU = re.compile(r"[ \t]*(?:số[ \t]*)?")
_LOAI_TRUOC_SO_HIEU = re.compile(
    r"(?P<loai>Bộ [Ll]uật|Luật|Nghị [Đđ]ịnh|Thông [Tt]ư liên tịch|Thông [Tt]ư|"
    r"Nghị [Qq]uyết|Quyết [Đđ]ịnh|Pháp [Ll]ệnh)[ \t]+(?:số[ \t]+)?$"
)
_DIEU_TRUOC = re.compile(
    r"(?:điểm[ \t]+(?P<diem>[a-zđ])[ \t,]+)?"
    r"(?:khoản[ \t]+(?P<khoan>\d+)[ \t,]+)?"
    r"Điều[ \t]+(?P<dieu>\d+[a-z]?)[ \t,]+(?:của[ \t]+)?$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class CitationMention:
    """Một lần xuất hiện: quote + offset trong chunk, dùng cho bang_chung_vien_dan."""

    doan_id: str
    page_start: int
    page_end: int
    start: int
    end: int
    quote: str


@dataclass
class CitationRecord:
    vien_dan_id: str
    hop_dong_id: str
    raw_text: str
    status: str
    so_hieu: str | None = None
    loai_van_ban: str | None = None
    ten_van_ban: str | None = None
    nam: int | None = None
    dieu: str | None = None
    khoan: str | None = None
    diem: str | None = None
    mentions: list[CitationMention] = field(default_factory=list)
    provenance: dict[str, str] = field(default_factory=dict)

    def to_contract(self) -> CitationExtraction:
        positions, seen = [], set()
        for m in self.mentions:
            key = (m.doan_id, m.page_start, m.page_end)
            if key not in seen:
                seen.add(key)
                positions.append(
                    CitationPosition(
                        doan_id=m.doan_id, page_start=m.page_start, page_end=m.page_end
                    )
                )
        return CitationExtraction(
            vien_dan_id=self.vien_dan_id,
            hop_dong_id=self.hop_dong_id,
            raw_text=self.raw_text,
            normalized=CitationNormalization(
                so_hieu=self.so_hieu,
                ten_van_ban=self.ten_van_ban,
                loai_van_ban=self.loai_van_ban,
                nam=self.nam,
                dieu=self.dieu,
                khoan=self.khoan,
            ),
            extraction=CitationExtractionMetadata(status=self.status),
            evidence=positions,
        )


def _loai_tu_so_hieu(so_hieu: str) -> str | None:
    suffix = so_hieu.rsplit("/", 1)[-1]
    for key, loai in _SUFFIX_LOAI:
        if suffix.startswith(key):
            return loai
    return None


def _name_after(text: str, loai_end: int, first_lower_ok: bool) -> tuple[str, int]:
    """Đọc tên văn bản sau loại: lấy từng từ cho tới từ dừng/dấu câu/xuống dòng."""
    words: list[str] = []
    end = loai_end
    for match in _WORD.finditer(text, loai_end):
        if match.start() != end or len(words) >= _MAX_NAME_WORDS:
            break
        word = match.group("word")
        if word.lower() in _STOP_WORDS or word[0].isdigit():
            break
        if not words and not (word[0].isupper() or first_lower_ok):
            break
        words.append(word)
        end = match.end()
    if words and words[0].lower() in _NOT_A_NAME:
        return "", loai_end
    return " ".join(words), end


def _spans(text: str) -> list[dict]:
    spans: list[dict] = []
    for m in _SO_HIEU.finditer(text):
        start = m.start()
        before = text[max(0, start - 30) : start]
        loai_m = _LOAI_TRUOC_SO_HIEU.search(before)
        if loai_m:
            start -= len(before) - loai_m.start()
        loai = _LOAI_CHUAN[loai_m.group("loai").lower()] if loai_m else None
        spans.append(
            {
                "start": start,
                "end": m.end(),
                "so_hieu": re.sub(r"\s+", "", m.group(0)),
                "loai": loai or _loai_tu_so_hieu(m.group(0)),
                "ten": None,
                "nam": int(m.group(0).split("/")[1]),
                "status": "EXTRACTED",
                "rule": "SO_HIEU",
            }
        )
    for m in _LOAI.finditer(text):
        if _GENERIC_BEFORE.search(text[max(0, m.start() - 10) : m.start()]):
            continue
        loai = _LOAI_CHUAN[m.group("loai").lower()]
        # "Căn cứ Luật bảo vệ người tiêu dùng": tên luật hay viết thường sau chữ "Luật" hoa.
        name, name_end = _name_after(text, m.end(), first_lower_ok=loai in ("Luật", "Bộ luật"))
        if not name:
            continue
        ten = f"{loai} {name}"
        nam_m = _NAM_SAU_TEN.match(text, name_end)
        nam = int(nam_m.group("nam")) if nam_m else None
        end = nam_m.end() if nam_m else name_end
        merged = next(
            (
                s
                for s in spans
                if s["start"] <= m.start() < s["end"]
                or (end <= s["start"] and _GAP_TO_SO_HIEU.fullmatch(text[end : s["start"]]))
            ),
            None,
        )
        if merged:  # "Luật Nhà ở số 65/2014/QH13": gộp tên vào span số hiệu
            merged["start"] = min(merged["start"], m.start())
            merged["loai"] = loai
            merged["ten"] = merged["ten"] or ten
            continue
        luat = loai in ("Luật", "Bộ luật")
        spans.append(
            {
                "start": m.start(),
                "end": end,
                "so_hieu": None,
                "loai": loai,
                "ten": ten,
                "nam": nam,
                "status": "EXTRACTED" if nam and luat else "AMBIGUOUS",
                "rule": "TEN_NAM" if nam else "TEN_ONLY",
            }
        )
    for s in spans:
        window = text[max(0, s["start"] - 60) : s["start"]]
        dieu_m = _DIEU_TRUOC.search(window)
        s["dieu"] = s["khoan"] = s["diem"] = None
        if dieu_m:
            s["start"] -= len(window) - dieu_m.start()
            s.update(dieu_m.groupdict())
    return sorted(spans, key=lambda s: s["start"])


def extract_citations(chunks: Iterable[ChunkRecord], *, version: str) -> list[CitationRecord]:
    records: dict[tuple, CitationRecord] = {}
    for chunk in chunks:
        for s in _spans(chunk.noi_dung):
            quote = chunk.noi_dung[s["start"] : s["end"]]
            doc_key = s["so_hieu"] or (s["ten"] or "").lower()
            key = (doc_key, s["nam"] if not s["so_hieu"] else None, s["dieu"], s["khoan"])
            record = records.get(key)
            if record is None:
                hop_dong_id = chunk.hop_dong_id
                record = CitationRecord(
                    vien_dan_id=f"{hop_dong_id}_VD_{version}_{len(records) + 1:03d}",
                    hop_dong_id=hop_dong_id,
                    raw_text=quote,
                    status=s["status"],
                    so_hieu=s["so_hieu"],
                    loai_van_ban=s["loai"],
                    ten_van_ban=s["ten"],
                    nam=s["nam"],
                    dieu=s["dieu"],
                    khoan=s["khoan"],
                    diem=s["diem"],
                    provenance={"method": EXTRACTOR_VERSION, "rule": s["rule"]},
                )
                records[key] = record
            record.mentions.append(
                CitationMention(
                    chunk.doan_id, chunk.page_start, chunk.page_end, s["start"], s["end"], quote
                )
            )
    return list(records.values())
