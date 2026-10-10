from datetime import datetime
from typing import Literal

from pydantic import Field

from app.contracts.models import (
    ApplicableRequirement,
    CitationValidation,
    Context,
    CriterionResult,
    Model,
    Recommendation,
    RequirementResult,
    RiskResult,
)


class AggregationPayload(Model):
    hop_dong_id: str
    requirements: list[ApplicableRequirement] = Field(min_length=1)
    criterion_results: list[CriterionResult]


class AggregationRequest(Context):
    contract_name: Literal["RequirementAggregationInput"] = "RequirementAggregationInput"
    payload: AggregationPayload


class RiskPayload(AggregationPayload):
    citations: list[CitationValidation] = Field(default_factory=list)


class RiskRequest(Context):
    contract_name: Literal["RiskInput"] = "RiskInput"
    payload: RiskPayload


class RecommendationPayload(Model):
    hop_dong_id: str
    requirements: list[ApplicableRequirement] = Field(min_length=1)
    risks: list[RiskResult]


class RecommendationRequest(Context):
    contract_name: Literal["RecommendationInput"] = "RecommendationInput"
    payload: RecommendationPayload


class ModuleResponse(Context):
    contract_name: Literal[
        "CriterionReasoning", "RequirementAggregation", "RiskResult", "Recommendation"
    ]
    produced_at: datetime
    payload: list[CriterionResult | RequirementResult | RiskResult | Recommendation]
