"""Step 1 / BR-01: interface only. Implement upload validation and a pinned C01 case."""

from typing import Protocol

from legal_checker.shared.contracts.assessment import AssessmentCase


class IntakeService(Protocol):
    def register(self, case: AssessmentCase) -> AssessmentCase: ...
