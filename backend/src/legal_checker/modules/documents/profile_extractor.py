"""C02 profile extraction from document text (quy tắc, chưa dùng LLM).

Hai lớp:
1. Trường ghi tường minh dạng "Nhãn: giá trị" (trang thông tin giao dịch, chỗ điền trong
   thân hợp đồng). Mỗi lần xuất hiện là một ứng viên kèm quote/offset trong chunk.
   Nhiều ứng viên khác giá trị → CONFLICT, giữ cả hai, không tự chọn.
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

PROFILE_EXTRACTOR_VERSION = "rules-v3"
LITERAL = "LABEL_REGEX"
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
    # Ô mẫu để trống ("……", "....", "[ ]") không phải giá trị.
    return value if value and not re.fullmatch(r"[.…_\[\]\s]+", value) else None


# Nhãn ở đầu dòng → (tên fact, hàm chuẩn hóa). Không trích dữ liệu định danh cá nhân
# (số giấy tờ, điện thoại, email, địa chỉ, ngày sinh, tài khoản) vì profile không dùng.
_LABELS: tuple[tuple[str, str, Callable[[str], object]], ...] = (
    ("ngay_giao_ket", r"Ngày giao kết", _parse_date),
    ("ngay_ky_nam", r"Ngày ký \(năm\)", _parse_year),
    ("ngay_ban_giao_du_kien", r"Ngày bàn giao dự kiến", _parse_date),
    ("gia_ban", r"Giá bán căn hộ[^:\n]*", _parse_money),
    ("don_gia", r"Đơn giá[^:\n]*", _parse_money),
    ("ten_ben_mua", r"Họ tên bên mua", _parse_text),
    ("dai_dien_ben_ban", r"Đại diện bên bán", _parse_text),
    ("ma_can_ho", r"(?:Mã căn hộ|Căn hộ)", _parse_text),
    ("tang_toa", r"Tầng / Tòa", _parse_text),
    ("dien_tich", r"Diện tích(?: sử dụng)?", _parse_number),
    ("so_hop_dong", r"Số hợp đồng", _parse_text),
    ("phuong_thuc_thanh_toan", r"Phương thức thanh toán", _parse_text),
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


def _drop_truncated(candidates: list[Candidate]) -> list[Candidate]:
    """Bỏ ứng viên chữ bị cắt do xuống dòng trong ô hẹp ("Đinh" so với "Đinh Tường Nam")."""
    texts = [c.value for c in candidates if isinstance(c.value, str)]
    return [
        c
        for c in candidates
        if not isinstance(c.value, str)
        or not any(t != c.value and t.startswith(c.value + " ") for t in texts)
    ]


def _resolve(builder: _Builder, name: str, candidates: list[Candidate]) -> object | None:
    """1 giá trị → EXTRACTED; nhiều giá trị khác nhau → CONFLICT (trả None, giữ ứng viên)."""
    candidates = _drop_truncated(candidates)
    if not candidates:
        return None
    distinct: dict[str, object] = {}
    for c in candidates:
        distinct.setdefault(_canonical(c.value), c.value)
    spans = [c.span for c in candidates]
    if len(distinct) == 1:
        value = candidates[0].value
        builder.fact(name, value, spans, status=EXTRACTED, method=LITERAL)
        return value
    ordered = [distinct[k] for k in sorted(distinct)]
    builder.fact(name, ordered, spans, status=CONFLICT, method=LITERAL, raw=None)
    return None


# ---------------------------------------------------------------- derived signals


def _find(chunks: Sequence[ChunkRecord], pattern: re.Pattern[str]) -> Span | None:
    for chunk in chunks:
        if m := pattern.search(chunk.noi_dung):
            return Span(chunk, m.start(), m.end())
    return None


_TITLE = re.compile(r"HỢP ĐỒNG MUA BÁN CĂN HỘ(?: CHUNG CƯ)?(?![^\n]*\.{4,})")
_FUTURE = re.compile(r"hình thành trong tương lai")
_PURPOSE_HOME = re.compile(r"Mục đích sử dụng(?: Căn [Hh]ộ)?:\s*(?:[Dd]ùng )?để ở", re.I)
_VN_LAW = re.compile(r"pháp luật Việt Nam|CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM", re.I)
_REAL_ESTATE_LAW = re.compile(r"Luật Kinh [Dd]oanh [Bb]ất [Đđ]ộng [Ss]ản")
_SELLER_IS_INVESTOR = re.compile(r"“Chủ đầu tư”,\s*“Bên Bán”|“Bên Bán”,\s*“Chủ đầu tư”")
# Tiêu đề "BÊN BÁN" ở đầu dòng, có thể có số thứ tự thường/La Mã ("1.", "I.").
# Tên công ty có thể nằm ngay sau trên cùng dòng ("BÊN BÁN: CÔNG TY ...").
_SELLER_HEADING = re.compile(r"^[ \t]*(?:(?:\d+|[IVX]+)\.[ \t]*)?BÊN BÁN\b", re.M)
# Dòng tiếp theo toàn chữ in hoa, ngắn: phần tên công ty bị xuống dòng.
_NAME_CONTINUATION = re.compile(r"\n[ \t]*([A-ZÀ-Ỹ][A-ZÀ-Ỹ \t()&.-]{0,40}?)[ \t]*(?=\n|$)")
# Tên tổ chức ở bất kỳ đâu trong dòng: "TỔNG CÔNG TY ...", "- Công ty: CÔNG TY CỔ PHẦN ...",
# "Tên Công ty: Công ty Cổ phần HBI". "Công ty:" (nhãn) không khớp vì sau đó là dấu hai chấm.
_ORG_NAME = re.compile(
    r"(?P<name>(?:TỔNG[ \t]+)?CÔNG[ \t]+TY[^\n]*"
    r"|(?:Tổng[ \t]+)?Công[ \t]+ty[ \t]+(?:[A-ZĐ]|cổ phần|trách nhiệm|TNHH)[^\n]*)"
)
_SELLER_WINDOW_LINES = 4


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


# ---------------------------------------------------------------- main


def extract_profile(
    chunks: Sequence[ChunkRecord], *, hop_dong_id: str, version: str
) -> ContractProfile:
    b = _Builder(hop_dong_id, version)
    found = _label_candidates(chunks)
    profile: dict[str, object] = {}

    def set_field(name: str, value: object, spans: Sequence[Span], method: str) -> None:
        if value is None or not spans:
            return
        profile[name] = value
        status = EXTRACTED if method == LITERAL else REVIEW_PENDING
        b.fact(f"profile.{name}", value, spans, status=status, method=method)

    # --- 1. Trường tường minh
    signing = _resolve(b, "ngay_giao_ket", found.get("ngay_giao_ket", []))
    year_only = _resolve(b, "ngay_ky_nam", found.get("ngay_ky_nam", []))
    handover = _resolve(b, "ngay_ban_giao_du_kien", found.get("ngay_ban_giao_du_kien", []))
    price = _resolve(b, "gia_ban", found.get("gia_ban", []))
    for name in ("don_gia", "dai_dien_ben_ban", "ma_can_ho", "tang_toa", "dien_tich"):
        _resolve(b, name, found.get(name, []))
    _resolve(b, "so_hop_dong", found.get("so_hop_dong", []))
    _resolve(b, "phuong_thuc_thanh_toan", found.get("phuong_thuc_thanh_toan", []))
    buyer = _resolve(b, "ten_ben_mua", found.get("ten_ben_mua", []))

    if signing is not None and (year_only is None or year_only == signing.year):
        spans = [c.span for c in found["ngay_giao_ket"]]
        set_field("ngay_giao_ket", signing, spans, LITERAL)
        set_field("ngay_giao_ket_raw", found["ngay_giao_ket"][0].raw, spans, LITERAL)
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
    if investor := _find(chunks, _SELLER_IS_INVESTOR):
        set_field("ben_ban_la_chu_dau_tu", True, [investor], DERIVED)

    seller = _find_seller(chunks)
    buyer_spans = [c.span for c in found.get("ten_ben_mua", [])] if buyer else []
    subjects: list[ProfileSubject] = []
    if seller:
        seller_name, seller_span = seller
        b.fact("ten_ben_ban", seller_name, [seller_span], status=EXTRACTED, method=LITERAL)
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
    markers += [
        ProfileTimeMarker(
            moc_id=f"{hop_dong_id}_MOC_{version}_{kind}",
            loai_moc=kind,
            do_chinh_xac="UNKNOWN",
            trang_thai="UNKNOWN",
        )
        for kind in ("COLLECTION", "PRE_HANDOVER_COLLECTION", "PRE_CERTIFICATE_COLLECTION")
    ]

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
