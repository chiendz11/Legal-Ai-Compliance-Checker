"""Step 9 / BR-15: build and export a report with separate compliance/citation sections."""

from typing import Protocol

from legal_checker.modules.legal_knowledge.models import KnowledgeSnapshot
from legal_checker.modules.reports.builder import build_draft_report
from legal_checker.shared.contracts.common import Context
from legal_checker.shared.contracts.report import FinalReport, ReportContent
from legal_checker.shared.contracts.workflow import AssessmentDraft
from legal_checker.workflows.handoffs import report_input_from_draft, validate_report


class ReportService(Protocol):
    def build(self, context: Context, content: ReportContent) -> FinalReport: ...
    def export(self, report: FinalReport, format: str) -> str: ...


def build_run_report(
    draft: AssessmentDraft, knowledge: KnowledgeSnapshot, module_source: str
) -> FinalReport:
    """Draft C13 from one completed run's pinned outputs; both branches kept, nothing re-run.

    C10/C11 come merged from the run (compliance and citation sources together), so the
    builder neither drops the citation branch nor adds its risks twice. audit.module_source
    records which step implementations produced the run (e.g. REFERENCE_REPLAY).
    """
    request = report_input_from_draft(draft)
    output = draft.evaluation.payload
    report = build_draft_report(
        request, knowledge, risks=output.risks, recommendations=output.recommendations
    )
    validate_report(
        request, report, knowledge, risks=output.risks, recommendations=output.recommendations
    )
    content = report.report_json
    audit = {**content.audit, "module_source": module_source}
    return report.model_copy(update={"report_json": content.model_copy(update={"audit": audit})})
