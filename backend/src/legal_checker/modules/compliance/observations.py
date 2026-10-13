"""Bridge verified facts and provider proposals into the step-5 input contract."""

from typing import Protocol

from legal_checker.modules.legal_knowledge.models import KnowledgeSnapshot
from legal_checker.shared.contracts.common import Context
from legal_checker.shared.contracts.document_intelligence import Chunk, ContractProfile
from legal_checker.shared.contracts.reasoning import Observation
from legal_checker.shared.contracts.retrieval import RetrievalEvidence
from legal_checker.shared.contracts.temporal import ApplicableRequirement


class ObservationProvider(Protocol):
    def observe(
        self,
        context: Context,
        profile: ContractProfile,
        requirements: list[ApplicableRequirement],
        retrieval: list[RetrievalEvidence],
        chunks: list[Chunk],
        knowledge: KnowledgeSnapshot,
    ) -> list[Observation]: ...
