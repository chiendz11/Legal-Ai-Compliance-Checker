from datetime import datetime, timezone

from app.business_modules.compliance_reasoning.runner import evaluate_compliance
from app.business_modules.recommendation.service import recommend
from app.business_modules.risk.service import citation_risks
from app.contracts.pipeline import PipelineRequest, PipelineResponse, PipelineResult
from app.contracts.reasoning import ReasoningPayload, ReasoningRequest
from app.shared.validation import validate_request
from app.workflows.interfaces.knowledge import KnowledgeSnapshot


def evaluate(request: PipelineRequest, knowledge: KnowledgeSnapshot) -> PipelineResponse:
    validate_request(request, knowledge)
    context = request.model_dump(exclude={"contract_name", "payload"})
    reasoning_request = ReasoningRequest(
        **context,
        payload=ReasoningPayload(**request.payload.model_dump(exclude={"citations"})),
    )
    compliance = evaluate_compliance(reasoning_request, knowledge)
    extra_risks = citation_risks(compliance.context, knowledge, request.payload.citations)
    extra_recommendations = recommend(
        compliance.context, knowledge, extra_risks, request.payload.requirements
    )
    return PipelineResponse(
        **context,
        produced_at=datetime.now(timezone.utc),
        payload=PipelineResult(
            criterion_results=compliance.criterion_results,
            requirement_results=compliance.requirement_results,
            risks=compliance.risks + extra_risks,
            recommendations=compliance.recommendations + extra_recommendations,
            excluded_requirements=[
                r.yeu_cau_ca_id
                for r in request.payload.requirements
                if r.applicability_status == "NOT_APPLICABLE"
            ],
        ),
    )
