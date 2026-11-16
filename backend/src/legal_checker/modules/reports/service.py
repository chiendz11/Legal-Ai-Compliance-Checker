"""Step 9 / BR-15: build and export a report with separate compliance/citation sections."""

from collections import Counter
from copy import deepcopy
from typing import Protocol

from legal_checker.modules.legal_knowledge.models import KnowledgeSnapshot
from legal_checker.modules.reports.assessment_status import (
    criterion_display_status,
    requirement_display_status,
)
from legal_checker.modules.reports.builder import build_draft_report
from legal_checker.shared.contracts.common import Context
from legal_checker.shared.contracts.report import FinalReport, ReportContent
from legal_checker.shared.contracts.review import REVIEW_POLICY
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
    dispositions = Counter(
        r.requirement_snapshot_json.get("assessment_disposition", "LEGACY")
        for r in output.requirement_results
    )
    summary = {
        **content.overall_summary,
        "assessment_disposition_counts": dict(dispositions),
        "requirement_display_statuses": [
            requirement_display_status(r) for r in output.requirement_results
        ],
        "criterion_display_statuses": [
            criterion_display_status(r) for r in output.criterion_results
        ],
        "non_triggered_requirement_count": dispositions["NOT_TRIGGERED"],
        "outside_review_scope_requirement_count": dispositions["OUTSIDE_REVIEW_SCOPE"],
        "unresolved_requirement_count": dispositions["NEEDS_EVIDENCE"]
        + dispositions["LEGAL_SCOPE_UNRESOLVED"],
    }
    audit = {
        **content.audit,
        "module_source": module_source,
        "knowledge_review_status": getattr(knowledge, "review_status", "DEV_UNVERIFIED"),
        "integration_policy": "INTEGRATION_V1",
        "review_policy": REVIEW_POLICY,
        "review_mode": draft.case.assessment_context.review_mode,
        "document_set_complete_declared": draft.case.assessment_context.document_set_complete,
        "review_scope_policy": "DRAFT_CONTENT_REVIEW_V1"
        if draft.case.assessment_context.review_mode == "DRAFT_REVIEW"
        else None,
        "diagnostics": deepcopy(output.diagnostics),
        "evidence_mode": "SYNTHETIC"
        if any(row.get("code") == "SYNTHETIC_SCENARIO_USED" for row in output.diagnostics)
        else "SOURCE_ONLY",
        "assessment_profile": {
            "id": "ACTUAL_CHECKLIST_V1",
            "requirement_ids": sorted({r.requirement_id for r in draft.requirements}),
            "count": len(draft.requirements),
        },
    }
    return report.model_copy(
        update={
            "report_json": content.model_copy(update={"audit": audit, "overall_summary": summary})
        }
    )
