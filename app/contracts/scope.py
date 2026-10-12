"""C04: candidate requirement families with three-state scope resolution."""

from typing import Any, Literal

from pydantic import Field

from app.contracts.common import Model


class ScopeResolution(Model):
    yeu_cau_ca_id: str
    ca_id: str
    requirement_id: str
    nhom_phien_ban: str | None = None
    scope_status: Literal["MATCH", "NO_MATCH", "UNKNOWN"]
    profile_snapshot_json: dict[str, Any] = Field(default_factory=dict)
    dieu_kien_snapshot_json: dict[str, Any] = Field(default_factory=dict)
    scope_reason: str = Field(min_length=1)
