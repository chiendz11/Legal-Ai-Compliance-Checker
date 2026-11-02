"""Compliance-only handoff for steps 5–7; observations come from trusted adapters."""

from legal_checker.modules.compliance.criterion_reasoner import reason
from legal_checker.modules.compliance.requirement_aggregator import aggregate
from legal_checker.modules.legal_knowledge.models import KnowledgeSnapshot
from legal_checker.modules.recommendations.service import generate_recommendations
from legal_checker.modules.risks.service import evaluate_risks
from legal_checker.shared.contracts.common import Context
from legal_checker.shared.contracts.handoffs import ComplianceOutput
from legal_checker.shared.contracts.modules import RecommendationRequest, RiskRequest
from legal_checker.shared.contracts.reasoning import ReasoningRequest
from legal_checker.shared.validation import validate_request


def evaluate_compliance(
    request: ReasoningRequest, knowledge: KnowledgeSnapshot
) -> ComplianceOutput:
    """Compute C07/C08 and only compliance-sourced C10/C11, without I/O."""
    request = ReasoningRequest.model_validate(request.model_dump())
    validate_request(request, knowledge)
    context = Context(**request.model_dump(include=set(Context.model_fields)))
    criteria = reason(request, knowledge)
    requirements = aggregate(request, knowledge, criteria, request.payload.requirements)
    diagnostics = [
        {"module": "C09", "code": "CITATION_BRANCH_NOT_RUN", "reason": "COMPLIANCE_ONLY"}
    ]
    diagnostics.extend(
        {
            "module": "C07",
            "code": "UNRESOLVED_CRITERION",
            "tieu_chi_id": result.tieu_chi_id,
            "yeu_cau_ca_id": result.yeu_cau_ca_id,
            "reason": result.uncertainty_reason,
        }
        for result in criteria
        if result.finding == "UNKNOWN" and not result.excluded
    )
    diagnostics.extend(
        {
            "module": "C08",
            "code": "INSUFFICIENT_REQUIREMENT",
            "yeu_cau_ca_id": result.yeu_cau_ca_id,
            "reason": result.giai_thich,
        }
        for result in requirements
        if result.status == "INSUFFICIENT"
    )
    common = {
        "hop_dong_id": request.payload.hop_dong_id,
        "requirements": request.payload.requirements,
    }
    risks = evaluate_risks(
        RiskRequest(**context.model_dump(), payload={**common, "criterion_results": criteria}),
        knowledge,
        diagnostics=diagnostics,
    )
    recommendations = generate_recommendations(
        RecommendationRequest(**context.model_dump(), payload={**common, "risks": risks}),
        knowledge,
        diagnostics=diagnostics,
    )
    return ComplianceOutput(
        context=context,
        hop_dong_id=request.payload.hop_dong_id,
        criterion_results=criteria,
        requirement_results=requirements,
        risks=risks,
        recommendations=recommendations,
        diagnostics=diagnostics,
    )
