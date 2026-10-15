"""Step 5–7 module skeleton. No evaluation logic."""

from legal_checker.modules.legal_knowledge.models import KnowledgeSnapshot
from legal_checker.shared.contracts.handoffs import ComplianceOutput
from legal_checker.shared.contracts.reasoning import ReasoningRequest


def evaluate_compliance(
    request: ReasoningRequest, knowledge: KnowledgeSnapshot
) -> ComplianceOutput:
    """Skeleton: implementation intentionally absent."""
    raise NotImplementedError("Steps 5–7 are skeletons; implement the module before evaluating.")
