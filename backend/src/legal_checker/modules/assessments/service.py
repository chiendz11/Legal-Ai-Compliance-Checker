"""Execute the implemented assessment workflow and persist an immutable run."""

from legal_checker.modules.assessments.interfaces import AssessmentStore
from legal_checker.modules.legal_knowledge.models import KnowledgeSnapshot
from legal_checker.shared.contracts.pipeline import PipelineRequest, PipelineResponse
from legal_checker.workflows.steps_5_7 import evaluate


def run_steps_5_7(
    request: PipelineRequest, knowledge: KnowledgeSnapshot, store: AssessmentStore
) -> PipelineResponse:
    response = evaluate(request, knowledge)
    return store.save(request, response)
