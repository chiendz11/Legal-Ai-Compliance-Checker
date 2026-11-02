"""C12 persistence: append-only review events per run, mirrored to the workbook C12 table.

Appends run under a per-run advisory lock and re-check the target hash inside it, so two
reviewers editing the same finding cannot both succeed against the same state.
"""

import uuid
from collections.abc import Callable
from datetime import timezone
from typing import Protocol

from psycopg.types.json import Jsonb

from legal_checker.core.postgres import connect_postgres
from legal_checker.shared.contracts.review import HumanReview, ReviewTarget


class ReviewStore(Protocol):
    def append(self, event: HumanReview) -> HumanReview: ...
    def events(self, ca_id: str, target_id: str) -> list[HumanReview]: ...


def _event(row) -> HumanReview:
    return HumanReview(
        review_id=row["review_id"],
        ca_id=row["ca_id"],
        target=ReviewTarget(doi_tuong_loai=row["doi_tuong_loai"], doi_tuong_id=row["doi_tuong_id"]),
        actor_id=row["actor_id"],
        action=row["action"],
        before=row["before_json"],
        after=row["after_json"],
        reason=row["reason"],
        reviewed_at=row["reviewed_at"].astimezone(timezone.utc),
        phien_ban_id=row["phien_ban_id"],
    )


class ReviewRepository:
    def __init__(self, database_url: str):
        self.database_url = database_url

    def for_run(self, ca_id: str, run_id: str) -> list[tuple[HumanReview, str]]:
        """Events in order, each with the target hash it was made against."""
        with connect_postgres(self.database_url) as connection:
            rows = connection.execute(
                "SELECT * FROM runtime.review_events WHERE ca_id=%s AND run_id=%s ORDER BY seq",
                (ca_id, run_id),
            ).fetchall()
        return [(_event(row), row["target_sha256"]) for row in rows]

    def append(
        self,
        ca_id: str,
        run_id: str,
        tenant_id: str,
        actor_id: str,
        phien_ban_id: str,
        target: ReviewTarget,
        action: str,
        after: dict,
        reason: str,
        check: Callable[[list[HumanReview]], tuple[dict, str]],
    ) -> HumanReview:
        """`check(existing_events)` validates against the latest state and returns the
        `before` snapshot and target hash; it raises to abort without writing."""
        with connect_postgres(self.database_url) as connection:
            connection.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                (f"review/{ca_id}/{run_id}",),
            )
            rows = connection.execute(
                "SELECT * FROM runtime.review_events WHERE ca_id=%s AND run_id=%s ORDER BY seq",
                (ca_id, run_id),
            ).fetchall()
            before, target_sha = check([_event(row) for row in rows])
            review_id = f"RV_{uuid.uuid4().hex}"
            row = connection.execute(
                """INSERT INTO runtime.review_events
                   (review_id, ca_id, run_id, doi_tuong_loai, doi_tuong_id, target_sha256, action,
                    before_json, after_json, reason, actor_id, tenant_id, phien_ban_id)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING *""",
                (
                    review_id,
                    ca_id,
                    run_id,
                    target.doi_tuong_loai,
                    target.doi_tuong_id,
                    target_sha,
                    action,
                    Jsonb(before),
                    Jsonb(after),
                    reason,
                    actor_id,
                    tenant_id,
                    phien_ban_id,
                ),
            ).fetchone()
            # Workbook C12 table, for consumers that read reviews per case.
            connection.execute(
                """INSERT INTO runtime.nhat_ky_review
                   (review_id, ca_id, doi_tuong_loai, doi_tuong_id, actor_id, hanh_dong,
                    gia_tri_truoc_json, gia_tri_sau_json, ly_do, ngay_review, phien_ban_id)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    review_id,
                    ca_id,
                    target.doi_tuong_loai,
                    target.doi_tuong_id,
                    actor_id,
                    action,
                    Jsonb({**before, "run_id": run_id}),
                    Jsonb(after),
                    reason,
                    row["reviewed_at"],
                    phien_ban_id,
                ),
            )
        return _event(row)
