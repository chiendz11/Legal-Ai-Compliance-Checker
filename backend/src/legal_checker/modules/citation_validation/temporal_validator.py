"""Citation validity at the relevant date; the current status is reported separately."""

from dataclasses import dataclass
from datetime import date
from typing import Any, Literal

TemporalStatus = Literal["IN_FORCE", "STALE", "NOT_YET_IN_FORCE", "UNKNOWN"]
# Relations that end the target document as a whole. Partial amendments
# (SUA_DOI_MOT_PHAN, SUA_DOI_NGAY_HIEU_LUC) never make the target stale.
_ENDING_RELATIONS = {"THAY_THE", "THAY_DANH_MUC_THEO_ND146"}


@dataclass
class TemporalResult:
    status: TemporalStatus
    reason_code: str
    detail: str
    replacement_van_ban_id: str | None = None


def as_date(value: Any) -> date | None:
    if value is None or isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def validate_temporal(
    document: dict[str, Any], relations: list[dict[str, Any]], relevant_date: date | None
) -> TemporalResult:
    """Valid on the signing date stays VALID even if replaced later (historical review)."""
    if relevant_date is None:
        return TemporalResult("UNKNOWN", "RELEVANT_DATE_UNKNOWN", "contract signing date unknown")
    start = as_date(document.get("hieu_luc_tu"))
    end = as_date(document.get("hieu_luc_den"))
    if start is None:
        return TemporalResult("UNKNOWN", "EFFECTIVE_DATE_UNKNOWN", "catalog has no effective date")
    if relevant_date < start:
        return TemporalResult(
            "NOT_YET_IN_FORCE",
            "NOT_YET_IN_FORCE_AT_DATE",
            f"in force from {start}, after the relevant date {relevant_date}",
        )
    replaced = sorted(
        (
            (as_date(r.get("moc_hieu_luc")), r["van_ban_nguon_id"])
            for r in relations
            if r.get("van_ban_dich_id") == document["van_ban_id"]
            and r.get("loai_quan_he") in _ENDING_RELATIONS
            and as_date(r.get("moc_hieu_luc")) is not None
            and as_date(r.get("moc_hieu_luc")) <= relevant_date
        ),
        key=lambda item: item[0],
    )
    if replaced:
        when, by = replaced[0]
        return TemporalResult("STALE", "REPLACED_BEFORE_DATE", f"replaced by {by} on {when}", by)
    if end is not None and end <= relevant_date:
        return TemporalResult(
            "STALE",
            "EXPIRED_BEFORE_DATE",
            f"no longer in force from {end}",
            document.get("van_ban_thay_the_id"),
        )
    return TemporalResult(
        "IN_FORCE", "IN_FORCE_AT_DATE", f"in force on {relevant_date} (from {start})"
    )
