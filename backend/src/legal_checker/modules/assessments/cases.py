"""Assessment cases (C01): read, filter for history, and create from an uploaded contract.

Authorization happens before these calls; `tenant_id` scopes every read and write.
"""

import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import date
from typing import Literal

from legal_checker.core.postgres import connect_postgres
from legal_checker.core.security import Actor
from legal_checker.shared.contracts.assessment import (
    AssessmentCase,
    AssessmentTiming,
    SourceDocument,
)
from legal_checker.shared.contracts.common import DeploymentPin

_CASE_QUERY = """
SELECT c.ca_id, c.hop_dong_id, c.ngay_danh_gia, c.moc_ap_dung, c.loai_moc_ap_dung,
       c.phien_ban_id, c.rule_version, c.legal_knowledge_version, c.tenant_id, c.created_by,
       coalesce(h.ten_tai_lieu, c.hop_dong_id) AS ten_tai_lieu,
       t.tep_id, t.url_nguon, t.object_uri, t.mime_type, t.sha256,
       r.run_id AS latest_run_id, r.status AS latest_run_status, r.created_at AS latest_run_at,
       rep.bao_cao_id AS latest_report_id,
       rep.report_json -> 'report_json' -> 'overall_summary' -> 'requirement_statuses'
           AS requirement_statuses
FROM runtime.ca_danh_gia c
JOIN runtime.hop_dong h ON h.hop_dong_id = c.hop_dong_id
JOIN runtime.tep_nguon t ON t.tep_id = h.tep_nguon_id
LEFT JOIN LATERAL (
    SELECT run_id, status, created_at FROM runtime.workflow_runs w
    WHERE w.ca_id = c.ca_id ORDER BY w.created_at DESC, w.run_id DESC LIMIT 1
) r ON TRUE
LEFT JOIN LATERAL (
    SELECT bao_cao_id, report_json FROM runtime.report_versions v
    WHERE v.ca_id = c.ca_id AND v.run_id = r.run_id ORDER BY v.version_no DESC LIMIT 1
) rep ON TRUE
"""

Sort = Literal["ca_id", "-ngay_danh_gia", "ngay_danh_gia", "-latest_run"]
_ORDER = {
    "ca_id": "c.ca_id",
    "ngay_danh_gia": "c.ngay_danh_gia, c.ca_id",
    "-ngay_danh_gia": "c.ngay_danh_gia DESC, c.ca_id",
    "-latest_run": "r.created_at DESC NULLS LAST, c.ca_id",
}


@dataclass(frozen=True)
class CaseFilter:
    tenant_id: str | None = None
    q: str | None = None  # ca_id, contract ID or title, case-insensitive substring
    run_status: str | None = None  # QUEUED/RUNNING/COMPLETED/FAILED, or NONE (never run)
    requirement_status: str | None = None  # latest report has a requirement with this status
    date_from: date | None = None
    date_to: date | None = None
    sort: Sort = "ca_id"


@dataclass(frozen=True)
class CaseRow:
    case: AssessmentCase
    ten_tai_lieu: str
    latest_run_id: str | None
    latest_run_status: str | None
    latest_report_id: str | None
    requirement_status_counts: dict[str, int]


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
        ten_tai_lieu=row["ten_tai_lieu"],
        latest_run_id=row["latest_run_id"],
        latest_run_status=row["latest_run_status"],
        latest_report_id=row["latest_report_id"],
        requirement_status_counts=dict(Counter(row["requirement_statuses"] or [])),
    )


def _where(f: CaseFilter) -> tuple[str, dict]:
    clauses, params = [], {}
    if f.tenant_id is not None:
        clauses.append("c.tenant_id = %(tenant)s")
        params["tenant"] = f.tenant_id
    if f.q:
        clauses.append(
            "(c.ca_id ILIKE %(q)s OR c.hop_dong_id ILIKE %(q)s OR h.ten_tai_lieu ILIKE %(q)s)"
        )
        params["q"] = "%" + f.q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
    if f.run_status == "NONE":
        clauses.append("r.run_id IS NULL")
    elif f.run_status:
        clauses.append("r.status = %(run_status)s")
        params["run_status"] = f.run_status
    if f.requirement_status:
        clauses.append(
            "rep.report_json -> 'report_json' -> 'overall_summary' -> 'requirement_statuses'"
            " ? %(requirement_status)s"
        )
        params["requirement_status"] = f.requirement_status
    if f.date_from:
        clauses.append("c.ngay_danh_gia >= %(date_from)s")
        params["date_from"] = f.date_from
    if f.date_to:
        clauses.append("c.ngay_danh_gia < %(date_to)s::date + 1")
        params["date_to"] = f.date_to
    return (" WHERE " + " AND ".join(clauses)) if clauses else "", params


class CaseRepository:
    """Cases with a registered source file; cases without one cannot be assessed or shown."""

    def __init__(self, database_url: str):
        self.database_url = database_url

    def list(
        self, f: CaseFilter | None = None, *, offset: int, limit: int
    ) -> tuple[list[CaseRow], int]:
        f = f or CaseFilter()
        where, params = _where(f)
        params.update(limit=limit, offset=offset)
        with connect_postgres(self.database_url) as connection:
            total = connection.execute(
                "SELECT count(*) AS n FROM (" + _CASE_QUERY + where + ") x", params
            ).fetchone()["n"]
            rows = connection.execute(
                _CASE_QUERY + where + f" ORDER BY {_ORDER[f.sort]}"
                " LIMIT %(limit)s OFFSET %(offset)s",
                params,
            ).fetchall()
        return [_case(row) for row in rows], total

    def get(self, ca_id: str, tenant_id: str | None = None) -> CaseRow | None:
        query = _CASE_QUERY + " WHERE c.ca_id = %(ca_id)s"
        if tenant_id is not None:
            query += " AND c.tenant_id = %(tenant)s"
        with connect_postgres(self.database_url) as connection:
            row = connection.execute(query, {"ca_id": ca_id, "tenant": tenant_id}).fetchone()
        return _case(row) if row else None

    def create(
        self,
        hop_dong_id: str,
        timing: AssessmentTiming,
        deployment: DeploymentPin,
        actor: Actor,
    ) -> CaseRow:
        """A new case pins deployment/knowledge versions; an unknown relevant date stays null."""
        ca_id = f"CA_UP_{uuid.uuid4().hex[:12].upper()}"
        with connect_postgres(self.database_url) as connection:
            connection.execute(
                """INSERT INTO runtime.ca_danh_gia
                   (ca_id, hop_dong_id, ngay_danh_gia, moc_ap_dung, loai_moc_ap_dung,
                    phien_ban_id, rule_version, legal_knowledge_version, tenant_id, created_by,
                    trang_thai, loai_du_lieu)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'CREATED', 'USER_UPLOAD')""",
                (
                    ca_id,
                    hop_dong_id,
                    timing.ngay_danh_gia,
                    timing.moc_ap_dung,
                    timing.loai_moc_ap_dung,
                    deployment.phien_ban_id,
                    deployment.rule_version,
                    deployment.legal_knowledge_version,
                    actor.tenant_id,
                    actor.actor_id,
                ),
            )
        row = self.get(ca_id)
        assert row is not None
        return row


class DeploymentCatalog:
    """Chooses the deployment pins for new cases: an allowed release plus its rule/knowledge
    versions (explicit settings first, else the versions existing cases of that release use)."""

    def __init__(
        self,
        database_url: str,
        *,
        rule_version: str | None = None,
        legal_knowledge_version: str | None = None,
    ):
        self.database_url = database_url
        self.rule_version = rule_version
        self.legal_knowledge_version = legal_knowledge_version

    def resolve(self, phien_ban_id: str | None) -> DeploymentPin:
        with connect_postgres(self.database_url) as connection:
            release = connection.execute(
                """SELECT phien_ban_id FROM knowledge.phien_ban_trien_khai
                   WHERE %(id)s::text IS NULL OR phien_ban_id = %(id)s
                   ORDER BY ngay_tao DESC NULLS LAST, phien_ban_id DESC LIMIT 1""",
                {"id": phien_ban_id},
            ).fetchone()
            if release is None:
                raise LookupError(f"Unknown deployment release {phien_ban_id!r}")
            used = connection.execute(
                """SELECT rule_version, legal_knowledge_version, count(*) AS n
                   FROM runtime.ca_danh_gia WHERE phien_ban_id = %s
                   AND rule_version IS NOT NULL AND legal_knowledge_version IS NOT NULL
                   GROUP BY 1, 2 ORDER BY n DESC LIMIT 1""",
                (release["phien_ban_id"],),
            ).fetchone()
        rule = self.rule_version or (used and used["rule_version"])
        legal = self.legal_knowledge_version or (used and used["legal_knowledge_version"])
        if not rule or not legal:
            raise LookupError(
                "No rule/knowledge version for this release; set DEPLOYMENT_RULE_VERSION and "
                "DEPLOYMENT_LEGAL_KNOWLEDGE_VERSION"
            )
        return DeploymentPin(
            phien_ban_id=release["phien_ban_id"], rule_version=rule, legal_knowledge_version=legal
        )
