from datetime import datetime, timezone

from app.contracts.models import PipelineRequest, PipelineResponse, PipelineResult
from app.knowledge import Knowledge
from app.services.aggregation import aggregate
from app.services.reasoning import reason
from app.services.recommendation import recommend
from app.services.risk import aggregate_risks


def evaluate(request: PipelineRequest, knowledge: Knowledge) -> PipelineResponse:
    criteria = reason(request, knowledge)
    requirements = aggregate(request, knowledge, criteria)
    risks = aggregate_risks(request, knowledge, criteria)
    recommendations = recommend(request, knowledge, risks)
    context = request.model_dump(exclude={"contract_name", "payload"})
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
