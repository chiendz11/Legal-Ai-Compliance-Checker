from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_services
from app.bootstrap import Services
from app.business_modules.compliance_reasoning.service import reason
from app.business_modules.recommendation.service import recommend
from app.business_modules.risk.service import aggregate_risks
from app.business_modules.rule_aggregation.service import aggregate
from app.contracts.modules import (
    AggregationRequest,
    ModuleResponse,
    RecommendationRequest,
    RiskRequest,
)
from app.contracts.reasoning import ReasoningRequest
from app.workflows.validation import stage_context, validate_criteria, validate_risks

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
        context = stage_context(request, services.knowledge)
        validate_criteria(request, services.knowledge)
        return envelope(
            request,
            "RiskResult",
            aggregate_risks(
                context,
                services.knowledge,
                request.payload.criterion_results,
                request.payload.citations,
            ),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/recommendations", response_model=ModuleResponse)
def recommendations(request: RecommendationRequest, services: ServicesDependency):
    try:
        context = stage_context(request, services.knowledge)
        validate_risks(
            context, request.payload.risks, services.knowledge, request.payload.requirements
        )
        return envelope(
            request,
            "Recommendation",
            recommend(
                context, services.knowledge, request.payload.risks, request.payload.requirements
            ),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
