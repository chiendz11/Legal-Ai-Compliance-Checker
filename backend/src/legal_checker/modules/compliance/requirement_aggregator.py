"""Step 5–7 module skeleton. No evaluation logic."""

from legal_checker.modules.legal_knowledge.models import KnowledgeSnapshot
from legal_checker.shared.contracts.aggregation import RequirementResult
from legal_checker.shared.contracts.common import Context
from legal_checker.shared.contracts.reasoning import CriterionResult
from legal_checker.shared.contracts.temporal import ApplicableRequirement


def aggregate(
    request: Context,
    knowledge: KnowledgeSnapshot,
    criteria: list[CriterionResult],
    requirements: list[ApplicableRequirement],
) -> list[RequirementResult]:
    """Skeleton: implementation intentionally absent."""
    raise NotImplementedError("Steps 5–7 are skeletons; implement the module before evaluating.")
