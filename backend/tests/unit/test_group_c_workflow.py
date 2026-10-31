"""Real workflow composition with synthetic trusted adapters and no database or API."""

from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace

import pytest
from legal_checker.modules.compliance.service import evaluate_compliance
from legal_checker.shared.contracts.assessment import AssessmentCase
from legal_checker.shared.contracts.citation import CitationExtraction, CitationValidation
from legal_checker.shared.contracts.common import Context
from legal_checker.shared.contracts.document_intelligence import (
    ContractProfile,
    DocumentIntelligenceResult,
)
from legal_checker.shared.contracts.handoffs import LegalOutput
from legal_checker.shared.contracts.pipeline import PipelineRequest
from legal_checker.shared.contracts.reasoning import ExternalEvidenceRegistration, ReasoningRequest
from legal_checker.shared.contracts.scope import ScopeResolution
from legal_checker.workflows.assessment_workflow import DraftAssessmentWorkflow, DraftModules
from legal_checker.workflows.handoffs import (
    report_input_from_draft,
    validate_compliance,
    validate_legal,
)
from legal_checker.workflows.steps_5_7 import evaluate
from test_criterion_reasoner import reasoning_case as reasoning_case
from test_group_c_core import configure_downstream


def pipeline_case(case, finding="VIOLATED"):
    knowledge, data = case
    data = deepcopy(data)
    observation = data["payload"]["observations"][0]
    observation["proposed_finding"] = finding
    observation["gates"].update(coverage_complete=True, absence_verified=True)
    if finding == "UNKNOWN":
        data["payload"]["observations"] = []
    configure_downstream(knowledge, finding)
    return knowledge, PipelineRequest.model_validate(data)


def citation_for(request, *, status="UNKNOWN", complete_provenance=True):
    return CitationValidation(
        finding_id="C09_TEST",
        ca_id=request.ca_id,
        vien_dan_id="C03_TEST",
        status=status,
        reason_code="MISSING_SOURCE" if status == "UNKNOWN" else "IDENTITY_INVALID",
        ly_do="Need the official source and date",
        domain_status="UNKNOWN" if status == "UNKNOWN" else "MATCH",
        finding_verified=False,
        source_snapshot_json={
            **(
                {
                    "knowledge_snapshot_sha256": request.knowledge_snapshot_sha256,
                    "context": request.model_dump(mode="json", include=set(Context.model_fields)),
                    "hop_dong_id": request.payload.hop_dong_id,
                }
                if complete_provenance
                else {}
            ),
        },
        lan_chay_id=request.run_id,
        knowledge_version=request.legal_knowledge_version,
    )


def assemble(request, knowledge, *, with_citation=False, registry=()):
    context = Context(**request.model_dump(include=set(Context.model_fields)))
    case = AssessmentCase(
        ca_id=context.ca_id,
        hop_dong_id=request.payload.hop_dong_id,
        source={
            "tep_id": "SOURCE_TEST",
            "object_uri": "fixture://input.pdf",
            "mime_type": "application/pdf",
            "sha256": "a" * 64,
        },
        assessment_context={"ngay_danh_gia": "2026-10-29"},
        deployment=context.model_dump(
            include={"phien_ban_id", "rule_version", "legal_knowledge_version"}
        ),
        tenant_id="TENANT_TEST",
        created_by="USER_TEST",
    )
    extracted = (
        [
            CitationExtraction(
                vien_dan_id="C03_TEST",
                hop_dong_id=case.hop_dong_id,
                raw_text="Synthetic citation input",
                normalized={},
                extraction={"status": "EXTRACTED"},
                evidence=[{"doan_id": "CHUNK_1", "page_start": 2, "page_end": 2}],
            )
        ]
        if with_citation
        else []
    )
    document = DocumentIntelligenceResult(
        contract_profile=ContractProfile(hop_dong_id=case.hop_dong_id, profile={}),
        chunks=request.payload.chunks,
        citations=extracted,
    )
    scopes = [
        ScopeResolution(
            yeu_cau_ca_id=row.yeu_cau_ca_id,
            ca_id=row.ca_id,
            requirement_id=row.requirement_id,
            scope_status=row.scope_status,
            scope_reason="Synthetic reviewed scope",
            nhom_phien_ban=row.nhom_phien_ban,
            profile_snapshot_json=row.profile_snapshot_json,
            dieu_kien_snapshot_json=row.dieu_kien_snapshot_json,
        )
        for row in request.payload.requirements
    ]
    modules = DraftModules(
        intake=SimpleNamespace(register=lambda item: item),
        documents=SimpleNamespace(extract=lambda item: document),
        scope=SimpleNamespace(resolve=lambda *args: scopes),
        temporal=SimpleNamespace(resolve=lambda *args: request.payload.requirements),
        retrieval=SimpleNamespace(retrieve=lambda *args: request.payload.retrieval),
        observations=SimpleNamespace(observe=lambda *args: request.payload.observations),
        citations=SimpleNamespace(
            validate=lambda *args: [citation_for(request)] if with_citation else []
        ),
        external_evidence_registry=registry,
    )
    return DraftAssessmentWorkflow(modules, knowledge), case, context, document


@pytest.mark.parametrize("finding", ["SATISFIED", "VIOLATED", "MISSING", "UNKNOWN"])
@pytest.mark.parametrize("citation_mode", ["not-run", "completed-empty", "unknown"])
def test_compliance_only_and_full_pipeline_preserve_independent_branches(
    reasoning_case, finding, citation_mode
):
    knowledge, request = pipeline_case(reasoning_case, finding)
    if citation_mode == "unknown":
        configure_downstream(knowledge, "UNKNOWN", citation=True)
        request.payload.citations = [citation_for(request)]
    request.payload.citation_branch_status = (
        "NOT_RUN" if citation_mode == "not-run" else "COMPLETED"
    )
    before = request.model_dump()
    reasoning = ReasoningRequest(
        **request.model_dump(include=set(Context.model_fields)),
        payload=request.payload.model_dump(
            exclude={"citations", "citation_branch_status", "reasoning_provenance"}
        ),
    )
    compliance = evaluate_compliance(reasoning, knowledge)
    output = evaluate(request, knowledge)
    assert compliance.criterion_results == output.payload.criterion_results
    assert compliance.requirement_results == output.payload.requirement_results
    assert all(row.source.citation_finding_id is None for row in compliance.risks)
    assert [
        row for row in output.payload.risks if row.source.ket_qua_tieu_chi_id
    ] == compliance.risks
    assert request.model_dump() == before
    expected_status = "NOT_RUN" if citation_mode == "not-run" else "COMPLETED"
    assert any(
        item["code"] == "CITATION_BRANCH_" + expected_status for item in output.payload.diagnostics
    )
    assert any(item["code"] == "CITATION_BRANCH_NOT_RUN" for item in compliance.diagnostics)
    validate_compliance(reasoning, compliance, knowledge)


def test_unresolved_c05_and_missing_upstream_remain_uncertain(reasoning_case):
    knowledge, request = pipeline_case(reasoning_case, "UNKNOWN")
    request.payload.requirements[0].version_status = "UNKNOWN"
    request.payload.requirements[0].applicability_status = "UNKNOWN"
    request.payload.retrieval.clear()
    request.payload.chunks.clear()
    output = evaluate(request, knowledge)
    assert output.payload.criterion_results == []
    assert output.payload.requirement_results[0].status == "INSUFFICIENT"
    assert output.payload.risks == output.payload.recommendations == []
    assert any(item["code"] == "INSUFFICIENT_REQUIREMENT" for item in output.payload.diagnostics)


def test_missing_observations_are_explicit_c07_diagnostics(reasoning_case):
    knowledge, request = pipeline_case(reasoning_case, "UNKNOWN")
    output = evaluate(request, knowledge)
    finding = output.payload.criterion_results[0]
    diagnostic = next(
        item for item in output.payload.diagnostics if item["code"] == "UNRESOLVED_CRITERION"
    )
    assert diagnostic["reason"] == finding.uncertainty_reason
    assert "observation" in diagnostic["reason"].lower()


def test_missing_known_c09_provenance_is_preserved_without_fabricated_pins(reasoning_case):
    knowledge, request = pipeline_case(reasoning_case)
    citation = citation_for(request, status="INVALID", complete_provenance=False)
    request.payload.citations = [citation]
    output = evaluate(request, knowledge)
    assert any(item["code"] == "C09_PROVENANCE_UNAVAILABLE" for item in output.payload.diagnostics)
    assert all(row.source.citation_finding_id is None for row in output.payload.risks)
    assert request.payload.citations[0].source_snapshot_json == {}


@pytest.mark.parametrize("missing", ["retrieval", "observations", "citations", "all"])
def test_draft_workflow_keeps_explicitly_unavailable_upstream_visible(reasoning_case, missing):
    knowledge, request = pipeline_case(reasoning_case)
    workflow, case, context, _ = assemble(request, knowledge, with_citation=True)
    names = {"retrieval", "observations", "citations"} if missing == "all" else {missing}
    workflow.modules = replace(workflow.modules, **{name: None for name in names})
    draft = workflow.evaluate(case, context)
    codes = {item["code"] for item in draft.evaluation.payload.diagnostics}
    if "retrieval" in names:
        assert draft.retrieval == []
        assert "RETRIEVAL_NOT_RUN" in codes
    if "observations" in names:
        assert "OBSERVATION_PROVIDER_NOT_RUN" in codes
    if "retrieval" in names or "observations" in names:
        assert all(row.finding == "UNKNOWN" for row in draft.evaluation.payload.criterion_results)
    if "citations" in names:
        assert draft.citation_findings == []
        assert "CITATION_BRANCH_NOT_RUN" in codes
        assert len(draft.extracted_citations) == 1
    handoff = report_input_from_draft(draft)
    assert handoff.compliance.diagnostics == draft.evaluation.payload.diagnostics


def test_completed_citation_adapter_must_cover_extracted_inputs(reasoning_case):
    knowledge, request = pipeline_case(reasoning_case)
    workflow, case, context, _ = assemble(request, knowledge, with_citation=True)
    workflow.modules.citations.validate = lambda *args: []
    with pytest.raises(ValueError, match="cover exactly"):
        workflow.evaluate(case, context)


def test_adapters_cannot_mutate_shared_pins_or_other_branch_inputs(reasoning_case):
    knowledge, request = pipeline_case(reasoning_case)
    workflow, case, context, document = assemble(request, knowledge, with_citation=True)
    before = deepcopy(
        (case.model_dump(), context.model_dump(), request.model_dump(), document.model_dump())
    )
    original_scope = workflow.modules.scope.resolve

    def scope(ctx, profile, kb):
        ctx.run_id = "MUTATED_RUN"
        profile.hop_dong_id = "MUTATED_CONTRACT"
        return original_scope()

    def citations(ctx, profile, rows, kb):
        ctx.rule_version = "MUTATED_RULES"
        profile.hop_dong_id = "MUTATED_CONTRACT"
        rows[0].raw_text = "MUTATED_CITATION"
        return [citation_for(request)]

    workflow.modules.scope.resolve = scope
    workflow.modules.citations.validate = citations
    draft = workflow.evaluate(case, context)
    assert (
        case.model_dump(),
        context.model_dump(),
        request.model_dump(),
        document.model_dump(),
    ) == before
    assert draft.evaluation.run_id == context.run_id
    assert draft.extracted_citations[0].raw_text == "Synthetic citation input"


def test_invalid_retrieval_fails_before_provider_can_run(reasoning_case):
    knowledge, request = pipeline_case(reasoning_case)
    workflow, case, context, _ = assemble(request, knowledge)
    request.payload.retrieval[0].lan_chay_id = "FOREIGN_RUN"
    workflow.modules.observations.observe = lambda *args: pytest.fail(
        "Provider must not receive invalid C06"
    )
    with pytest.raises(ValueError, match="Retrieval run"):
        workflow.evaluate(case, context)


@pytest.mark.parametrize("registry_state", ["valid", "absent", "foreign"])
def test_draft_external_evidence_uses_only_independent_registry(reasoning_case, registry_state):
    knowledge, request = pipeline_case(reasoning_case, "SATISFIED")
    knowledge.criteria["CRITERION_1"]["loai_kiem_tra"] = "PERFORMANCE_WITH_DOCUMENTS"
    request.payload.retrieval.clear()
    observation = request.payload.observations[0]
    observation.evidence.clear()
    from legal_checker.shared.contracts.document_intelligence import ExternalEvidence

    observation.external_evidence = [
        ExternalEvidence(
            bang_chung_id="RECEIPT_TEST",
            object_uri="fixture://verified-receipt.pdf",
            sha256="b" * 64,
            verified=True,
        )
    ]
    registration = ExternalEvidenceRegistration(
        **request.model_dump(include=set(Context.model_fields)),
        hop_dong_id=request.payload.hop_dong_id,
        yeu_cau_ca_id=request.payload.requirements[0].yeu_cau_ca_id,
        tieu_chi_id="CRITERION_1",
        bang_chung_id="RECEIPT_TEST",
        object_uri="fixture://verified-receipt.pdf",
        sha256="b" * 64,
        verified=True,
        verification_reference="fixture://backend/receipt-review",
    )
    if registry_state == "foreign":
        registration.ca_id = "FOREIGN_CASE"
    registry = [registration] if registry_state != "absent" else []
    workflow, case, context, _ = assemble(request, knowledge, registry=registry)
    before = [item.model_dump() for item in registry]
    if registry_state == "foreign":
        with pytest.raises(ValueError, match="External registry"):
            workflow.evaluate(case, context)
    else:
        draft = workflow.evaluate(case, context)
        expected = "SATISFIED" if registry_state == "valid" else "UNKNOWN"
        assert draft.evaluation.payload.criterion_results[0].finding == expected
        assert [item.model_dump() for item in registry] == before


def test_legal_handoff_not_run_rejects_claimed_findings(reasoning_case):
    knowledge, request = pipeline_case(reasoning_case)
    workflow, _, context, document = assemble(request, knowledge, with_citation=True)
    scopes = workflow.modules.scope.resolve()
    with pytest.raises(ValueError, match="NOT_RUN"):
        validate_legal(
            context,
            document,
            LegalOutput(
                scope=scopes,
                requirements=request.payload.requirements,
                citations=[citation_for(request)],
            ),
            knowledge,
            citation_branch_status="NOT_RUN",
        )
