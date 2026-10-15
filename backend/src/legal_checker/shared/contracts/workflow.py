"""Draft checkpoint for stages 1–7; review and report publishing remain separate."""

from legal_checker.shared.contracts.assessment import AssessmentCase
from legal_checker.shared.contracts.citation import CitationExtraction, CitationValidation
from legal_checker.shared.contracts.common import Context, Model
from legal_checker.shared.contracts.document_intelligence import Chunk, ContractProfile
from legal_checker.shared.contracts.pipeline import PipelineResponse
from legal_checker.shared.contracts.retrieval import RetrievalEvidence
from legal_checker.shared.contracts.scope import ScopeResolution
from legal_checker.shared.contracts.temporal import ApplicableRequirement


class AssessmentDraft(Model):
    context: Context
    case: AssessmentCase
    contract_profile: ContractProfile
    chunks: list[Chunk]
    extracted_citations: list[CitationExtraction]
    citation_findings: list[CitationValidation]
    scope: list[ScopeResolution]
    requirements: list[ApplicableRequirement]
    retrieval: list[RetrievalEvidence]
    evaluation: PipelineResponse
