"""Validate C07 provenance and checklist completeness at consumer boundaries."""

from legal_checker.modules.legal_knowledge.models import KnowledgeSnapshot


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
