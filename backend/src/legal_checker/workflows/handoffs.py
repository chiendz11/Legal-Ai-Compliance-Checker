"""Conformance checks usable by each module owner without running its predecessors."""

from datetime import datetime, timezone

from legal_checker.modules.assessments.integrity import validate_membership
from legal_checker.modules.compliance.requirement_aggregator import excluded_requirement_ids
from legal_checker.modules.legal_knowledge.models import KnowledgeSnapshot
from legal_checker.shared.contracts.assessment import AssessmentCase
from legal_checker.shared.contracts.common import Context
from legal_checker.shared.contracts.document_intelligence import DocumentIntelligenceResult
from legal_checker.shared.contracts.handoffs import (
    ComplianceOutput,
    IntegrationInput,
    LegalOutput,
    RetrievalInput,
)
from legal_checker.shared.contracts.pipeline import (
    PipelineRequest,
    PipelineResponse,
    PipelineResult,
)
from legal_checker.shared.contracts.reasoning import ReasoningPayload, ReasoningRequest
from legal_checker.shared.contracts.recommendation import Recommendation
from legal_checker.shared.contracts.report import FinalReport
from legal_checker.shared.contracts.retrieval import RetrievalEvidence
from legal_checker.shared.contracts.risk import RiskResult
from legal_checker.shared.contracts.workflow import AssessmentDraft
from legal_checker.shared.validation import (
    validate_citations,
    validate_context,
    validate_request,
    validate_requirements,
)


def report_input_from_draft(draft: AssessmentDraft) -> IntegrationInput:
    """Preserve both branches; Person 4 owns only criterion-sourced risks/actions."""
    output = draft.evaluation.payload
    risks = [item for item in output.risks if item.source.ket_qua_tieu_chi_id]
    risk_ids = {item.ket_qua_rui_ro_id for item in risks}
    return IntegrationInput(
        context=draft.context,
        case=draft.case,
        document=DocumentIntelligenceResult(
            contract_profile=draft.contract_profile,
            chunks=draft.chunks,
            citations=draft.extracted_citations,
        ),
        legal=LegalOutput(
            scope=draft.scope,
            requirements=draft.requirements,
            citations=draft.citation_findings,
        ),
        compliance=ComplianceOutput(
            context=draft.context,
            hop_dong_id=draft.case.hop_dong_id,
            criterion_results=output.criterion_results,
            requirement_results=output.requirement_results,
            risks=risks,
            recommendations=[r for r in output.recommendations if r.ket_qua_rui_ro_id in risk_ids],
            diagnostics=output.diagnostics,
        ),
    )


def unique(rows, key):
    ids = [getattr(row, key) for row in rows]
    if len(set(ids)) != len(ids):
        raise ValueError(f"Duplicate {key} in handoff")


def validate_case(context: Context, case: AssessmentCase, knowledge: KnowledgeSnapshot):
    validate_context(context, knowledge)
    if case.ca_id != context.ca_id:
        raise ValueError("Case does not match handoff context")
    if any(getattr(context, key) != value for key, value in case.deployment.model_dump().items()):
        raise ValueError("Case deployment does not match handoff context")


def validate_document(case: AssessmentCase, document: DocumentIntelligenceResult):
    profile = document.contract_profile
    if profile.hop_dong_id != case.hop_dong_id:
        raise ValueError("Profile belongs to a different contract")
    unique(document.chunks, "doan_id")
    unique(document.citations, "vien_dan_id")
    unique(profile.facts, "trich_xuat_id")
    unique(profile.evidence, "bang_chung_id")
    unique(profile.subjects, "chu_the_id")
    unique(profile.time_markers, "moc_id")
    chunks = {chunk.doan_id: chunk for chunk in document.chunks}
    if any(chunk.hop_dong_id != case.hop_dong_id for chunk in chunks.values()):
        raise ValueError("Chunk belongs to a different contract")
    evidence_ids = {item.bang_chung_id for item in profile.evidence}
    fact_ids = {item.trich_xuat_id for item in profile.facts}
    for evidence in profile.evidence:
        chunk = chunks.get(evidence.doan_id)
        if (
            not chunk
            or chunk.noi_dung[evidence.ky_tu_bat_dau : evidence.ky_tu_ket_thuc]
            != evidence.trich_dan
        ):
            raise ValueError("Profile evidence quote/offset does not match a source chunk")
        if evidence.ky_tu_ket_thuc > len(chunk.noi_dung):
            raise ValueError("Profile evidence offset exceeds the source chunk")
    for fact in profile.facts:
        if not set(fact.evidence_ids) <= evidence_ids:
            raise ValueError("Profile fact references unknown evidence")
        if fact.gia_tri_chuan_json is not None and not fact.evidence_ids:
            raise ValueError("An extracted value needs evidence provenance")
    facts = {item.ten_truong: item for item in profile.facts}
    for key, value in profile.profile.model_dump(mode="json").items():
        if value is None:
            continue
        fact = facts.get(f"profile.{key}")
        if not fact or fact.gia_tri_chuan_json != value or not fact.evidence_ids:
            raise ValueError(f"Profile field {key} needs a matching extracted fact/evidence")
    for subject in profile.subjects:
        if subject.doan_bang_chung_id and subject.doan_bang_chung_id not in chunks:
            raise ValueError("Subject references an unknown source chunk")
    for marker in profile.time_markers:
        if marker.trich_xuat_id and marker.trich_xuat_id not in fact_ids:
            raise ValueError("Time marker references an unknown extracted fact")
        if marker.duoc_dung_phan_giai and (not marker.ngay or not marker.trich_xuat_id):
            raise ValueError("A resolution time marker needs a date and provenance")
    for citation in document.citations:
        if citation.hop_dong_id != case.hop_dong_id:
            raise ValueError("Extracted citation belongs to a different contract")
        for position in citation.evidence:
            chunk = chunks.get(position.doan_id)
            if not chunk or not (
                chunk.page_start <= position.page_start <= position.page_end <= chunk.page_end
            ):
                raise ValueError("Citation position does not match a source chunk/page")


def validate_legal(
    context: Context,
    document: DocumentIntelligenceResult,
    output: LegalOutput,
    knowledge: KnowledgeSnapshot,
    *,
    citation_branch_status: str = "COMPLETED",
):
    validate_context(context, knowledge)
    unique(output.scope, "yeu_cau_ca_id")
    if not output.requirements:
        raise ValueError("An explicit applicable-law checklist is required")
    validate_requirements(context, output.requirements, knowledge)
    validate_citations(context, output.citations)
    known_families = {version["requirement_id"] for version in knowledge.versions.values()}
    if any(item.requirement_id not in known_families for item in output.scope):
        raise ValueError("Scope references a family outside the pinned knowledge snapshot")
    scopes = {item.yeu_cau_ca_id: item for item in output.scope}
    if set(scopes) != {item.yeu_cau_ca_id for item in output.requirements}:
        raise ValueError("Temporal output changed the scope checklist")
    for requirement in output.requirements:
        scope = scopes[requirement.yeu_cau_ca_id]
        if scope.ca_id != context.ca_id or (
            scope.requirement_id,
            scope.scope_status,
            scope.nhom_phien_ban,
        ) != (
            requirement.requirement_id,
            requirement.scope_status,
            requirement.nhom_phien_ban,
        ):
            raise ValueError("Temporal output changed scope ownership")
        if (
            scope.profile_snapshot_json != requirement.profile_snapshot_json
            or scope.dieu_kien_snapshot_json != requirement.dieu_kien_snapshot_json
        ):
            raise ValueError("Temporal output changed scope provenance")
    if citation_branch_status not in {"COMPLETED", "NOT_RUN"}:
        raise ValueError("Unsupported citation branch status")
    if citation_branch_status == "NOT_RUN":
        if output.citations:
            raise ValueError("NOT_RUN citation branch cannot contain findings")
    else:
        citation_ids = {item.vien_dan_id for item in document.citations}
        if {item.vien_dan_id for item in output.citations} != citation_ids:
            raise ValueError("Citation findings must cover exactly the extracted citations")
    if any(
        reference and reference not in knowledge.documents
        for item in output.citations
        for reference in (item.normalized_van_ban_id, item.replacement_van_ban_id)
    ):
        raise ValueError("Citation finding references an unknown legal document")


def validate_retrieval(
    request: RetrievalInput,
    output: list[RetrievalEvidence],
    knowledge: KnowledgeSnapshot,
):
    # Reuse the consumer's C05/C06 checks, including duplicate IDs and run ownership.
    consumer = ReasoningRequest(
        **request.context.model_dump(),
        payload=ReasoningPayload(
            hop_dong_id=request.hop_dong_id,
            requirements=request.requirements,
            chunks=request.chunks,
            retrieval=output,
        ),
    )
    validate_request(consumer, knowledge)


def validate_compliance(
    request: ReasoningRequest, output: ComplianceOutput, knowledge: KnowledgeSnapshot
):
    """Check the handoff graph and checklist without recomputing any finding/risk."""
    validate_request(request, knowledge)
    output = ComplianceOutput.model_validate(output.model_dump())
    context = request.model_dump(include=set(Context.model_fields))
    if output.context.model_dump() != context or output.hop_dong_id != request.payload.hop_dong_id:
        raise ValueError("Compliance output context or contract mismatch")
    expected = {
        (requirement.yeu_cau_ca_id, criterion["tieu_chi_id"])
        for requirement in request.payload.requirements
        if requirement.version_status == "RESOLVED" and requirement.requirement_version_id
        for criterion in knowledge.criteria_for(requirement.requirement_version_id)
    }
    if {(row.yeu_cau_ca_id, row.tieu_chi_id) for row in output.criterion_results} != expected:
        raise ValueError("Compliance output lost or added checklist criteria")
    excluded = excluded_requirement_ids(request, knowledge, request.payload.requirements)
    if {row.yeu_cau_ca_id for row in output.requirement_results} != (
        {row.yeu_cau_ca_id for row in request.payload.requirements} - set(excluded)
    ):
        raise ValueError("Compliance output lost or added checklist requirements")
    for result in output.criterion_results:
        if any(
            result.tieu_chi_snapshot_json.get(key) != value
            for key, value in knowledge.criteria[result.tieu_chi_id].items()
        ):
            raise ValueError("Compliance output changed the pinned criterion snapshot")
    validate_membership(
        PipelineRequest(**context, payload=request.payload.model_dump()),
        PipelineResponse(
            **context,
            produced_at=datetime.now(timezone.utc),
            payload=PipelineResult(
                criterion_results=output.criterion_results,
                requirement_results=output.requirement_results,
                risks=output.risks,
                recommendations=output.recommendations,
                excluded_requirements=excluded,
                diagnostics=output.diagnostics,
            ),
        ),
    )


def validate_report(
    request: IntegrationInput,
    report: FinalReport,
    knowledge: KnowledgeSnapshot,
    *,
    risks: list[RiskResult],
    recommendations: list[Recommendation],
):
    content = report.report_json
    if report.ca_id != request.context.ca_id or content.case != request.case:
        raise ValueError("Report belongs to a different case")
    if content.contract_profile != request.document.contract_profile:
        raise ValueError("Report changed the contract profile")
    if (
        content.applicable_legal_scope != request.legal.requirements
        or content.checklist != request.legal.scope
    ):
        raise ValueError("Report changed the applicable-law branch")
    if (
        content.compliance.criterion_results != request.compliance.criterion_results
        or content.compliance.requirement_results != request.compliance.requirement_results
    ):
        raise ValueError("Report changed the compliance findings")
    expected_evidence = [
        item.model_dump(mode="json")
        for result in request.compliance.criterion_results
        for item in result.evidence
    ]
    if content.compliance.evidence != expected_evidence:
        raise ValueError("Report lost or changed compliance evidence")
    expected_basis = [
        {"id": item}
        for item in sorted(
            {
                value
                for result in request.compliance.criterion_results
                for value in result.legal_basis_ids
            }
        )
    ]
    if content.compliance.legal_basis != expected_basis:
        raise ValueError("Report lost or changed legal provenance")
    if (
        content.citation_validation.citations != request.document.citations
        or content.citation_validation.findings != request.legal.citations
    ):
        raise ValueError("Report changed the citation branch")
    for name, risk_type in (
        ("compliance", "COMPLIANCE"),
        ("citation", "CITATION"),
        ("verification", "VERIFICATION"),
    ):
        if any(item.risk_type != risk_type for item in getattr(content.risks, name)):
            raise ValueError("Report mixed risk sections")
    all_risks = risks
    for name, risk_type in (
        ("compliance", "COMPLIANCE"),
        ("citation", "CITATION"),
        ("verification", "VERIFICATION"),
    ):
        if getattr(content.risks, name) != [r for r in all_risks if r.risk_type == risk_type]:
            raise ValueError("Report lost or changed risks from a source branch")
    if content.recommendations != recommendations:
        raise ValueError("Report lost or changed supplied recommendations")
    if report.report_status != "DRAFT" or report.review_status != "PENDING":
        raise ValueError("Development handoff report must remain DRAFT/PENDING")
    if content.audit.get("context") != request.context.model_dump(mode="json"):
        raise ValueError("Report lost the pinned run/trace/knowledge context")
