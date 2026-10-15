"""Step 5–7 module skeleton. No evaluation logic."""

from legal_checker.modules.legal_knowledge.models import KnowledgeSnapshot
from legal_checker.shared.contracts.reasoning import CriterionResult, ReasoningRequest


def reason(request: ReasoningRequest, knowledge: KnowledgeSnapshot) -> list[CriterionResult]:
    """Skeleton: implementation intentionally absent."""
    raise NotImplementedError("Steps 5–7 are skeletons; implement the module before evaluating.")
