"""C13 report versions and export artifacts remain tied to an assessment case and run.

Versions live in runtime.report_versions (full FinalReport, immutable). The workbook
projection table runtime.bao_cao_danh_gia is not written: its INTEGER phien_ban_bao_cao vs
the contract's string version still needs a team-agreed mapping.
"""

import hashlib
import json
from dataclasses import dataclass
from typing import Protocol

from psycopg.types.json import Jsonb

from legal_checker.core.exceptions import ConflictError
from legal_checker.core.postgres import connect_postgres
from legal_checker.shared.contracts.report import FinalReport

NO_REVIEW = "none"


@dataclass(frozen=True)
class StoredReport:
    run_id: str
    version_no: int
    review_revision: str
    report: FinalReport
    exports: dict


class ReportStore(Protocol):
    def save_version(self, run_id: str, report: FinalReport) -> StoredReport: ...
    def get(self, bao_cao_id: str) -> StoredReport | None: ...
    def list_for_run(
        self, ca_id: str, run_id: str, *, offset: int, limit: int
    ) -> tuple[list[StoredReport], int]: ...
    def record_export(self, bao_cao_id: str, fmt: str, uri: str, sha256: str) -> None: ...


def report_digest(report: FinalReport) -> str:
    return hashlib.sha256(
        json.dumps(report.model_dump(mode="json"), sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def _stored(row) -> StoredReport:
    return StoredReport(
        run_id=row["run_id"],
        version_no=row["version_no"],
        review_revision=row["review_revision"],
        report=FinalReport.model_validate(row["report_json"]),
        exports=row["exports_json"],
    )


_COLUMNS = "run_id, version_no, review_revision, report_json, exports_json"


class PostgresReportStore:
    def __init__(self, database_url: str):
        self.database_url = database_url

    def save_version(self, run_id: str, report: FinalReport) -> StoredReport:
        """Same report content is idempotent; a different one under the same ID conflicts."""
        sha = report_digest(report)
        with connect_postgres(self.database_url) as connection:
            connection.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (f"report/{run_id}",)
            )
            existing = connection.execute(
                f"SELECT {_COLUMNS}, report_sha256 FROM runtime.report_versions "
                "WHERE bao_cao_id=%s",
                (report.bao_cao_id,),
            ).fetchone()
            if existing:
                if existing["report_sha256"] != sha or existing["run_id"] != run_id:
                    raise ConflictError("Report ID already holds a different report version")
                return _stored(existing)
            version_no = connection.execute(
                "SELECT coalesce(max(version_no), 0) + 1 AS n FROM runtime.report_versions "
                "WHERE ca_id=%s AND run_id=%s",
                (report.ca_id, run_id),
            ).fetchone()["n"]
            row = connection.execute(
                f"""INSERT INTO runtime.report_versions
                    (bao_cao_id, ca_id, run_id, version_no, review_revision, report_json,
                     report_sha256)
                    VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING {_COLUMNS}""",
                (
                    report.bao_cao_id,
                    report.ca_id,
                    run_id,
                    version_no,
                    NO_REVIEW,
                    Jsonb(report.model_dump(mode="json")),
                    sha,
                ),
            ).fetchone()
        return _stored(row)

    def get(self, bao_cao_id: str) -> StoredReport | None:
        with connect_postgres(self.database_url) as connection:
            row = connection.execute(
                f"SELECT {_COLUMNS} FROM runtime.report_versions WHERE bao_cao_id=%s",
                (bao_cao_id,),
            ).fetchone()
        return _stored(row) if row else None

    def list_for_run(
        self, ca_id: str, run_id: str, *, offset: int, limit: int
    ) -> tuple[list[StoredReport], int]:
        with connect_postgres(self.database_url) as connection:
            total = connection.execute(
                "SELECT count(*) AS n FROM runtime.report_versions WHERE ca_id=%s AND run_id=%s",
                (ca_id, run_id),
            ).fetchone()["n"]
            rows = connection.execute(
                f"""SELECT {_COLUMNS} FROM runtime.report_versions
                    WHERE ca_id=%s AND run_id=%s ORDER BY version_no DESC LIMIT %s OFFSET %s""",
                (ca_id, run_id, limit, offset),
            ).fetchall()
        return [_stored(row) for row in rows], total

    def record_export(self, bao_cao_id: str, fmt: str, uri: str, sha256: str) -> None:
        with connect_postgres(self.database_url) as connection:
            connection.execute(
                """UPDATE runtime.report_versions
                   SET exports_json = exports_json || jsonb_build_object(%s::text, %s::jsonb)
                   WHERE bao_cao_id=%s""",
                (fmt, json.dumps({"uri": uri, "sha256": sha256}), bao_cao_id),
            )
