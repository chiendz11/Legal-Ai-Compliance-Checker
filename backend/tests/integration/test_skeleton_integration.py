from dataclasses import replace

import pytest
from fastapi.testclient import TestClient
from legal_checker.api.dependencies import Services
from legal_checker.core.config import Settings
from legal_checker.shared.contracts.reasoning import ReasoningPayload, ReasoningRequest
from pydantic import ValidationError


def test_reasoning_uses_its_own_contract(request_factory):
    pipeline = request_factory(finding="MISSING").model_dump(mode="json")
    direct = {**pipeline, "contract_name": "CriterionReasoningInput"}
    direct["payload"] = {
        k: v for k, v in pipeline["payload"].items() if k in ReasoningPayload.model_fields
    }
    assert ReasoningRequest.model_validate(direct).contract_name == "CriterionReasoningInput"
    direct["payload"]["observations"].append(direct["payload"]["observations"][0])
    with pytest.raises(ValidationError, match="Duplicate IDs"):
        ReasoningRequest.model_validate(direct)


@pytest.mark.parametrize("include_citations", [False, True])
def test_reasoning_rejects_pipeline_contract(request_factory, include_citations):
    request = request_factory().model_dump(mode="json")
    if not include_citations:
        request["payload"].pop("citations")
    with pytest.raises(ValidationError):
        ReasoningRequest.model_validate(request)


def test_composition_can_replace_storage_without_opening_database(app_factory, knowledge):
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
    assert client.get("/health").status_code == 200
    assert client.get("/api/v1/knowledge").json()["knowledge_snapshot_sha256"] == knowledge.sha256
    assert client.get("/api/v1/cases/CA_TEST/runs/RUN_TEST").status_code == 404
    assert memory.runs == {}


def test_environment_can_select_database_and_snapshot(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://custom/custom_db")
    monkeypatch.setenv("KNOWLEDGE_SNAPSHOT_SHA256", "a" * 64)
    settings = Settings.from_env()
    assert settings.database_url == "postgresql://custom/custom_db"
    assert settings.knowledge_snapshot_sha256 == "a" * 64
