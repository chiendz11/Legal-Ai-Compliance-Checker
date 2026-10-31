"""Kiểm tra ranh giới giữa nhận định thủ công và các xác minh chưa hoàn tất."""

from datetime import date
from types import SimpleNamespace

import pytest
from legal_checker.modules.compliance.criterion_reasoner import reason
from legal_checker.modules.compliance.demo_c07 import build_dev_request
from legal_checker.modules.compliance.manual_observations import build_reviewed_observation
from legal_checker.shared.contracts.document_intelligence import Chunk, Evidence
from legal_checker.shared.contracts.reasoning import ReasoningRequest
from legal_checker.shared.contracts.temporal import ApplicableRequirement


@pytest.fixture
def criterion():
    """Criterion đang học, không sử dụng dữ liệu thật hoặc kết luận seed."""
    return {
        "tieu_chi_id": "TC_PV_HYC049_01",
        "requirement_version_id": "PV_HYC049",
        "loai_kiem_tra": "CONTRACT_CONTENT",
        "source_dieu_khoan_id": "ARTICLE_TEST",
    }


@pytest.fixture
def requirement():
    """C05 xác nhận trong kịch bản synthetic vẫn không chứng minh phạm vi riêng."""
    return ApplicableRequirement(
        yeu_cau_ca_id="CASE_TEST_MAINTENANCE",
        ca_id="CASE_TEST",
        requirement_id="FAM_MAINTENANCE_2_PERCENT",
        requirement_version_id="PV_HYC049",
        scope_status="MATCH",
        version_status="RESOLVED",
        applicability_status="CONFIRMED",
        moc_ap_dung=date(2017, 2, 16),
        profile_snapshot_json={"synthetic": True},
        phien_ban_id="DEPLOYMENT_TEST",
    )


@pytest.fixture
def evidence():
    """Giữ khoảng trắng và Unicode tổ hợp để phát hiện quote bị làm sạch."""
    quote = "\n  Phi\u0301 bảo trì: 2% giá bán căn hộ chưa gồm VAT.  \n"
    return Evidence(
        doan_id="HD360_001_LS2_C00286",
        trich_dan=quote,
        ky_tu_bat_dau=0,
        ky_tu_ket_thuc=len(quote),
    )


def test_reviewed_content_does_not_promote_unverified_gates(criterion, requirement, evidence):
    observation = build_reviewed_observation(criterion, requirement, [evidence])

    assert observation.proposed_finding == "SATISFIED"
    assert observation.local_applicability == "UNKNOWN"
    assert observation.gates.evidence_validated is True
    assert observation.gates.scope_confirmed is True
    assert observation.gates.version_resolved is True
    assert observation.gates.source_verified is False
    assert observation.gates.exceptions_resolved is False
    assert observation.gates.reliable() is False
    assert "synthetic" in observation.giai_thich


def test_unconfirmed_c05_keeps_scope_and_version_unverified(criterion, requirement, evidence):
    requirement = requirement.model_copy(
        update={
            "scope_status": "UNKNOWN",
            "version_status": "UNKNOWN",
            "applicability_status": "UNKNOWN",
        }
    )
    observation = build_reviewed_observation(criterion, requirement, [evidence])

    assert observation.gates.scope_confirmed is False
    assert observation.gates.version_resolved is False
    assert observation.local_applicability == "UNKNOWN"


@pytest.mark.parametrize(
    "changes",
    [
        {"tieu_chi_id": "OTHER_CRITERION"},
        {"requirement_version_id": "OTHER_VERSION"},
        {"requirement_version_id": None},
        {"loai_kiem_tra": "NUMERIC"},
    ],
)
def test_rejects_criterion_outside_review_scope(criterion, requirement, evidence, changes):
    with pytest.raises(ValueError):
        build_reviewed_observation({**criterion, **changes}, requirement, [evidence])


def test_rejects_empty_reviewed_evidence(criterion, requirement):
    with pytest.raises(ValueError, match="evidence"):
        build_reviewed_observation(criterion, requirement, [])


def test_preserves_raw_quotes_and_copies_evidence(criterion, requirement, evidence):
    original_quote = evidence.trich_dan
    original_requirement = requirement.model_dump()
    items = [evidence]
    observation = build_reviewed_observation(criterion, requirement, items)

    assert observation.evidence[0].model_dump() == evidence.model_dump()
    assert observation.evidence[0] is not evidence
    assert requirement.model_dump() == original_requirement

    evidence.trich_dan = "changed by caller"
    items.clear()
    assert observation.evidence[0].trich_dan == original_quote


def test_revalidates_evidence_dto(criterion, requirement, evidence):
    invalid = evidence.model_copy(update={"ky_tu_ket_thuc": 0})
    with pytest.raises(ValueError):
        build_reviewed_observation(criterion, requirement, [invalid])


def test_does_not_invent_synthetic_provenance(criterion, requirement, evidence):
    requirement = requirement.model_copy(update={"profile_snapshot_json": {}})
    observation = build_reviewed_observation(criterion, requirement, [evidence])
    assert "synthetic" not in observation.giai_thich


def test_demo_uses_helper_and_reasoner_preserves_unknown(criterion, requirement, evidence):
    """Chạy luồng DEV bằng knowledge tối thiểu trong bộ nhớ, không kết nối DB."""
    version = {
        "requirement_id": requirement.requirement_id,
        "source_van_ban_id": "DOCUMENT_TEST",
    }
    rule = {
        "tieu_chi_id": criterion["tieu_chi_id"],
        "finding": "SATISFIED",
        "dieu_kien_json": {
            "enabled": True,
            "predicate": "Manually reviewed maintenance-content proposal.",
            "gate": {"exceptions_resolved": True},
        },
    }
    basis = [requirement.requirement_version_id, "ARTICLE_TEST", "DOCUMENT_TEST"]
    knowledge = SimpleNamespace(
        sha256="a" * 64,
        criteria={criterion["tieu_chi_id"]: criterion},
        versions={requirement.requirement_version_id: version},
        articles={"ARTICLE_TEST": {"van_ban_id": "DOCUMENT_TEST"}},
        documents={"DOCUMENT_TEST": {}},
        criteria_for=lambda version_id: [criterion],
        decision=lambda criterion_id, finding: rule,
        legal_basis=lambda item: basis,
    )
    request = ReasoningRequest(
        ca_id=requirement.ca_id,
        phien_ban_id=requirement.phien_ban_id,
        rule_version="RULES_TEST",
        legal_knowledge_version="KNOWLEDGE_TEST",
        knowledge_snapshot_sha256=knowledge.sha256,
        run_id="REFERENCE_TEST",
        trace_id="TRACE_TEST",
        payload={
            "hop_dong_id": "CONTRACT_TEST",
            "requirements": [requirement],
            "chunks": [
                Chunk(
                    doan_id=evidence.doan_id,
                    hop_dong_id="CONTRACT_TEST",
                    noi_dung=evidence.trich_dan,
                    page_start=1,
                    page_end=1,
                )
            ],
        },
    )
    original_request = request.model_dump()
    dev = build_dev_request(request, evidence, knowledge, include_observation=True)
    result = reason(dev, knowledge)[0]

    assert request.model_dump() == original_request
    assert len(dev.payload.observations) == len(dev.payload.retrieval) == 1
    assert dev.payload.observations[0].proposed_finding == "SATISFIED"
    assert result.finding == "UNKNOWN"
    assert result.review_status == "PENDING"
    assert "local_applicability" in result.uncertainty_reason
    assert "source_verified" in result.uncertainty_reason
    assert "exceptions_resolved" in result.uncertainty_reason
