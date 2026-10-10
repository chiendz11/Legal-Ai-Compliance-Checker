import os
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException

from app.contracts.models import PipelineRequest, PipelineResponse
from app.contracts.modules import (
    AggregationRequest,
    ModuleResponse,
    RecommendationRequest,
    RiskRequest,
)
from app.knowledge import DEFAULT_KNOWLEDGE, Knowledge
from app.services.aggregation import aggregate
from app.services.interfaces import stage_context, validate_criteria
from app.services.pipeline import evaluate
from app.services.reasoning import reason
from app.services.recommendation import recommend
from app.services.risk import aggregate_risks
from app.storage import ConflictError, Store


def create_app(knowledge_path: Path = DEFAULT_KNOWLEDGE, database_path: Path | None = None):
    knowledge = Knowledge(knowledge_path)
    store = Store(database_path or Path(os.getenv("DATABASE_PATH", "data/private/runtime.sqlite3")))
    api = FastAPI(title="Legal AI Compliance Checker", version="0.1.0")

    @api.get("/health")
    def health():
        return {"status": "ok", "schema_version": "v7.3.2"}

    @api.get("/api/v1/knowledge")
    def snapshot():
        return {
            "schema_version": "v7.3.2",
            "knowledge_snapshot_sha256": knowledge.sha256,
            "counts": {k: len(v) for k, v in knowledge.tables.items()},
            "review_status": "PENDING_HUMAN_REVIEW",
        }

    @api.post("/api/v1/pipeline/steps-5-7", response_model=PipelineResponse)
    def pipeline(request: PipelineRequest):
        try:
            response = evaluate(request, knowledge)
            return store.save(request, response)
        except ConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @api.get("/api/v1/cases/{ca_id}/runs/{run_id}", response_model=PipelineResponse)
    def get_run(ca_id: str, run_id: str):
        response = store.get(ca_id, run_id)
        if response is None:
            raise HTTPException(status_code=404, detail="Assessment run not found")
        return response

    def envelope(request, name, payload):
        return ModuleResponse(
            **request.model_dump(exclude={"payload", "contract_name"}),
            contract_name=name,
            produced_at=datetime.now(timezone.utc),
            payload=payload,
        )

    @api.post("/api/v1/reasoning", response_model=ModuleResponse)
    def reasoning(request: PipelineRequest):
        try:
            return envelope(request, "CriterionReasoning", reason(request, knowledge))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @api.post("/api/v1/aggregation", response_model=ModuleResponse)
    def aggregation(request: AggregationRequest):
        try:
            context = stage_context(request, knowledge)
            validate_criteria(request, knowledge, complete=True)
            return envelope(
                request,
                "RequirementAggregation",
                aggregate(context, knowledge, request.payload.criterion_results),
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @api.post("/api/v1/risks", response_model=ModuleResponse)
    def risks(request: RiskRequest):
        try:
            context = stage_context(request, knowledge)
            validate_criteria(request, knowledge)
            return envelope(
                request,
                "RiskResult",
                aggregate_risks(context, knowledge, request.payload.criterion_results),
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @api.post("/api/v1/recommendations", response_model=ModuleResponse)
    def recommendations(request: RecommendationRequest):
        try:
            context = stage_context(request, knowledge)
            for risk in request.payload.risks:
                if risk.ca_id != request.ca_id:
                    raise ValueError("Risk belongs to a different case")
                if knowledge.risks.get(risk.rui_ro_id) != risk.risk_snapshot:
                    raise ValueError("Risk snapshot differs from pinned knowledge")
                if risk.severity != risk.risk_snapshot["muc_do_co_so"]:
                    raise ValueError("Risk severity differs from pinned catalog")
            return envelope(
                request, "Recommendation", recommend(context, knowledge, request.payload.risks)
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    return api
