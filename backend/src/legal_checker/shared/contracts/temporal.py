from datetime import date
from typing import Any, Literal

from pydantic import Field, model_validator

from legal_checker.shared.contracts.common import Model


class ApplicableRequirement(Model):
    yeu_cau_ca_id: str = Field(min_length=1)
    ca_id: str = Field(min_length=1)
    requirement_id: str = Field(min_length=1)
    requirement_version_id: str | None = None
    nhom_phien_ban: str | None = None
    scope_status: Literal["MATCH", "NO_MATCH", "UNKNOWN"]
    version_status: Literal["RESOLVED", "UNKNOWN"]
    applicability_status: Literal["CONFIRMED", "NOT_APPLICABLE", "UNKNOWN"]
    moc_id: str | None = None
    loai_moc: str | None = None
    moc_ap_dung: date | None = None
    resolution_method: str | None = None
    profile_snapshot_json: dict[str, Any] = Field(default_factory=dict)
    dieu_kien_snapshot_json: dict[str, Any] = Field(default_factory=dict)
    nguon_snapshot_json: dict[str, Any] = Field(default_factory=dict)
    phien_ban_id: str
    reason: dict[str, str] = Field(default_factory=dict)

    @property
    def confirmed(self) -> bool:
        return (
            self.scope_status == "MATCH"
            and self.version_status == "RESOLVED"
            and self.applicability_status == "CONFIRMED"
        )

    @model_validator(mode="after")
    def consistent(self):
        if self.confirmed and (not self.requirement_version_id or not self.moc_ap_dung):
            raise ValueError("Confirmed requirement needs version and relevant date")
        if self.applicability_status == "CONFIRMED" and not self.confirmed:
            raise ValueError("CONFIRMED requires MATCH and RESOLVED")
        return self
