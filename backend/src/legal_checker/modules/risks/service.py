"""Validate a risk-stage request and aggregate the two independent risk branches."""

from legal_checker.modules.compliance.grounding_validator import validate_criteria
from legal_checker.modules.legal_knowledge.models import KnowledgeSnapshot
from legal_checker.modules.risks.aggregator import aggregate_risks
from legal_checker.shared.contracts.modules import RiskRequest
from legal_checker.shared.contracts.risk import RiskResult
from legal_checker.shared.validation import stage_context


def evaluate_risks(request: RiskRequest, knowledge: KnowledgeSnapshot) -> list[RiskResult]:
    context = stage_context(request, knowledge)
    validate_criteria(request, knowledge)
    return aggregate_risks(
        context, knowledge, request.payload.criterion_results, request.payload.citations
    )
