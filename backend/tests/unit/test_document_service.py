"""Group A step 2: service ghép parser → chunker → C02/C03 và mapper Q10 → C01."""

import hashlib
from datetime import date, datetime, timezone

import pytest
from legal_checker.modules.documents.repository import case_from_row
from legal_checker.modules.documents.service import PdfDocumentIntelligence, SourceMismatchError
from legal_checker.shared.contracts.assessment import AssessmentCase, SourceDocument
from legal_checker.shared.contracts.common import DeploymentPin
from test_document_parser_chunker import _minimal_pdf  # cùng thư mục tests/unit

PDF = _minimal_pdf(
    [
        "HOP DONG MUA BAN\nCan cu Nghi dinh 99/2015/ND-CP\nNgay giao ket: 2017-02-16",
        "Dieu 1. Doi tuong\nBen A ban can ho so 12A cho Ben B",
    ]
)


class FakeStorage:
    def __init__(self, content: bytes) -> None:
        self.content = content

    def read(self, source: SourceDocument) -> bytes:
        return self.content


def _case(sha256: str) -> AssessmentCase:
    return AssessmentCase(
        ca_id="CA_TEST",
        hop_dong_id="HD_TEST",
        source=SourceDocument(
            tep_id="TEP", object_uri="x://HD.pdf", mime_type="application/pdf", sha256=sha256
        ),
        assessment_context={"ngay_danh_gia": date(2026, 11, 3)},
        deployment=DeploymentPin(phien_ban_id="P", rule_version="R", legal_knowledge_version="L"),
        tenant_id="T",
        created_by="dev",
    )


def test_service_returns_validated_result_and_stable_version():
    pytest.importorskip("pypdf")
    case = _case(hashlib.sha256(PDF).hexdigest())
    service = PdfDocumentIntelligence(FakeStorage(PDF))
    first, again = service.run(case), service.run(case)
    assert first.result.chunks and first.result.contract_profile.hop_dong_id == "HD_TEST"
    assert {c.normalized.so_hieu for c in first.result.citations} == {"99/2015/ND-CP"}
    assert first.version == again.version
    assert [c.doan_id for c in first.chunks] == [c.doan_id for c in again.chunks]
    assert service.extract(case) == first.result


def test_service_refuses_bytes_that_do_not_match_c01():
    pytest.importorskip("pypdf")
    with pytest.raises(SourceMismatchError):
        PdfDocumentIntelligence(FakeStorage(PDF)).run(_case("0" * 64))


def test_q10_row_maps_to_c01_with_utc_date():
    case = case_from_row(
        {
            "ca_id": "CA360_001",
            "hop_dong_id": "HD360_001",
            "tenant_id": "T",
            "created_by": "seed",
            "ngay_danh_gia": datetime(2026, 1, 5, 23, 30, tzinfo=timezone.utc),
            "moc_ap_dung": date(2017, 2, 16),
            "loai_moc_ap_dung": "NGAY_GIAO_KET",
            "phien_ban_id": "P",
            "rule_version": "R",
            "legal_knowledge_version": "L",
            "tep_id": "TEP",
            "object_uri": "https://example.invalid/HD360_001.pdf",
            "url_nguon": None,
            "mime_type": "application/pdf",
            "sha256": " " + "A" * 64 + " ",
        }
    )
    assert case.source.sha256 == "a" * 64
    assert case.assessment_context.ngay_danh_gia == date(2026, 1, 5)
