from datetime import datetime, timezone

from app.application.ports.knowledge import KnowledgeSnapshot
from app.contracts.common import Context
from app.contracts.pipeline import PipelineRequest, PipelineResponse, PipelineResult
from app.contracts.reasoning import ReasoningPayload, ReasoningRequest
from app.core.validation import validate_request
from app.modules.compliance_reasoning.service import reason
from app.modules.recommendation.service import recommend
from app.modules.risk.service import aggregate_risks
from app.modules.rule_aggregation.service import aggregate


def evaluate(request: PipelineRequest, knowledge: KnowledgeSnapshot) -> PipelineResponse:
    validate_request(request, knowledge)
    context = request.model_dump(exclude={"contract_name", "payload"})
    reasoning_request = ReasoningRequest(
        **context,
        payload=ReasoningPayload(**request.payload.model_dump(exclude={"citations"})),
    )
    module_context = Context(**context)
    criteria = reason(reasoning_request, knowledge)
    requirements = aggregate(module_context, knowledge, criteria, request.payload.requirements)
    risks = aggregate_risks(module_context, knowledge, criteria, request.payload.citations)
    recommendations = recommend(module_context, knowledge, risks, request.payload.requirements)
    return PipelineResponse(
        **context,
        produced_at=datetime.now(timezone.utc),
        payload=PipelineResult(
            criterion_results=criteria,
            requirement_results=requirements,
            risks=risks,
            recommendations=recommendations,
            excluded_requirements=[
                r.yeu_cau_ca_id
                for r in request.payload.requirements
                if r.applicability_status == "NOT_APPLICABLE"
            ],
        ),
    )
