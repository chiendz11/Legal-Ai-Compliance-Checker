"""Step 3A / BR-05: resolve versions and transition rules without changing scope ownership."""

from typing import Protocol

from app.contracts.common import Context
from app.contracts.document_intelligence import ContractProfile
from app.contracts.scope import ScopeResolution
from app.contracts.temporal import ApplicableRequirement
from app.workflows.interfaces.knowledge import KnowledgeSnapshot


class TemporalResolver(Protocol):
    def resolve(
        self,
        context: Context,
        profile: ContractProfile,
        scope: list[ScopeResolution],
        knowledge: KnowledgeSnapshot,
    ) -> list[ApplicableRequirement]: ...
