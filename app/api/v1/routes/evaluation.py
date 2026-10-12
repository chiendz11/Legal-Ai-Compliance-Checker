from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_services
from app.application.validation import stage_context, validate_criteria
from app.bootstrap import Services
from app.contracts.modules import (
    AggregationRequest,
    ModuleResponse,
    RecommendationRequest,
    RiskRequest,
)
from app.contracts.pipeline import PipelineRequest
from app.contracts.reasoning import ReasoningPayload, ReasoningRequest
from app.modules.compliance_reasoning.service import reason
from app.modules.recommendation.service import recommend
from app.modules.risk.service import aggregate_risks
from app.modules.rule_aggregation.service import aggregate

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
def reasoning(request: PipelineRequest | ReasoningRequest, services: ServicesDependency):
    try:
        if isinstance(request, PipelineRequest):
            request = ReasoningRequest(
                **request.model_dump(exclude={"contract_name", "payload"}),
                payload=ReasoningPayload(**request.payload.model_dump(exclude={"citations"})),
            )
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
        for risk in request.payload.risks:
            if risk.ca_id != request.ca_id:
                raise ValueError("Risk belongs to a different case")
            if services.knowledge.risks.get(risk.rui_ro_id) != risk.risk_snapshot:
                raise ValueError("Risk snapshot differs from pinned knowledge")
            if risk.severity != risk.risk_snapshot["muc_do_co_so"]:
                raise ValueError("Risk severity differs from pinned catalog")
        return envelope(
            request,
            "Recommendation",
            recommend(
                context, services.knowledge, request.payload.risks, request.payload.requirements
            ),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
