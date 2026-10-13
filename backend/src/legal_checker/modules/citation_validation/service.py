"""Step 3B / BR-20–24: interface only; never decides the applicable-law checklist."""

from typing import Protocol

from legal_checker.modules.legal_knowledge.models import KnowledgeSnapshot
from legal_checker.shared.contracts.citation import CitationExtraction, CitationValidation
from legal_checker.shared.contracts.common import Context
from legal_checker.shared.contracts.document_intelligence import ContractProfile


class CitationValidator(Protocol):
    def validate(
        self,
        context: Context,
        profile: ContractProfile,
        citations: list[CitationExtraction],
        knowledge: KnowledgeSnapshot,
    ) -> list[CitationValidation]: ...
