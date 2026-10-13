from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from legal_checker.api.dependencies import Services, get_services
from legal_checker.modules.compliance.criterion_reasoner import reason
from legal_checker.modules.compliance.grounding_validator import validate_criteria
from legal_checker.modules.compliance.requirement_aggregator import aggregate
from legal_checker.modules.recommendations.service import generate_recommendations
from legal_checker.modules.risks.service import evaluate_risks
from legal_checker.shared.contracts.modules import (
    AggregationRequest,
    ModuleResponse,
    RecommendationRequest,
    RiskRequest,
)
from legal_checker.shared.contracts.reasoning import ReasoningRequest
from legal_checker.shared.validation import stage_context

router = APIRouter(prefix="/api/v1")
ServicesDependency = Annotated[Services, Depends(get_services)]


def envelope(request, name, payload):
    return ModuleResponse(
        **request.model_dump(exclude={"payload", "contract_name"}),
        contract_name=name,
        produced_at=datetime.now(timezone.utc),
        payload=payload,
    )


@router.post("/reasoning", response_model=ModuleResponse)
def reasoning(request: ReasoningRequest, services: ServicesDependency):
    try:
        return envelope(request, "CriterionReasoning", reason(request, services.knowledge))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/aggregation", response_model=ModuleResponse)
def aggregation(request: AggregationRequest, services: ServicesDependency):
    try:
        context = stage_context(request, services.knowledge)
        validate_criteria(request, services.knowledge, complete=True)
        return envelope(
            request,
            "RequirementAggregation",
            aggregate(
                context,
                services.knowledge,
                request.payload.criterion_results,
                request.payload.requirements,
            ),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/risks", response_model=ModuleResponse)
def risks(request: RiskRequest, services: ServicesDependency):
    try:
        return envelope(request, "RiskResult", evaluate_risks(request, services.knowledge))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/recommendations", response_model=ModuleResponse)
def recommendations(request: RecommendationRequest, services: ServicesDependency):
    try:
        return envelope(
            request, "Recommendation", generate_recommendations(request, services.knowledge)
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
