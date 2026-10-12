from fastapi import APIRouter

from app.api.v1.routes import assessments, evaluation, system

router = APIRouter()
router.include_router(system.router, tags=["system"])
router.include_router(assessments.router, tags=["assessments"])
router.include_router(evaluation.router, tags=["evaluation"])
