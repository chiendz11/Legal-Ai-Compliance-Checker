"""Group A step 1 → 2: upload tạo C01 qua Q10, bước 2 đọc lại đúng bytes và ghi được kết quả."""

from dataclasses import replace
from datetime import date

import pytest
from legal_checker.core.postgres import connect_postgres
from legal_checker.modules.documents.intake import (
    CaseRequest,
    LocalSourceStore,
    PostgresIntake,
    UnknownDeploymentError,
    UploadRejectedError,
)
from legal_checker.modules.documents.repository import DocumentRepository
from legal_checker.modules.documents.service import PdfDocumentIntelligence
from legal_checker.shared.contracts.common import DeploymentPin
from legal_checker.shared.storage.http import CachedHttpSourceStorage
from unit.test_document_parser_chunker import _minimal_pdf

PDF = _minimal_pdf(["HOP DONG MUA BAN\nCan cu Nghi dinh 99/2015/ND-CP"])
REQUEST = CaseRequest(
    tenant_id="TENANT_DI",
    created_by="dev",
    deployment=DeploymentPin(
        phien_ban_id="DEPLOY_DI", rule_version="RULE_DI", legal_knowledge_version="LEGAL_DI"
    ),
    ngay_danh_gia=date(2026, 11, 3),
)


def _rows(database_url) -> int:
    with connect_postgres(database_url) as conn:
        return sum(
            conn.execute(f"SELECT count(*) AS n FROM runtime.{t}").fetchone()["n"]
            for t in ("hop_dong", "tep_nguon", "ca_danh_gia")
        )


@pytest.fixture
def intake(database_url, tmp_path):
    with connect_postgres(database_url) as conn:
        conn.execute(
            "INSERT INTO knowledge.phien_ban_trien_khai (phien_ban_id) VALUES ('DEPLOY_DI')"
        )
    return PostgresIntake(database_url, LocalSourceStore(tmp_path), new_id=lambda: "T1")


def test_upload_creates_pinned_case_that_step_2_can_process(intake, database_url, tmp_path):
    pytest.importorskip("pypdf")
    case = intake.submit(PDF, file_name="HD.pdf", mime_type="application/pdf", request=REQUEST)
    assert (case.ca_id, case.hop_dong_id, case.source.tep_id) == (
        "CA_UP_T1",
        "HD_UP_T1",
        "TEP_UP_T1",
    )
    assert case.deployment == REQUEST.deployment
    assert case.assessment_context.ngay_danh_gia == date(2026, 11, 3)
    assert intake.register(case) == case

    extraction = PdfDocumentIntelligence(CachedHttpSourceStorage(tmp_path)).run(case)
    report = DocumentRepository(database_url).save(extraction)
    assert report.chunks > 0 and report.citations == 1


def test_register_rejects_a_case_that_differs_from_the_database(intake):
    case = intake.submit(PDF, file_name="HD.pdf", mime_type="application/pdf", request=REQUEST)
    with pytest.raises(ValueError):
        intake.register(case.model_copy(update={"tenant_id": "OTHER"}))


def test_rejected_upload_or_unknown_deployment_writes_nothing(intake, database_url):
    with pytest.raises(UploadRejectedError):
        intake.submit(b"not a pdf", file_name="x.pdf", mime_type="application/pdf", request=REQUEST)
    unknown = replace(
        REQUEST,
        deployment=REQUEST.deployment.model_copy(update={"phien_ban_id": "DEPLOY_ABSENT"}),
    )
    with pytest.raises(UnknownDeploymentError):
        intake.submit(PDF, file_name="HD.pdf", mime_type="application/pdf", request=unknown)
    assert _rows(database_url) == 0
