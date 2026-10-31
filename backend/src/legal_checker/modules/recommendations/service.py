"""Validated deterministic C11 generation; no LLM calls or approval side effects."""

from legal_checker.modules.legal_knowledge.models import KnowledgeSnapshot
from legal_checker.modules.recommendations.generator import recommend
from legal_checker.modules.risks.policy import Diagnostics
from legal_checker.shared.contracts.modules import RecommendationRequest
from legal_checker.shared.contracts.recommendation import Recommendation


def generate_recommendations(
    request: RecommendationRequest, knowledge: KnowledgeSnapshot, *, diagnostics: Diagnostics = None
) -> list[Recommendation]:
    request = RecommendationRequest.model_validate(request.model_dump())
    return recommend(
        request,
        knowledge,
        request.payload.risks,
        request.payload.requirements,
        diagnostics=diagnostics,
    )
