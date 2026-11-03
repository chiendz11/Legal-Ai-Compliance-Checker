"""Uploaded contracts (C01 source registration). Bytes live in upload storage; this module
records the contract, its original source file and which tenant uploaded it."""

import hashlib
from dataclasses import dataclass
from datetime import datetime

from legal_checker.core.postgres import connect_postgres
from legal_checker.core.security import Actor
from legal_checker.shared.contracts.assessment import SourceDocument
from legal_checker.shared.storage.uploads import StoredUpload


@dataclass(frozen=True)
class ContractRow:
    hop_dong_id: str
    ten_tai_lieu: str
    source: SourceDocument
    created_at: datetime


_SELECT = """
SELECT h.hop_dong_id, coalesce(h.ten_tai_lieu, h.hop_dong_id) AS ten_tai_lieu,
       coalesce(u.uploaded_at, h.ngay_thu_thap, t.ngay_thu_thap, now()) AS created_at,
       t.tep_id, t.url_nguon, t.object_uri, t.mime_type, t.sha256
FROM runtime.hop_dong h
JOIN runtime.tep_nguon t ON t.tep_id = h.tep_nguon_id
LEFT JOIN runtime.contract_uploads u ON u.hop_dong_id = h.hop_dong_id
"""
# A tenant sees contracts it uploaded and contracts of its cases.
_TENANT = """(u.tenant_id = %(tenant)s OR EXISTS (
    SELECT 1 FROM runtime.ca_danh_gia c
    WHERE c.hop_dong_id = h.hop_dong_id AND c.tenant_id = %(tenant)s))"""


def _row(row) -> ContractRow:
    return ContractRow(
        hop_dong_id=row["hop_dong_id"],
        ten_tai_lieu=row["ten_tai_lieu"],
        source=SourceDocument(
            tep_id=row["tep_id"],
            url_nguon=row["url_nguon"],
            object_uri=row["object_uri"],
            mime_type=row["mime_type"],
            sha256=row["sha256"],
        ),
        created_at=row["created_at"],
    )


def contract_id(tenant_id: str, sha256: str) -> str:
    """Same file, same tenant → same contract; other tenants get their own record."""
    return "HD_UP_" + hashlib.sha256(f"{tenant_id}:{sha256}".encode()).hexdigest()[:16].upper()


class ContractRepository:
    def __init__(self, database_url: str):
        self.database_url = database_url

    def register(
        self, stored: StoredUpload, title: str, filename: str | None, actor: Actor
    ) -> ContractRow:
        hop_dong_id = contract_id(actor.tenant_id, stored.sha256)
        tep_id = f"{hop_dong_id}_SRC"
        kind = "PDF" if stored.mime_type.endswith("pdf") else "DOCX"
        with connect_postgres(self.database_url) as connection:
            connection.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (hop_dong_id,)
            )
            exists = connection.execute(
                "SELECT 1 FROM runtime.contract_uploads WHERE hop_dong_id=%s", (hop_dong_id,)
            ).fetchone()
            if not exists:
                connection.execute(
                    """INSERT INTO runtime.tep_nguon
                       (tep_id, hop_dong_id, vai_tro, object_uri, mime_type, sha256,
                        ngay_thu_thap, trang_thai_ban_goc, loai_du_lieu)
                       VALUES (%s, %s, 'USER_UPLOAD_ORIGINAL', %s, %s, %s, now(),
                               'ORIGINAL', 'USER_UPLOAD')""",
                    (tep_id, hop_dong_id, stored.object_uri, stored.mime_type, stored.sha256),
                )
                connection.execute(
                    """INSERT INTO runtime.hop_dong
                       (hop_dong_id, ten_tai_lieu, loai_nguon, sha256_tep_nguon, ngay_thu_thap,
                        loai_tai_lieu, trang_thai_xu_ly, tep_nguon_id, loai_du_lieu)
                       VALUES (%s, %s, 'UPLOAD', %s, now(), %s, 'UPLOADED', %s, 'USER_UPLOAD')""",
                    (hop_dong_id, title, stored.sha256, kind, tep_id),
                )
                connection.execute(
                    """INSERT INTO runtime.contract_uploads
                       (hop_dong_id, tenant_id, uploaded_by, original_filename, size_bytes)
                       VALUES (%s, %s, %s, %s, %s)""",
                    (hop_dong_id, actor.tenant_id, actor.actor_id, filename, stored.size_bytes),
                )
        row = self.get(hop_dong_id, actor.tenant_id)
        assert row is not None
        return row

    def get(self, hop_dong_id: str, tenant_id: str | None) -> ContractRow | None:
        query = _SELECT + " WHERE h.hop_dong_id = %(id)s"
        if tenant_id is not None:
            query += " AND " + _TENANT
        with connect_postgres(self.database_url) as connection:
            row = connection.execute(query, {"id": hop_dong_id, "tenant": tenant_id}).fetchone()
        return _row(row) if row else None

    def list(
        self, tenant_id: str | None, *, offset: int, limit: int
    ) -> tuple[list[ContractRow], int]:
        where = (" WHERE " + _TENANT) if tenant_id is not None else ""
        params = {"tenant": tenant_id, "limit": limit, "offset": offset}
        with connect_postgres(self.database_url) as connection:
            total = connection.execute(
                "SELECT count(*) AS n FROM (" + _SELECT + where + ") x", params
            ).fetchone()["n"]
            rows = connection.execute(
                _SELECT + where + " ORDER BY created_at DESC, h.hop_dong_id"
                " LIMIT %(limit)s OFFSET %(offset)s",
                params,
            ).fetchall()
        return [_row(row) for row in rows], total
