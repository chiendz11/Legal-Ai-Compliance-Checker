"""Versioned input/output boundaries for the five-person development plan.

These DTOs reuse C01–C11/C13 schemas; they are local integration contracts,
not new HTTP endpoints or new legal findings.
"""

from typing import Literal

from pydantic import Field, model_validator

from legal_checker.shared.contracts.aggregation import RequirementResult
from legal_checker.shared.contracts.assessment import AssessmentCase
from legal_checker.shared.contracts.citation import CitationExtraction, CitationValidation
from legal_checker.shared.contracts.common import Context, Model, RequirementStatus
from legal_checker.shared.contracts.document_intelligence import (
    Chunk,
    ContractProfile,
    DocumentIntelligenceResult,
)
from legal_checker.shared.contracts.pipeline import PipelineResponse
from legal_checker.shared.contracts.reasoning import CriterionResult, ReasoningRequest
from legal_checker.shared.contracts.recommendation import Recommendation
from legal_checker.shared.contracts.report import FinalReport
from legal_checker.shared.contracts.retrieval import RetrievalEvidence
from legal_checker.shared.contracts.risk import RiskResult
from legal_checker.shared.contracts.scope import ScopeResolution
from legal_checker.shared.contracts.temporal import ApplicableRequirement


class DocumentInput(Model):
    context: Context
    case: AssessmentCase


class ScopeInput(Model):
    """Applicable-law branch deliberately has no citations field."""

    context: Context
    contract_profile: ContractProfile


class TemporalInput(ScopeInput):
    scope: list[ScopeResolution]


class CitationInput(ScopeInput):
    citations: list[CitationExtraction]
    chunks: list[Chunk]


class LegalOutput(Model):
    scope: list[ScopeResolution]
    requirements: list[ApplicableRequirement]
    citations: list[CitationValidation]


class RetrievalInput(Model):
    context: Context
    hop_dong_id: str
    requirements: list[ApplicableRequirement] = Field(min_length=1)
    chunks: list[Chunk]


class ComplianceOutput(Model):
    context: Context
    hop_dong_id: str
    criterion_results: list[CriterionResult]
    requirement_results: list[RequirementResult]
    risks: list[RiskResult]
    recommendations: list[Recommendation]

    @model_validator(mode="after")
    def compliance_branch_only(self):
        if any(r.source.citation_finding_id for r in self.risks):
            raise ValueError("Person 4 output cannot contain citation-branch risks")
        return self


class IntegrationInput(Model):
    context: Context
    case: AssessmentCase
    document: DocumentIntelligenceResult
    legal: LegalOutput
    compliance: ComplianceOutput


class HandoffSet(Model):
    """All development checkpoints; one JSON file per field in each scenario."""

    document_input: DocumentInput
    document_output: DocumentIntelligenceResult
    scope_input: ScopeInput
    temporal_input: TemporalInput
    citation_input: CitationInput
    legal_output: LegalOutput
    retrieval_input: RetrievalInput
    retrieval_output: list[RetrievalEvidence]
    compliance_input: ReasoningRequest
    compliance_output: ComplianceOutput
    integration_input: IntegrationInput
    pipeline_output: PipelineResponse
    report_output: FinalReport


class FixtureExpectations(Model):
    requirement_status: RequirementStatus
    criterion_findings: list[Literal["SATISFIED", "MISSING", "VIOLATED", "UNKNOWN"]]
    compliance_risks: int = Field(ge=0)
    citation_risks: int = Field(ge=0)
    verification_risks: int = Field(ge=0)


class FixtureManifest(Model):
    schema_version: Literal["v7.3.2"] = "v7.3.2"
    fixture_version: Literal["parallel-v1"] = "parallel-v1"
    fixture_only: Literal[True] = True
    scenario: str
    notice: Literal["SYNTHETIC_NOT_GOLD_NOT_HUMAN_VERIFIED"]
    knowledge_snapshot_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    files: dict[str, str]
    expected: FixtureExpectations
