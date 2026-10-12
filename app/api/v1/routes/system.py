from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import get_services
from app.bootstrap import Services

router = APIRouter()
ServicesDependency = Annotated[Services, Depends(get_services)]


@router.get("/health")
def health():
    return {"status": "ok", "schema_version": "v7.3.2"}


@router.get("/api/v1/knowledge")
def snapshot(services: ServicesDependency):
    knowledge = services.knowledge
    return {
        "schema_version": "v7.3.2",
        "knowledge_snapshot_sha256": knowledge.sha256,
        "counts": {k: len(v) for k, v in knowledge.tables.items()},
        "review_status": "PENDING_HUMAN_REVIEW",
    }
