"""Step 2 / BR-02, BR-19: interface only, no OCR or fabricated extraction."""

from typing import Protocol

from app.contracts.assessment import AssessmentCase
from app.contracts.document_intelligence import DocumentIntelligenceResult


class DocumentIntelligenceService(Protocol):
    def extract(self, case: AssessmentCase) -> DocumentIntelligenceResult: ...
