"""AUTH_MODE=on: session cookie / bearer, role checks, disabled users, throttling."""

from dataclasses import replace

import pytest
from legal_checker.api.v1 import auth as auth_routes
from legal_checker.modules.accounts.repository import UserRepository
from legal_checker.modules.accounts.security import SessionSigner
from test_assessment_runs import CASE, env  # noqa: F401  (fixture re-export)

PASSWORD = "mat-khau-thu-nghiem"


@pytest.fixture
def secured(env):  # noqa: F811
    users = UserRepository(env.database_url)
    users.create("reviewer1", "TENANT_TEST", "Chuyên viên", ["viewer", "reviewer"], PASSWORD)
    users.create("uploader1", "TENANT_TEST", "Người tải", ["viewer", "uploader"], PASSWORD)
    users.create("outsider", "OTHER_TENANT", "Người ngoài", ["viewer", "uploader"], PASSWORD)
    env.app.state.services = replace(
        env.app.state.services, users=users, sessions=SessionSigner("k" * 40, 3600)
    )
    auth_routes._failures.clear()
    env.users = users
    return env


def login(client, user_id, password=PASSWORD):
    return client.post("/api/v1/auth/login", json={"user_id": user_id, "password": password})


def test_requests_need_a_session(secured):
    response = secured.client.get("/api/v1/cases")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"
    assert secured.client.get("/health").status_code == 200  # liveness stays public


def test_cookie_session_scopes_reads_to_the_users_tenant(secured):
    assert login(secured.client, "reviewer1", "wrong").status_code == 401
    response = login(secured.client, "reviewer1")
    assert response.status_code == 200
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie
    me = secured.client.get("/api/v1/auth/me").json()
    assert me["actor_id"] == "reviewer1" and me["roles"] == ["reviewer", "viewer"]
    assert [i["case"]["ca_id"] for i in secured.client.get("/api/v1/cases").json()["items"]] == [
        CASE
    ]
    secured.client.post("/api/v1/auth/logout")
    assert secured.client.get("/api/v1/cases").status_code == 401


def test_roles_gate_writes(secured):
    login(secured.client, "reviewer1")
    started = secured.client.post(f"/api/v1/cases/{CASE}/runs", headers={"Idempotency-Key": "k"})
    assert started.status_code == 403
    assert (
        secured.client.post(
            "/api/v1/contracts", files={"file": ("a.pdf", b"%PDF-1.4 x")}
        ).status_code
        == 403
    )
    secured.client.post("/api/v1/auth/logout")
    login(secured.client, "uploader1")
    started = secured.client.post(f"/api/v1/cases/{CASE}/runs", headers={"Idempotency-Key": "k"})
    assert started.status_code == 202


def test_bearer_token_and_tampering(secured):
    token = secured.app.state.services.sessions.issue("outsider")
    client = secured.client
    client.cookies.clear()
    ok = client.get("/api/v1/cases", headers={"Authorization": f"Bearer {token}"})
    assert ok.status_code == 200 and ok.json()["total"] == 0  # other tenant sees nothing
    assert (
        client.get(
            f"/api/v1/cases/{CASE}", headers={"Authorization": f"Bearer {token}"}
        ).status_code
        == 404
    )
    body, signature = token.split(".")
    tampered = f"{body}x.{signature}"
    assert (
        client.get("/api/v1/cases", headers={"Authorization": f"Bearer {tampered}"}).status_code
        == 401
    )


def test_disabled_users_lose_access_immediately(secured):
    login(secured.client, "reviewer1")
    assert secured.client.get("/api/v1/cases").status_code == 200
    secured.users.set_disabled("reviewer1", True)
    assert secured.client.get("/api/v1/cases").status_code == 401
    assert login(secured.client, "reviewer1").status_code == 401


def test_repeated_failures_are_throttled(secured):
    for _ in range(10):
        assert login(secured.client, "reviewer1", "wrong").status_code == 401
    response = login(secured.client, "reviewer1")  # correct password, still throttled
    assert response.status_code == 403
    assert login(secured.client, "ghost", "x").status_code in (401, 403)


def test_auth_off_reports_dev_identity_and_refuses_login(env):  # noqa: F811
    me = env.client.get("/api/v1/auth/me").json()
    assert me["auth_mode"] == "off" and me["tenant_id"] == "TENANT_TEST"
    assert login(env.client, "anyone").status_code == 409
