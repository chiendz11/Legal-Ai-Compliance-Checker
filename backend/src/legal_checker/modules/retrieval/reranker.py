"""Reranking interface only; no model/backend is configured."""

from typing import Protocol

from legal_checker.modules.retrieval.retriever import SearchCandidate
from legal_checker.shared.contracts.document_intelligence import Chunk


class EvidenceReranker(Protocol):
    def rank(self, query: str, chunks: list[Chunk]) -> list[SearchCandidate]: ...
