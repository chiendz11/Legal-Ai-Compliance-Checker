from typing import Literal

from pydantic import Field

from legal_checker.shared.contracts.citation import CitationValidation
from legal_checker.shared.contracts.common import Context, Model
from legal_checker.shared.contracts.reasoning import CriterionResult
from legal_checker.shared.contracts.risk import RiskResult
from legal_checker.shared.contracts.temporal import ApplicableRequirement


class AggregationPayload(Model):
    hop_dong_id: str
    requirements: list[ApplicableRequirement] = Field(min_length=1)
    criterion_results: list[CriterionResult]


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
