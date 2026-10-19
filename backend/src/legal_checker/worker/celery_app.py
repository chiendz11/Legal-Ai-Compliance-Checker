"""Celery application for background assessments (Redis broker).

Install the `worker` extra and run:
    celery -A legal_checker.worker.celery_app worker --loglevel=INFO
    celery -A legal_checker.worker.celery_app beat   # optional: periodic lost-run recovery
"""

import os

from celery import Celery

from legal_checker.core.config import Settings

settings = Settings.from_env()

app = Celery(
    "legal_checker",
    broker=settings.redis_url,
    include=["legal_checker.worker.tasks.analysis_tasks"],
)
app.conf.update(
    task_acks_late=True,  # a crashed worker's job returns to the queue
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_default_queue="assessments",
    broker_connection_retry_on_startup=True,
    beat_schedule={
        "recover-lost-runs": {
            "task": "legal_checker.recover_runs",
            "schedule": float(os.getenv("RUN_RECOVERY_INTERVAL_SECONDS", "60")),
        }
    },
)
