"""Load full engine knowledge from PostgreSQL and pin immutable content in the DB."""

import hashlib
import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from psycopg import sql
from psycopg.types.json import Jsonb

from legal_checker.core.postgres import connect_postgres

TABLE_KEYS = {
    "loai_hop_dong": "loai_hop_dong_id",
    "van_ban_phap_ly": "van_ban_id",
    "dieu_khoan_phap_ly": "dieu_khoan_id",
    "nguon_phap_ly": "nguon_id",
    "quan_he_van_ban": "quan_he_id",
    "yeu_cau_phap_ly": "requirement_id",
    "phien_ban_yeu_cau": "requirement_version_id",
    "nguon_yeu_cau": "lien_ket_id",
    "pham_vi_ap_dung": "pham_vi_id",
    "ngoai_le_ap_dung": "ngoai_le_id",
    "tieu_chi_danh_gia": "tieu_chi_id",
    "quy_tac_quyet_dinh": "quy_tac_id",
    "chinh_sach_bang_chung": "chinh_sach_id",
    "quy_tac_tong_hop": "quy_tac_tong_hop_id",
    "quy_tac_rui_ro": "quy_tac_id",
    "danh_muc_rui_ro": "rui_ro_id",
    "danh_muc_khuyen_nghi": "khuyen_nghi_id",
    "rui_ro_khuyen_nghi": "lien_ket_id",
}


def json_value(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    raise TypeError(f"Unsupported knowledge value: {type(value).__name__}")


def canonical(content) -> str:
    return json.dumps(
        content,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        default=json_value,
        allow_nan=False,
    )


class Knowledge:
    """Full KnowledgeSnapshot adapter with SQL source tables and immutable history.

    The content hash is independent of the Excel archive/old releases. Verification
    flags remain unchanged: capturing dev data never approves it as legal knowledge.
    """

    def __init__(self, database_url: str, snapshot_sha256: str | None = None):
        with connect_postgres(database_url) as connection:
            if snapshot_sha256:
                row = connection.execute(
                    "SELECT content FROM knowledge.knowledge_snapshots WHERE sha256=%s",
                    (snapshot_sha256,),
                ).fetchone()
                if row is None:
                    raise ValueError("Unknown knowledge snapshot SHA256")
                snapshot = row["content"]
            else:
                connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
                tables = {
                    name: connection.execute(
                        sql.SQL("SELECT * FROM {} ORDER BY {}").format(
                            sql.Identifier("knowledge", name), sql.Identifier(key)
                        )
                    ).fetchall()
                    for name, key in TABLE_KEYS.items()
                }
                if not tables["tieu_chi_danh_gia"]:
                    raise ValueError("Knowledge is empty. Seed the workbook into PostgreSQL first")
                snapshot = json.loads(canonical({"schema_version": "v7.4.9", "tables": tables}))
                sha = hashlib.sha256(canonical(snapshot).encode()).hexdigest()
                # Persist the captured content in a fresh READ COMMITTED transaction.
                # Concurrent app startups can then insert the same hash idempotently.
                connection.commit()
                connection.execute(
                    "INSERT INTO knowledge.knowledge_snapshots (sha256, schema_version, content) "
                    "VALUES (%s, %s, %s) ON CONFLICT (sha256) DO NOTHING",
                    (sha, snapshot["schema_version"], Jsonb(snapshot)),
                )
        self.sha256 = hashlib.sha256(canonical(snapshot).encode()).hexdigest()
        if snapshot_sha256 and self.sha256 != snapshot_sha256:
            raise ValueError("Stored knowledge snapshot checksum is invalid")
        self.schema_version = snapshot["schema_version"]
        self.tables = snapshot["tables"]
        # Existing rule engines consume JSON text. Normalize these cells at the adapter
        # boundary; source tables and immutable content retain JSONB and verification flags.
        for name, columns in {
            "quy_tac_quyet_dinh": ("dieu_kien_json",),
            "quy_tac_rui_ro": ("trigger_json",),
        }.items():
            for row in self.tables[name]:
                for column in columns:
                    if not isinstance(row[column], str):
                        row[column] = canonical(row[column])
        self.criteria = self.index("tieu_chi_danh_gia", "tieu_chi_id")
        self.versions = self.index("phien_ban_yeu_cau", "requirement_version_id")
        self.risks = self.index("danh_muc_rui_ro", "rui_ro_id")
        self.recommendations = self.index("danh_muc_khuyen_nghi", "khuyen_nghi_id")
        self.aggregations = self.index("quy_tac_tong_hop", "quy_tac_tong_hop_id")
        self.articles = self.index("dieu_khoan_phap_ly", "dieu_khoan_id")
        self.documents = self.index("van_ban_phap_ly", "van_ban_id")

    def index(self, table: str, key: str) -> dict[str, dict[str, Any]]:
        result = {}
        for row in self.tables[table]:
            if not row[key] or row[key] in result:
                raise ValueError(f"Invalid or duplicate {table}.{key}")
            result[row[key]] = row
        return result

    def criteria_for(self, version_id: str | None):
        return sorted(
            [r for r in self.criteria.values() if r["requirement_version_id"] == version_id],
            key=lambda r: (r["thu_tu"] or 0, r["tieu_chi_id"]),
        )

    def decision(self, criterion_id: str, finding: str):
        matches = [
            r
            for r in self.tables["quy_tac_quyet_dinh"]
            if r["tieu_chi_id"] == criterion_id and r["finding"] == finding
        ]
        if len(matches) != 1:
            raise ValueError(f"Expected one decision rule for {criterion_id}/{finding}")
        return matches[0]

    def legal_basis(self, criterion):
        article_id = criterion.get("source_dieu_khoan_id")
        version_id = criterion["requirement_version_id"]
        version = self.versions[version_id]
        document_id = version["source_van_ban_id"]
        if article_id not in self.articles or document_id not in self.documents:
            return []
        return [version_id, article_id, document_id]
