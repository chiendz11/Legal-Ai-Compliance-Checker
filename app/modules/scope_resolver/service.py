"""Step 3A / BR-03, BR-04, BR-06: independent from contract-authored citations."""

from typing import Protocol

from app.application.ports.knowledge import KnowledgeSnapshot
from app.contracts.common import Context
from app.contracts.document_intelligence import ContractProfile
from app.contracts.scope import ScopeResolution


class ScopeResolver(Protocol):
    def resolve(
        self, context: Context, profile: ContractProfile, knowledge: KnowledgeSnapshot
    ) -> list[ScopeResolution]: ...
