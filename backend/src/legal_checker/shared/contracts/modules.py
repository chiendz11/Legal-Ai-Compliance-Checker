from datetime import datetime
from typing import Literal

from pydantic import Field

from legal_checker.shared.contracts.aggregation import RequirementResult
from legal_checker.shared.contracts.citation import CitationValidation
from legal_checker.shared.contracts.common import Context, Model
from legal_checker.shared.contracts.reasoning import CriterionResult
from legal_checker.shared.contracts.recommendation import Recommendation
from legal_checker.shared.contracts.risk import RiskResult
from legal_checker.shared.contracts.temporal import ApplicableRequirement


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
