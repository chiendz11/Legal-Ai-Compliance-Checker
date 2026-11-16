"""Finite content predicates over exact C02 facts; no blanket LLM/human approval.

These recipes establish presence/consistency, not land ownership, real bank account
validity or transaction execution. Missing/conflicting facts fall back to reasoning.
"""

import re
import unicodedata
from datetime import date
from decimal import Decimal, InvalidOperation

from legal_checker.modules.compliance.automatic_review import automatic_review
from legal_checker.modules.compliance.reviewed_observations import build_verified_observation
from legal_checker.modules.retrieval.fact_evidence import fold
from legal_checker.shared.contracts.common import Context
from legal_checker.shared.contracts.document_intelligence import Evidence
from legal_checker.shared.contracts.reasoning import Observation

RECIPES = {
    "TC_ACCOUNT_2015_03": (
        "PV_APT_MAINTENANCE_ACCOUNT_2015",
        ("maintenance_account_number", "maintenance_account_holder", "maintenance_bank"),
    ),
    "TC_PV_HYC040_04": ("PV_HYC040", ("dien_tich", "gross_area_m2")),
    "TC_PV_HYC040_02": (
        "PV_HYC040",
        ("land_address", "land_parcel_no", "land_map_sheet", "land_area_m2"),
    ),
    "TC_PV_HYC039_02": ("PV_HYC039", ("dia_chi_ben_ban", "dia_chi_ben_mua")),
    "TC_PV_HYC049_01": ("PV_HYC049", ("maintenance_amount", "maintenance_percent")),
    "TC_PV_DS446_02": (
        "PV_DS446",
        ("warranty_months", "warranty_start", "warranty_start_date", "acceptance_date"),
    ),
    "TC_PV_HYC022_01": ("PV_HYC022", ("ngay_ban_giao_du_kien",)),
    "TC_PV_HYC043_01": ("PV_HYC043", ("ngay_ban_giao_du_kien",)),
}
VERSION = "C07_EXACT_CONTENT_V3"

SOURCE_LABELS = {
    "maintenance_account_number": ("tai khoan bao tri", "so tai khoan bao tri"),
    "maintenance_account_holder": ("ten tai khoan bao tri", "chu tai khoan bao tri"),
    "maintenance_bank": ("ngan hang tai khoan bao tri", "to chuc tin dung mo tai khoan bao tri"),
    "dien_tich": ("dien tich", "dien tich su dung"),
    "gross_area_m2": ("dien tich san xay dung can ho",),
    "land_address": ("vi tri thua dat",),
    "land_parcel_no": ("so thua dat",),
    "land_map_sheet": ("to ban do so",),
    "land_area_m2": ("dien tich thua dat",),
    "dia_chi_ben_ban": ("dia chi ben ban", "dia chi tru so ben ban", "dia chi lien he ben ban"),
    "dia_chi_ben_mua": ("dia chi ben mua", "dia chi lien he ben mua"),
    "maintenance_amount": ("so tien kinh phi bao tri",),
    "maintenance_percent": ("ty le kinh phi bao tri",),
    "warranty_start_date": ("ngay bat dau bao hanh",),
    "acceptance_date": ("ngay nghiem thu hoan thanh dua vao su dung",),
    "ngay_ban_giao_du_kien": ("ngay ban giao du kien",),
}


def source_agrees(name, value, quote):
    text = fold(quote)
    if name in {"maintenance_account_number", "maintenance_account_holder", "maintenance_bank"}:
        # The legacy one-line representation must carry its role labels as well.
        # A bare payment-account value is never sufficient to identify a maintenance account.
        legacy = re.fullmatch(
            r"tai khoan bao tri(?: gia lap)?\s*:\s*(?P<number>[^;]+);\s*"
            r"ten tai khoan\s+(?P<holder>[^;]+);\s*to chuc tin dung\s+(?P<bank>.+)",
            text,
        )
        if legacy:
            group = {
                "maintenance_account_number": "number",
                "maintenance_account_holder": "holder",
                "maintenance_bank": "bank",
            }[name]
            return fold(str(value)).rstrip(".") == legacy[group].strip().rstrip(".")
        if ":" not in text or text.split(":", 1)[0] not in SOURCE_LABELS[name]:
            return False
        return fold(str(value)).rstrip(".;,") == text.split(":", 1)[1].strip().rstrip(".;,")
    if name == "warranty_start":
        return (
            value == "COMPLETION_AND_ACCEPTANCE_INTO_USE"
            and "nghiem thu" in text
            and bool(re.search(r"\bdua\b.*\bvao su dung\b", text))
        )
    if name == "warranty_months":
        match = re.search(r"(\d+)\s*(?:\([^)]*\)\s*)?(thang|nam)\b", text)
        return bool(
            match and Decimal(str(value)) == int(match[1]) * (12 if match[2] == "nam" else 1)
        )
    if name not in SOURCE_LABELS:
        return True
    if ":" not in text or text.split(":", 1)[0] not in SOURCE_LABELS[name]:
        return False
    raw = text.split(":", 1)[1].strip()
    if name in {
        "land_area_m2",
        "maintenance_amount",
        "maintenance_percent",
        "dien_tich",
        "gross_area_m2",
    }:
        number = re.match(r"\d+(?:[.,]\d+)?", raw)
        try:
            return bool(number and Decimal(number[0].replace(",", ".")) == Decimal(str(value)))
        except InvalidOperation:
            return False
    if name in {"warranty_start_date", "acceptance_date", "ngay_ban_giao_du_kien"}:
        return str(value) in raw
    return (
        " ".join(unicodedata.normalize("NFC", str(value)).split()).casefold()
        == " ".join(unicodedata.normalize("NFC", quote.split(":", 1)[1]).split()).casefold()
    )


def fact_sources(profile, chunks):
    if any(c.hop_dong_id != profile.hop_dong_id for c in chunks):
        raise ValueError("Exact-content source belongs to another contract")
    active = {c.doan_id: c for c in chunks}
    evidence = {
        e.bang_chung_id: e
        for e in profile.evidence
        if e.doan_id in active
        and active[e.doan_id].noi_dung[e.ky_tu_bat_dau : e.ky_tu_ket_thuc] == e.trich_dan
    }
    groups = {}
    for fact in profile.facts:
        groups.setdefault(fact.ten_truong, []).append(fact)
    result = {}
    for name, rows in groups.items():
        if (
            len(rows) != 1
            or rows[0].trang_thai != "EXTRACTED"
            or rows[0].gia_tri_chuan_json is None
            or not rows[0].evidence_ids
            or not set(rows[0].evidence_ids) <= evidence.keys()
            or not all(
                source_agrees(name, rows[0].gia_tri_chuan_json, evidence[key].trich_dan)
                for key in rows[0].evidence_ids
            )
        ):
            continue
        result[name] = (rows[0].gia_tri_chuan_json, [evidence[k] for k in rows[0].evidence_ids])
    return result


def _predicate(key, values):
    try:
        if key == "TC_ACCOUNT_2015_03":
            # Check only what the draft names. No claim that the account exists,
            # is open, belongs to the seller, or that the named institution is licensed.
            return all(
                isinstance(v, str)
                and len(v.strip()) >= 3
                and not any(mark in v for mark in ("[", "]", "…", "..."))
                and not re.search(
                    r"\b(?:unknown|n/a|chua (?:duoc )?(?:cung cap|xac dinh|bo sung)|khong ro)\b",
                    fold(v),
                )
                for v in values.values()
            )
        if key == "TC_PV_HYC040_04":
            return all(Decimal(str(values[n])) > 0 for n in ("dien_tich", "gross_area_m2"))
        if key == "TC_PV_HYC040_02":
            return (
                all(
                    isinstance(values[n], str)
                    and len(values[n].strip()) >= 3
                    and not any(x in values[n] for x in ("[", "]", "…", "..."))
                    for n in ("land_address", "land_parcel_no", "land_map_sheet")
                )
                and Decimal(str(values["land_area_m2"])) > 0
            )
        if key == "TC_PV_HYC039_02":
            return all(
                isinstance(v, str)
                and len(v.strip()) >= 10
                and not any(x in v for x in ("[", "]", "…", "..."))
                for v in values.values()
            )
        if key == "TC_PV_HYC049_01":
            return (
                Decimal(str(values["maintenance_amount"])) > 0
                and 0 < Decimal(str(values["maintenance_percent"])) <= 100
            )
        if key == "TC_PV_DS446_02":
            return (
                Decimal(str(values["warranty_months"])) > 0
                and values["warranty_start"] == "COMPLETION_AND_ACCEPTANCE_INTO_USE"
                and date.fromisoformat(values["warranty_start_date"])
                == date.fromisoformat(values["acceptance_date"])
            )
        if key in {"TC_PV_HYC022_01", "TC_PV_HYC043_01"}:
            return bool(date.fromisoformat(values["ngay_ban_giao_du_kien"]))
    except (TypeError, ValueError, InvalidOperation):
        return False
    return False


def content_candidates(profile, requirements, chunks, knowledge):
    sources = fact_sources(profile, chunks)
    owners = {
        c["tieu_chi_id"]: r
        for r in requirements
        if r.confirmed
        for c in knowledge.criteria_for(r.requirement_version_id)
    }
    result = {}
    for key, (version, names) in RECIPES.items():
        owner = owners.get(key)
        if (
            not owner
            or owner.requirement_version_id != version
            or not set(names) <= sources.keys()
            or knowledge.criteria[key].get("loai_kiem_tra")
            not in {"CONTRACT_CONTENT", "NOI_DUNG_BAT_BUOC", "DOI_CHIEU_CO_DIEU_KIEN"}
        ):
            continue
        if not _predicate(key, {n: sources[n][0] for n in names}):
            continue
        result[(owner.yeu_cau_ca_id, key)] = list(
            dict.fromkeys(e.doan_id for n in names for e in sources[n][1])
        )
    return result


def admit_content(request, profile, knowledge, verifications):
    sources = fact_sources(profile, request.payload.chunks)
    candidates = content_candidates(
        profile, request.payload.requirements, request.payload.chunks, knowledge
    )
    records = {r.tieu_chi_id: r for r in verifications}
    selected = {
        (r.yeu_cau_ca_id, r.tieu_chi_id, r.doan_id)
        for r in request.payload.retrieval
        if r.duoc_chon and r.giai_doan == "FINAL" and r.lan_chay_id == request.run_id
    }
    result = []
    for (owner, key), ids in candidates.items():
        record = records.get(key)
        if not record or not record.facts_verified:
            continue
        if (
            record.yeu_cau_ca_id != owner
            or record.hop_dong_id != profile.hop_dong_id
            or any(
                getattr(record, n) != getattr(request, n)
                for n in Context.model_fields
                if n != "trace_id"
            )
        ):
            raise ValueError("Exact-content verification context mismatch")
        if not all((owner, key, i) in selected for i in ids):
            continue
        names = RECIPES[key][1]
        evidence = {e.bang_chung_id: e for n in names for e in sources[n][1]}
        excerpts = [Evidence(**e.model_dump(exclude={"bang_chung_id"})) for e in evidence.values()]
        explanation = (
            "Backend kiểm predicate nội dung từ C02 có quote/offset: "
            + "; ".join(n + "=" + str(sources[n][0]) for n in names)
            + ". Đây là kiểm nội dung/nhất quán; "
            "không xác nhận giao dịch hoặc chủ thể ngoài thực tế."
        )
        model_version = VERSION
        proposal = Observation(
            tieu_chi_id=key,
            proposed_finding="SATISFIED",
            giai_thich=explanation,
            evidence=excerpts,
            model_version=model_version,
            prompt_version="NO_LLM_EXACT_CONTENT_V1",
        )
        review = automatic_review(proposal, request, knowledge, verification=record)
        observation = build_verified_observation(proposal, review, request, knowledge)
        if observation.proposed_finding == "SATISFIED":
            result.append(observation)
    return result
