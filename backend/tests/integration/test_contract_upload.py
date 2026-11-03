"""Upload → contract → case, history filters, and tenant isolation of every read."""

import hashlib
import io
import zipfile

import pytest
from legal_checker.api.auth import current_actor
from legal_checker.core.security import Actor
from test_assessment_runs import CASE, env, start  # noqa: F401  (fixture re-export)

PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


def docx_bytes():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("word/document.xml", "<w:document/>")
    return buffer.getvalue()


def upload(client, payload, name="hop_dong.pdf", title=None):
    data = {"ten_tai_lieu": title} if title else {}
    return client.post("/api/v1/contracts", files={"file": (name, payload)}, data=data)


def test_upload_stores_bytes_once_and_serves_them_back(env):  # noqa: F811
    first = upload(env.client, PDF, title="Hợp đồng mua bán căn hộ A1")
    assert first.status_code == 201, first.text
    record = first.json()
    assert record["ten_tai_lieu"] == "Hợp đồng mua bán căn hộ A1"
    assert record["source"]["sha256"] == hashlib.sha256(PDF).hexdigest()
    assert record["source"]["object_uri"].startswith("upload://")
    assert record["source"]["mime_type"] == "application/pdf"
    again = upload(env.client, PDF, name="copy.pdf").json()
    assert again["hop_dong_id"] == record["hop_dong_id"]  # same tenant, same bytes
    source = env.client.get(f"/api/v1/contracts/{record['hop_dong_id']}/source")
    assert source.status_code == 200 and source.content == PDF
    assert source.headers["content-type"] == "application/pdf"
    listed = env.client.get("/api/v1/contracts").json()
    assert record["hop_dong_id"] in {c["hop_dong_id"] for c in listed["items"]}
    docx = upload(env.client, docx_bytes(), name="hd.docx").json()
    assert docx["source"]["mime_type"].endswith("wordprocessingml.document")


@pytest.mark.parametrize(
    "payload,code,error",
    [
        (b"not a contract", 415, "UNSUPPORTED_MEDIA_TYPE"),
        (b"PK\x03\x04 broken zip", 415, "UNSUPPORTED_MEDIA_TYPE"),
        (b"", 415, "UNSUPPORTED_MEDIA_TYPE"),
        (b"%PDF-" + b"x" * 5000, 413, "FILE_TOO_LARGE"),
    ],
)
def test_upload_rejects_wrong_type_and_oversized_files(env, payload, code, error):  # noqa: F811
    response = upload(env.client, payload, name="evil.pdf")
    assert response.status_code == code
    assert response.json()["error"]["code"] == error


def test_case_creation_pins_server_side_deployment(env):  # noqa: F811
    contract = upload(env.client, PDF).json()
    response = env.client.post(
        "/api/v1/cases",
        json={"hop_dong_id": contract["hop_dong_id"], "ngay_danh_gia": "2026-11-03"},
    )
    assert response.status_code == 201, response.text
    case = response.json()["case"]
    assert case["ca_id"].startswith("CA_UP_")
    assert case["tenant_id"] == "TENANT_TEST" and case["created_by"] == "USER_TEST"
    assert case["deployment"] == {
        "phien_ban_id": "DEPLOY_TEST",
        "rule_version": "RULE_TEST",
        "legal_knowledge_version": "LEGAL_TEST",
    }
    assert case["assessment_context"]["moc_ap_dung"] is None  # unknown stays unknown
    assert response.json()["latest_run_id"] is None
    rejected = env.client.post(
        "/api/v1/cases",
        json={
            "hop_dong_id": contract["hop_dong_id"],
            "ngay_danh_gia": "2026-11-03",
            "tenant_id": "OTHER",
        },
    )
    assert rejected.status_code == 422  # clients cannot set server-owned fields
    missing = env.client.post(
        "/api/v1/cases", json={"hop_dong_id": "HD_NOPE", "ngay_danh_gia": "2026-11-03"}
    )
    assert missing.status_code == 404


def test_history_filters_and_sorting(env):  # noqa: F811
    contract = upload(env.client, PDF, title="Căn hộ B2").json()
    created = env.client.post(
        "/api/v1/cases",
        json={"hop_dong_id": contract["hop_dong_id"], "ngay_danh_gia": "2026-11-03"},
    ).json()["case"]["ca_id"]
    start(env.client)  # CA_TEST gets a COMPLETED run and report

    def ids(**params):
        return [
            i["case"]["ca_id"]
            for i in env.client.get("/api/v1/cases", params=params).json()["items"]
        ]

    assert set(ids()) == {CASE, created}
    assert ids(run_status="COMPLETED") == [CASE]
    assert ids(run_status="NONE") == [created]
    assert ids(q="căn hộ b2") == [created]
    assert ids(q="%") == []  # wildcards are matched literally
    assert ids(date_from="2026-11-01") == [created]
    assert ids(date_to="2026-10-31") == [CASE]
    assert ids(sort="-ngay_danh_gia")[0] == created
    completed = env.client.get("/api/v1/cases", params={"run_status": "COMPLETED"}).json()["items"][
        0
    ]
    assert completed["latest_report_id"] and completed["ten_tai_lieu"]
    assert env.client.get("/api/v1/cases", params={"run_status": "DONE"}).status_code == 422


def test_other_tenants_cannot_see_cases_runs_reports_or_contracts(env):  # noqa: F811
    run_id = start(env.client)["context"]["run_id"]
    report_id = env.client.get(f"/api/v1/cases/{CASE}/runs/{run_id}/reports").json()["items"][0][
        "report"
    ]["bao_cao_id"]
    contract = upload(env.client, PDF).json()["hop_dong_id"]
    env.app.dependency_overrides[current_actor] = lambda: Actor(
        "OUTSIDER", "OTHER_TENANT", frozenset({"viewer", "uploader"})
    )
    try:
        assert env.client.get("/api/v1/cases").json()["total"] == 0
        for url in (
            f"/api/v1/cases/{CASE}",
            f"/api/v1/cases/{CASE}/runs/{run_id}/status",
            f"/api/v1/cases/{CASE}/runs/{run_id}/results",
            f"/api/v1/reports/{report_id}",
            f"/api/v1/reports/{report_id}/export?format=docx",
            f"/api/v1/contracts/{contract}",
            f"/api/v1/contracts/{contract}/source",
        ):
            assert env.client.get(url).status_code == 404, url
        started = env.client.post(f"/api/v1/cases/{CASE}/runs", headers={"Idempotency-Key": "x"})
        assert started.status_code == 404
        # The same bytes uploaded by another tenant become that tenant's own contract.
        assert upload(env.client, PDF).json()["hop_dong_id"] != contract
    finally:
        env.app.dependency_overrides.clear()
