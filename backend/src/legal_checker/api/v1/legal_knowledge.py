from typing import Annotated

from fastapi import APIRouter, Depends

from legal_checker.api.dependencies import Services, get_services

router = APIRouter()
ServicesDependency = Annotated[Services, Depends(get_services)]


@router.get("/api/v1/knowledge")
def snapshot(services: ServicesDependency):
    knowledge = services.knowledge
    return {
        "schema_version": knowledge.schema_version,
        "knowledge_snapshot_sha256": knowledge.sha256,
        "counts": {k: len(v) for k, v in knowledge.tables.items()},
        "review_status": "PENDING_HUMAN_REVIEW",
    }
