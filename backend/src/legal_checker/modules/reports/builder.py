"""Build an unreviewed C13 draft from validated handoffs; no publishing or persistence."""

from legal_checker.modules.legal_knowledge.models import KnowledgeSnapshot
from legal_checker.shared.contracts.handoffs import IntegrationInput
from legal_checker.shared.contracts.recommendation import Recommendation
from legal_checker.shared.contracts.report import (
    FinalReport,
    ReportCitations,
    ReportCompliance,
    ReportContent,
    ReportRisks,
)
from legal_checker.shared.contracts.risk import RiskResult
from legal_checker.shared.ids import stable_id
from legal_checker.shared.validation import validate_citations, validate_context


def build_draft_report(
    request: IntegrationInput,
    knowledge: KnowledgeSnapshot,
    *,
    risks: list[RiskResult],
    recommendations: list[Recommendation],
) -> FinalReport:
    """Assemble a draft from supplied C10/C11; never infer risks or actions."""
    validate_context(request.context, knowledge)
    validate_citations(request.context, request.legal.citations)
    if (
        request.case.ca_id != request.context.ca_id
        or request.compliance.context != request.context
        or request.document.contract_profile.hop_dong_id != request.case.hop_dong_id
        or request.compliance.hop_dong_id != request.case.hop_dong_id
    ):
        raise ValueError("Report handoffs belong to different contexts/contracts")
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
