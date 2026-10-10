import sqlite3

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(database_path=tmp_path / "runtime.sqlite3"))


def test_pipeline_roundtrip_and_idempotency(client, request_factory):
    payload = request_factory().model_dump(mode="json")
    first = client.post("/api/v1/pipeline/steps-5-7", json=payload)
    assert first.status_code == 200, first.text
    second = client.post("/api/v1/pipeline/steps-5-7", json=payload)
    assert second.json() == first.json()
    stored = client.get("/api/v1/cases/CA_TEST/runs/RUN_TEST")
    assert stored.json() == first.json()
    assert client.get("/api/v1/cases/none/runs/none").status_code == 404


def test_changed_run_input_and_case_snapshot_conflict(client, request_factory):
    payload = request_factory().model_dump(mode="json")
    assert client.post("/api/v1/pipeline/steps-5-7", json=payload).status_code == 200
    payload["trace_id"] = "DIFFERENT"
    assert client.post("/api/v1/pipeline/steps-5-7", json=payload).status_code == 409
    payload["run_id"] = "NEW_RUN"
    payload["rule_version"] = "DIFFERENT"
    for r in payload["payload"]["retrieval"]:
        r["lan_chay_id"] = "NEW_RUN"
    assert client.post("/api/v1/pipeline/steps-5-7", json=payload).status_code == 409


@pytest.mark.parametrize("mutation", ["checksum", "foreign_chunk", "foreign_citation", "date"])
def test_invalid_input_is_422(client, request_factory, mutation):
    payload = request_factory().model_dump(mode="json")
    if mutation == "checksum":
        payload["knowledge_snapshot_sha256"] = "0" * 64
    elif mutation == "foreign_chunk":
        payload["payload"]["chunks"][0]["hop_dong_id"] = "FOREIGN"
    elif mutation == "date":
        payload["payload"]["requirements"][0]["moc_ap_dung"] = "2020-01-01"
    else:
        payload["payload"]["observations"][0]["tieu_chi_id"] = "FOREIGN"
    assert client.post("/api/v1/pipeline/steps-5-7", json=payload).status_code == 422


def test_workbook_runtime_tables_are_persisted(tmp_path, request_factory):
    path = tmp_path / "runtime.sqlite3"
    client = TestClient(create_app(database_path=path))
    payload = request_factory(finding="MISSING").model_dump(mode="json")
    assert client.post("/api/v1/pipeline/steps-5-7", json=payload).status_code == 200
    with sqlite3.connect(path) as db:
        for name in [
            "ket_qua_tieu_chi",
            "ket_qua_tuan_thu",
            "ket_qua_rui_ro",
            "khuyen_nghi_danh_gia",
        ]:
            assert db.execute(f"SELECT count(*) FROM {name}").fetchone()[0] > 0
        assert db.execute("SELECT input_sha256, output_sha256 FROM nhat_ky_ra_soat").fetchone()
