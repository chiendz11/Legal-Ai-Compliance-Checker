import json

from app.application.ports.knowledge import KnowledgeSnapshot
from app.contracts.common import Context
from app.contracts.risk import RiskResult
from app.contracts.temporal import ApplicableRequirement
from app.core.validation import validate_citations, validate_context, validate_requirements


def stage_context(request, knowledge: KnowledgeSnapshot) -> Context:
    context = request.model_dump(exclude={"contract_name", "payload"})
    context = Context(**context)
    validate_context(context, knowledge)
    validate_requirements(context, request.payload.requirements, knowledge)
    validate_citations(context, getattr(request.payload, "citations", []))
    return context


def validate_criteria(request, knowledge: KnowledgeSnapshot, complete: bool = False):
    requirements = {r.yeu_cau_ca_id: r for r in request.payload.requirements}
    seen = set()
    for result in request.payload.criterion_results:
        requirement = requirements.get(result.yeu_cau_ca_id)
        criterion = knowledge.criteria.get(result.tieu_chi_id)
        if (
            not requirement
            or not criterion
            or result.ca_id != request.ca_id
            or result.lan_chay_id != request.run_id
            or criterion["requirement_version_id"] != requirement.requirement_version_id
        ):
            raise ValueError("Criterion result case/run/version does not match consumer context")
        key = (result.yeu_cau_ca_id, result.tieu_chi_id)
        if key in seen:
            raise ValueError("Duplicate criterion result")
        seen.add(key)
        if result.mandatory != bool(criterion["bat_buoc"]):
            raise ValueError("Criterion mandatory flag differs from knowledge")
        if result.tieu_chi_snapshot_json.get("criterion") != criterion:
            raise ValueError("Criterion snapshot differs from pinned knowledge")
        if set(result.legal_basis_ids) != set(knowledge.legal_basis(criterion)):
            raise ValueError("Criterion legal basis differs from pinned knowledge")
        decision = knowledge.decision(result.tieu_chi_id, result.finding)
        if result.tieu_chi_snapshot_json.get("decision_rule") != decision:
            raise ValueError("Criterion decision rule differs from pinned knowledge")
        if result.finding == "MISSING" and not criterion["noi_dung_bat_buoc_trong_hd"]:
            raise ValueError("MISSING requires mandatory contract content")
        if result.finding != "UNKNOWN" and not requirement.confirmed:
            raise ValueError("Known finding requires confirmed applicability")
        if result.excluded and (
            result.finding != "UNKNOWN" or not requirement.confirmed or not result.gates.reliable()
        ):
            raise ValueError("Exclusion requires verified applicability and evidence gates")
    if complete:
        expected = {
            (r.yeu_cau_ca_id, c["tieu_chi_id"])
            for r in requirements.values()
            if r.applicability_status != "NOT_APPLICABLE"
            for c in knowledge.criteria_for(r.requirement_version_id)
        }
        if seen != expected:
            raise ValueError("Aggregation requires the complete criterion checklist")


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
