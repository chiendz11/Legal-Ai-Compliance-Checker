from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from legal_checker.api.dependencies import Services, get_services
from legal_checker.core.exceptions import ConflictError
from legal_checker.modules.assessments.service import run_steps_5_7
from legal_checker.shared.contracts.pipeline import PipelineRequest, PipelineResponse

router = APIRouter(prefix="/api/v1")
ServicesDependency = Annotated[Services, Depends(get_services)]


@router.post("/pipeline/steps-5-7", response_model=PipelineResponse)
def pipeline(request: PipelineRequest, services: ServicesDependency):
    try:
        return run_steps_5_7(request, services.knowledge, services.assessments)
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
