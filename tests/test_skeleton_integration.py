from fastapi.testclient import TestClient

from app.bootstrap import Services
from app.main import create_app


def test_reasoning_specific_contract_matches_existing_pipeline_input(tmp_path, request_factory):
    client = TestClient(create_app(database_path=tmp_path / "runtime.sqlite3"))
    legacy = request_factory(finding="MISSING").model_dump(mode="json")
    direct = {**legacy, "contract_name": "CriterionReasoningInput"}
    direct["payload"] = {k: v for k, v in legacy["payload"].items() if k != "citations"}
    old = client.post("/api/v1/reasoning", json=legacy)
    new = client.post("/api/v1/reasoning", json=direct)
    assert old.status_code == new.status_code == 200
    assert old.json()["payload"] == new.json()["payload"]
    direct["payload"]["observations"].append(direct["payload"]["observations"][0])
    assert client.post("/api/v1/reasoning", json=direct).status_code == 422


def test_composition_can_replace_storage_without_creating_sqlite(
    tmp_path, knowledge, request_factory
):
    class MemoryStore:
        def __init__(self):
            self.runs = {}

        def save(self, request, response):
            self.runs[request.ca_id, request.run_id] = response
            return response

        def get(self, ca_id, run_id):
            return self.runs.get((ca_id, run_id))

    database = tmp_path / "must-not-be-created.sqlite3"
    memory = MemoryStore()
    client = TestClient(create_app(database_path=database, services=Services(knowledge, memory)))
    response = client.post(
        "/api/v1/pipeline/steps-5-7",
        json=request_factory(finding="MISSING").model_dump(mode="json"),
    )
    assert response.status_code == 200, response.text
    assert client.get("/api/v1/cases/CA_TEST/runs/RUN_TEST").json() == response.json()
    assert not database.exists()


def test_environment_can_select_knowledge_snapshot(tmp_path, monkeypatch):
    missing = tmp_path / "missing-snapshot.json"
    monkeypatch.setenv("KNOWLEDGE_PATH", str(missing))
    try:
        create_app(database_path=tmp_path / "runtime.sqlite3")
    except FileNotFoundError as exc:
        assert exc.filename == str(missing)
    else:
        raise AssertionError("The application ignored the configured knowledge snapshot")
