from typing import Any

from app.contracts.common import Model, RequirementStatus


class RequirementResult(Model):
    tuan_thu_id: str
    yeu_cau_ca_id: str
    status: RequirementStatus
    so_tieu_chi_ap_dung: int
    so_tieu_chi_da_danh_gia: int
    so_unknown: int
    rule_version: str
    giai_thich: str
    requirement_snapshot_json: dict[str, Any]
    coverage_complete: bool
