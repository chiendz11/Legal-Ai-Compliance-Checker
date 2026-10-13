from dataclasses import replace

import pytest
from fastapi.testclient import TestClient
from legal_checker.api.dependencies import Services
from legal_checker.core.config import Settings


def test_reasoning_uses_its_own_contract(app_factory, request_factory):
    client = TestClient(app_factory())
    pipeline = request_factory(finding="MISSING").model_dump(mode="json")
    direct = {**pipeline, "contract_name": "CriterionReasoningInput"}
    direct["payload"] = {k: v for k, v in pipeline["payload"].items() if k != "citations"}
    result = client.post("/api/v1/reasoning", json=direct)
    assert result.status_code == 200, result.text
    assert all(item["finding"] == "MISSING" for item in result.json()["payload"])
    direct["payload"]["observations"].append(direct["payload"]["observations"][0])
    assert client.post("/api/v1/reasoning", json=direct).status_code == 422


@pytest.mark.parametrize("include_citations", [False, True])
def test_reasoning_rejects_pipeline_contract(app_factory, request_factory, include_citations):
    client = TestClient(app_factory())
    request = request_factory().model_dump(mode="json")
    if not include_citations:
        request["payload"].pop("citations")
    assert client.post("/api/v1/reasoning", json=request).status_code == 422


def test_composition_can_replace_storage_without_opening_database(
    tmp_path, app_factory, knowledge, request_factory
):
    class MemoryStore:
        def __init__(self):
            self.runs = {}

        def save(self, request, response):
            self.runs[request.ca_id, request.run_id] = response
            return response

        def get(self, ca_id, run_id):
            return self.runs.get((ca_id, run_id))

    database = "postgresql://invalid/never_connected"
    memory = MemoryStore()
    settings = replace(Settings.from_env(), database_url=database)
    client = TestClient(app_factory(settings=settings, services=Services(knowledge, memory)))
    response = client.post(
        "/api/v1/pipeline/steps-5-7",
        json=request_factory(finding="MISSING").model_dump(mode="json"),
    )
    assert response.status_code == 200, response.text
    assert client.get("/api/v1/cases/CA_TEST/runs/RUN_TEST").json() == response.json()
    assert memory.runs


def test_environment_can_select_database_and_snapshot(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://custom/custom_db")
    monkeypatch.setenv("KNOWLEDGE_SNAPSHOT_SHA256", "a" * 64)
    settings = Settings.from_env()
    assert settings.database_url == "postgresql://custom/custom_db"
    assert settings.knowledge_snapshot_sha256 == "a" * 64
