"""Step 5–7 module skeleton. No evaluation logic."""

from legal_checker.modules.legal_knowledge.models import KnowledgeSnapshot
from legal_checker.shared.contracts.pipeline import PipelineRequest, PipelineResponse


def evaluate(request: PipelineRequest, knowledge: KnowledgeSnapshot) -> PipelineResponse:
    """Skeleton: implementation intentionally absent."""
    raise NotImplementedError("Steps 5–7 are skeletons; implement the module before evaluating.")
