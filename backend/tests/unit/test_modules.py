from fastapi.testclient import TestClient
from legal_checker.shared.contracts.reasoning import ReasoningPayload, ReasoningRequest


def test_modules_consume_predecessor_contracts_without_retrieval(app_factory, request_factory):
    client = TestClient(app_factory())
    pipeline = request_factory(finding="MISSING")
    request = ReasoningRequest(
        **pipeline.model_dump(exclude={"contract_name", "payload"}),
        payload=ReasoningPayload(**pipeline.payload.model_dump(exclude={"citations"})),
    ).model_dump(mode="json")
    context = {k: v for k, v in request.items() if k not in ("contract_name", "payload")}
    reasoning = client.post("/api/v1/reasoning", json=request)
    assert reasoning.status_code == 200, reasoning.text
    intermediate = {
        **context,
        "payload": {
            "hop_dong_id": request["payload"]["hop_dong_id"],
            "requirements": request["payload"]["requirements"],
            "criterion_results": reasoning.json()["payload"],
        },
    }
    aggregate = client.post("/api/v1/aggregation", json=intermediate)
    assert aggregate.status_code == 200, aggregate.text
    assert aggregate.json()["payload"][0]["status"] == "NON_COMPLIANT"
    risk = client.post("/api/v1/risks", json=intermediate)
    assert risk.status_code == 200, risk.text
    recommendation_request = {
        **context,
        "payload": {
            "hop_dong_id": request["payload"]["hop_dong_id"],
            "requirements": request["payload"]["requirements"],
            "risks": risk.json()["payload"],
        },
    }
    recommendations = client.post("/api/v1/recommendations", json=recommendation_request)
    assert recommendations.status_code == 200, recommendations.text
    assert len(recommendations.json()["payload"]) > 0
    assert all(r["review_status"] == "PENDING" for r in recommendations.json()["payload"])
    # Missing criteria cannot silently make an incomplete checklist COMPLIANT.
    intermediate["payload"]["criterion_results"] = intermediate["payload"]["criterion_results"][:1]
    assert client.post("/api/v1/aggregation", json=intermediate).status_code == 422
