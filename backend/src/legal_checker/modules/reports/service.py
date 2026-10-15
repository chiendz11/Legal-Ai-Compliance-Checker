"""Step 9 / BR-15: build and export a report with separate compliance/citation sections."""

from typing import Protocol

from legal_checker.shared.contracts.common import Context
from legal_checker.shared.contracts.report import FinalReport, ReportContent


class ReportService(Protocol):
    def build(self, context: Context, content: ReportContent) -> FinalReport: ...
    def export(self, report: FinalReport, format: str) -> str: ...
