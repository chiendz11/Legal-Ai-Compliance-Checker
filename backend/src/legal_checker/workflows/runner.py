"""Execute one persisted run: claim it, run steps 1–7, build the C13 draft, record outcome.

API and worker share this use case. Transient infrastructure errors are re-raised after
the run is released back to QUEUED, so the caller (Celery) retries with backoff; anything
else ends the run FAILED with a reason. A failure is processing state, never a legal label.
"""

from dataclasses import dataclass
from datetime import timedelta
from typing import Protocol

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
    if isinstance(error, (NotImplementedError, ModulesUnavailable)):
        return "MODULE_NOT_IMPLEMENTED"
    if isinstance(error, LookupError):
        return "REFERENCE_UNAVAILABLE"
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

    def execute(self, ca_id: str, run_id: str) -> RunRecord | None:
        record = self.runs.claim(ca_id, run_id, self.lease)
        if record is None:
            # Already finished, owned by a live worker, or unknown: nothing to do.
            return self.runs.get(ca_id, run_id)
        context = record.context
        try:
            case, modules, evaluator = self.source.prepare(context)
            draft = DraftAssessmentWorkflow(modules, self.knowledge, evaluator=evaluator).evaluate(
                case,
                context,
                on_stage=lambda stage, status: self.runs.mark_stage(ca_id, run_id, stage, status),
            )
            report = build_run_report(draft, self.knowledge, record.module_source)
        except TRANSIENT_ERRORS as error:
            self.runs.release(ca_id, run_id)
            raise TransientRunError(str(error)) from error
        except Exception as error:  # every other failure is recorded on the run
            self.runs.fail(ca_id, run_id, failure_reason(error), str(error))
            return self.runs.get(ca_id, run_id)
        self.runs.complete(ca_id, run_id, draft)
        self.reports.save_version(run_id, report)
        return self.runs.get(ca_id, run_id)
