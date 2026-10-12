"""Step 2 / BR-02, BR-19: interface only, no OCR or fabricated extraction."""

from typing import Protocol

from app.contracts.assessment import AssessmentCase
from app.contracts.citation import CitationExtraction
from app.contracts.common import Model
from app.contracts.document_intelligence import Chunk, ContractProfile


class DocumentIntelligenceResult(Model):
    contract_profile: ContractProfile
    chunks: list[Chunk]
    citations: list[CitationExtraction]


class DocumentIntelligenceService(Protocol):
    def extract(self, case: AssessmentCase) -> DocumentIntelligenceResult: ...
