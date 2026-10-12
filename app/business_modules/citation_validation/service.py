"""Step 3B / BR-20–24: interface only; never decides the applicable-law checklist."""

from typing import Protocol

from app.contracts.citation import CitationExtraction, CitationValidation
from app.contracts.common import Context
from app.contracts.document_intelligence import ContractProfile
from app.workflows.interfaces.knowledge import KnowledgeSnapshot


class CitationValidator(Protocol):
    def validate(
        self,
        context: Context,
        profile: ContractProfile,
        citations: list[CitationExtraction],
        knowledge: KnowledgeSnapshot,
    ) -> list[CitationValidation]: ...
