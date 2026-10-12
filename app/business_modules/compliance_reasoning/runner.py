"""Person 4 entry point: C07/C08 plus risks and recommendations from compliance only."""

from app.business_modules.compliance_reasoning.service import reason
from app.business_modules.recommendation.service import recommend
from app.business_modules.risk.service import compliance_risks
from app.business_modules.rule_aggregation.service import aggregate
from app.contracts.common import Context
from app.contracts.handoffs import ComplianceOutput
from app.contracts.reasoning import ReasoningRequest
from app.workflows.interfaces.knowledge import KnowledgeSnapshot


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
