from datetime import datetime
from typing import Literal

from pydantic import Field, model_validator

from app.contracts.aggregation import RequirementResult
from app.contracts.citation import CitationValidation
from app.contracts.common import Context, Model
from app.contracts.document_intelligence import Chunk
from app.contracts.reasoning import CriterionResult, Observation
from app.contracts.recommendation import Recommendation
from app.contracts.retrieval import RetrievalEvidence
from app.contracts.risk import RiskResult
from app.contracts.temporal import ApplicableRequirement


class PipelinePayload(Model):
    hop_dong_id: str
    requirements: list[ApplicableRequirement] = Field(min_length=1)
    chunks: list[Chunk] = Field(default_factory=list)
    retrieval: list[RetrievalEvidence] = Field(default_factory=list)
    observations: list[Observation] = Field(default_factory=list)
    citations: list[CitationValidation] = Field(default_factory=list)

    @model_validator(mode="after")
    def unique_ids(self):
        for attr, key in [
            ("requirements", "yeu_cau_ca_id"),
            ("chunks", "doan_id"),
            ("observations", "tieu_chi_id"),
            ("citations", "finding_id"),
            ("retrieval", "truy_xuat_id"),
        ]:
            rows = getattr(self, attr)
            ids = [getattr(r, key) for r in rows]
            if len(ids) != len(set(ids)):
                raise ValueError(f"Duplicate IDs in {attr}")
        return self


class PipelineRequest(Context):
    contract_name: Literal["Steps57Input"] = "Steps57Input"
    payload: PipelinePayload


class PipelineResult(Model):
    criterion_results: list[CriterionResult]
    requirement_results: list[RequirementResult]
    risks: list[RiskResult]
    recommendations: list[Recommendation]
    excluded_requirements: list[str]


class PipelineResponse(Context):
    contract_name: Literal["Steps57Result"] = "Steps57Result"
    produced_at: datetime
    payload: PipelineResult
