"""FastAPI factory; business logic and repositories live in their owning modules."""

from fastapi import FastAPI

from legal_checker.api.dependencies import Services, build_services
from legal_checker.api.errors import install_error_handlers
from legal_checker.api.v1.router import router
from legal_checker.core.config import Settings
from legal_checker.core.logging import configure_logging
from legal_checker.core.metrics import install_metrics


def create_app(
    *,
    settings: Settings | None = None,
    services: Services | None = None,
):
    settings = settings if settings is not None else Settings.from_env()
    configure_logging()
    api = FastAPI(title="Legal AI Compliance Checker", version="0.1.0")
    api.state.services = services if services is not None else build_services(settings)
    api.include_router(router)
    install_error_handlers(api)
    install_metrics(api)
    return api
