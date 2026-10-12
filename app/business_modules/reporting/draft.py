"""Build an unreviewed C13 draft from validated handoffs; no publishing or persistence."""

from app.business_modules.recommendation.service import recommend
from app.business_modules.risk.service import citation_risks
from app.contracts.handoffs import IntegrationInput
from app.contracts.report import (
    FinalReport,
    ReportCitations,
    ReportCompliance,
    ReportContent,
    ReportRisks,
)
from app.shared.ids import stable_id
from app.shared.validation import validate_citations, validate_context
from app.workflows.interfaces.knowledge import KnowledgeSnapshot


def build_draft_report(request: IntegrationInput, knowledge: KnowledgeSnapshot) -> FinalReport:
    validate_context(request.context, knowledge)
    validate_citations(request.context, request.legal.citations)
    if (
        request.case.ca_id != request.context.ca_id
        or request.compliance.context != request.context
        or request.document.contract_profile.hop_dong_id != request.case.hop_dong_id
        or request.compliance.hop_dong_id != request.case.hop_dong_id
    ):
        raise ValueError("Report handoffs belong to different contexts/contracts")
    extra_risks = citation_risks(request.context, knowledge, request.legal.citations)
    risks = request.compliance.risks + extra_risks
    recommendations = request.compliance.recommendations + recommend(
        request.context, knowledge, extra_risks, request.legal.requirements
    )
    content = ReportContent(
        case=request.case,
        contract_profile=request.document.contract_profile,
        applicable_legal_scope=request.legal.requirements,
        checklist=request.legal.scope,
        compliance=ReportCompliance(
            requirement_results=request.compliance.requirement_results,
            criterion_results=request.compliance.criterion_results,
            evidence=[
                item.model_dump(mode="json")
                for result in request.compliance.criterion_results
                for item in result.evidence
            ],
            legal_basis=[
                {"id": item}
                for item in sorted(
                    {
                        value
                        for result in request.compliance.criterion_results
                        for value in result.legal_basis_ids
                    }
                )
            ],
        ),
        citation_validation=ReportCitations(
            citations=request.document.citations, findings=request.legal.citations
        ),
        risks=ReportRisks(
            compliance=[item for item in risks if item.risk_type == "COMPLIANCE"],
            citation=[item for item in risks if item.risk_type == "CITATION"],
            verification=[item for item in risks if item.risk_type == "VERIFICATION"],
        ),
        recommendations=recommendations,
        overall_summary={
            "requirement_statuses": [r.status for r in request.compliance.requirement_results],
            "criterion_count": len(request.compliance.criterion_results),
            "review_required": True,
        },
        audit={"context": request.context.model_dump(mode="json")},
    )
    return FinalReport(
        bao_cao_id=stable_id(request.context, "REPORT", request.case.hop_dong_id),
        ca_id=request.context.ca_id,
        phien_ban_bao_cao="draft-v1",
        report_json=content,
        report_status="DRAFT",
        review_status="PENDING",
    )
