"""Step 3A / BR-05: resolve versions and transition rules without changing scope ownership."""

from typing import Protocol

from legal_checker.modules.legal_knowledge.models import KnowledgeSnapshot
from legal_checker.shared.contracts.common import Context
from legal_checker.shared.contracts.document_intelligence import ContractProfile
from legal_checker.shared.contracts.scope import ScopeResolution
from legal_checker.shared.contracts.temporal import ApplicableRequirement


class TemporalResolver(Protocol):
    def resolve(
        self,
        context: Context,
        profile: ContractProfile,
        scope: list[ScopeResolution],
        knowledge: KnowledgeSnapshot,
    ) -> list[ApplicableRequirement]: ...
