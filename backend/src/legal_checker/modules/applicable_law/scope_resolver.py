"""Step 3A / BR-03, BR-04, BR-06: independent from contract-authored citations."""

from typing import Protocol

from legal_checker.modules.legal_knowledge.models import KnowledgeSnapshot
from legal_checker.shared.contracts.common import Context
from legal_checker.shared.contracts.document_intelligence import ContractProfile
from legal_checker.shared.contracts.scope import ScopeResolution


class ScopeResolver(Protocol):
    def resolve(
        self, context: Context, profile: ContractProfile, knowledge: KnowledgeSnapshot
    ) -> list[ScopeResolution]: ...
