"""Do not conflate source curation, human approval, and unreviewed knowledge in HTTP."""

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from legal_checker.api.dependencies import Services
from legal_checker.main import create_app


@pytest.mark.parametrize(
    "stored,expected",
    [
        ("SOURCE_CHECKED", "SOURCE_CHECKED"),
        ("HUMAN_VERIFIED", "HUMAN_VERIFIED"),
        ("DEV_UNVERIFIED", "PENDING_HUMAN_REVIEW"),
        (None, "PENDING_HUMAN_REVIEW"),
    ],
)
def test_knowledge_endpoint_preserves_source_review_level(stored, expected):
    knowledge = SimpleNamespace(
        schema_version="v7.4.9",
        sha256="a" * 64,
        tables={"tieu_chi_danh_gia": []},
        review_status=stored,
    )
    with TestClient(create_app(services=Services(knowledge=knowledge, assessments=None))) as client:
        response = client.get("/api/v1/knowledge")
    assert response.status_code == 200
    assert response.json()["review_status"] == expected
    assert response.json()["knowledge_snapshot_sha256"] == "a" * 64
