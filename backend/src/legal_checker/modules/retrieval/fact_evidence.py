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
_PRICE = r"\bgia (?:mua )?ban\b|\bgia tri (hop dong|can ho)\b"
DEFAULT_FACT_PATTERNS: Mapping[str, str] = {
    "maintenance_account_number": r"\bso tai khoan bao tri\b",
    "maintenance_account_holder": r"\bten tai khoan bao tri\b",
    "maintenance_bank": r"\bto chuc tin dung.*tai khoan bao tri\b|\bngan hang.*bao tri\b",
    "ten_ben_ban": r"\bten (?:cua )?(?:ben ban|cac ben)\b|\bten to chuc.*cac ben\b",
    "ten_ben_mua": r"\bten\b.*\bben mua\b|\bten cac ben\b|\bten to chuc.*cac ben\b",
    "dia_chi_ben_mua": r"\bdia chi\b",
    "dien_thoai_ben_mua": r"\bdien thoai\b",
    "email_ben_mua": r"\bemail\b|\bthu dien tu\b|\bphuong thuc lien he\b",
    "ma_dinh_danh_ben_mua": r"\bdinh danh\b|\bcan cuoc\b|\bchung minh\b|\bho chieu\b",
    "ma_can_ho": (
        r"\bky hieu\b|\bso can\b|\bma can\b|\bthong tin (xac dinh duoc )?can ho\b|"
        r"\bdac diem (?:cua )?can ho\b"
    ),
    "tang_toa": r"\btang\W+toa\b|\bdac diem (?:cua )?can ho\b",
    "dien_tich_thong_thuy": r"\bdien tich\b|\bdac diem (?:cua )?can ho\b",
    "gross_area_m2": r"\bdien tich san\b|\bdien tich.*so huu rieng\b",
    "dia_chi_ben_ban": r"\bdia chi\b",
    "maintenance_amount": r"\bkinh phi bao tri\b",
    "maintenance_percent": r"\bkinh phi bao tri\b",
    "maintenance_base_reference": r"\bkinh phi bao tri\b",
    "land_address": r"\bthua dat\b",
    "land_area_m2": r"\bthua dat\b",
    "land_parcel_no": r"\bthua dat\b",
    "land_map_sheet": r"\bthua dat\b",
    "don_gia": r"\bdon gia\b",
    "gia_tri_hop_dong": _PRICE,
    "contract_price": _PRICE,
    "gia_ban_ung_vien": _PRICE,
    "phuong_thuc_thanh_toan": r"\bphuong thuc thanh toan\b",
    "tai_khoan_nhan_tien": r"\btai khoan\b",
    "warranty_months": r"\bbao hanh\b",
    "warranty_start": r"\bbao hanh\b",
    "ngay_giao_ket": r"\bngay giao ket\b|\bngay ky\b|\bngay\W+thang\W+nam\W+ky ket\b",
    "ngay_hieu_luc_hop_dong": r"\bthoi diem (?:co )?hieu luc\b|\bngay hieu luc\b",
    "ngay_ban_giao_du_kien": r"\bban giao\b|\bgiao nhan\b|\bthoi han giao\b",
    "muc_dich_giao_dich": r"\bmuc dich\b",
}

# A criterion can describe its legal predicate without repeating its topic name.
# These explicit bindings prevent lexical guesses from replacing known C02 sources.
CRITERION_FACT_FIELDS = {
    "TC_PV_DS446_02": ("warranty_months", "warranty_start"),
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
    *,
    criterion_id: str | None = None,
) -> list[tuple[str, str]]:
    """(doan_id, ten_truong) of facts the criterion asks for, in pattern order, deduplicated."""
    text = fold(criterion_text)
    wanted = list(
        dict.fromkeys(
            [
                *CRITERION_FACT_FIELDS.get(criterion_id, ()),
                *(name for name, pattern in patterns.items() if re.search(pattern, text)),
            ]
        )
    )
    by_field: dict[str, list[str]] = {}
    aliases = {"gia_ban": "gia_tri_hop_dong", "dien_tich": "dien_tich_thong_thuy"}
    for fact in facts:
        name = fact.ten_truong.removeprefix("profile.")
        by_field.setdefault(aliases.get(name, name), []).extend(fact.doan_ids)
    found: list[tuple[str, str]] = []
    # Give each requested field a source before spending the budget on repeated
    # occurrences of the first field (e.g. apartment code starving floor/area).
    rounds = max((len(by_field.get(name, [])) for name in wanted), default=0)
    for index in range(rounds):
        for name in wanted:
            values = by_field.get(name, [])
            if index < len(values) and values[index] not in {d for d, _ in found}:
                found.append((values[index], name))
                if len(found) >= limit:
                    return found[:limit]
    return found[:limit]
