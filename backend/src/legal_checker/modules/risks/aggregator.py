from legal_checker.modules.risks.citation_mapper import citation_risks
from legal_checker.modules.risks.compliance_mapper import compliance_risks


def aggregate_risks(request, knowledge, criteria, citations):
    # Separate source IDs remain visible; no mutation of compliance results.
    return compliance_risks(request, knowledge, criteria) + citation_risks(
        request, knowledge, citations
    )
