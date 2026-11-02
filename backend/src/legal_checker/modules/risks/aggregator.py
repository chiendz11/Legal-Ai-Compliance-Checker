"""Combine independently mapped risk branches with stable business identities."""

from legal_checker.modules.legal_knowledge.models import KnowledgeSnapshot
from legal_checker.modules.risks.citation_mapper import citation_risks
from legal_checker.modules.risks.compliance_mapper import compliance_risks
from legal_checker.modules.risks.policy import Diagnostics, deduplicate, diagnostic
from legal_checker.shared.contracts.citation import CitationValidation
from legal_checker.shared.contracts.common import Context
from legal_checker.shared.contracts.reasoning import CriterionResult
from legal_checker.shared.contracts.risk import RiskResult


def aggregate_risks(
    request: Context,
    knowledge: KnowledgeSnapshot,
    criteria: list[CriterionResult],
    citations: list[CitationValidation],
    *,
    diagnostics: Diagnostics = None,
) -> list[RiskResult]:
    if not citations:
        diagnostic(
            diagnostics,
            "C09_INPUT_EMPTY",
            request.ca_id,
            "No C09 findings were supplied; citation verification has not been established",
        )
    return deduplicate(
        compliance_risks(request, knowledge, criteria, diagnostics=diagnostics)
        + citation_risks(request, knowledge, citations, diagnostics=diagnostics)
    )
