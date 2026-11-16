"""Vietnamese legal-reference spans in source text, independent of chunk boundaries.

This finder extracts observed text only; catalog identity/effectiveness is C09 work.
"""

import re
from collections import Counter

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
    "này đó nêu dựa vào thực phải từ bằng hoặc nhưng do ngày số năm quy đã sẽ nghĩa là trừ "
    "trên dưới hướng liên gồm bao chưa không nếu đến tới cùng hay ra "
    # Đầu dòng tiếp theo là mục mới, không phải phần tên bị xuống dòng.
    "điều khoản điểm bên trang chương mục phụ".split()
)
# Sau "pháp" là cách nói chung ("pháp Luật Việt Nam"), sau "Luật" mà là "sư" là luật sư.
_GENERIC_BEFORE = re.compile(r"pháp\s*$", re.IGNORECASE)
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
_DYNAMIC_SUFFIX = re.compile(
    r"\s+(?:hiện\s+hành|(?:và\s+)?(?:các\s+)?(?:văn\s+bản\s+)?"
    r"(?:sửa\s+đổi|thay\s+thế)[^.;\n]{0,100}từng\s+thời\s+điểm)",
    re.I,
)
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


def _loai_tu_so_hieu(so_hieu: str) -> str | None:
    suffix = so_hieu.rsplit("/", 1)[-1]
    for key, loai in _SUFFIX_LOAI:
        if suffix.startswith(key):
            return loai
    return None


def _name_after(
    text: str, loai_end: int, first_lower_ok: bool, barriers: list[tuple[int, int]]
) -> tuple[str, int]:
    """Đọc tên văn bản sau loại: lấy từng từ cho tới từ dừng/dấu câu/xuống dòng."""
    words: list[str] = []
    end = loai_end
    for match in _WORD.finditer(text, loai_end):
        if match.start() != end or len(words) >= _MAX_NAME_WORDS:
            break
        word = match.group("word")
        if any(a <= match.start("word") < b for a, b in barriers):
            break
        if word.lower() in _STOP_WORDS or word[0].isdigit():
            break
        if not words and not (word[0].isupper() or first_lower_ok):
            break
        words.append(word)
        end = match.end()
    if words and words[0].lower() in _NOT_A_NAME:
        return "", loai_end
    return " ".join(words), end


def find_citation_spans(text: str) -> list[dict]:
    # Repeated uppercase running banners are not continuations of a legal title.
    # Keep every source character; these ranges only constrain name interpretation.
    lines = list(re.finditer(r"[^\n]+", text))
    counts = Counter(m[0].strip() for m in lines)
    barriers = [
        (m.start(), m.end())
        for m in lines
        if counts[m[0].strip()] >= 3
        and len(m[0].strip()) >= 12
        and m[0].isupper()
        and re.search(r"\s[-–—]\s", m[0])
    ]
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
        name, name_end = _name_after(
            text, m.end(), first_lower_ok=loai in ("Luật", "Bộ luật"), barriers=barriers
        )
        # General/defined terms are not titles of a uniquely identifiable statute.
        if re.match(r"^(?:áp\s+dụng|việt\s+nam)(?:\s|$)", name, re.I):
            continue
        if not name:
            if _DIEU_TRUOC.search(text[max(0, m.start() - 60) : m.start()]) and not any(
                s["start"] <= m.start() < s["end"] for s in spans
            ):
                spans.append(
                    dict(
                        start=m.start(),
                        end=m.end(),
                        so_hieu=None,
                        loai=loai,
                        ten=None,
                        nam=None,
                        status="AMBIGUOUS",
                        rule="PARTIAL_TYPE_REFERENCE",
                    )
                )
            continue
        ten = f"{loai} {name}"
        nam_m = _NAM_SAU_TEN.match(text, name_end)
        nam = int(nam_m.group("nam")) if nam_m else None
        end = nam_m.end() if nam_m else name_end
        dynamic = _DYNAMIC_SUFFIX.match(text, end)
        if dynamic:
            end = dynamic.end()
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
