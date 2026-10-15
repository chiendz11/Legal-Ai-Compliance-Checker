"""Step 5–7 module skeleton. No evaluation logic."""

from legal_checker.modules.legal_knowledge.models import KnowledgeSnapshot
from legal_checker.shared.contracts.modules import RiskRequest
from legal_checker.shared.contracts.risk import RiskResult


def evaluate_risks(request: RiskRequest, knowledge: KnowledgeSnapshot) -> list[RiskResult]:
    """Skeleton: implementation intentionally absent."""
    raise NotImplementedError("Steps 5–7 are skeletons; implement the module before evaluating.")
