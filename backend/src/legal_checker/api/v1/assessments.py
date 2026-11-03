from fastapi import APIRouter, HTTPException

from legal_checker.api.auth import ActorDependency, ServicesDependency
from legal_checker.shared.contracts.pipeline import PipelineResponse

router = APIRouter(prefix="/api/v1")


@router.get("/cases/{ca_id}/runs/{run_id}", response_model=PipelineResponse)
def get_run(ca_id: str, run_id: str, services: ServicesDependency, actor: ActorDependency):
    # Other tenants' cases look absent; minimal compositions without cases skip the check.
    if services.cases is not None:
        owner = services.cases.tenant_of(ca_id)
        if owner is not None and owner != actor.tenant_id:
            raise HTTPException(status_code=404, detail="Assessment run not found")
    response = services.assessments.get(ca_id, run_id)
    if response is None:
        raise HTTPException(status_code=404, detail="Assessment run not found")
    return response
