import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path

from app.contracts.pipeline import PipelineRequest, PipelineResponse
from app.core.errors import ConflictError

OUTPUTS = {
    "ket_qua_tieu_chi": ("criterion_results", "ket_qua_id"),
    "ket_qua_tuan_thu": ("requirement_results", "tuan_thu_id"),
    "ket_qua_rui_ro": ("risks", "ket_qua_rui_ro_id"),
    "khuyen_nghi_danh_gia": ("recommendations", "khuyen_nghi_ca_id"),
}


def digest(model):
    return hashlib.sha256(
        json.dumps(model.model_dump(mode="json"), sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def pin(request):
    return json.dumps(
        {
            k: getattr(request, k)
            for k in (
                "phien_ban_id",
                "rule_version",
                "legal_knowledge_version",
                "knowledge_snapshot_sha256",
            )
        },
        sort_keys=True,
    )


class Store:
    """SQLite MVP adapter: workbook runtime tables, transactional immutable run snapshots."""

    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(path)) as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute(
                "CREATE TABLE IF NOT EXISTS ca_danh_gia "
                "(ca_id TEXT PRIMARY KEY, hop_dong_id TEXT NOT NULL, pin_json TEXT NOT NULL)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS nhat_ky_ra_soat "
                "(ca_id TEXT, run_id TEXT, input_sha256 TEXT NOT NULL, "
                "output_sha256 TEXT NOT NULL, response_json TEXT NOT NULL, "
                "input_json TEXT NOT NULL, "
                "PRIMARY KEY(ca_id, run_id))"
            )
            for table in OUTPUTS:
                db.execute(
                    f"CREATE TABLE IF NOT EXISTS {table} "
                    "(id TEXT PRIMARY KEY, ca_id TEXT NOT NULL, run_id TEXT NOT NULL, "
                    "payload_json TEXT NOT NULL)"
                )
            for table in ("bang_chung_ket_qua", "bang_chung_ngoai"):
                db.execute(
                    f"CREATE TABLE IF NOT EXISTS {table} "
                    "(id TEXT PRIMARY KEY, ca_id TEXT NOT NULL, run_id TEXT NOT NULL, "
                    "payload_json TEXT NOT NULL)"
                )
            db.commit()

    def get(self, ca_id, run_id):
        with closing(sqlite3.connect(self.path)) as db:
            row = db.execute(
                "SELECT response_json FROM nhat_ky_ra_soat WHERE ca_id=? AND run_id=?",
                (ca_id, run_id),
            ).fetchone()
        return PipelineResponse.model_validate_json(row[0]) if row else None

    def save(self, request: PipelineRequest, response: PipelineResponse):
        with closing(sqlite3.connect(self.path, timeout=30)) as db, db:
            db.execute("BEGIN IMMEDIATE")
            case = db.execute(
                "SELECT hop_dong_id, pin_json FROM ca_danh_gia WHERE ca_id=?", (request.ca_id,)
            ).fetchone()
            if case and case != (request.payload.hop_dong_id, pin(request)):
                raise ConflictError("Case contract or deployment/knowledge/rule pin cannot change")
            previous = db.execute(
                "SELECT input_sha256, response_json FROM nhat_ky_ra_soat "
                "WHERE ca_id=? AND run_id=?",
                (request.ca_id, request.run_id),
            ).fetchone()
            if previous:
                if previous[0] != digest(request):
                    raise ConflictError("Run ID already exists with a different input")
                return PipelineResponse.model_validate_json(previous[1])
            db.execute(
                "INSERT OR IGNORE INTO ca_danh_gia VALUES (?, ?, ?)",
                (request.ca_id, request.payload.hop_dong_id, pin(request)),
            )
            for table, (attr, key) in OUTPUTS.items():
                for row in getattr(response.payload, attr):
                    db.execute(
                        f"INSERT INTO {table} VALUES (?, ?, ?, ?)",
                        (getattr(row, key), request.ca_id, request.run_id, row.model_dump_json()),
                    )
            for result in response.payload.criterion_results:
                for table, items in [
                    ("bang_chung_ket_qua", result.evidence),
                    ("bang_chung_ngoai", result.external_evidence),
                ]:
                    for index, item in enumerate(items):
                        snapshot = {"ket_qua_id": result.ket_qua_id, **item.model_dump(mode="json")}
                        db.execute(
                            f"INSERT INTO {table} VALUES (?, ?, ?, ?)",
                            (
                                f"{result.ket_qua_id}/{table}/{index}",
                                request.ca_id,
                                request.run_id,
                                json.dumps(snapshot, ensure_ascii=False),
                            ),
                        )
            db.execute(
                "INSERT INTO nhat_ky_ra_soat VALUES (?, ?, ?, ?, ?, ?)",
                (
                    request.ca_id,
                    request.run_id,
                    digest(request),
                    digest(response),
                    response.model_dump_json(),
                    request.model_dump_json(),
                ),
            )
        return response
