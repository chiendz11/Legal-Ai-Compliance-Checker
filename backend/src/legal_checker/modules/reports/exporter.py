"""Export capability only; PDF/DOCX export is not implemented yet."""

from typing import Protocol

from legal_checker.shared.contracts.report import FinalReport


class ReportExporter(Protocol):
    def export(self, report: FinalReport, format: str) -> str: ...
