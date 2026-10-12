"""Technical index adapters return candidates; they never return legal findings."""

from dataclasses import dataclass
from typing import Protocol

from app.contracts.document_intelligence import Chunk


@dataclass(frozen=True)
class SearchCandidate:
    doan_id: str
    score: float
    index_version: str


class EvidenceIndex(Protocol):
    def index(self, hop_dong_id: str, chunks: list[Chunk], index_version: str) -> None: ...
    def search(
        self, hop_dong_id: str, query: str, limit: int, index_version: str
    ) -> list[SearchCandidate]: ...


class EvidenceReranker(Protocol):
    def rank(self, query: str, chunks: list[Chunk]) -> list[SearchCandidate]: ...
