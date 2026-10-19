from fastapi import APIRouter

from legal_checker.api.v1 import (
    assessments,
    cases,
    contracts,
    legal_knowledge,
    reports,
    reviews,
    system,
)

router = APIRouter()
router.include_router(system.router, tags=["system"])
router.include_router(legal_knowledge.router, tags=["system"])
router.include_router(assessments.router, tags=["assessments"])
router.include_router(cases.router)

router.include_router(contracts.router, tags=["contracts"])
router.include_router(reviews.router, tags=["reviews"])
router.include_router(reports.router, tags=["reports"])
