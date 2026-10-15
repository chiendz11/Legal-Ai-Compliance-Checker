"""C13 typed report sections preserve compliance/citation branches separately."""

from typing import Any, Literal

from pydantic import Field

from legal_checker.shared.contracts.aggregation import RequirementResult
from legal_checker.shared.contracts.assessment import AssessmentCase
from legal_checker.shared.contracts.citation import CitationExtraction, CitationValidation
from legal_checker.shared.contracts.common import Model
from legal_checker.shared.contracts.document_intelligence import ContractProfile
from legal_checker.shared.contracts.reasoning import CriterionResult
from legal_checker.shared.contracts.recommendation import Recommendation
from legal_checker.shared.contracts.risk import RiskResult
from legal_checker.shared.contracts.scope import ScopeResolution
from legal_checker.shared.contracts.temporal import ApplicableRequirement


class ReportCompliance(Model):
    requirement_results: list[RequirementResult]
    criterion_results: list[CriterionResult]
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    legal_basis: list[dict[str, Any]] = Field(default_factory=list)


class ReportCitations(Model):
    citations: list[CitationExtraction]
    findings: list[CitationValidation]


class ReportRisks(Model):
    compliance: list[RiskResult]
    citation: list[RiskResult]
    verification: list[RiskResult]


class ReportContent(Model):
    case: AssessmentCase
    contract_profile: ContractProfile
    applicable_legal_scope: list[ApplicableRequirement]
    checklist: list[ScopeResolution]
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
