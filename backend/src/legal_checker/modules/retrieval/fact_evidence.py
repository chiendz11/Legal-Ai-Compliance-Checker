"""Evidence chunks of extracted C02 fields (price, area, warranty…) as retrieval candidates.

Short key-value lines such as "Diện tích sử dụng: 62.4 m²" are the best evidence for data
criteria but rank low lexically. Step 2 already located them; a criterion that names a
field reuses those chunks instead of searching again.
"""

import re
import unicodedata
from collections.abc import Iterable, Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class FactEvidence:
    """One extracted field of a contract and the chunks that support it."""

    ten_truong: str
    doan_ids: tuple[str, ...]


# Team policy: which criterion wording (diacritics-folded regex) asks for which field.
# Auditable on purpose: fuzzy name matching linked "Không được đơn phương thay đổi hợp đồng"
# to gia_tri_hop_dong and "phương thức giải quyết tranh chấp" to the payment method.
# Fields absent here (tinh_trang_tai_san, la_nha_o_xa_hoi, …) are never promoted.
_PRICE = r"\bgia ban\b|\bgia tri (hop dong|can ho)\b"
DEFAULT_FACT_PATTERNS: Mapping[str, str] = {
    "ten_ben_ban": r"\bten\b",
    "ten_ben_mua": r"\bten\b",
    "dia_chi_ben_mua": r"\bdia chi\b",
    "dien_thoai_ben_mua": r"\bdien thoai\b",
    "email_ben_mua": r"\bemail\b|\bthu dien tu\b|\bphuong thuc lien he\b",
    "ma_dinh_danh_ben_mua": r"\bdinh danh\b|\bcan cuoc\b|\bchung minh\b|\bho chieu\b",
    "ma_can_ho": r"\bky hieu\b|\bso can\b|\bma can\b|\bthong tin (xac dinh duoc )?can ho\b",
    "tang_toa": r"\btang\W+toa\b",
    "dien_tich_thong_thuy": r"\bdien tich\b",
    "don_gia": r"\bdon gia\b",
    "gia_tri_hop_dong": _PRICE,
    "contract_price": _PRICE,
    "gia_ban_ung_vien": _PRICE,
    "phuong_thuc_thanh_toan": r"\bphuong thuc thanh toan\b",
    "tai_khoan_nhan_tien": r"\btai khoan\b",
    "warranty_months": r"\bbao hanh\b",
    "warranty_start": r"\bbao hanh\b",
    "ngay_giao_ket": r"\bngay giao ket\b|\bngay ky\b",
    "ngay_ban_giao_du_kien": r"\bban giao\b|\bgiao nhan\b",
    "muc_dich_giao_dich": r"\bmuc dich\b",
}


def fold(text: str) -> str:
    """Lower-case and strip Vietnamese diacritics (đ→d) so patterns stay ASCII."""
    decomposed = unicodedata.normalize("NFD", text.replace("đ", "d").replace("Đ", "D"))
    plain = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    return re.sub(r"\s+", " ", plain).strip().lower()


def matching_chunks(
    criterion_text: str,
    facts: Iterable[FactEvidence],
    patterns: Mapping[str, str] = DEFAULT_FACT_PATTERNS,
    limit: int = 3,
) -> list[tuple[str, str]]:
    """(doan_id, ten_truong) of facts the criterion asks for, in pattern order, deduplicated."""
    text = fold(criterion_text)
    wanted = [name for name, pattern in patterns.items() if re.search(pattern, text)]
    by_field: dict[str, list[str]] = {}
    for fact in facts:
        by_field.setdefault(fact.ten_truong, []).extend(fact.doan_ids)
    found: list[tuple[str, str]] = []
    for name in wanted:
        for doan_id in by_field.get(name, []):
            if doan_id not in {d for d, _ in found}:
                found.append((doan_id, name))
    return found[:limit]
