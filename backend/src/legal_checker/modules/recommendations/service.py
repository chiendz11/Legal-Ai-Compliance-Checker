"""Validate a recommendation-stage request and select pending-review templates."""

from legal_checker.modules.legal_knowledge.models import KnowledgeSnapshot
from legal_checker.modules.recommendations.generator import recommend
from legal_checker.modules.recommendations.validator import validate_risks
from legal_checker.shared.contracts.modules import RecommendationRequest
from legal_checker.shared.contracts.recommendation import Recommendation
from legal_checker.shared.validation import stage_context


def generate_recommendations(
    request: RecommendationRequest, knowledge: KnowledgeSnapshot
) -> list[Recommendation]:
    context = stage_context(request, knowledge)
    validate_risks(context, request.payload.risks, knowledge, request.payload.requirements)
    return recommend(context, knowledge, request.payload.risks, request.payload.requirements)
