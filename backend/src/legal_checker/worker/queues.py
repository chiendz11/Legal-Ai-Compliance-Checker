"""Queue adapters behind RunQueue: Celery for deployments, in-process threads for local dev."""

import logging
from concurrent.futures import ThreadPoolExecutor

from legal_checker.workflows.runner import AssessmentRunner

log = logging.getLogger(__name__)


class CeleryQueue:
    def enqueue(self, ca_id: str, run_id: str) -> None:
        from legal_checker.worker.tasks.analysis_tasks import run_assessment

        run_assessment.delay(ca_id, run_id)


class InlineQueue:
    """Runs jobs on a small thread pool inside the API process. No retry or crash recovery
    beyond the persisted run state; meant for machines without Redis."""

    def __init__(self, runner: AssessmentRunner, workers: int = 2):
        self.runner = runner
        self.pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="assessment")

    def enqueue(self, ca_id: str, run_id: str) -> None:
        self.pool.submit(self._run, ca_id, run_id)

    def _run(self, ca_id: str, run_id: str) -> None:
        try:
            self.runner.execute(ca_id, run_id)
        except Exception:  # transient errors leave the run QUEUED for recovery
            log.exception("Assessment run %s/%s did not finish", ca_id, run_id)
