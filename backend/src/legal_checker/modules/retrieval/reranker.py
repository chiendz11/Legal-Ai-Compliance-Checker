"""Cross-encoder reranking of retrieved candidates; scores are relevance probabilities."""

import math
from typing import Protocol

from legal_checker.modules.retrieval.embedding import load_model
from legal_checker.modules.retrieval.retriever import SearchCandidate
from legal_checker.shared.contracts.document_intelligence import Chunk

DEFAULT_RERANK_MODEL = "BAAI/bge-reranker-v2-m3"


class EvidenceReranker(Protocol):
    def rank(
        self, query: str, chunks: list[Chunk], index_version: str = ""
    ) -> list[SearchCandidate]: ...


class CrossEncoderReranker:
    def __init__(
        self,
        model_name: str = DEFAULT_RERANK_MODEL,
        device: str | None = None,
        batch_size: int = 16,
        max_length: int = 512,
    ):
        self.model_name, self.device = model_name, device
        self.batch_size, self.max_length = batch_size, max_length

    def rank(
        self, query: str, chunks: list[Chunk], index_version: str = ""
    ) -> list[SearchCandidate]:
        if not chunks:
            return []
        model = load_model("rerank", self.model_name, self.device, self.max_length)
        raw = model.predict(
            [(query, c.noi_dung) for c in chunks],
            batch_size=self.batch_size,
            show_progress_bar=False,
        )
        scores = [float(s) for s in raw]
        # Library versions differ on the default activation; normalize logits to [0, 1].
        if any(s < 0 or s > 1 for s in scores):
            scores = [1 / (1 + math.exp(-s)) for s in scores]
        ranked = sorted(zip(scores, chunks, strict=True), key=lambda p: (-p[0], p[1].doan_id))
        return [SearchCandidate(c.doan_id, s, index_version) for s, c in ranked]
