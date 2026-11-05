"""Reviewed releases must not overwrite developer edits or historical assessments."""

import hashlib
import json
from pathlib import Path

import pytest
from devtools.database_schema import TABLES
from devtools.database_seed import SeedError, read_workbook, seed_database
from devtools.database_update import update_database
from devtools.qa_schema import QA_TABLES
from legal_checker.core.postgres import connect_postgres
from legal_checker.modules.legal_knowledge.repository import TABLE_KEYS, Knowledge, canonical
from openpyxl import Workbook


def release_file(path: Path, reviewed: bool):
    records = {t.name: [] for t in TABLES}

    def add(name, **values):
        table = next(t for t in TABLES if t.name == name)
        row = {column: None for column, _ in table.columns}
        row.update(values)
        records[name].append(row)

    version = "REVIEWED" if reviewed else "OLD"
    add("phien_ban_trien_khai", phien_ban_id="DEPLOY")
    for document in ("LAW_Z", "LAWA", "LAW_A"):
        add("van_ban_phap_ly", van_ban_id=document)
    add("yeu_cau_phap_ly", requirement_id="REQ")
    add(
        "phien_ban_yeu_cau",
        requirement_version_id="VER",
        requirement_id="REQ",
        trang_thai_ra_soat="HUMAN_VERIFIED" if reviewed else "PENDING",
    )
    add(
        "tieu_chi_danh_gia",
        tieu_chi_id="CRIT",
        requirement_version_id="VER",
        noi_dung="Original criterion",
        human_verified=reviewed,
        trang_thai_nguon="VERIFIED" if reviewed else "PENDING",
    )
    add(
        "quy_tac_quyet_dinh",
        quy_tac_id="RULE",
        tieu_chi_id="CRIT",
        finding="UNKNOWN",
        human_verified=reviewed,
    )
    add("hop_dong", hop_dong_id="DOC")
    for number in (1, 2):
        add(
            "ca_danh_gia",
            ca_id=f"CASE{number}",
            hop_dong_id="DOC",
            phien_ban_id="DEPLOY",
            legal_knowledge_version=version,
        )
    add(
        "yeu_cau_ap_dung",
        yeu_cau_ca_id="APPL",
        ca_id="CASE1",
        requirement_id="REQ",
        requirement_version_id="VER",
        phien_ban_id="DEPLOY",
    )
    add(
        "ket_qua_tieu_chi",
        ket_qua_id="RESULT",
        ca_id="CASE1",
        tieu_chi_id="CRIT",
        yeu_cau_ca_id="APPL",
        loai_phat_hien="UNKNOWN",
        tieu_chi_snapshot_json={"human_verified": reviewed},
    )
    snapshot = {
        "schema_version": "v7.4.9",
        "tables": {
            name: sorted(records[name], key=lambda row, pk=key: row[pk])
            for name, key in TABLE_KEYS.items()
        },
    }
    knowledge_hash = hashlib.sha256(canonical(snapshot).encode()).hexdigest()
    qa = {t.name: [] for t in QA_TABLES}
    for case_id, kind, split in (
        ("CASE1", "CORPUS", "DEV"),
        ("CONTROL", "CONTROLLED", "REGRESSION"),
    ):
        qa["case_manifest"].append(
            {
                "case_id": case_id,
                "hop_dong_id": "DOC",
                "group_id": case_id,
                "split": split,
                "case_kind": kind,
                "label_quality": "SYNTHETIC_SPEC",
                "knowledge_snapshot_sha256": knowledge_hash,
            }
        )
        payload = json.dumps(
            {"knowledge_snapshot_sha256": knowledge_hash, "source_verified": False}
        )
        pieces = [payload] if reviewed else [payload[:20], payload[20:]]
        for number, piece in enumerate(pieces, 1):
            qa["artifacts"].append(
                {
                    "artifact_part_id": case_id + f"/{number}",
                    "case_id": case_id,
                    "role": "INPUT",
                    "contract_name": "Fixture",
                    "record_id": case_id,
                    "part_number": number,
                    "part_count": len(pieces),
                    "payload_sha256": hashlib.sha256(payload.encode()).hexdigest(),
                    "content": piece,
                }
            )
    wb = Workbook(write_only=True)
    for table in (*TABLES, *QA_TABLES):
        sheet_name = table.name if table.schema != "qa" else "QA_" + table.name.upper()
        sheet = wb.create_sheet(sheet_name)
        sheet.append([name for name, _ in table.columns])
        for row in (records if table.schema != "qa" else qa)[table.name]:
            sheet.append(
                [
                    json.dumps(row[name])
                    if kind == "JSONB" and row.get(name) is not None
                    else row.get(name)
                    for name, kind in table.columns
                ]
            )
    wb.save(path)
    return knowledge_hash


@pytest.fixture
def release(empty_database_url, tmp_path):
    old, new = tmp_path / "old.xlsx", tmp_path / "new.xlsx"
    old_hash = release_file(old, False)
    new_hash = release_file(new, True)
    seed_database(empty_database_url, read_workbook(old))
    assert Knowledge(empty_database_url).sha256 == old_hash
    return empty_database_url, old, new, old_hash, new_hash


def apply(release, **kwargs):
    url, old, new, _, expected = release
    return update_database(
        url,
        old,
        new,
        legal_knowledge_version="REVIEWED",
        expected_knowledge_sha256=expected,
        **kwargs,
    )


def historical_run(url, status="COMPLETED"):
    with connect_postgres(url) as c:
        c.execute(
            """INSERT INTO runtime.workflow_runs
            (ca_id,run_id,idempotency_key,context_json,module_source,status,stages_json,draft_json)
            VALUES ('CASE1','RUN','key','{}','MODULES',%s,'{}',%s)""",
            (status, "{}" if status == "COMPLETED" else None),
        )
        c.execute(
            """INSERT INTO runtime.assessment_runs
            (ca_id,run_id,input_sha256,output_sha256,input_json,response_json)
            VALUES ('CASE1','RUN',%s,%s,'{}','{}')""",
            ("a" * 64, "b" * 64),
        )
        c.execute("""INSERT INTO runtime.assessment_output_lineage
            VALUES ('ket_qua_tieu_chi','RESULT','CASE1','RUN','{}')""")
        c.execute(
            """INSERT INTO runtime.report_versions
            (bao_cao_id,ca_id,run_id,version_no,review_revision,report_json,report_sha256)
            VALUES ('REPORT','CASE1','RUN',1,'none','{"original":true}',%s)""",
            ("c" * 64,),
        )
        c.execute(
            "INSERT INTO runtime.hop_dong(hop_dong_id,ten_tai_lieu) VALUES ('UPLOAD','Keep me')"
        )


def test_update_preserves_uploads_history_and_old_snapshot(release):
    url, _, _, old_hash, new_hash = release
    historical_run(url)
    result = apply(release)
    assert result["status"] == "updated"
    assert result["tables"]["runtime.ca_danh_gia"]["protected"] == 1
    assert result["tables"]["runtime.ket_qua_tieu_chi"]["protected"] == 1
    assert Knowledge(url).sha256 == new_hash
    assert Knowledge(url).review_status == "HUMAN_VERIFIED"
    assert Knowledge(url, old_hash).criteria["CRIT"]["human_verified"] is False
    with connect_postgres(url) as c:
        assert (
            c.execute(
                "SELECT ten_tai_lieu FROM runtime.hop_dong WHERE hop_dong_id='UPLOAD'"
            ).fetchone()["ten_tai_lieu"]
            == "Keep me"
        )
        cases = c.execute(
            "SELECT ca_id,legal_knowledge_version FROM runtime.ca_danh_gia ORDER BY ca_id"
        ).fetchall()
        assert [r["legal_knowledge_version"] for r in cases] == ["OLD", "REVIEWED"]
        assert c.execute("SELECT tieu_chi_snapshot_json FROM runtime.ket_qua_tieu_chi").fetchone()[
            "tieu_chi_snapshot_json"
        ] == {"human_verified": False}
        assert c.execute("SELECT count(*) n FROM dev_meta.seed_imports").fetchone()["n"] == 1
        assert c.execute("SELECT count(*) n FROM dev_meta.dataset_updates").fetchone()["n"] == 1
        assert all(
            json.loads(r["content"])["source_verified"] is False
            for r in c.execute("SELECT content FROM qa.artifacts").fetchall()
        )
        assert all(
            r["tgenabled"] == "O"
            for r in c.execute(
                "SELECT tgenabled FROM pg_trigger WHERE tgname IN "
                "('immutable_case_manifest','immutable_qa_artifact','immutable_controlled_assertion')"
            ).fetchall()
        )


def test_update_dry_run_and_idempotency(release):
    url, _, new, old_hash, _ = release
    assert apply(release, dry_run=True)["status"] == "dry_run"
    assert Knowledge(url).sha256 == old_hash
    apply(release)
    assert apply(release)["status"] == "already_applied"
    assert seed_database(url, read_workbook(new))["updated_release"] is True


def test_developer_change_rolls_back_release(release):
    url = release[0]
    with connect_postgres(url) as c:
        c.execute("UPDATE knowledge.tieu_chi_danh_gia SET noi_dung='Developer edit'")
    with pytest.raises(SeedError, match="developer changes"):
        apply(release)
    with connect_postgres(url) as c:
        row = c.execute(
            "SELECT noi_dung,human_verified FROM knowledge.tieu_chi_danh_gia"
        ).fetchone()
        assert row == {"noi_dung": "Developer edit", "human_verified": False}
        assert c.execute("SELECT count(*) n FROM dev_meta.dataset_updates").fetchone()["n"] == 0
        assert (
            c.execute("SELECT trang_thai_ra_soat FROM knowledge.phien_ban_yeu_cau").fetchone()[
                "trang_thai_ra_soat"
            ]
            == "PENDING"
        )


def test_running_assessment_blocks_update(release):
    historical_run(release[0], "RUNNING")
    with pytest.raises(SeedError, match="queued/running"):
        apply(release)


def test_knowledge_api_reads_stored_review_state(release, app_factory):
    from fastapi.testclient import TestClient
    from legal_checker.core.config import Settings

    apply(release)
    with TestClient(app_factory(settings=Settings(database_url=release[0]))) as client:
        assert client.get("/api/v1/knowledge").json()["review_status"] == "HUMAN_VERIFIED"


def test_fresh_seed_registers_pinned_reviewed_snapshot(empty_database_url, tmp_path):
    path = tmp_path / "reviewed.xlsx"
    expected = release_file(path, True)
    seed_database(empty_database_url, read_workbook(path), reviewed_knowledge_sha256=expected)
    assert Knowledge(empty_database_url).review_status == "HUMAN_VERIFIED"


def test_wrong_reviewed_hash_rolls_back_fresh_seed(empty_database_url, tmp_path):
    path = tmp_path / "reviewed.xlsx"
    release_file(path, True)
    with pytest.raises(SeedError, match="pinned reviewed release"):
        seed_database(empty_database_url, read_workbook(path), reviewed_knowledge_sha256="0" * 64)
    with connect_postgres(empty_database_url) as c:
        assert c.execute("SELECT count(*) n FROM runtime.hop_dong").fetchone()["n"] == 0
