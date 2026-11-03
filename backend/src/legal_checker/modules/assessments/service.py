"""Full-assessment use cases: start runs, expose processing state, review, rebuild and publish.

Step-specific reasoning/risk/recommendation logic belongs to its business module; this
service pins the context, persists the run, records reviews and versions the report.
"""

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol

from legal_checker.core.exceptions import ConflictError
from legal_checker.core.security import Actor
from legal_checker.modules.assessments.cases import CaseRepository
from legal_checker.modules.assessments.runs import RunRecord, RunRepository
from legal_checker.modules.legal_knowledge.models import KnowledgeSnapshot
from legal_checker.modules.reports.repository import ReportStore, StoredReport
from legal_checker.modules.reports.service import build_run_report
from legal_checker.modules.reviews.repository import ReviewRepository
from legal_checker.modules.reviews.service import (
    TARGETS,
    TargetState,
    check_review,
    digest,
    publication_blockers,
    review_layer,
    review_revision,
    target_states,
)
from legal_checker.shared.contracts.assessment import AssessmentCase
from legal_checker.shared.contracts.common import Context
from legal_checker.shared.contracts.report import FinalReport
from legal_checker.shared.contracts.review import HumanReview, ReviewTarget
from legal_checker.shared.ids import stable_id


class RunQueue(Protocol):
    def enqueue(self, ca_id: str, run_id: str) -> None: ...


class NotFound(LookupError):
    pass


class ResultNotReady(ConflictError):
    pass


class ReviewRequired(ConflictError):
    """Publication blocked: required reviews are missing or still open."""

    def __init__(self, message: str, details: list[dict[str, str]]):
        super().__init__(message)
        self.details = details


@dataclass(frozen=True)
class ReviewState:
    revision: str
    states: dict[tuple[str, str], TargetState]
    events: list[tuple[HumanReview, str]]


@dataclass
class AssessmentService:
    cases: CaseRepository
    runs: RunRepository
    reports: ReportStore
    knowledge: KnowledgeSnapshot
    queue: RunQueue
    # Fixed name, or a function of the case when the step implementations depend on it.
    module_source: str | Callable[[AssessmentCase], str]
    reviews: ReviewRepository | None = None

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
        label = self.module_source
        if callable(label):
            label = label(row.case)
        record = self.runs.create(context, idempotency_key, label)
        if record.status == "QUEUED":
            # Re-enqueueing an accepted run is safe: only one worker can claim it.
            self.queue.enqueue(record.ca_id, record.run_id)
        return record

    def get_run(self, ca_id: str, run_id: str) -> RunRecord:
        record = self.runs.get(ca_id, run_id)
        if record is None:
            raise NotFound(f"Run {run_id} not found for case {ca_id}")
        return record

    def _draft(self, ca_id: str, run_id: str):
        record = self.get_run(ca_id, run_id)
        draft = self.runs.draft(ca_id, run_id)
        if draft is None:
            raise ResultNotReady(f"Run {run_id} is {record.status}, not COMPLETED")
        return record, draft

    def _events(self, ca_id: str, run_id: str) -> list[tuple[HumanReview, str]]:
        return self.reviews.for_run(ca_id, run_id) if self.reviews else []

    def review_state(self, ca_id: str, run_id: str) -> ReviewState:
        _, draft = self._draft(ca_id, run_id)
        events = self._events(ca_id, run_id)
        plain = [event for event, _ in events]
        return ReviewState(review_revision(plain), target_states(draft, plain), events)

    def add_review(
        self,
        ca_id: str,
        run_id: str,
        actor: Actor,
        target: ReviewTarget,
        action: str,
        after: dict[str, Any],
        reason: str,
        expected_target_sha256: str,
    ) -> tuple[HumanReview, str]:
        """Append one C12 event after re-checking the target hash under a per-run lock."""
        record, draft = self._draft(ca_id, run_id)
        key = (target.doi_tuong_loai, target.doi_tuong_id)

        def check(existing: list[HumanReview]):
            state = target_states(draft, existing).get(key)
            check_review(state, action, after, expected_target_sha256)
            editable = TARGETS[state.kind].editable
            before = {name: state.effective.get(name) for name in editable}
            return {**before, "target_sha256": state.sha256}, state.sha256

        event = self.reviews.append(
            ca_id,
            run_id,
            actor.tenant_id,
            actor.actor_id,
            record.context.phien_ban_id,
            target,
            action,
            after,
            reason,
            check,
        )
        return event, expected_target_sha256

    def _variant(self, report: FinalReport, *parts: str) -> str:
        context = Context.model_validate(report.report_json.audit["context"])
        return stable_id(context, "REPORT", "/".join((report.report_json.case.hop_dong_id, *parts)))

    def build_report(self, ca_id: str, run_id: str) -> StoredReport:
        """Draft from the run's machine outputs plus the current review layer.

        Without reviews the content is identical on every rebuild (same version). Reviews add
        an `audit.review` section and make a new version; machine findings are never edited.
        """
        record, draft = self._draft(ca_id, run_id)
        report = build_run_report(draft, self.knowledge, record.module_source)
        events = [event for event, _ in self._events(ca_id, run_id)]
        revision = review_revision(events)
        if events:
            content = report.report_json
            audit = {**content.audit, "review": review_layer(target_states(draft, events), events)}
            report = report.model_copy(
                update={
                    "bao_cao_id": self._variant(report, revision),
                    "phien_ban_bao_cao": f"{report.phien_ban_bao_cao}+{revision}",
                    "review_status": "IN_REVIEW",
                    "report_json": content.model_copy(update={"audit": audit}),
                }
            )
        return self.reports.save_version(run_id, report, review_revision=revision)

    def publish(self, stored: StoredReport, actor: Actor, expected_review_revision: str):
        """Publish exactly this report version if it reflects every review of its run and no
        required review is missing; publication is a new immutable version."""
        report = stored.report
        if report.report_status == "PUBLISHED":
            raise ConflictError("This report version is already published")
        state = self.review_state(report.ca_id, stored.run_id)
        if expected_review_revision != state.revision or stored.review_revision != state.revision:
            raise ReviewRequired(
                "Reviews changed since this report version; rebuild the report and try again",
                [{"current_review_revision": state.revision}],
            )
        if state.revision == "none":
            raise ReviewRequired("A report needs at least one human review before publication", [])
        blockers = publication_blockers(state.states)
        if blockers:
            raise ReviewRequired(f"{len(blockers)} finding(s) still need review", blockers)
        published_id = self._variant(report, state.revision, "published")
        existing = self.reports.get(published_id)
        if existing is not None:  # publishing twice returns the first publication
            return existing
        audit = {
            **report.report_json.audit,
            "publication": {
                "published_by": actor.actor_id,
                "published_at": datetime.now(timezone.utc).isoformat(),
                "source_bao_cao_id": report.bao_cao_id,
                "review_revision": state.revision,
                "content_sha256": digest(report.model_dump(mode="json")),
            },
        }
        published = report.model_copy(
            update={
                "bao_cao_id": published_id,
                "report_status": "PUBLISHED",
                "review_status": "APPROVED",
                "report_json": report.report_json.model_copy(update={"audit": audit}),
            }
        )
        return self.reports.save_version(stored.run_id, published, review_revision=state.revision)

    def recover(self, queued_for, lease) -> list[tuple[str, str]]:
        """Re-enqueue runs whose job was lost (never started, or worker died mid-run)."""
        lost = self.runs.recoverable(queued_for, lease)
        for ca_id, run_id in lost:
            self.queue.enqueue(ca_id, run_id)
        return lost
