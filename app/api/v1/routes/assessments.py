from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_services
from app.bootstrap import Services
from app.contracts.pipeline import PipelineRequest, PipelineResponse
from app.shared.errors import ConflictError
from app.workflows.pipelines.steps_5_7 import evaluate

router = APIRouter(prefix="/api/v1")
ServicesDependency = Annotated[Services, Depends(get_services)]


@router.post("/pipeline/steps-5-7", response_model=PipelineResponse)
def pipeline(request: PipelineRequest, services: ServicesDependency):
    try:
        response = evaluate(request, services.knowledge)
        return services.assessments.save(request, response)
    except ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/cases/{ca_id}/runs/{run_id}", response_model=PipelineResponse)
def get_run(ca_id: str, run_id: str, services: ServicesDependency):
    response = services.assessments.get(ca_id, run_id)
    if response is None:
        raise HTTPException(status_code=404, detail="Assessment run not found")
    return response
