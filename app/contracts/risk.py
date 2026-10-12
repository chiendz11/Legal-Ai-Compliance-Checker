from typing import Any, Literal

from pydantic import model_validator

from app.contracts.common import Model, RiskType, Severity


class RiskSource(Model):
    yeu_cau_ca_id: str | None = None
    ket_qua_tieu_chi_id: str | None = None
    citation_finding_id: str | None = None

    @model_validator(mode="after")
    def single_source(self):
        if bool(self.ket_qua_tieu_chi_id) == bool(self.citation_finding_id):
            raise ValueError("Risk must reference exactly one criterion or citation finding")
        return self


class RiskResult(Model):
    ket_qua_rui_ro_id: str
    ca_id: str
    risk_type: RiskType
    rui_ro_id: str
    severity: Severity
    source: RiskSource
    quy_tac_id: str
    giai_thich: str
    risk_snapshot: dict[str, Any]
    rule_snapshot_json: dict[str, Any]
    evidence_ids: list[str]
    legal_basis_ids: list[str]
    review_status: Literal["PENDING"] = "PENDING"
