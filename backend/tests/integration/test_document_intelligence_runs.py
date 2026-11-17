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


def case_for(ctx, payload, name, *, review_mode="DRAFT_REVIEW"):
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
            "review_mode": review_mode,
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
    integrated.runner.source.allow_reference_documents = True
    record, _, _ = run(integrated, CASE)
    assert record.module_source == REFERENCE_DI_SOURCE


@pytest.mark.parametrize(
    "review_mode,missing_provider",
    [("DRAFT_REVIEW", False), ("FULL_ASSESSMENT", True)],
)
def test_live_run_persists_active_extraction_before_retrieval(
    integrated, review_mode, missing_provider
):
    from legal_checker.core.postgres import connect_postgres

    ca_id = case_for(integrated, CONTRACT, "persist.pdf", review_mode=review_mode)
    record, status, _ = run(integrated, ca_id)
    assert status["status"] == "COMPLETED", status.get("error")
    draft = integrated.runs.draft(ca_id, record.run_id)
    with connect_postgres(integrated.database_url) as connection:
        rows = connection.execute(
            "SELECT doan_id FROM runtime.doan_hop_dong WHERE hop_dong_id=%s",
            (draft.case.hop_dong_id,),
        ).fetchall()
    assert {row["doan_id"] for row in rows} == {chunk.doan_id for chunk in draft.chunks}
    report = integrated.client.get(f"/api/v1/cases/{ca_id}/runs/{record.run_id}/reports").json()
    audit = report["items"][0]["report"]["report_json"]["audit"]
    assert any(d["code"] == "DOCUMENT_EXTRACTION_PERSISTED" for d in audit["diagnostics"])
    # Draft review creates SourceFactVerifier even without an injected provider.
    # Full assessment still reports the missing explicit verification provider.
    assert draft.case.assessment_context.review_mode == review_mode
    assert (
        any(d["code"] == "VERIFICATION_PROVIDER_NOT_CONFIGURED" for d in audit["diagnostics"])
        is missing_provider
    )
    assert audit["assessment_profile"]["requirement_ids"] == sorted(
        {r.requirement_id for r in draft.requirements}
    )


def test_modules_never_uses_qa_when_source_is_unavailable(integrated):
    source = integrated.runner.source
    assert source.allow_reference_documents is False
    source._reference = lambda case: pytest.fail("Live mode must not use QA")
    record, status, _ = run(integrated, CASE)
    assert record.module_source == MODULE_SOURCE
    assert status["status"] == "FAILED"


def test_person_four_verifier_is_called_with_live_upstream(integrated):
    from types import SimpleNamespace

    from legal_checker.core.postgres import connect_postgres

    calls = []

    def verify(context, profile, requirements, chunks, knowledge, *, coverage=None):
        with connect_postgres(integrated.database_url) as connection:
            count = connection.execute(
                "SELECT count(*) AS n FROM runtime.doan_hop_dong WHERE hop_dong_id=%s",
                (profile.hop_dong_id,),
            ).fetchone()["n"]
        assert count == len(chunks)  # Document writer completed before verifier/consumer.
        assert context.knowledge_snapshot_sha256 == knowledge.sha256
        assert coverage is not None
        assert coverage.hop_dong_id == profile.hop_dong_id
        assert coverage.page_count == 1 and coverage.unreadable_pages == []
        assert coverage.all_pages_have_text
        calls.append(context.run_id)
        return []  # No independent attestation: never fabricate verified facts.

    integrated.runner.source.verification_provider = SimpleNamespace(verify=verify)
    ca_id = case_for(integrated, CONTRACT, "verify.pdf")
    record, status, _ = run(integrated, ca_id)
    assert status["status"] == "COMPLETED", status.get("error")
    assert calls == [record.run_id]


def test_external_source_registry_rejects_another_run_before_processing(integrated):
    from types import SimpleNamespace

    from legal_checker.shared.contracts.reasoning import ExternalEvidenceRegistration

    def load(context, case, knowledge):
        assert knowledge.sha256 == context.knowledge_snapshot_sha256
        return [
            ExternalEvidenceRegistration(
                **{**context.model_dump(), "run_id": "FOREIGN_RUN"},
                hop_dong_id=case.hop_dong_id,
                yeu_cau_ca_id="YCCA",
                tieu_chi_id="TC",
                bang_chung_id="EXT",
                object_uri="fixture://receipt",
                sha256="a" * 64,
                verified=False,
                verification_reference="REGISTERED_NOT_VERIFIED",
            )
        ]

    integrated.runner.source.external_registry_provider = SimpleNamespace(load=load)
    ca_id = case_for(integrated, CONTRACT, "registry.pdf")
    _, status, _ = run(integrated, ca_id)
    assert status["status"] == "FAILED"
    assert status["error"]["details"] == [{"reason": "HANDOFF_VALIDATION_FAILED"}]
