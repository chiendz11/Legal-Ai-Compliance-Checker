"""Step 9 / BR-15: build and export a report with separate compliance/citation sections."""

from typing import Protocol

from app.contracts.common import Context
from app.contracts.report import FinalReport, ReportContent


class ReportService(Protocol):
    def build(self, context: Context, content: ReportContent) -> FinalReport: ...
    def export(self, report: FinalReport, format: str) -> str: ...
