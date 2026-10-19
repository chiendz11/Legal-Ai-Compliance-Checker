"""Background assessment tasks. The task only calls the shared runner use case."""

from datetime import timedelta
from functools import cache

from legal_checker.api.dependencies import Services, build_services
from legal_checker.core.config import Settings
from legal_checker.worker.celery_app import app
from legal_checker.workflows.runner import TransientRunError


@cache
def services() -> Services:
    # One Knowledge snapshot/reader per worker process, like the API process.
    return build_services(Settings.from_env())


@app.task(
    name="legal_checker.run_assessment",
    autoretry_for=(TransientRunError,),
    retry_backoff=5,
    retry_backoff_max=120,
    retry_jitter=True,
    max_retries=4,
)
def run_assessment(ca_id: str, run_id: str) -> str | None:
    record = services().runner.execute(ca_id, run_id)
    return record.status if record else None


@app.task(name="legal_checker.recover_runs")
def recover_runs() -> int:
    settings = services().settings
    lost = services().assessment_service.recover(
        queued_for=timedelta(seconds=settings.run_requeue_after_seconds),
        lease=timedelta(seconds=settings.run_lease_seconds),
    )
    return len(lost)
