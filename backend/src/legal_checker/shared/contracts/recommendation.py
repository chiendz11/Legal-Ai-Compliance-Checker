from typing import Any, Literal

from pydantic import Field

from legal_checker.shared.contracts.common import Model, Severity


class Recommendation(Model):
    khuyen_nghi_ca_id: str
    ket_qua_rui_ro_id: str
    khuyen_nghi_id: str
    noi_dung: str
    loai_hanh_dong: str
    uu_tien: Severity
    dieu_kien_snapshot: dict[str, Any]
    evidence_ids: list[str]
    legal_basis_ids: list[str]
    template_snapshot_json: dict[str, Any]
    rule_version: str
    knowledge_snapshot_sha256: str
    model_version: str = Field(default="TEMPLATE_ENGINE_NO_LLM", min_length=1)
    prompt_version: str = Field(default="NOT_USED", min_length=1)
    review_status: Literal["PENDING"] = "PENDING"
