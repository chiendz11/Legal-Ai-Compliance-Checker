"""C10 boundary validation and independent compliance/citation mapping."""

from legal_checker.modules.legal_knowledge.models import KnowledgeSnapshot
from legal_checker.modules.risks.aggregator import aggregate_risks
from legal_checker.modules.risks.policy import Diagnostics
from legal_checker.shared.contracts.modules import RiskRequest
from legal_checker.shared.contracts.risk import RiskResult
from legal_checker.shared.validation import validate_context, validate_requirements


def evaluate_risks(
    request: RiskRequest, knowledge: KnowledgeSnapshot, *, diagnostics: Diagnostics = None
) -> list[RiskResult]:
    request = RiskRequest.model_validate(request.model_dump())
    validate_context(request, knowledge)
    validate_requirements(request, request.payload.requirements, knowledge)
    owners = {row.yeu_cau_ca_id: row for row in request.payload.requirements}
    for finding in request.payload.criterion_results:
        requirement = owners.get(finding.yeu_cau_ca_id)
        criterion = knowledge.criteria.get(finding.tieu_chi_id)
        if (
            not requirement
            or not criterion
            or criterion.get("requirement_version_id") != requirement.requirement_version_id
        ):
            raise ValueError("C07 risk input requirement/version ownership mismatch")
        if finding.finding != "UNKNOWN" and not requirement.confirmed:
            raise ValueError("Known C07 finding requires confirmed requirement")
    return aggregate_risks(
        request,
        knowledge,
        request.payload.criterion_results,
        request.payload.citations,
        diagnostics=diagnostics,
    )
