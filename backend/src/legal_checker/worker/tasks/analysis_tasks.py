"""Background assessment tasks. The task only calls the shared runner use case."""

import logging
from datetime import timedelta
from functools import cache
from threading import Event, Thread

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
    current = services()
    stop = Event()

    def heartbeat():
        interval = max(1, min(30, current.settings.run_lease_seconds / 3))
        while not stop.wait(interval):
            try:
                current.runner.runs.heartbeat(ca_id, run_id)
            except Exception:
                logging.getLogger(__name__).warning("Run heartbeat failed", exc_info=False)

    # Only heartbeat after this runner has actually claimed the run. The runner
    # invokes the hook inside its claim boundary, so duplicate jobs cannot keep a
    # stale owner's lease alive.
    thread = Thread(target=heartbeat, daemon=True)
    try:
        record = current.runner.execute(ca_id, run_id, on_claim=thread.start)
        return record.status if record else None
    finally:
        stop.set()
        if thread.ident is not None:
            thread.join(timeout=5)


@app.task(name="legal_checker.recover_runs")
def recover_runs() -> int:
    settings = services().settings
    lost = services().assessment_service.recover(
        queued_for=timedelta(seconds=settings.run_requeue_after_seconds),
        lease=timedelta(seconds=settings.run_lease_seconds),
    )
    return len(lost)
