"""Synthetic adapter integration; this does not claim real OCR/retrieval/LLM quality."""

from types import SimpleNamespace

import pytest
from legal_checker.shared.contracts.assessment import AssessmentCase
from legal_checker.shared.contracts.citation import CitationExtraction, CitationValidation
from legal_checker.shared.contracts.common import Context
from legal_checker.shared.contracts.document_intelligence import (
    ContractProfile,
    DocumentIntelligenceResult,
)
from legal_checker.shared.contracts.scope import ScopeResolution
from legal_checker.workflows.assessment_workflow import DraftAssessmentWorkflow, DraftModules


def assemble(request, knowledge, citation_status=None):
    context = Context(**request.model_dump(exclude={"payload", "contract_name"}))
    case = AssessmentCase(
        ca_id=context.ca_id,
        hop_dong_id=request.payload.hop_dong_id,
        source={
            "tep_id": "TEP_TEST",
            "object_uri": "fixture://contract.pdf",
            "mime_type": "application/pdf",
            "sha256": "a" * 64,
        },
        assessment_context={"ngay_danh_gia": "2026-10-12"},
        deployment={
            k: getattr(context, k)
            for k in ("phien_ban_id", "rule_version", "legal_knowledge_version")
        },
        tenant_id="TENANT_TEST",
        created_by="USER_TEST",
    )
    extracted = []
    validated = []
    if citation_status:
        extracted = [
            CitationExtraction(
                vien_dan_id="VD_TEST",
                hop_dong_id=case.hop_dong_id,
                raw_text="Synthetic citation",
                normalized={},
                extraction={"status": "EXTRACTED"},
                evidence=[{"doan_id": "D_TEST", "page_start": 1, "page_end": 1}],
            )
        ]
        validated = [
            CitationValidation(
                finding_id="CF_TEST",
                ca_id=case.ca_id,
                vien_dan_id="VD_TEST",
                normalized_van_ban_id="VBPL001",
                relevant_date="2026-01-15",
                status=citation_status,
                reason_code="SYNTHETIC_FIXTURE",
                ly_do="Fixture citation",
                domain_status="MATCH",
                finding_verified=True,
                source_snapshot_json={
                    "reviewed_knowledge": True,
                    "official_evidence_required": True,
                    "identity_or_context_invalidity_proven": True,
                },
                lan_chay_id=context.run_id,
                knowledge_version=context.legal_knowledge_version,
            )
        ]
    document = DocumentIntelligenceResult(
        contract_profile=ContractProfile(hop_dong_id=case.hop_dong_id, profile={}),
        chunks=request.payload.chunks,
        citations=extracted,
    )
    scopes = [
        ScopeResolution(
            yeu_cau_ca_id=r.yeu_cau_ca_id,
            ca_id=r.ca_id,
            requirement_id=r.requirement_id,
            scope_status=r.scope_status,
            scope_reason="Fixture scope",
        )
        for r in request.payload.requirements
    ]
    modules = DraftModules(
        intake=SimpleNamespace(register=lambda item: item),
        documents=SimpleNamespace(extract=lambda item: document),
        scope=SimpleNamespace(resolve=lambda ctx, profile, kb: scopes),
        temporal=SimpleNamespace(
            resolve=lambda ctx, profile, scope, kb: request.payload.requirements
        ),
        retrieval=SimpleNamespace(retrieve=lambda ctx, req, chunks, kb: request.payload.retrieval),
        citations=SimpleNamespace(validate=lambda ctx, profile, raw, kb: validated),
        observations=SimpleNamespace(observe=lambda *args: request.payload.observations),
    )
    return DraftAssessmentWorkflow(modules, knowledge), case, context, document, scopes


def test_upstream_adapters_stop_at_unimplemented_step_5(knowledge, request_factory):
    workflow, case, context, _, _ = assemble(request_factory(finding="MISSING"), knowledge)
    with pytest.raises(NotImplementedError, match="skeletons"):
        workflow.evaluate(case, context)


def test_intake_cannot_mutate_the_original_pin(knowledge, request_factory):
    workflow, case, context, _, _ = assemble(request_factory(), knowledge)

    def mutate(item):
        item.deployment.rule_version = "DIFFERENT"
        return item

    workflow.modules.intake.register = mutate
    with pytest.raises(ValueError, match="Intake changed"):
        workflow.evaluate(case, context)
    assert case.deployment.rule_version == context.rule_version


@pytest.mark.parametrize("change", ["deployment", "profile", "chunk", "scope", "checklist"])
def test_workflow_rejects_foreign_or_changed_upstream_context(knowledge, request_factory, change):
    request = request_factory()
    workflow, case, context, document, scopes = assemble(request, knowledge)
    if change == "deployment":
        context.rule_version = "DIFFERENT"
    elif change == "profile":
        document.contract_profile.hop_dong_id = "FOREIGN"
    elif change == "chunk":
        document.chunks[0].hop_dong_id = "FOREIGN"
    elif change == "scope":
        scopes[0].scope_status = "UNKNOWN"
    else:
        scopes.clear()
    with pytest.raises(ValueError):
        workflow.evaluate(case, context)
