"""C02 profile extraction from document text (quy tắc, chưa dùng LLM).

Hai lớp:
1. Trường ghi tường minh dạng "Nhãn: giá trị" (trang thông tin giao dịch, chỗ điền trong
   thân hợp đồng). Mỗi lần xuất hiện là một ứng viên kèm quote/offset trong chunk.
   Nhiều ứng viên khác giá trị → CONFLICT, giữ cả hai, không tự chọn.
   Ngày ký còn được nhận từ câu ký kết ("Hôm nay, ngày 01 tháng 11 năm 2026") của hợp
   đồng thật; câu đó là một ứng viên nữa của cùng trường, cùng quy tắc CONFLICT.
2. Phân loại theo mã danh mục (loại hợp đồng, tình trạng tài sản...) từ dấu hiệu trong
   văn bản. Đây là suy luận theo quy tắc nên luôn ở trạng thái chờ review.

Không có bằng chứng thì trường để None. Không suy ra ngày đầy đủ từ một trường chỉ có năm.
"""

import json
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from legal_checker.modules.documents.chunker import ChunkRecord
from legal_checker.shared.contracts.document_intelligence import (
    ContractProfile,
    ExtractedFact,
    ProfileEvidence,
    ProfileFields,
    ProfileSubject,
    ProfileTimeMarker,
)

PROFILE_EXTRACTOR_VERSION = "rules-v12"
LITERAL = "LABEL_REGEX"
PHRASE = "PHRASE_REGEX"  # giá trị ghi nguyên văn trong câu (không có nhãn "X:")
DERIVED = "RULE_DERIVED"
EXTRACTED = "EXTRACTED"
REVIEW_PENDING = "DERIVED_REVIEW_PENDING"
CONFLICT = "CONFLICT"


@dataclass(frozen=True)
class Span:
    """Một đoạn bằng chứng nằm trọn trong một chunk."""

    chunk: ChunkRecord
    start: int
    end: int

    @property
    def quote(self) -> str:
        return self.chunk.noi_dung[self.start : self.end]


@dataclass
class Candidate:
    name: str
    value: object  # giá trị chuẩn hóa (date, Decimal, str, int, bool)
    raw: str
    span: Span
    method: str = LITERAL


@dataclass
class _Builder:
    """Tạo fact và bằng chứng. Mỗi bằng chứng thuộc đúng một fact (bảng bang_chung_truong
    có cột trich_xuat_id), nên cùng một câu làm bằng chứng cho hai fact sẽ có hai bản."""

    hop_dong_id: str
    version: str
    facts: list[ExtractedFact] = field(default_factory=list)
    evidence: list[ProfileEvidence] = field(default_factory=list)

    def fact(
        self,
        name: str,
        value: object,
        spans: Sequence[Span],
        *,
        status: str,
        method: str,
        raw: str | None = None,
    ) -> str:
        fact_id = f"{self.hop_dong_id}_TX_{self.version}_{name}"
        evidence_ids = []
        for i, span in enumerate(spans, start=1):
            evidence_id = f"{fact_id}_BC{i}"
            evidence_ids.append(evidence_id)
            self.evidence.append(
                ProfileEvidence(
                    bang_chung_id=evidence_id,
                    doan_id=span.chunk.doan_id,
                    trich_dan=span.quote,
                    ky_tu_bat_dau=span.start,
                    ky_tu_ket_thuc=span.end,
                )
            )
        self.facts.append(
            ExtractedFact(
                trich_xuat_id=fact_id,
                ten_truong=name,
                gia_tri_raw=raw if raw is not None else (spans[0].quote if spans else None),
                gia_tri_chuan_json=_json(value),
                trang_thai=status,
                phuong_phap=method,
                human_verified=False,
                evidence_ids=evidence_ids,
            )
        )
        return fact_id


def _json(value: object) -> object:
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, list):
        return [_json(v) for v in value]
    if isinstance(value, dict):
        return {k: _json(v) for k, v in value.items()}
    return value


def _canonical(value: object) -> str:
    return json.dumps(_json(value), sort_keys=True, ensure_ascii=False)


# ---------------------------------------------------------------- parse values

_DATE_ISO = re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})$")
_DATE_VN = re.compile(r"^(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})$")
_MONEY = re.compile(r"^(?P<so>\d{1,3}(?:[.,]\d{3})+|\d+)\s*(?P<tien>VND|VNĐ|đồng|USD)?", re.I)
_NUMBER = re.compile(r"^\d+(?:[.,]\d+)?")


def _parse_date(text: str) -> date | None:
    text = text.strip().rstrip(".;,")
    if m := _DATE_ISO.match(text):
        y, mo, d = map(int, m.groups())
    elif m := _DATE_VN.match(text):
        d, mo, y = map(int, m.groups())
    else:
        return None
    try:
        return date(y, mo, d)
    except ValueError:
        return None


def _parse_year(text: str) -> int | None:
    text = text.strip().rstrip(".;,")
    return int(text) if re.fullmatch(r"(19|20)\d{2}", text) else None


def _parse_money(text: str) -> dict[str, object] | None:
    m = _MONEY.match(text.strip())
    if not m:
        return None
    unit = (m.group("tien") or "VND").upper().replace("VNĐ", "VND").replace("ĐỒNG", "VND")
    return {"so_tien": Decimal(re.sub(r"[.,]", "", m.group("so"))), "don_vi": unit}


def _parse_number(text: str) -> Decimal | None:
    m = _NUMBER.match(text.strip())
    return Decimal(m.group(0).replace(",", ".")) if m else None


def _parse_text(text: str) -> str | None:
    value = text.strip().rstrip(".;,").strip()
    # Ô mẫu để trống ("……", "....", "[ ]", "[*]", "[Tên Dự án]") không phải giá trị.
    if not value or re.fullmatch(
        r"[:.…_\[\]*\s-]+|:\s*\[[^\]]*\]|\[(?:[._*\s-]*|Tên[^\]]*)\]",
        value,
        flags=re.I,
    ):
        return None
    return value


def _parse_rep_name(text: str) -> str | None:
    cleaned = re.sub(r"\s*\(nhân vật giả lập\)\s*$", "", text.strip(), flags=re.I)
    return _parse_text(cleaned)


def _parse_map_sheet(text: str) -> str | None:
    val = _parse_text(text)
    if val and ("cấp bởi" in val.casefold() or len(val) > 40):
        return None
    return val


def _parse_payment_method(text: str) -> str | None:
    val = _parse_text(text)
    if val and ("hoặc" in val.casefold() or len(val) > 45):
        return None
    return val


def _parse_bool(text: str) -> bool | None:
    value = text.strip().casefold()
    if value in {"có", "co", "true", "yes"}:
        return True
    if value in {"không", "khong", "false", "no"}:
        return False
    return None


# Nhãn ở đầu dòng → (tên fact, hàm chuẩn hóa).
_LABELS: tuple[tuple[str, str, Callable[[str], object]], ...] = (
    ("ngay_giao_ket", r"Ngày giao kết", _parse_date),
    ("ngay_ky_nam", r"Ngày ký \(năm\)", _parse_year),
    ("ngay_ban_giao_du_kien", r"Ngày bàn giao dự kiến", _parse_date),
    ("gia_ban", r"Giá bán căn hộ[^:\n]*", _parse_money),
    ("don_gia", r"Đơn giá[^:\n]*", _parse_money),
    ("ten_ben_ban", r"Tên bên bán", _parse_text),
    ("ten_ben_mua", r"Họ tên bên mua", _parse_text),
    ("dai_dien_ben_ban", r"(?:Người đại diện|Đại diện) bên bán", _parse_rep_name),
    ("buyer_identity", r"Mã định danh bên mua", _parse_text),
    ("buyer_birth", r"Ngày sinh bên mua", _parse_date),
    ("buyer_phone", r"Điện thoại bên mua", _parse_text),
    ("buyer_email", r"Email bên mua", _parse_text),
    ("project_name", r"Dự án", _parse_text),
    ("ma_can_ho", r"(?:Mã căn hộ|Căn hộ)", _parse_text),
    ("tang_toa", r"Tầng / Tòa", _parse_text),
    ("dien_tich", r"Diện tích(?: sử dụng)?", _parse_number),
    ("gross_area_m2", r"Diện tích sàn xây dựng căn hộ", _parse_number),
    ("document_stage", r"Trạng thái", _parse_text),
    ("so_hop_dong", r"Số hợp đồng", _parse_text),
    ("phuong_thuc_thanh_toan", r"Phương thức thanh toán", _parse_payment_method),
    ("purchase_bank", r"Ngân hàng nhận tiền mua nhà", _parse_text),
    ("purchase_account", r"Tài khoản nhận tiền mua nhà", _parse_text),
    ("la_nha_o_xa_hoi", r"Là nhà ở xã hội", _parse_bool),
    ("ben_ban_co_von_nuoc_ngoai", r"Bên bán có vốn nước ngoài", _parse_bool),
    ("la_giao_dich_dien_tu", r"Là giao dịch điện tử", _parse_bool),
    ("co_thoa_thuan_trong_tai", r"Có thỏa thuận trọng tài", _parse_bool),
    ("la_hop_dong_theo_mau", r"Là hợp đồng theo mẫu", _parse_bool),
    ("co_thoa_thuan_dat_coc", r"Có thỏa thuận đặt cọc", _parse_bool),
    ("dia_chi_ben_ban", r"Địa chỉ(?: trụ sở| liên hệ)? bên bán", _parse_text),
    ("dia_chi_ben_mua", r"Địa chỉ(?: liên hệ)? bên mua", _parse_text),
    ("land_address", r"Vị trí thửa đất", _parse_text),
    ("land_parcel_no", r"Số thửa đất", _parse_text),
    ("land_map_sheet", r"Tờ bản đồ số", _parse_map_sheet),
    ("land_area_m2", r"Diện tích thửa đất", _parse_number),
    ("maintenance_amount", r"Số tiền kinh phí bảo trì", _parse_number),
    ("maintenance_percent", r"Tỷ lệ kinh phí bảo trì", _parse_number),
    (
        "maintenance_account_number",
        r"(?i:(?:số[ \t]+)?tài[ \t]+khoản[ \t]+bảo[ \t]+trì)",
        _parse_text,
    ),
    (
        "maintenance_account_holder",
        r"(?i:(?:tên|chủ)[ \t]+tài[ \t]+khoản[ \t]+bảo[ \t]+trì)",
        _parse_text,
    ),
    (
        "maintenance_bank",
        r"(?i:ngân[ \t]+hàng[ \t]+tài[ \t]+khoản[ \t]+bảo[ \t]+trì|"
        r"tổ[ \t]+chức[ \t]+tín[ \t]+dụng[ \t]+mở[ \t]+tài[ \t]+khoản[ \t]+bảo[ \t]+trì)",
        _parse_text,
    ),
    ("warranty_start_date", r"Ngày bắt đầu bảo hành", _parse_date),
    ("acceptance_date", r"Ngày nghiệm thu hoàn thành đưa vào sử dụng", _parse_date),
    ("ngay_hieu_luc_hop_dong", r"Ngày hiệu lực hợp đồng", _parse_date),
    ("COLLECTION", r"Ngày thu tiền thực tế", _parse_date),
    ("PRE_HANDOVER_COLLECTION", r"Ngày thu tiền trước bàn giao", _parse_date),
    ("PRE_CERTIFICATE_COLLECTION", r"Ngày thu tiền trước cấp giấy chứng nhận", _parse_date),
    ("TEMPLATE_USE", r"Ngày sử dụng hợp đồng theo mẫu", _parse_date),
)
_LABEL_RES = tuple(
    (name, re.compile(rf"^[ \t]*{label}[ \t]*:[ \t]*(?P<value>[^\n]*?)[ \t]*$", re.M), parse)
    for name, label, parse in _LABELS
)


def _label_candidates(chunks: Sequence[ChunkRecord]) -> dict[str, list[Candidate]]:
    found: dict[str, list[Candidate]] = {}
    for chunk in chunks:
        for name, pattern, parse in _LABEL_RES:
            for m in pattern.finditer(chunk.noi_dung):
                value = parse(m.group("value"))
                if value is None:
                    continue
                start = m.start() + len(m.group(0)) - len(m.group(0).lstrip())
                span = Span(chunk, start, m.end())
                found.setdefault(name, []).append(Candidate(name, value, m.group("value"), span))
    return found


# Câu ký kết trong thân hợp đồng thật (không có nhãn "Ngày giao kết:"):
#   "Hôm nay, ngày 01 tháng 11 năm 2026, tại ..." / "Hôm nay là ngày 01/11/2026"
#   "Hợp đồng này được lập/ký/ký kết/giao kết (vào) ngày 01 tháng 11 năm 2026"
# Chỉ nhận hai mở đầu này: "được ký ngày ..." đứng một mình hay gặp khi viện dẫn hợp đồng,
# văn bản khác, và dòng "Hà Nội, ngày ..." chỉ là ngày soạn thảo. Mẫu trống ("ngày ....
# tháng .... năm 20...") không có chữ số nên không khớp.
_SIGNING_OPENING = (
    r"(?:Hôm\s+nay(?:\s+là)?"
    r"|Hợp\s+đồng\s+này\s+(?:đã\s+)?được\s+(?:lập|ký\s+kết|ký|giao\s+kết)(?:\s+vào)?)"
)
_SIGNING_PROSE = re.compile(
    _SIGNING_OPENING + r"[ \t,:]*(?P<raw>ngày\s+(?:"
    r"(?P<d>\d{1,2})\s+tháng\s+(?P<m>\d{1,2})\s+năm\s+(?P<y>\d{4})"
    r"|(?P<dmy>\d{1,2}[/.-]\d{1,2}[/.-]\d{4})))",
    re.I,
)


def _signing_phrase_candidates(chunks: Sequence[ChunkRecord]) -> list[Candidate]:
    found = []
    for chunk in chunks:
        for m in _SIGNING_PROSE.finditer(chunk.noi_dung):
            if m.group("dmy"):
                value = _parse_date(m.group("dmy"))
            else:
                try:
                    value = date(int(m.group("y")), int(m.group("m")), int(m.group("d")))
                except ValueError:
                    value = None
            if value is None:
                continue
            raw = " ".join(m.group("raw").split())
            span = Span(chunk, m.start(), m.end())
            found.append(Candidate("ngay_giao_ket", value, raw, span, PHRASE))
    return found


def _account_continuations(chunks: Sequence[ChunkRecord]) -> list[Candidate]:
    """Join a wrapped account field only up to the next explicit account label.

    Do not borrow another paragraph, cross a heading/footer, or scan unbounded text.
    The full original span is retained even when its canonical value joins lines.
    """
    fields = {"maintenance_account_number", "maintenance_account_holder", "maintenance_bank"}
    result = []
    stop = re.compile(r"^(?:Điều\s+\d+|Trang\s+\d+|DỰ THẢO|Thông tin|Không|Ghi chú|Đây là)", re.I)
    for chunk in chunks:
        matches = sorted(
            (
                (m.start(), name, m)
                for name, pattern, _ in _LABEL_RES
                if name in fields
                for m in pattern.finditer(chunk.noi_dung)
            ),
            key=lambda row: row[0],
        )
        for (_, name, match), (next_start, _, _) in zip(matches, matches[1:], strict=False):
            continuation = chunk.noi_dung[match.end() : next_start].strip()
            if not continuation:
                continue
            lines = continuation.splitlines()
            if len(lines) > 3 or any(
                not line.strip() or ":" in line or stop.match(line.strip()) for line in lines
            ):
                continue
            end = next_start
            while end > match.end() and chunk.noi_dung[end - 1].isspace():
                end -= 1
            raw = chunk.noi_dung[match.start("value") : end]
            if len(raw) > 512:
                continue
            value = _parse_text(" ".join(raw.split()))
            if value is not None:
                start = match.start() + len(match.group(0)) - len(match.group(0).lstrip())
                result.append(Candidate(name, value, raw, Span(chunk, start, end)))
    return result


def _drop_truncated(candidates: list[Candidate]) -> list[Candidate]:
    """Bỏ ứng viên chữ bị cắt do xuống dòng trong ô hẹp ("Đinh" so với "Đinh Tường Nam")."""
    texts = [c.value for c in candidates if isinstance(c.value, str)]
    return [
        c
        for c in candidates
        if not isinstance(c.value, str)
        or not any(t != c.value and t.startswith(c.value + " ") for t in texts)
    ]


def _method(candidates: Sequence[Candidate]) -> str:
    """Nhãn tường minh là bằng chứng mạnh nhất; có ứng viên từ câu thì ghi PHRASE."""
    return LITERAL if all(c.method == LITERAL for c in candidates) else PHRASE


def _resolve(builder: _Builder, name: str, candidates: list[Candidate]) -> object | None:
    """1 giá trị → EXTRACTED; nhiều giá trị khác nhau → CONFLICT (trả None, giữ ứng viên)."""
    candidates = _drop_truncated(candidates)
    if not candidates:
        return None
    distinct: dict[str, object] = {}
    for c in candidates:
        distinct.setdefault(_canonical(c.value), c.value)
    spans = [c.span for c in candidates]
    method = _method(candidates)
    if len(distinct) == 1:
        value = candidates[0].value
        builder.fact(name, value, spans, status=EXTRACTED, method=method)
        return value
    ordered = [distinct[k] for k in sorted(distinct)]
    builder.fact(name, ordered, spans, status=CONFLICT, method=method, raw=None)
    return None


# ---------------------------------------------------------------- derived signals


def _find(chunks: Sequence[ChunkRecord], pattern: re.Pattern[str]) -> Span | None:
    for chunk in chunks:
        if m := pattern.search(chunk.noi_dung):
            return Span(chunk, m.start(), m.end())
    return None


_TITLE = re.compile(
    r"HỢP\s+ĐỒNG\s+MUA\s+BÁN\s+(?:CĂN\s+HỘ(?:\s+CHUNG\s+CƯ)?|NHÀ\s+Ở(?:\s+XÃ\s+HỘI)?)"
    r"(?![^\n]*\.{4,})"
)
_FUTURE = re.compile(r"hình thành trong tương lai")
_NEW_BUILDING = re.compile(
    r"hình\s+thành\s+trong\s+tương\s+lai"
    r"|nhà\s+chung\s+cư\s+do\s+(?:Bên\s+Bán|Chủ\s+đầu\s+tư)\s+đầu\s+tư\s+xây\s+dựng"
    r"|nghiệm\s+thu\s+hoàn\s+thành\s+đưa\s+nhà\s+ở\s+vào\s+sử\s+dụng",
    re.I,
)
_PURPOSE_HOME = re.compile(
    r"M(?:ụ|u\s*/)c\s+đích\s+sử\s+d(?:ụ|u\s*/)ng(?:\s+Căn\s+[Hh]ộ)?:\s*(?:[Dd]ùng\s+)?để\s+ở"
    r"|Sử\s+d(?:ụ|u\s*/)ng\s+Căn\s+hộ\s+đúng\s+m(?:ụ|u\s*/)c\s+đích\s+để\s+ở"
    r"|m(?:ụ|u\s*/)c\s+đích\s+sử\s+d(?:ụ|u\s*/)ng[^.\n]{0,30}(?:để\s+ở|làm\s+nhà\s+ở)",
    re.I,
)
_VN_LAW = re.compile(r"pháp luật Việt Nam|CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM", re.I)
_REAL_ESTATE_LAW = re.compile(r"Luật Kinh [Dd]oanh [Bb]ất [Đđ]ộng [Ss]ản")
_SELLER_IS_INVESTOR = re.compile(
    r"“Chủ đầu tư”,\s*“Bên Bán”|“Bên Bán”,\s*“Chủ đầu tư”"
    r"|nhà\s+chung\s+cư\s+do\s+(?:Bên\s+Bán|Chủ\s+đầu\s+tư)\s+đầu\s+tư\s+xây\s+dựng"
    r"|do\s+Bên\s+Bán\s+làm\s+chủ\s+đầu\s+tư"
    # Only the seller itself: "Dự án do Công ty X làm chủ đầu tư" names some company, which
    # _find_named_investor compares with the seller's name instead.
    r"|Bên\s+Bán[^.\n]{0,60}?làm\s+(?:đồng\s+|Liên\s+danh\s+)?chủ\s+đầu\s+tư"
    r"|“Chủ\s+đầu\s+tư\s*”\s+là\s+Công\s+ty"
    r"|Ngày\s+Chủ\s+đầu\s+tư\s+ban\s+hành\s+nội\s+quy"
    r"|Chủ\s+đầu\s+tư\s*:"
    r"|công\s+nhận\s+chủ\s+đầu\s+tư"
    r"|Chủ\s+đầu\s+tư[^\n()]{0,40}\(sau đây gọi tắt là[^)]*Bên\s+Bán\)"
    r"|Bên\s+Bán\s+là\s+Chủ\s+đầu\s+tư"
    r"|do\s+Bên\s+Bán\s+là\s+chủ\s+đầu\s+tư",
    re.I,
)
# "Dự án ... do Công ty Cổ phần X làm chủ đầu tư": khớp khi X đúng là tên bên bán.
_NAMED_INVESTOR = re.compile(
    r"do\s+(?P<name>(?:(?:Tổng\s+)?Công\s+ty|Tập\s+đoàn)\s[^“”]{3,150}?)"
    r"\s+(?:làm|là)\s+chủ\s+đầu\s+tư",
    re.I,
)
# Tiêu đề hợp đồng nói rõ là nhà ở xã hội: yêu cầu chỉ dành cho nhà ở thương mại bị loại.
_SOCIAL_HOUSING_TITLE = re.compile(r"HỢP ĐỒNG (?:MUA BÁN|THUÊ MUA) NHÀ Ở XÃ HỘI")
_WARRANTY_APPENDIX_SUPERSEDES = re.compile(
    r"Điều\s+khoản\s+bảo\s+hành\s+nhà\s+ở\s+của\s+phụ\s+lục\s+này\s+thay\s+thế\s+thời\s+hạn\s+bảo\s+hành\s+nhà\s+ở",
    re.I,
)
_WARRANTY_APPENDIX_LABEL = re.compile(
    r"^[ \t]*Thời\s+hạn\s+bảo\s+hành\s+nhà\s+ở[ \t]*:[ \t]*(?P<months>\d{1,3})\s*tháng",
    re.I | re.M,
)
# Tiêu đề "BÊN BÁN" ở đầu dòng, có thể có số thứ tự thường/La Mã ("1.", "I.") hoặc nhãn
# "BÊN A:" phía trước ("I. BÊN A: BÊN BÁN NHÀ Ở ...").
# Tên công ty có thể nằm ngay sau trên cùng dòng ("BÊN BÁN: CÔNG TY ...").
_SELLER_HEADING = re.compile(
    r"^[ \t]*(?:(?:\d+|[IVX]+)\.[ \t]*)?(?:BÊN A[ \t]*:[ \t]*)?BÊN BÁN\b", re.M
)
# Dòng tiếp theo toàn chữ in hoa, ngắn: phần tên công ty bị xuống dòng.
_NAME_CONTINUATION = re.compile(r"\n[ \t]*([A-ZÀ-Ỹ][A-ZÀ-Ỹ \t()&.-]{0,40}?)[ \t]*(?=\n|$)")
# Tên tổ chức ở bất kỳ đâu trong dòng: "TỔNG CÔNG TY ...", "- Công ty: CÔNG TY CỔ PHẦN ...",
# "Tên Công ty: Công ty Cổ phần HBI". "Công ty:" (nhãn) không khớp vì sau đó là dấu hai chấm.
_ORG_NAME = re.compile(
    r"(?P<name>(?:TỔNG[ \t]+)?CÔNG[ \t]+TY[^\n]*"
    r"|(?:Tổng[ \t]+)?Công[ \t]+[Tt]y[ \t]+(?:[A-ZĐ]|cổ phần|trách nhiệm|TNHH)[^\n]*)"
)
_SELLER_WINDOW_LINES = 4

_WARRANTY = re.compile(
    r"(?:[Tt]hời\s+(?:gian|hạn)\s+)?bảo\s+hành\s+(?:nhà\s+ở|căn\s+hộ|nhà\s+chung\s+cư)"
    r"\s*(?:là|:)?\s*(?P<months>\d{1,3})\s*tháng",
    re.I,
)
_WARRANTY_START = re.compile(
    r"(?:(?:tính|kể)\s+từ|Mốc\s+bắt\s+đầu\s+bảo\s+hành\s*:\s*Từ)"
    r"[^.;]{0,130}nghiệm\s+thu[^.;]{0,90}đưa\s+nhà\s+ở\s+vào\s+sử\s+dụng",
    re.I,
)
_MAINTENANCE_ACCOUNT = re.compile(
    r"Tài\s+khoản\s+bảo\s+trì(?:\s+giả\s+lập)?\s*:\s*(?P<number>[^;\n]+);\s*"
    r"tên\s+tài\s+khoản\s+(?P<holder>[^;\n]+);\s*tổ\s+chức\s+tín\s+dụng\s+(?P<bank>[^.\n]+)",
    re.I,
)


def _find_seller(chunks: Sequence[ChunkRecord]) -> tuple[str, Span] | None:
    """Tên tổ chức ngay sau tiêu đề "BÊN BÁN" (cùng dòng hoặc vài dòng sau)."""
    for chunk in chunks:
        text = chunk.noi_dung
        for heading in _SELLER_HEADING.finditer(text):
            window_end = heading.end()
            for _ in range(_SELLER_WINDOW_LINES):
                nxt = text.find("\n", window_end + 1)
                window_end = len(text) if nxt == -1 else nxt
            m = _ORG_NAME.search(text, heading.end(), window_end)
            if not m:
                continue
            start = m.start("name")
            end = start + len(m.group("name").rstrip(" \t:;,"))
            cont = _NAME_CONTINUATION.match(text, m.end())
            if cont and m.group("name").isupper() and cont.group(1).isupper():
                end = cont.end(1)  # "... CAO ỐC" + "THIÊN LONG"
            return " ".join(text[start:end].split()), Span(chunk, start, end)
    return None


def _plain_name(text: str) -> str:
    return " ".join(text.replace("–", "-").split()).casefold().rstrip(" .,;:")


def _same_party(a: str, b: str) -> bool:
    """Equal names, or one cut short by a line break (at least five words in common)."""
    a, b = _plain_name(a), _plain_name(b)
    short, long = sorted((a, b), key=len)
    return a == b or (len(short.split()) >= 5 and long.startswith(short))


def _find_named_investor(chunks: Sequence[ChunkRecord], seller_name: str) -> Span | None:
    """The contract names the seller itself as the project's investor."""
    for chunk in chunks:
        for m in _NAMED_INVESTOR.finditer(chunk.noi_dung):
            if _same_party(m.group("name"), seller_name):
                return Span(chunk, m.start(), m.end())
    return None


# ---------------------------------------------------------------- main


def extract_profile(
    chunks: Sequence[ChunkRecord],
    *,
    hop_dong_id: str,
    version: str,
    complete_draft_source: bool = False,
) -> ContractProfile:
    b = _Builder(hop_dong_id, version)
    found = _label_candidates(chunks)
    if phrases := _signing_phrase_candidates(chunks):
        found.setdefault("ngay_giao_ket", []).extend(phrases)
    profile: dict[str, object] = {}

    def set_field(name: str, value: object, spans: Sequence[Span], method: str) -> None:
        if value is None or not spans:
            return
        profile[name] = value
        status = EXTRACTED if method in (LITERAL, PHRASE) else REVIEW_PENDING
        b.fact(f"profile.{name}", value, spans, status=status, method=method)

    # --- 1. Trường tường minh
    signing = _resolve(b, "ngay_giao_ket", found.get("ngay_giao_ket", []))
    year_only = _resolve(b, "ngay_ky_nam", found.get("ngay_ky_nam", []))
    handover = _resolve(b, "ngay_ban_giao_du_kien", found.get("ngay_ban_giao_du_kien", []))
    price = _resolve(b, "gia_ban", found.get("gia_ban", []))
    for name in (
        "don_gia",
        "dai_dien_ben_ban",
        "ma_can_ho",
        "tang_toa",
        "dien_tich",
        "gross_area_m2",
    ):
        _resolve(b, name, found.get(name, []))
    stages = [c for c in found.get("document_stage", []) if "DRAFT_REVIEW" in c.raw]
    for candidate in stages:
        candidate.value = "DRAFT_REVIEW"
    _resolve(b, "document_stage", stages)
    _resolve(b, "so_hop_dong", found.get("so_hop_dong", []))
    _resolve(b, "phuong_thuc_thanh_toan", found.get("phuong_thuc_thanh_toan", []))
    project_candidates = found.get("project_name", [])
    unbulleted_projects = [
        c for c in project_candidates if not c.span.quote.lstrip().startswith("-")
    ]
    appendix_projects = [c for c in unbulleted_projects if "(giả lập)" in str(c.value).casefold()]
    _resolve(
        b,
        "project_name",
        appendix_projects or unbulleted_projects or project_candidates,
    )
    for name in (
        "dia_chi_ben_ban",
        "dia_chi_ben_mua",
        "buyer_identity",
        "buyer_birth",
        "buyer_phone",
        "buyer_email",
        "purchase_bank",
        "purchase_account",
        "land_address",
        "land_parcel_no",
        "land_map_sheet",
        "land_area_m2",
        "maintenance_amount",
        "maintenance_percent",
        "warranty_start_date",
        "acceptance_date",
    ):
        _resolve(b, name, found.get(name, []))
    buyer = _resolve(b, "ten_ben_mua", found.get("ten_ben_mua", []))
    for name in (
        "la_nha_o_xa_hoi",
        "ben_ban_co_von_nuoc_ngoai",
        "la_giao_dich_dien_tu",
        "co_thoa_thuan_trong_tai",
        "co_thoa_thuan_dat_coc",
        "la_hop_dong_theo_mau",
        "ngay_hieu_luc_hop_dong",
    ):
        value = _resolve(b, name, found.get(name, []))
        if value is not None:
            set_field(name, value, [c.span for c in found[name]], LITERAL)
    # A source-limited draft observation, never a statement about other agreements.
    # The caller supplies completeness from persisted C01 + physical read coverage.
    text = "\n".join(c.noi_dung for c in chunks)
    court = re.compile(
        r"(?:các|hai|một\s+trong\s+hai)\s+bên[^.?!]{0,180}"
        r"(?:yêu\s+cầu|lựa\s+chọn|chọn)\s+(?:Tòa|Toà)\s+án\s+giải\s+quyết",
        re.I,
    )
    court_span = _find(chunks, court)
    if (
        complete_draft_source
        and court_span
        and "co_thoa_thuan_trong_tai" not in profile
        and not re.search(r"trọng\s+tài", text, re.I)
    ):
        profile["co_thoa_thuan_trong_tai"] = False
        b.fact(
            "profile.co_thoa_thuan_trong_tai",
            False,
            [court_span],
            status=REVIEW_PENDING,
            method="COMPLETE_DRAFT_COURT_ONLY_V1",
        )
    warranty = []
    if _find(chunks, _WARRANTY_APPENDIX_SUPERSEDES) is not None:
        for chunk in chunks:
            for match in _WARRANTY_APPENDIX_LABEL.finditer(chunk.noi_dung):
                warranty.append(
                    Candidate(
                        "warranty_months",
                        Decimal(match["months"]),
                        match["months"],
                        Span(chunk, match.start(), match.end()),
                    )
                )
    if not warranty:
        for chunk in chunks:
            for match in _WARRANTY.finditer(chunk.noi_dung):
                warranty.append(
                    Candidate(
                        "warranty_months",
                        Decimal(match["months"]),
                        match["months"],
                        Span(chunk, match.start(), match.end()),
                    )
                )
    months = _resolve(b, "warranty_months", warranty)
    if months is not None:
        spans = [c.span for c in warranty]
        b.fact("warranty_unit", "MONTH", spans, status=EXTRACTED, method=LITERAL)
        if all(re.search(r"nhà ở|căn hộ|nhà chung cư", span.quote, re.I) for span in spans):
            b.fact("warranty_subject", "BUILDING", spans, status=EXTRACTED, method=LITERAL)
        # A duration alone does not establish the commencement event.
        if start := _find(chunks, _WARRANTY_START):
            b.fact(
                "warranty_start",
                "COMPLETION_AND_ACCEPTANCE_INTO_USE",
                [start],
                status=EXTRACTED,
                method=LITERAL,
            )

    account_candidates = {
        key: list(found.get(key, []))
        for key in (
            "maintenance_account_number",
            "maintenance_account_holder",
            "maintenance_bank",
        )
    }
    for candidate in _account_continuations(chunks):
        # Replace only the truncated view of this exact physical field. A second
        # occurrence with a different value remains a genuine conflict.
        account_candidates[candidate.name] = [
            c
            for c in account_candidates[candidate.name]
            if (c.span.chunk.doan_id, c.span.start)
            != (candidate.span.chunk.doan_id, candidate.span.start)
        ]
        account_candidates[candidate.name].append(candidate)
    for chunk in chunks:
        for match in _MAINTENANCE_ACCOUNT.finditer(chunk.noi_dung):
            for key, group in (
                ("maintenance_account_number", "number"),
                ("maintenance_account_holder", "holder"),
                ("maintenance_bank", "bank"),
            ):
                value = match[group].strip()
                account_candidates[key].append(
                    Candidate(key, value, value, Span(chunk, match.start(), match.end()))
                )
    for key, candidates in account_candidates.items():
        _resolve(b, key, candidates)
    base_link = _find(
        chunks,
        re.compile(r"giá trị căn cứ(?: giả định)? cùng phạm vi\s+giá nêu trên", re.I),
    )
    if base_link:
        b.fact(
            "maintenance_base_reference",
            "STATED_SALE_PRICE",
            [base_link],
            status=EXTRACTED,
            method=LITERAL,
        )

    if signing is not None and (year_only is None or year_only == signing.year):
        spans = [c.span for c in found["ngay_giao_ket"]]
        method = _method(found["ngay_giao_ket"])
        set_field("ngay_giao_ket", signing, spans, method)
        set_field("ngay_giao_ket_raw", found["ngay_giao_ket"][0].raw, spans, method)
        set_field("do_chinh_xac_ngay", "DAY", spans, DERIVED)
        set_field("trang_thai_ngay", EXTRACTED, spans, DERIVED)
        set_field("loai_moc_ap_dung", "NGAY_GIAO_KET", spans, DERIVED)
    elif year_only is not None and signing is None:
        # Chỉ có năm: ghi nhận độ chính xác YEAR, không tự dựng ngày đầy đủ.
        spans = [c.span for c in found["ngay_ky_nam"]]
        set_field("ngay_giao_ket_raw", str(year_only), spans, LITERAL)
        set_field("do_chinh_xac_ngay", "YEAR", spans, DERIVED)
    if handover is not None:
        set_field(
            "ngay_ban_giao_du_kien",
            handover,
            [c.span for c in found["ngay_ban_giao_du_kien"]],
            LITERAL,
        )
    if price is not None:
        amount, unit = price["so_tien"], price["don_vi"]
        spans = [c.span for c in found["gia_ban"]]
        set_field("gia_tri_hop_dong", amount, spans, LITERAL)
        set_field("don_vi_tien", unit, spans, LITERAL)

    # --- 2. Phân loại theo quy tắc
    if title := _find(chunks, _TITLE):
        set_field("loai_hop_dong_id", "MB_CAN_HO_CHUNG_CU", [title], DERIVED)
        set_field("doi_tuong", "NHA_O", [title], DERIVED)
        set_field("linh_vuc", "NHA_O", [title], DERIVED)
    if law := _find(chunks, _VN_LAW):
        set_field("he_phap_luat", "VIET_NAM", [law], DERIVED)
    if future := _find(chunks, _FUTURE):
        set_field("tinh_trang_tai_san", "HINH_THANH_TRONG_TUONG_LAI", [future], DERIVED)
        set_field("la_nha_xay_moi", True, [future], DERIVED)
    elif new_bldg := _find(chunks, _NEW_BUILDING):
        set_field("la_nha_xay_moi", True, [new_bldg], DERIVED)
    if social := _find(chunks, _SOCIAL_HOUSING_TITLE):
        set_field("la_nha_o_xa_hoi", True, [social], DERIVED)

    seller_from_label = _resolve(b, "ten_ben_ban", found.get("ten_ben_ban", []))
    if seller_from_label is not None and found.get("ten_ben_ban"):
        seller = (str(seller_from_label), found["ten_ben_ban"][0].span)
    else:
        seller = _find_seller(chunks)
        if seller and not found.get("ten_ben_ban"):
            b.fact("ten_ben_ban", seller[0], [seller[1]], status=EXTRACTED, method=LITERAL)
    if investor := _find(chunks, _SELLER_IS_INVESTOR):
        set_field("ben_ban_la_chu_dau_tu", True, [investor], DERIVED)
    elif seller and (named := _find_named_investor(chunks, seller[0])):
        set_field("ben_ban_la_chu_dau_tu", True, [seller[1], named], DERIVED)
    buyer_spans = [c.span for c in found.get("ten_ben_mua", [])] if buyer else []
    subjects: list[ProfileSubject] = []
    if seller:
        seller_name, seller_span = seller
        set_field("ben_ban_la_ca_nhan", False, [seller_span], DERIVED)
        subjects.append(
            ProfileSubject(
                chu_the_id=f"{hop_dong_id}_CT_{version}_BEN_BAN",
                vai_tro="BEN_BAN",
                ten_chu_the=seller_name,
                loai_chu_the="DOANH_NGHIEP",
                la_thuong_nhan=True,
                la_chu_the_kinh_doanh=True,
                doan_bang_chung_id=seller_span.chunk.doan_id,
            )
        )
        if law_kd := _find(chunks, _REAL_ESTATE_LAW):
            set_field("che_do_giao_dich", "KINH_DOANH_BDS", [seller_span, law_kd], DERIVED)
    if buyer:
        set_field("ben_mua_la_ca_nhan", True, buyer_spans, DERIVED)
        subjects.append(
            ProfileSubject(
                chu_the_id=f"{hop_dong_id}_CT_{version}_BEN_MUA",
                vai_tro="BEN_MUA",
                ten_chu_the=str(buyer),
                loai_chu_the="CA_NHAN",
                la_thuong_nhan=False,
                la_chu_the_kinh_doanh=False,
                doan_bang_chung_id=buyer_spans[0].chunk.doan_id,
            )
        )
    if seller and buyer:
        spans = [seller[1], *buyer_spans]
        set_field("quan_he_chu_the", "DOANH_NGHIEP_VA_CA_NHAN", spans, DERIVED)
    if (purpose := _find(chunks, _PURPOSE_HOME)) is not None:
        set_field("muc_dich_su_dung_can_ho", "DE_O", [purpose], DERIVED)
        if buyer:
            set_field("muc_dich_giao_dich", "TIEU_DUNG_KHONG_THUONG_MAI", [purpose], DERIVED)

    # --- 3. Mốc thời gian: chỉ mốc có bằng chứng mới được dùng để phân giải
    facts_by_name = {f.ten_truong: f for f in b.facts}
    markers = [
        _marker(hop_dong_id, version, "SIGNING", profile.get("ngay_giao_ket"), facts_by_name),
        _marker(
            hop_dong_id,
            version,
            "EXPECTED_HANDOVER",
            profile.get("ngay_ban_giao_du_kien"),
            facts_by_name,
        ),
    ]
    for kind in (
        "COLLECTION",
        "PRE_HANDOVER_COLLECTION",
        "PRE_CERTIFICATE_COLLECTION",
        "TEMPLATE_USE",
    ):
        day = _resolve(b, kind, found.get(kind, []))
        markers.append(
            ProfileTimeMarker(
                moc_id=f"{hop_dong_id}_MOC_{version}_{kind}",
                loai_moc=kind,
                ngay=day,
                gia_tri_raw=day.isoformat() if day else None,
                do_chinh_xac="DAY" if day else "UNKNOWN",
                trang_thai=EXTRACTED if day else "UNKNOWN",
                duoc_dung_phan_giai=day is not None,
                trich_xuat_id=f"{hop_dong_id}_TX_{version}_{kind}" if day else None,
            )
        )

    return ContractProfile(
        hop_dong_id=hop_dong_id,
        profile=ProfileFields(**profile),
        subjects=subjects,
        time_markers=markers,
        facts=b.facts,
        evidence=b.evidence,
    )


_MARKER_FIELD = {"SIGNING": "ngay_giao_ket", "EXPECTED_HANDOVER": "ngay_ban_giao_du_kien"}


def _marker(hop_dong_id, version, kind, day, facts_by_name) -> ProfileTimeMarker:
    fact = facts_by_name.get(f"profile.{_MARKER_FIELD[kind]}")
    if day is None or fact is None:
        return ProfileTimeMarker(
            moc_id=f"{hop_dong_id}_MOC_{version}_{kind}",
            loai_moc=kind,
            do_chinh_xac="UNKNOWN",
            trang_thai="UNKNOWN",
        )
    return ProfileTimeMarker(
        moc_id=f"{hop_dong_id}_MOC_{version}_{kind}",
        loai_moc=kind,
        gia_tri_raw=fact.gia_tri_raw,
        ngay=day,
        do_chinh_xac="DAY",
        trang_thai=EXTRACTED,
        duoc_dung_phan_giai=True,
        trich_xuat_id=fact.trich_xuat_id,
    )
