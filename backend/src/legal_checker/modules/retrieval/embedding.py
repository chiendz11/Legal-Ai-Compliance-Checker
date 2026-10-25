"""Dense (semantic) chunk index. Heavy ML dependencies load lazily on first use.

Install with `pip install -e "./backend[retrieval]"` plus a torch build for the machine.
"""

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from legal_checker.modules.retrieval.retriever import SearchCandidate
from legal_checker.shared.contracts.document_intelligence import Chunk

DEFAULT_EMBEDDING_MODEL = "BAAI/bge-m3"
# E5 models expect role prefixes on both sides.
MODEL_PREFIXES = {"intfloat/multilingual-e5": ("query: ", "passage: ")}


def prefixes_for(model_name: str) -> tuple[str, str]:
    for family, pair in MODEL_PREFIXES.items():
        if model_name.startswith(family):
            return pair
    return "", ""


_MODELS: dict[tuple[str, str], Any] = {}


def load_model(kind: str, name: str, device: str | None, max_length: int):
    """One shared instance per (kind, model).

    LEGAL_CHECKER_ML_DEVICE overrides the device (e.g. "cpu" for one model when two do not
    fit in GPU memory). LEGAL_CHECKER_ML_FP16=1 enables half precision; it is off by default
    because GPUs without tensor cores (GTX 16xx) run fp16 about 4x slower than fp32.
    """
    key = (kind, name)
    if key not in _MODELS:
        import torch
        from sentence_transformers import CrossEncoder, SentenceTransformer

        device = (
            device
            or os.environ.get("LEGAL_CHECKER_ML_DEVICE")
            or ("cuda" if torch.cuda.is_available() else "cpu")
        )
        if kind == "embedding":
            model = SentenceTransformer(name, device=device)
            model.max_seq_length = max_length
        else:
            model = CrossEncoder(name, device=device, max_length=max_length)
        if device.startswith("cuda") and os.environ.get("LEGAL_CHECKER_ML_FP16") == "1":
            (model if kind == "embedding" else model.model).half()
        _MODELS[key] = model
    return _MODELS[key]


class EmbeddingIndex:
    """Cosine search over normalized sentence embeddings, scoped per contract/version.

    `cache_dir` keeps chunk vectors on disk by (model, contract, index version), so
    repeated evaluation runs do not re-encode unchanged contracts.
    """

    def __init__(
        self,
        model_name: str = DEFAULT_EMBEDDING_MODEL,
        device: str | None = None,
        batch_size: int = 16,
        max_length: int = 512,
        cache_dir: Path | None = None,
        query_prefix: str | None = None,
        passage_prefix: str | None = None,
    ):
        self.model_name, self.device = model_name, device
        self.batch_size, self.max_length = batch_size, max_length
        self.cache_dir = cache_dir
        default_query, default_passage = prefixes_for(model_name)
        self.query_prefix = default_query if query_prefix is None else query_prefix
        self.passage_prefix = default_passage if passage_prefix is None else passage_prefix
        self._indexes: dict[tuple[str, str], tuple[list[str], Any]] = {}

    @property
    def model(self):
        return load_model("embedding", self.model_name, self.device, self.max_length)

    def cache_path(self, hop_dong_id: str, chunks: list[Chunk]) -> Path | None:
        """Keyed by model and chunk content only, so every retrieval mode (and an offline
        GPU run such as Colab) shares the same vectors for an unchanged contract."""
        if self.cache_dir is None:
            return None
        model = hashlib.sha256(self.model_name.encode()).hexdigest()[:12]
        digest = hashlib.sha256()
        for chunk in sorted(chunks, key=lambda c: c.doan_id):
            digest.update(f"{chunk.doan_id}\0{self.passage_prefix}{chunk.noi_dung}\0".encode())
        return self.cache_dir / model / f"{hop_dong_id}_{digest.hexdigest()[:16]}.npz"

    def encode(self, texts: list[str]):
        return self.model.encode(
            texts,
            batch_size=self.batch_size,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )

    def index(self, hop_dong_id: str, chunks: list[Chunk], index_version: str) -> None:
        import numpy as np

        foreign = {c.doan_id for c in chunks if c.hop_dong_id != hop_dong_id}
        if foreign:
            raise ValueError(f"Chunks of another contract: {sorted(foreign)[:3]}")
        ids = [c.doan_id for c in chunks]
        path = self.cache_path(hop_dong_id, chunks)
        if path is not None and path.exists():
            stored = np.load(path, allow_pickle=False)
            if json.loads(str(stored["ids"])) == ids:
                self._indexes[(hop_dong_id, index_version)] = (ids, stored["vectors"])
                return
        vectors = self.encode([self.passage_prefix + c.noi_dung for c in chunks]).astype("float32")
        if path is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
            np.savez(path, ids=json.dumps(ids), vectors=vectors)
        self._indexes[(hop_dong_id, index_version)] = (ids, vectors)

    def search(
        self, hop_dong_id: str, query: str, limit: int, index_version: str
    ) -> list[SearchCandidate]:
        state = self._indexes.get((hop_dong_id, index_version))
        if state is None:
            raise KeyError(f"No index {index_version} for contract {hop_dong_id}")
        ids, vectors = state
        query_vector = self.encode([self.query_prefix + query])[0].astype("float32")
        scores = vectors @ query_vector
        order = scores.argsort()[::-1][:limit]
        return [SearchCandidate(ids[i], float(scores[i]), index_version) for i in order]
