"""Step 5–7 module skeleton. No evaluation logic."""

from legal_checker.modules.legal_knowledge.models import KnowledgeSnapshot
from legal_checker.shared.contracts.common import Context
from legal_checker.shared.contracts.risk import RiskResult
from legal_checker.shared.contracts.temporal import ApplicableRequirement


def validate_risks(
    context: Context,
    risks: list[RiskResult],
    knowledge: KnowledgeSnapshot,
    requirements: list[ApplicableRequirement],
):
    """Skeleton: implementation intentionally absent."""
    raise NotImplementedError("Steps 5–7 are skeletons; implement the module before evaluating.")
