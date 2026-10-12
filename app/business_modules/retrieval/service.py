"""Step 4 / BR-07, BR-08: candidate selection interface; no legal finding from a miss."""

from typing import Protocol

from app.contracts.common import Context
from app.contracts.document_intelligence import Chunk
from app.contracts.retrieval import RetrievalEvidence
from app.contracts.temporal import ApplicableRequirement
from app.workflows.interfaces.knowledge import KnowledgeSnapshot


class RetrievalService(Protocol):
    def retrieve(
        self,
        context: Context,
        requirements: list[ApplicableRequirement],
        chunks: list[Chunk],
        knowledge: KnowledgeSnapshot,
    ) -> list[RetrievalEvidence]: ...
