"""C13 report versions and export artifacts remain tied to an assessment case."""

from typing import Protocol

from app.contracts.report import FinalReport


class ReportStore(Protocol):
    def save_version(self, report: FinalReport) -> FinalReport: ...
    def get(self, ca_id: str, report_version: str) -> FinalReport | None: ...


class ReportExporter(Protocol):
    def export(self, report: FinalReport, format: str) -> str: ...
