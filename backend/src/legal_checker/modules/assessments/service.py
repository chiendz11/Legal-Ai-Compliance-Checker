"""Full-assessment use cases: start runs, expose processing state, rebuild report drafts.

Step-specific reasoning/risk/recommendation logic belongs to its business module; this
service only pins the context, persists the run and hands it to a queue.
"""

import uuid
from dataclasses import dataclass
from typing import Protocol

from legal_checker.core.exceptions import ConflictError
from legal_checker.modules.assessments.cases import CaseRepository
from legal_checker.modules.assessments.runs import RunRecord, RunRepository
from legal_checker.modules.legal_knowledge.models import KnowledgeSnapshot
from legal_checker.modules.reports.repository import ReportStore, StoredReport
from legal_checker.modules.reports.service import build_run_report
from legal_checker.shared.contracts.common import Context


class RunQueue(Protocol):
    def enqueue(self, ca_id: str, run_id: str) -> None: ...


class NotFound(LookupError):
    pass


class ResultNotReady(ConflictError):
    pass


@dataclass
class AssessmentService:
    cases: CaseRepository
    runs: RunRepository
    reports: ReportStore
    knowledge: KnowledgeSnapshot
    queue: RunQueue
    module_source: str

    def start_run(self, ca_id: str, idempotency_key: str) -> RunRecord:
        """Pin deployment/knowledge server-side; the same key returns the original run."""
        row = self.cases.get(ca_id)
        if row is None:
            raise NotFound(f"Case {ca_id} not found")
        token = uuid.uuid4().hex
        context = Context(
            ca_id=ca_id,
            **row.case.deployment.model_dump(),
            knowledge_snapshot_sha256=self.knowledge.sha256,
            run_id=f"RUN_{token}",
            trace_id=f"TRACE_{token}",
        )
        record = self.runs.create(context, idempotency_key, self.module_source)
        if record.status == "QUEUED":
            # Re-enqueueing an accepted run is safe: only one worker can claim it.
            self.queue.enqueue(record.ca_id, record.run_id)
        return record

    def get_run(self, ca_id: str, run_id: str) -> RunRecord:
        record = self.runs.get(ca_id, run_id)
        if record is None:
            raise NotFound(f"Run {run_id} not found for case {ca_id}")
        return record

    def build_report(self, ca_id: str, run_id: str) -> StoredReport:
        """Rebuild the draft from the completed run; identical content returns the same version."""
        record = self.get_run(ca_id, run_id)
        draft = self.runs.draft(ca_id, run_id)
        if draft is None:
            raise ResultNotReady(f"Run {run_id} is {record.status}, not COMPLETED")
        report = build_run_report(draft, self.knowledge, record.module_source)
        return self.reports.save_version(run_id, report)

    def recover(self, queued_for, lease) -> list[tuple[str, str]]:
        """Re-enqueue runs whose job was lost (never started, or worker died mid-run)."""
        lost = self.runs.recoverable(queued_for, lease)
        for ca_id, run_id in lost:
            self.queue.enqueue(ca_id, run_id)
        return lost
