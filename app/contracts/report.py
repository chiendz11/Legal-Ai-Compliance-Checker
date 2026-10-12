"""C13 starter: report sections preserve compliance/citation branches separately."""

from typing import Any, Literal

from pydantic import Field

from app.contracts.aggregation import RequirementResult
from app.contracts.citation import CitationValidation
from app.contracts.common import Model
from app.contracts.reasoning import CriterionResult
from app.contracts.recommendation import Recommendation
from app.contracts.risk import RiskResult


class ReportCompliance(Model):
    requirement_results: list[RequirementResult]
    criterion_results: list[CriterionResult]
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    legal_basis: list[dict[str, Any]] = Field(default_factory=list)


class ReportCitations(Model):
    citations: list[dict[str, Any]]
    findings: list[CitationValidation]


class ReportRisks(Model):
    compliance: list[RiskResult]
    citation: list[RiskResult]
    verification: list[RiskResult]


class ReportContent(Model):
    case: dict[str, Any]
    contract_profile: dict[str, Any]
    applicable_legal_scope: list[dict[str, Any]]
    checklist: list[dict[str, Any]]
    compliance: ReportCompliance
    citation_validation: ReportCitations
    risks: ReportRisks
    recommendations: list[Recommendation]
    overall_summary: dict[str, Any]
    audit: dict[str, Any]


class FinalReport(Model):
    bao_cao_id: str
    ca_id: str
    phien_ban_bao_cao: str
    report_json: ReportContent
    report_status: Literal["DRAFT", "REVIEW_REQUIRED", "PUBLISHED"]
    review_status: str
    report_uri: str | None = None
