"""Application composition root; business logic lives in app/modules."""

from dataclasses import replace
from pathlib import Path

from fastapi import FastAPI

from app.api.v1.router import router
from app.bootstrap import Services, build_services
from app.core.config import Settings
from app.infrastructure.knowledge.snapshot import DEFAULT_KNOWLEDGE


def create_app(
    knowledge_path: Path = DEFAULT_KNOWLEDGE,
    database_path: Path | None = None,
    *,
    services: Services | None = None,
):
    settings = Settings.from_env()
    # Retain existing factory arguments while allowing env-configured adapters.
    if knowledge_path != DEFAULT_KNOWLEDGE:
        settings = replace(settings, knowledge_path=knowledge_path)
    if database_path is not None:
        settings = replace(settings, database_path=database_path)
    api = FastAPI(title="Legal AI Compliance Checker", version="0.1.0")
    api.state.services = services if services is not None else build_services(settings)
    api.include_router(router)
    return api
