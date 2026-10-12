"""Full-assessment orchestration contract. Steps 1–4, 8–9 are not implemented yet.

Applicable-law (C02 → C04 → C05 → C06 → C07/C08) and citation (C03 → C09)
branches stay independent until C10 risk aggregation; review/report consume pinned outputs.
"""

from typing import Protocol

from app.contracts.assessment import AssessmentCase
from app.contracts.report import FinalReport


class AssessmentPipeline(Protocol):
    def run(self, case: AssessmentCase) -> FinalReport: ...
