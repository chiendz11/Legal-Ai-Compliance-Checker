"""Index/search interface only; no full-text or vector backend is configured."""

from typing import Protocol

from legal_checker.modules.retrieval.retriever import SearchCandidate
from legal_checker.shared.contracts.document_intelligence import Chunk


class EvidenceIndex(Protocol):
    def index(self, hop_dong_id: str, chunks: list[Chunk], index_version: str) -> None: ...
    def search(
        self, hop_dong_id: str, query: str, limit: int, index_version: str
    ) -> list[SearchCandidate]: ...
