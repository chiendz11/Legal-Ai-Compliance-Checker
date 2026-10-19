"""Persisted full-assessment runs: acceptance, worker claim, stage progress and outcome.

A run row is created QUEUED before any job is enqueued, so a lost enqueue is recovered by
re-queuing rows that never started. Workers claim with a row lock; a RUNNING row whose
heartbeat is older than the lease can be reclaimed after a worker crash.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from psycopg.types.json import Jsonb

from legal_checker.core.exceptions import ConflictError
from legal_checker.core.postgres import connect_postgres
from legal_checker.shared.contracts.common import Context
from legal_checker.shared.contracts.workflow import AssessmentDraft
from legal_checker.workflows.states import Stage, StageStatus, initial_stages


@dataclass(frozen=True)
class RunRecord:
    context: Context
    module_source: str
    status: str
    stages: list[dict]
    error: dict | None
    attempts: int
    created_at: datetime
    updated_at: datetime

    @property
    def ca_id(self) -> str:
        return self.context.ca_id

    @property
    def run_id(self) -> str:
        return self.context.run_id


def _record(row) -> RunRecord:
    return RunRecord(
        context=Context.model_validate(row["context_json"]),
        module_source=row["module_source"],
        status=row["status"],
        stages=row["stages_json"],
        error=row["error_json"],
        attempts=row["attempts"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


_COLUMNS = (
    "context_json, module_source, status, stages_json, error_json, attempts, created_at, updated_at"
)


class RunRepository:
    def __init__(self, database_url: str):
        self.database_url = database_url

    def create(self, context: Context, idempotency_key: str, module_source: str) -> RunRecord:
        """Insert a QUEUED run, or return the run already accepted for this key."""
        with connect_postgres(self.database_url) as connection:
            row = connection.execute(
                f"""INSERT INTO runtime.workflow_runs
                    (ca_id, run_id, idempotency_key, context_json, module_source, stages_json)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (ca_id, idempotency_key) DO NOTHING
                    RETURNING {_COLUMNS}""",
                (
                    context.ca_id,
                    context.run_id,
                    idempotency_key,
                    Jsonb(context.model_dump(mode="json")),
                    module_source,
                    Jsonb(initial_stages()),
                ),
            ).fetchone()
            if row is None:
                row = connection.execute(
                    f"SELECT {_COLUMNS} FROM runtime.workflow_runs "
                    "WHERE ca_id=%s AND idempotency_key=%s",
                    (context.ca_id, idempotency_key),
                ).fetchone()
        return _record(row)

    def get(self, ca_id: str, run_id: str) -> RunRecord | None:
        with connect_postgres(self.database_url) as connection:
            row = connection.execute(
                f"SELECT {_COLUMNS} FROM runtime.workflow_runs WHERE ca_id=%s AND run_id=%s",
                (ca_id, run_id),
            ).fetchone()
        return _record(row) if row else None

    def claim(self, ca_id: str, run_id: str, lease: timedelta) -> RunRecord | None:
        """Move QUEUED (or a RUNNING run with an expired lease) to RUNNING; else None."""
        with connect_postgres(self.database_url) as connection:
            row = connection.execute(
                f"""UPDATE runtime.workflow_runs
                    SET status='RUNNING', attempts=attempts+1, error_json=NULL,
                        stages_json=%s, heartbeat_at=now(), updated_at=now()
                    WHERE ca_id=%s AND run_id=%s AND (
                        status='QUEUED' OR (status='RUNNING' AND heartbeat_at < now() - %s))
                    RETURNING {_COLUMNS}""",
                (Jsonb(initial_stages()), ca_id, run_id, lease),
            ).fetchone()
        return _record(row) if row else None

    def mark_stage(self, ca_id: str, run_id: str, stage: Stage, status: StageStatus) -> None:
        now = datetime.now(timezone.utc).isoformat()
        stamp = "started_at" if status == "RUNNING" else "finished_at"
        with connect_postgres(self.database_url) as connection:
            connection.execute(
                """UPDATE runtime.workflow_runs SET
                       stages_json = (
                           SELECT jsonb_agg(CASE WHEN s->>'stage' = %s
                               THEN s || jsonb_build_object('status', %s::text, %s::text, %s::text)
                               ELSE s END ORDER BY n)
                           FROM jsonb_array_elements(stages_json) WITH ORDINALITY AS t(s, n)
                       ),
                       heartbeat_at=now(), updated_at=now()
                   WHERE ca_id=%s AND run_id=%s AND status='RUNNING'""",
                (stage, status, stamp, now, ca_id, run_id),
            )

    def complete(self, ca_id: str, run_id: str, draft: AssessmentDraft) -> None:
        with connect_postgres(self.database_url) as connection:
            updated = connection.execute(
                """UPDATE runtime.workflow_runs
                   SET status='COMPLETED', draft_json=%s, updated_at=now()
                   WHERE ca_id=%s AND run_id=%s AND status='RUNNING'""",
                (Jsonb(draft.model_dump(mode="json")), ca_id, run_id),
            ).rowcount
        if not updated:
            raise ConflictError("Run is no longer RUNNING; another worker owns it")

    def fail(self, ca_id: str, run_id: str, reason: str, message: str) -> None:
        error = {"code": "PROCESSING_FAILED", "message": message, "details": [{"reason": reason}]}
        with connect_postgres(self.database_url) as connection:
            connection.execute(
                """UPDATE runtime.workflow_runs
                   SET status='FAILED', error_json=%s, updated_at=now()
                   WHERE ca_id=%s AND run_id=%s AND status IN ('QUEUED', 'RUNNING')""",
                (Jsonb(error), ca_id, run_id),
            )

    def release(self, ca_id: str, run_id: str) -> None:
        """Hand a claimed run back to the queue after a transient failure."""
        with connect_postgres(self.database_url) as connection:
            connection.execute(
                """UPDATE runtime.workflow_runs
                   SET status='QUEUED', stages_json=%s, heartbeat_at=NULL, updated_at=now()
                   WHERE ca_id=%s AND run_id=%s AND status='RUNNING'""",
                (Jsonb(initial_stages()), ca_id, run_id),
            )

    def draft(self, ca_id: str, run_id: str) -> AssessmentDraft | None:
        with connect_postgres(self.database_url) as connection:
            row = connection.execute(
                "SELECT draft_json FROM runtime.workflow_runs "
                "WHERE ca_id=%s AND run_id=%s AND status='COMPLETED'",
                (ca_id, run_id),
            ).fetchone()
        return AssessmentDraft.model_validate(row["draft_json"]) if row else None

    def recoverable(self, queued_for: timedelta, lease: timedelta) -> list[tuple[str, str]]:
        """Runs whose job was probably lost: QUEUED too long, or RUNNING past its lease."""
        with connect_postgres(self.database_url) as connection:
            rows = connection.execute(
                """SELECT ca_id, run_id FROM runtime.workflow_runs
                   WHERE (status='QUEUED' AND updated_at < now() - %s)
                      OR (status='RUNNING' AND heartbeat_at < now() - %s)
                   ORDER BY updated_at""",
                (queued_for, lease),
            ).fetchall()
        return [(row["ca_id"], row["run_id"]) for row in rows]
