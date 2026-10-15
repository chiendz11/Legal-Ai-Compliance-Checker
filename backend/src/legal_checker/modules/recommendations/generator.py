"""Step 5–7 module skeleton. No evaluation logic."""

from legal_checker.modules.legal_knowledge.models import KnowledgeSnapshot
from legal_checker.shared.contracts.common import Context
from legal_checker.shared.contracts.recommendation import Recommendation
from legal_checker.shared.contracts.risk import RiskResult
from legal_checker.shared.contracts.temporal import ApplicableRequirement


def recommend(
    request: Context,
    knowledge: KnowledgeSnapshot,
    risks: list[RiskResult],
    requirements: list[ApplicableRequirement],
) -> list[Recommendation]:
    """Skeleton: implementation intentionally absent."""
    raise NotImplementedError("Steps 5–7 are skeletons; implement the module before evaluating.")
