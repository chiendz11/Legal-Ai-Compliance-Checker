"""Internal evaluation routes are absent; historical run reads remain usable."""

from fastapi.testclient import TestClient
from legal_checker.core.postgres import connect_postgres
from legal_checker.modules.assessments.repository import Store
from legal_checker.modules.legal_knowledge.repository import Knowledge


def test_internal_evaluation_routes_are_not_public_and_do_not_persist(app_factory, database_url):
    client = TestClient(app_factory())
    public_paths = client.get("/openapi.json").json()["paths"]
    for path in ["pipeline/steps-5-7", "reasoning", "aggregation", "risks", "recommendations"]:
        url = f"/api/v1/{path}"
        assert url not in public_paths
        assert client.post(url, json={}).status_code == 404
    with connect_postgres(database_url) as connection:
        for table in (
            "assessment_runs",
            "ca_danh_gia",
            "ket_qua_tieu_chi",
            "ket_qua_tuan_thu",
            "ket_qua_rui_ro",
            "khuyen_nghi_danh_gia",
        ):
            assert (
                connection.execute(f"SELECT count(*) AS n FROM runtime.{table}").fetchone()["n"]
                == 0
            )
    assert client.get("/api/v1/cases/CA_TEST/runs/RUN_TEST").status_code == 404


def test_existing_run_can_be_read(app_factory, request_factory, response_factory, database_url):
    request = request_factory()
    Knowledge(database_url)
    response = response_factory(request)
    Store(database_url).save(request, response)
    client = TestClient(app_factory())
    saved = client.get(f"/api/v1/cases/{request.ca_id}/runs/{request.run_id}")
    assert saved.status_code == 200
    assert saved.json() == response.model_dump(mode="json")
