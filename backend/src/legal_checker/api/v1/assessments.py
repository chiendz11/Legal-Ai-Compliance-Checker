from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from legal_checker.api.dependencies import Services, get_services
from legal_checker.shared.contracts.pipeline import PipelineResponse

router = APIRouter(prefix="/api/v1")
ServicesDependency = Annotated[Services, Depends(get_services)]


@router.get("/cases/{ca_id}/runs/{run_id}", response_model=PipelineResponse)
def get_run(ca_id: str, run_id: str, services: ServicesDependency):
    response = services.assessments.get(ca_id, run_id)
    if response is None:
        raise HTTPException(status_code=404, detail="Assessment run not found")
    return response
