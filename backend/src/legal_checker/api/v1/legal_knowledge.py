from typing import Annotated

from fastapi import APIRouter, Depends

from legal_checker.api.dependencies import Services, get_services
from legal_checker.api.v1.schemas import KnowledgeInfo

router = APIRouter()
ServicesDependency = Annotated[Services, Depends(get_services)]


@router.get("/api/v1/knowledge", response_model=KnowledgeInfo)
def snapshot(services: ServicesDependency):
    knowledge = services.knowledge
    review = getattr(knowledge, "review_status", None)
    return {
        "schema_version": knowledge.schema_version,
        "knowledge_snapshot_sha256": knowledge.sha256,
        "counts": {k: len(v) for k, v in knowledge.tables.items()},
        "review_status": review
        if review in {"HUMAN_VERIFIED", "SOURCE_CHECKED"}
        else "PENDING_HUMAN_REVIEW",
    }
