"""Step 5–7 module skeleton. No evaluation logic."""

from legal_checker.modules.legal_knowledge.models import KnowledgeSnapshot
from legal_checker.shared.contracts.modules import RecommendationRequest
from legal_checker.shared.contracts.recommendation import Recommendation


def generate_recommendations(
    request: RecommendationRequest, knowledge: KnowledgeSnapshot
) -> list[Recommendation]:
    """Skeleton: implementation intentionally absent."""
    raise NotImplementedError("Steps 5–7 are skeletons; implement the module before evaluating.")
