"""Uploaded contracts run group A's document intelligence inside the full assessment run."""

import pytest
from legal_checker.modules.assessments.cases import CaseRepository
from legal_checker.workflows.integrated import (
    MODULE_SOURCE,
    REFERENCE_DI_SOURCE,
    IntegratedModulesSource,
)
from test_assessment_runs import CASE, env, start  # noqa: F401  (fixture re-export)
from test_contract_upload import docx_bytes
from unit.test_document_parser_chunker import _minimal_pdf

CONTRACT = _minimal_pdf(
    [
        "HOP DONG MUA BAN CAN HO CHUNG CU\n"
        "Dieu 1. Doi tuong cua hop dong\n"
        "Ben ban dong y ban va ben mua dong y mua can ho so A1-12.\n"
        "Dieu 2. Gia ban va phuong thuc thanh toan\n"
        "Gia ban can ho la 2.000.000.000 dong.",
    ]
)


@pytest.fixture
def integrated(env):  # noqa: F811
    pytest.importorskip("pypdf")
    source = IntegratedModulesSource(
        env.database_url,
        CaseRepository(env.database_url),
        storage=env.document_sources,
        upload_dir=env.upload_dir,
        source_cache_dir=env.upload_dir / "no-cache",
    )
    env.runner.source = source
    env.service.module_source = source.label
    return env


def case_for(ctx, payload, name):
    contract = ctx.client.post(
        "/api/v1/contracts", files={"file": (name, payload, "application/octet-stream")}
    )
    assert contract.status_code == 201, contract.text
    created = ctx.client.post(
        "/api/v1/cases",
        json={
            "hop_dong_id": contract.json()["hop_dong_id"],
            "ngay_danh_gia": "2026-10-14",
            "moc_ap_dung": None,
            "loai_moc_ap_dung": None,
            "phien_ban_id": None,
        },
    )
    assert created.status_code == 201, created.text
    return created.json()["case"]["ca_id"]


def run(ctx, ca_id):
    accepted = ctx.client.post(
        f"/api/v1/cases/{ca_id}/runs", headers={"Idempotency-Key": f"di-{ca_id}"}
    )
    assert accepted.status_code == 202, accepted.text
    run_id = accepted.json()["context"]["run_id"]
    status = ctx.client.get(accepted.json()["status_url"]).json()
    return ctx.runs.get(ca_id, run_id), status, {s["stage"]: s["status"] for s in status["stages"]}


def test_uploaded_pdf_is_read_by_group_a_and_labelled_as_modules(integrated):
    ca_id = case_for(integrated, CONTRACT, "hop_dong.pdf")
    record, status, stages = run(integrated, ca_id)
    assert record.module_source == MODULE_SOURCE
    assert stages["INTAKE"] == "COMPLETED"
    assert stages["DOCUMENT_INTELLIGENCE"] == "COMPLETED", status.get("error")
    assert status["status"] == "COMPLETED", status.get("error")
    draft = integrated.runs.draft(ca_id, record.run_id)
    assert draft.contract_profile.hop_dong_id == draft.case.hop_dong_id
    assert "HOP DONG MUA BAN" in " ".join(c.noi_dung for c in draft.chunks)
    report = integrated.client.get(f"/api/v1/cases/{ca_id}/runs/{record.run_id}/reports").json()
    assert report["items"][0]["report"]["report_json"]["audit"]["module_source"] == MODULE_SOURCE


def test_uploaded_docx_fails_with_a_clear_format_reason(integrated):
    ca_id = case_for(integrated, docx_bytes(), "hop_dong.docx")
    record, status, stages = run(integrated, ca_id)
    assert record.module_source == MODULE_SOURCE
    assert status["status"] == "FAILED"
    assert status["error"]["details"] == [{"reason": "DOCUMENT_FORMAT_UNSUPPORTED"}]
    assert stages["DOCUMENT_INTELLIGENCE"] == "FAILED"


def test_scanned_pdf_without_text_stops_instead_of_an_empty_assessment(integrated):
    ca_id = case_for(integrated, _minimal_pdf([""]), "scan.pdf")
    record, status, stages = run(integrated, ca_id)
    assert status["status"] == "FAILED"
    assert status["error"]["details"] == [{"reason": "DOCUMENT_NOT_READABLE"}]
    assert stages["DOCUMENT_INTELLIGENCE"] == "FAILED"
    assert integrated.runs.draft(ca_id, record.run_id) is None


def test_seeded_case_without_local_source_keeps_the_reference_label(integrated):
    record, _, _ = run(integrated, CASE)
    assert record.module_source == REFERENCE_DI_SOURCE
