"""Step 4 / BR-07, BR-08: candidate selection interface; no legal finding from a miss."""

from typing import Protocol

from legal_checker.modules.legal_knowledge.models import KnowledgeSnapshot
from legal_checker.shared.contracts.common import Context
from legal_checker.shared.contracts.document_intelligence import Chunk
from legal_checker.shared.contracts.retrieval import RetrievalEvidence
from legal_checker.shared.contracts.temporal import ApplicableRequirement


class RetrievalService(Protocol):
    def retrieve(
        self,
        context: Context,
        requirements: list[ApplicableRequirement],
        chunks: list[Chunk],
        knowledge: KnowledgeSnapshot,
    ) -> list[RetrievalEvidence]: ...
