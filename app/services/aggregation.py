from app.contracts.models import CriterionResult, PipelineRequest, RequirementResult
from app.knowledge import Knowledge
from app.services.reasoning import stable_id


def aggregate(request: PipelineRequest, knowledge: Knowledge, criteria: list[CriterionResult]):
    results = []
    for req in request.payload.requirements:
        if req.applicability_status == "NOT_APPLICABLE":
            continue
        version = knowledge.versions.get(req.requirement_version_id, {})
        rule = knowledge.aggregations.get(version.get("quy_tac_tong_hop_id"), {})
        if rule and rule["quy_tac_tong_hop_id"] != "AGG_CAN_HO_V1":
            raise ValueError("Unsupported aggregation policy")
        applicable = [
            r
            for r in criteria
            if r.yeu_cau_ca_id == req.yeu_cau_ca_id and r.mandatory and not r.excluded
        ]
        findings = [r.finding for r in applicable]
        unknown = findings.count("UNKNOWN")
        if not req.confirmed or not rule or not findings:
            status = "INSUFFICIENT"
        elif "VIOLATED" in findings:
            status = "NON_COMPLIANT"
        elif unknown:
            status = "INSUFFICIENT"
        elif all(f == "MISSING" for f in findings):
            status = "NON_COMPLIANT"
        elif "MISSING" in findings:
            status = "PARTIAL"
        else:
            status = "COMPLIANT"
        results.append(
            RequirementResult(
                tuan_thu_id=stable_id(request, "TT", req.yeu_cau_ca_id),
                yeu_cau_ca_id=req.yeu_cau_ca_id,
                status=status,
                so_tieu_chi_ap_dung=len(applicable),
                so_tieu_chi_da_danh_gia=len(applicable) - unknown,
                so_unknown=unknown,
                rule_version=request.rule_version,
                giai_thich=f"{status}: mandatory criterion findings={findings}; "
                f"scope/version confirmed={req.confirmed}",
                requirement_snapshot_json={
                    "applicable_requirement": req.model_dump(mode="json"),
                    "version": version,
                    "aggregation_rule": rule,
                },
                coverage_complete=bool(findings) and unknown == 0 and req.confirmed,
            )
        )
    return results
