"""Boundary regressions without examples/parallel or checked-in DTO fixture files."""

from copy import deepcopy

import pytest
from legal_checker.core.postgres import connect_postgres
from legal_checker.modules.assessments.repository import Store
from legal_checker.modules.reports.builder import build_draft_report
from legal_checker.modules.retrieval.repository import RetrievalDatasetRepository
from legal_checker.shared.contracts.assessment import AssessmentCase
from legal_checker.shared.contracts.common import Context
from legal_checker.shared.contracts.document_intelligence import (
    ContractProfile,
    DocumentIntelligenceResult,
    ProfileFields,
)
from legal_checker.shared.contracts.handoffs import (
    ComplianceOutput,
    IntegrationInput,
    LegalOutput,
    RetrievalInput,
    ScopeInput,
)
from legal_checker.shared.contracts.scope import ScopeResolution
from legal_checker.workflows.handoffs import (
    validate_document,
    validate_legal,
    validate_report,
    validate_retrieval,
)
from pydantic import ValidationError


@pytest.fixture
def handoffs(database_url, knowledge, request_factory, response_factory):
    request = request_factory()
    response = response_factory(request)
    # Capture this snapshot in the isolated runtime DB too.
    from legal_checker.modules.legal_knowledge.repository import Knowledge

    assert Knowledge(database_url).sha256 == knowledge.sha256
    Store(database_url).save(request, response)
    with connect_postgres(database_url) as connection:
        raw = connection.execute(
            "SELECT input_json FROM runtime.assessment_runs WHERE ca_id=%s AND run_id=%s",
            (request.ca_id, request.run_id),
        ).fetchone()
    request = type(request).model_validate(raw["input_json"])
    context = Context(**request.model_dump(exclude={"payload", "contract_name"}))
    case = AssessmentCase(
        ca_id=context.ca_id,
        hop_dong_id=request.payload.hop_dong_id,
        source={
            "tep_id": "TEST_SOURCE",
            "object_uri": "test://source",
            "mime_type": "application/pdf",
            "sha256": "a" * 64,
        },
        assessment_context={"ngay_danh_gia": "2026-01-15"},
        deployment={
            k: getattr(context, k)
            for k in ("phien_ban_id", "rule_version", "legal_knowledge_version")
        },
        tenant_id="TEST",
        created_by="TEST",
    )
    evidence = request.payload.observations[0].evidence[0].model_dump()
    profile = ContractProfile(
        hop_dong_id=case.hop_dong_id,
        profile={"la_hop_dong_theo_mau": True},
        evidence=[{"bang_chung_id": "PROFILE_EVIDENCE", **evidence}],
        facts=[
            {
                "trich_xuat_id": "FACT",
                "ten_truong": "profile.la_hop_dong_theo_mau",
                "gia_tri_chuan_json": True,
                "trang_thai": "TEST_UNVERIFIED",
                "phuong_phap": "TEST",
                "evidence_ids": ["PROFILE_EVIDENCE"],
            }
        ],
    )
    document = DocumentIntelligenceResult(
        contract_profile=profile, chunks=request.payload.chunks, citations=[]
    )
    scopes = [
        ScopeResolution(
            **r.model_dump(
                include={
                    "ca_id",
                    "yeu_cau_ca_id",
                    "requirement_id",
                    "scope_status",
                    "nhom_phien_ban",
                    "profile_snapshot_json",
                    "dieu_kien_snapshot_json",
                }
            ),
            scope_reason="Test input",
        )
        for r in request.payload.requirements
    ]
    legal = LegalOutput(scope=scopes, requirements=request.payload.requirements, citations=[])
    return request, context, case, document, legal


@pytest.mark.parametrize("change", ["chunk", "quote", "fact", "duplicate", "provenance"])
def test_document_boundary_rejects_bad_provenance(handoffs, change):
    _, _, case, document, _ = handoffs
    validate_document(case, document)
    if change == "chunk":
        document.chunks[0].hop_dong_id = "FOREIGN"
    elif change == "quote":
        document.contract_profile.evidence[0].trich_dan = "Invented"
    elif change == "fact":
        document.contract_profile.facts[0].evidence_ids = ["NO_EVIDENCE"]
    elif change == "duplicate":
        document.chunks.append(document.chunks[0])
    else:
        document.contract_profile.facts.clear()
    with pytest.raises(ValueError):
        validate_document(case, document)


def test_unknown_boolean_and_scope_branch_contract(handoffs):
    _, context, _, document, _ = handoffs
    assert ProfileFields(ben_ban_la_ca_nhan=None).ben_ban_la_ca_nhan is None
    with pytest.raises(ValidationError):
        ProfileFields(ben_ban_la_ca_nhan="UNKNOWN")
    with pytest.raises(ValidationError):
        ScopeInput(context=context, contract_profile=document.contract_profile, citations=[])


@pytest.mark.parametrize("change", ["scope", "version", "pin", "family", "provenance"])
def test_legal_boundary_retains_checklist_ownership(handoffs, knowledge, change):
    _, context, _, document, legal = handoffs
    validate_legal(context, document, legal, knowledge)
    if change == "scope":
        legal.scope[0].scope_status = "NO_MATCH"
    elif change == "version":
        legal.requirements[0].requirement_version_id = "FOREIGN"
    elif change == "pin":
        legal.requirements[0].phien_ban_id = "FOREIGN"
    elif change == "family":
        legal.scope[0].requirement_id = "FOREIGN"
    else:
        legal.requirements[0].profile_snapshot_json = {"different": "profile"}
    with pytest.raises(ValueError):
        validate_legal(context, document, legal, knowledge)


@pytest.mark.parametrize("change", ["chunk", "criterion", "requirement", "run", "duplicate"])
def test_retrieval_boundary_uses_persisted_case_run(handoffs, knowledge, change):
    request, context, case, document, legal = handoffs
    inputs = RetrievalInput(
        context=context,
        hop_dong_id=case.hop_dong_id,
        requirements=legal.requirements,
        chunks=document.chunks,
    )
    output = deepcopy(request.payload.retrieval)
    validate_retrieval(inputs, output, knowledge)
    if change == "duplicate":
        output.append(output[0])
    else:
        setattr(
            output[0],
            {
                "chunk": "doan_id",
                "criterion": "tieu_chi_id",
                "requirement": "yeu_cau_ca_id",
                "run": "lan_chay_id",
            }[change],
            "FOREIGN",
        )
    with pytest.raises(ValueError):
        validate_retrieval(inputs, output, knowledge)


@pytest.mark.parametrize("change", ["profile", "evidence", "run", "publish", "scope"])
def test_report_boundary_preserves_pending_branches(handoffs, knowledge, request_factory, change):
    pipeline, context, case, document, legal = handoffs
    integration = IntegrationInput(
        context=context,
        case=case,
        document=document,
        legal=legal,
        compliance=ComplianceOutput(
            context=context,
            hop_dong_id=case.hop_dong_id,
            criterion_results=[],
            requirement_results=[],
            risks=[],
            recommendations=[],
        ),
    )
    report = build_draft_report(integration, knowledge, risks=[], recommendations=[])
    validate_report(integration, report, knowledge, risks=[], recommendations=[])
    report = report.model_copy(deep=True)
    if change == "profile":
        report.report_json.contract_profile.hop_dong_id = "FOREIGN"
    elif change == "evidence":
        report.report_json.compliance.evidence.append({"invented": True})
    elif change == "run":
        report.report_json.audit["context"]["run_id"] = "FOREIGN"
    elif change == "publish":
        report.report_status = "PUBLISHED"
    else:
        report.report_json.applicable_legal_scope.clear()
    with pytest.raises(ValueError):
        validate_report(integration, report, knowledge, risks=[], recommendations=[])


def test_db_reader_can_load_module_input_without_file_fixtures(handoffs, database_url):
    request, *_ = handoffs
    repo = RetrievalDatasetRepository(database_url)
    rows = repo.load_input_rows(request.ca_id)
    assert len(rows["criteria"]) == 3
    assert len(repo.load_seeded_evidence(request.ca_id, request.run_id)) == 3
