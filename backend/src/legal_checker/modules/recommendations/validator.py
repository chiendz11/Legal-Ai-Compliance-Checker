"""Validate C10 before selecting recommendation templates."""

import json

from legal_checker.modules.legal_knowledge.models import KnowledgeSnapshot
from legal_checker.shared.contracts.common import Context
from legal_checker.shared.contracts.risk import RiskResult
from legal_checker.shared.contracts.temporal import ApplicableRequirement


def validate_risks(
    context: Context,
    risks: list[RiskResult],
    knowledge: KnowledgeSnapshot,
    requirements: list[ApplicableRequirement],
):
    """Validate C10 at the Recommendation boundary, independent of HTTP routing."""
    rules = {r["quy_tac_id"]: r for r in knowledge.tables["quy_tac_rui_ro"]}
    applicable = {r.yeu_cau_ca_id: r for r in requirements}
    seen = set()
    for risk in risks:
        if risk.ket_qua_rui_ro_id in seen:
            raise ValueError("Duplicate risk result IDs")
        seen.add(risk.ket_qua_rui_ro_id)
        if risk.ca_id != context.ca_id:
            raise ValueError("Risk belongs to a different case")
        if knowledge.risks.get(risk.rui_ro_id) != risk.risk_snapshot:
            raise ValueError("Risk snapshot differs from pinned knowledge")
        if risk.severity != risk.risk_snapshot["muc_do_co_so"]:
            raise ValueError("Risk severity differs from pinned catalog")
        rule = rules.get(risk.quy_tac_id)
        if not rule or rule != risk.rule_snapshot_json or rule["rui_ro_id"] != risk.rui_ro_id:
            raise ValueError("Risk rule differs from pinned knowledge")
        branch = "CITATION" if risk.source.citation_finding_id else "COMPLIANCE"
        if rule["nhanh"] != branch:
            raise ValueError("Risk source differs from rule branch")
        expected_type = "VERIFICATION" if rule["trigger_status"] == "UNKNOWN" else branch
        if risk.risk_type != expected_type:
            raise ValueError("Risk type differs from source branch")
        if branch == "COMPLIANCE":
            requirement = applicable.get(risk.source.yeu_cau_ca_id)
            criterion = knowledge.criteria.get(rule["tieu_chi_id"])
            if (
                not requirement
                or not criterion
                or criterion["requirement_version_id"] != requirement.requirement_version_id
            ):
                raise ValueError("Risk criterion is outside the applicable checklist")
            if json.loads(rule["trigger_json"]).get("enabled") is not True:
                raise ValueError("Risk rule is disabled")
            if set(risk.legal_basis_ids) != set(knowledge.legal_basis(criterion)):
                raise ValueError("Risk legal basis differs from pinned knowledge")
