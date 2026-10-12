"""Draft checkpoint for stages 1–7; review and report publishing remain separate."""

from app.contracts.assessment import AssessmentCase
from app.contracts.citation import CitationExtraction
from app.contracts.common import Context, Model
from app.contracts.document_intelligence import Chunk, ContractProfile
from app.contracts.pipeline import PipelineResponse
from app.contracts.retrieval import RetrievalEvidence
from app.contracts.scope import ScopeResolution
from app.contracts.temporal import ApplicableRequirement


class AssessmentDraft(Model):
    context: Context
    case: AssessmentCase
    contract_profile: ContractProfile
    chunks: list[Chunk]
    extracted_citations: list[CitationExtraction]
    scope: list[ScopeResolution]
    requirements: list[ApplicableRequirement]
    retrieval: list[RetrievalEvidence]
    evaluation: PipelineResponse
