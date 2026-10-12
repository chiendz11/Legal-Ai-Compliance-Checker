"""Application composition root; business logic lives in app/modules."""

from fastapi import FastAPI

from app.api.v1.router import router
from app.bootstrap import Services, build_services
from app.core.config import Settings


def create_app(
    *,
    settings: Settings | None = None,
    services: Services | None = None,
):
    settings = settings if settings is not None else Settings.from_env()
    api = FastAPI(title="Legal AI Compliance Checker", version="0.1.0")
    api.state.services = services if services is not None else build_services(settings)
    api.include_router(router)
    return api
