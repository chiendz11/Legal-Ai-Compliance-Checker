"""Compatibility exports. New code imports the owning contract module."""

from app.contracts.aggregation import RequirementResult as RequirementResult
from app.contracts.citation import CitationValidation as CitationValidation
from app.contracts.common import Context as Context
from app.contracts.common import Finding as Finding
from app.contracts.common import Model as Model
from app.contracts.common import RequirementStatus as RequirementStatus
from app.contracts.common import RiskType as RiskType
from app.contracts.common import Severity as Severity
from app.contracts.document_intelligence import Chunk as Chunk
from app.contracts.document_intelligence import Evidence as Evidence
from app.contracts.document_intelligence import ExternalEvidence as ExternalEvidence
from app.contracts.pipeline import PipelinePayload as PipelinePayload
from app.contracts.pipeline import PipelineRequest as PipelineRequest
from app.contracts.pipeline import PipelineResponse as PipelineResponse
from app.contracts.pipeline import PipelineResult as PipelineResult
from app.contracts.reasoning import CriterionResult as CriterionResult
from app.contracts.reasoning import Gates as Gates
from app.contracts.reasoning import Observation as Observation
from app.contracts.recommendation import Recommendation as Recommendation
from app.contracts.retrieval import RetrievalEvidence as RetrievalEvidence
from app.contracts.risk import RiskResult as RiskResult
from app.contracts.risk import RiskSource as RiskSource
from app.contracts.temporal import ApplicableRequirement as ApplicableRequirement
