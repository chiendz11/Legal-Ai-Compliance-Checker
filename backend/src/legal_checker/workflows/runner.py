"""Execute one persisted run: claim it, run steps 1–7, build the C13 draft, record outcome.

API and worker share this use case. Transient infrastructure errors are re-raised after
the run is released back to QUEUED, so the caller (Celery) retries with backoff; anything
else ends the run FAILED with a reason. A failure is processing state, never a legal label.
"""

import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import Callable, Protocol

import psycopg

from legal_checker.modules.assessments.runs import RunRecord, RunRepository
from legal_checker.modules.legal_knowledge.models import KnowledgeSnapshot
from legal_checker.modules.reports.repository import ReportStore
from legal_checker.modules.reports.service import build_run_report
from legal_checker.shared.contracts.assessment import AssessmentCase
from legal_checker.shared.contracts.common import Context
from legal_checker.workflows.assessment_workflow import (
    DraftAssessmentWorkflow,
    DraftModules,
    Evaluator,
)
from legal_checker.workflows.reference import MODULE_SOURCE, ReferenceReplay

TRANSIENT_ERRORS = (psycopg.OperationalError, TimeoutError, ConnectionError)


class TransientRunError(RuntimeError):
    """Infrastructure hiccup; the run was released to QUEUED and may be retried."""


Prepared = tuple[AssessmentCase, DraftModules, Evaluator]


class ModuleSource(Protocol):
    """Supplies the pinned case and step implementations for a run."""

    name: str

    def prepare(self, context: Context) -> Prepared: ...


class ModulesUnavailable(LookupError):
    pass


class UnconfiguredModules:
    """Default until groups A/B/C deliver: runs fail clearly instead of inventing results."""

    name = "UNCONFIGURED"

    def prepare(self, context: Context) -> Prepared:
        raise ModulesUnavailable(
            "Steps 1–7 have no implementations wired yet; set ASSESSMENT_MODULES=reference "
            "to replay QA references for integration testing"
        )


class ReferenceReplaySource:
    name = MODULE_SOURCE

    def __init__(self, database_url: str):
        self.database_url = database_url

    def prepare(self, context: Context) -> Prepared:
        replay = ReferenceReplay.load(self.database_url, context.ca_id)
        return (replay.case, *replay.build(context))


def failure_reason(error: Exception) -> str:
    if isinstance(getattr(error, "reason", None), str):  # errors that name their own cause
        return error.reason
    if isinstance(error, (NotImplementedError, ModulesUnavailable)):
        return "MODULE_NOT_IMPLEMENTED"
    if isinstance(error, ValueError):
        return "HANDOFF_VALIDATION_FAILED"
    return "UNEXPECTED_ERROR"


@dataclass
class AssessmentRunner:
    runs: RunRepository
    reports: ReportStore
    knowledge: KnowledgeSnapshot
    source: ModuleSource
    lease: timedelta = timedelta(minutes=10)

    def execute(
        self, ca_id: str, run_id: str, *, on_claim: Callable[[], None] | None = None
    ) -> RunRecord | None:
        record = self.runs.claim(ca_id, run_id, self.lease)
        if record is None:
            # Already finished, owned by a live worker, or unknown: nothing to do.
            return self.runs.get(ca_id, run_id)
        if on_claim:
            on_claim()
        context = record.context
        running: set[str] = set()
        log = logging.getLogger(__name__)
        log_context = {"ca_id": ca_id, "run_id": run_id, "trace_id": context.trace_id}
        log.info("assessment_started", extra=log_context)

        def on_stage(stage, status):
            (running.add if status == "RUNNING" else running.discard)(stage)
            self.runs.mark_stage(ca_id, run_id, stage, status)
            log.info("assessment_stage", extra={**log_context, "stage": stage, "status": status})

        try:
            case, modules, evaluator = self.source.prepare(context)
            draft = DraftAssessmentWorkflow(modules, self.knowledge, evaluator=evaluator).evaluate(
                case, context, on_stage=on_stage
            )
            report = build_run_report(draft, self.knowledge, record.module_source)
        except TRANSIENT_ERRORS as error:
            self.runs.release(ca_id, run_id)
            raise TransientRunError(str(error)) from error
        except Exception as error:  # every other failure is recorded on the run
            for stage in sorted(running):  # the stage(s) in flight when it failed
                self.runs.mark_stage(ca_id, run_id, stage, "FAILED")
            self.runs.fail(ca_id, run_id, failure_reason(error), str(error))
            return self.runs.get(ca_id, run_id)
        self.runs.complete(ca_id, run_id, draft)
        self.reports.save_version(run_id, report)
        log.info("assessment_completed", extra=log_context)
        return self.runs.get(ca_id, run_id)
