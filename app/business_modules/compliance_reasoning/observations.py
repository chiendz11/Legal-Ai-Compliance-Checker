"""Bridge verified facts and provider proposals into the step-5 input contract."""

from typing import Protocol

from app.contracts.common import Context
from app.contracts.document_intelligence import Chunk, ContractProfile
from app.contracts.reasoning import Observation
from app.contracts.retrieval import RetrievalEvidence
from app.contracts.temporal import ApplicableRequirement
from app.workflows.interfaces.knowledge import KnowledgeSnapshot


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
