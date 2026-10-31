"""Pure steps 5–7 composition. Citation joins compliance only at risk mapping."""

from datetime import datetime, timezone

from legal_checker.modules.compliance.criterion_reasoner import reason
from legal_checker.modules.compliance.requirement_aggregator import (
    aggregate,
    excluded_requirement_ids,
)
from legal_checker.modules.legal_knowledge.models import KnowledgeSnapshot
from legal_checker.modules.recommendations.service import generate_recommendations
from legal_checker.modules.risks.service import evaluate_risks
from legal_checker.shared.contracts.common import Context
from legal_checker.shared.contracts.modules import RecommendationRequest, RiskRequest
from legal_checker.shared.contracts.pipeline import (
    PipelineRequest,
    PipelineResponse,
    PipelineResult,
)
from legal_checker.shared.contracts.reasoning import ReasoningPayload, ReasoningRequest
from legal_checker.shared.validation import validate_request


def evaluate(request: PipelineRequest, knowledge: KnowledgeSnapshot) -> PipelineResponse:
    """Compute each branch once, retaining missing-input and knowledge diagnostics."""
    request = PipelineRequest.model_validate(request.model_dump())
    validate_request(request, knowledge)
    context = request.model_dump(include=set(Context.model_fields))
    payload = request.payload
    criteria = reason(
        ReasoningRequest(
            **context,
            payload=payload.model_dump(include=set(ReasoningPayload.model_fields)),
        ),
        knowledge,
    )
    requirements = aggregate(request, knowledge, criteria, payload.requirements)
    diagnostics = []
    citation_status = payload.citation_branch_status or (
        "COMPLETED" if payload.citations else "NOT_RUN"
    )
    diagnostics.append(
        {
            "module": "C09",
            "code": "CITATION_BRANCH_" + citation_status,
            "finding_count": len(payload.citations),
        }
    )
    diagnostics.extend(
        {
            "module": "C07",
            "code": "UNRESOLVED_CRITERION",
            "tieu_chi_id": result.tieu_chi_id,
            "yeu_cau_ca_id": result.yeu_cau_ca_id,
            "reason": result.uncertainty_reason,
        }
        for result in criteria
        if result.finding == "UNKNOWN" and not result.excluded
    )
    for requirement in requirements:
        if requirement.status == "INSUFFICIENT":
            diagnostics.append(
                {
                    "module": "C08",
                    "code": "INSUFFICIENT_REQUIREMENT",
                    "yeu_cau_ca_id": requirement.yeu_cau_ca_id,
                    "reason": requirement.giai_thich,
                }
            )
    common = {"hop_dong_id": payload.hop_dong_id, "requirements": payload.requirements}
    risks = evaluate_risks(
        RiskRequest(
            **context,
            payload={**common, "criterion_results": criteria, "citations": payload.citations},
        ),
        knowledge,
        diagnostics=diagnostics,
    )
    recommendations = generate_recommendations(
        RecommendationRequest(**context, payload={**common, "risks": risks}),
        knowledge,
        diagnostics=diagnostics,
    )
    return PipelineResponse(
        **context,
        produced_at=datetime.now(timezone.utc),
        payload=PipelineResult(
            criterion_results=criteria,
            requirement_results=requirements,
            risks=risks,
            recommendations=recommendations,
            excluded_requirements=excluded_requirement_ids(
                request, knowledge, payload.requirements
            ),
            diagnostics=diagnostics,
        ),
    )
