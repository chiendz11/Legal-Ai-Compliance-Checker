from app.application.ports.knowledge import KnowledgeSnapshot
from app.contracts.common import Context
from app.contracts.pipeline import PipelinePayload, PipelineRequest
from app.core.validation import validate_request


def stage_context(request, knowledge: KnowledgeSnapshot) -> Context:
    context = request.model_dump(exclude={"contract_name", "payload"})
    pipeline = PipelineRequest(
        **context,
        payload=PipelinePayload(
            hop_dong_id=request.payload.hop_dong_id,
            requirements=request.payload.requirements,
            citations=getattr(request.payload, "citations", []),
        ),
    )
    validate_request(pipeline, knowledge)
    return Context(**context)


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
        if result.finding != "UNKNOWN" and not requirement.confirmed:
            raise ValueError("Known finding requires confirmed applicability")
        if result.excluded and (not requirement.confirmed or not result.gates.reliable()):
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
