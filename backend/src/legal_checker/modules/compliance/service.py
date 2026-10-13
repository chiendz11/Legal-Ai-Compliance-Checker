"""Person 4 entry point: C07/C08 plus risks and recommendations from compliance only."""

from legal_checker.modules.compliance.criterion_reasoner import reason
from legal_checker.modules.compliance.requirement_aggregator import aggregate
from legal_checker.modules.legal_knowledge.models import KnowledgeSnapshot
from legal_checker.modules.recommendations.generator import recommend
from legal_checker.modules.risks.compliance_mapper import compliance_risks
from legal_checker.shared.contracts.common import Context
from legal_checker.shared.contracts.handoffs import ComplianceOutput
from legal_checker.shared.contracts.reasoning import ReasoningRequest


def evaluate_compliance(
    request: ReasoningRequest, knowledge: KnowledgeSnapshot
) -> ComplianceOutput:
    context = Context(**request.model_dump(exclude={"contract_name", "payload"}))
    criteria = reason(request, knowledge)
    requirements = aggregate(context, knowledge, criteria, request.payload.requirements)
    risks = compliance_risks(context, knowledge, criteria)
    return ComplianceOutput(
        context=context,
        hop_dong_id=request.payload.hop_dong_id,
        criterion_results=criteria,
        requirement_results=requirements,
        risks=risks,
        recommendations=recommend(context, knowledge, risks, request.payload.requirements),
    )
