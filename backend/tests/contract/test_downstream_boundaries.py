from copy import deepcopy

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def prepared(app_factory, request_factory):
    client = TestClient(app_factory())
    request = request_factory(finding="MISSING").model_dump(mode="json")
    response = client.post("/api/v1/pipeline/steps-5-7", json=request)
    assert response.status_code == 200, response.text
    context = {k: v for k, v in request.items() if k not in ("payload", "contract_name")}
    base = {
        "hop_dong_id": request["payload"]["hop_dong_id"],
        "requirements": request["payload"]["requirements"],
    }
    return client, context, base, response.json()["payload"]


@pytest.mark.parametrize("change", ["legal_basis", "decision_rule", "duplicate_requirement"])
def test_c07_consumer_rejects_tampered_or_duplicate_context(prepared, change):
    client, context, base, results = prepared
    payload = {**deepcopy(base), "criterion_results": deepcopy(results["criterion_results"])}
    if change == "legal_basis":
        payload["criterion_results"][0]["legal_basis_ids"] = ["FOREIGN_SOURCE"]
    elif change == "decision_rule":
        payload["criterion_results"][0]["tieu_chi_snapshot_json"]["decision_rule"][
            "ly_do_chuan"
        ] = "Tampered"
    else:
        payload["requirements"].append(payload["requirements"][0])
    response = client.post("/api/v1/aggregation", json={**context, "payload": payload})
    assert response.status_code == 422, response.text


@pytest.mark.parametrize("change", ["rule", "type", "duplicate_risk", "source", "legal_basis"])
def test_c10_consumer_rejects_tampered_provenance(prepared, change):
    client, context, base, results = prepared
    payload = {**base, "risks": deepcopy(results["risks"])}
    if change == "rule":
        payload["risks"][0]["rule_snapshot_json"]["trigger_status"] = "VIOLATED"
    elif change == "type":
        payload["risks"][0]["risk_type"] = "CITATION"
    elif change == "source":
        payload["risks"][0]["source"]["yeu_cau_ca_id"] = "FOREIGN"
    elif change == "legal_basis":
        payload["risks"][0]["legal_basis_ids"] = ["FOREIGN_SOURCE"]
    else:
        payload["risks"].append(payload["risks"][0])
    response = client.post("/api/v1/recommendations", json={**context, "payload": payload})
    assert response.status_code == 422, response.text
