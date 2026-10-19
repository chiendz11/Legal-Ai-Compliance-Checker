"""Read assessment cases (C01) from runtime tables. Authorization happens before these calls."""

from dataclasses import dataclass

from legal_checker.core.postgres import connect_postgres
from legal_checker.shared.contracts.assessment import (
    AssessmentCase,
    AssessmentTiming,
    SourceDocument,
)
from legal_checker.shared.contracts.common import DeploymentPin

_CASE_QUERY = """
SELECT c.ca_id, c.hop_dong_id, c.ngay_danh_gia, c.moc_ap_dung, c.loai_moc_ap_dung,
       c.phien_ban_id, c.rule_version, c.legal_knowledge_version, c.tenant_id, c.created_by,
       t.tep_id, t.url_nguon, t.object_uri, t.mime_type, t.sha256,
       r.run_id AS latest_run_id, r.status AS latest_run_status
FROM runtime.ca_danh_gia c
JOIN runtime.hop_dong h ON h.hop_dong_id = c.hop_dong_id
JOIN runtime.tep_nguon t ON t.tep_id = h.tep_nguon_id
LEFT JOIN LATERAL (
    SELECT run_id, status FROM runtime.workflow_runs w
    WHERE w.ca_id = c.ca_id ORDER BY w.created_at DESC, w.run_id DESC LIMIT 1
) r ON TRUE
"""


@dataclass(frozen=True)
class CaseRow:
    case: AssessmentCase
    latest_run_id: str | None
    latest_run_status: str | None


def _case(row) -> CaseRow:
    return CaseRow(
        case=AssessmentCase(
            ca_id=row["ca_id"],
            hop_dong_id=row["hop_dong_id"],
            source=SourceDocument(
                tep_id=row["tep_id"],
                url_nguon=row["url_nguon"],
                object_uri=row["object_uri"],
                mime_type=row["mime_type"],
                sha256=row["sha256"],
            ),
            assessment_context=AssessmentTiming(
                ngay_danh_gia=row["ngay_danh_gia"].date(),
                moc_ap_dung=row["moc_ap_dung"],
                loai_moc_ap_dung=row["loai_moc_ap_dung"],
            ),
            deployment=DeploymentPin(
                phien_ban_id=row["phien_ban_id"],
                rule_version=row["rule_version"],
                legal_knowledge_version=row["legal_knowledge_version"],
            ),
            tenant_id=row["tenant_id"],
            created_by=row["created_by"],
        ),
        latest_run_id=row["latest_run_id"],
        latest_run_status=row["latest_run_status"],
    )


class CaseRepository:
    """Cases with a registered source file; cases without one cannot be assessed or shown."""

    def __init__(self, database_url: str):
        self.database_url = database_url

    def list(self, *, offset: int, limit: int) -> tuple[list[CaseRow], int]:
        with connect_postgres(self.database_url) as connection:
            total = connection.execute(
                """SELECT count(*) AS n FROM runtime.ca_danh_gia c
                   JOIN runtime.hop_dong h ON h.hop_dong_id = c.hop_dong_id
                   JOIN runtime.tep_nguon t ON t.tep_id = h.tep_nguon_id"""
            ).fetchone()["n"]
            rows = connection.execute(
                _CASE_QUERY + " ORDER BY c.ca_id LIMIT %s OFFSET %s", (limit, offset)
            ).fetchall()
        return [_case(row) for row in rows], total

    def get(self, ca_id: str) -> CaseRow | None:
        with connect_postgres(self.database_url) as connection:
            row = connection.execute(_CASE_QUERY + " WHERE c.ca_id = %s", (ca_id,)).fetchone()
        return _case(row) if row else None
