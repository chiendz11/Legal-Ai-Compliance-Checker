"""Index/search for contract chunks. BM25 over Vietnamese syllables and syllable bigrams."""

import math
import re
import unicodedata
from collections import Counter
from typing import Protocol

from legal_checker.modules.retrieval.retriever import SearchCandidate
from legal_checker.shared.contracts.document_intelligence import Chunk


class EvidenceIndex(Protocol):
    def index(self, hop_dong_id: str, chunks: list[Chunk], index_version: str) -> None: ...
    def search(
        self, hop_dong_id: str, query: str, limit: int, index_version: str
    ) -> list[SearchCandidate]: ...


# Function syllables that carry no evidence on their own; bigrams keep phrases like "bên mua".
STOPWORDS = frozenset(
    "và của các cho theo trong với này đã được có là không khi thì những một tại về từ "
    "đến hoặc nếu do bởi để như mà sẽ phải đó ra vào trên dưới lại cũng".split()
)
_WORD = re.compile(r"\w+", re.UNICODE)


def tokenize(text: str) -> list[str]:
    """Lower-cased NFC syllables (minus stopwords) plus adjacent-syllable bigrams.

    Vietnamese words are mostly two syllables, so bigrams approximate word segmentation
    without an external segmenter.
    """
    syllables = _WORD.findall(unicodedata.normalize("NFC", text).lower())
    unigrams = [s for s in syllables if s not in STOPWORDS and not s.isdigit()]
    bigrams = [f"{a}_{b}" for a, b in zip(syllables, syllables[1:], strict=False)]
    return unigrams + bigrams


class BM25Index:
    """In-memory Okapi BM25 per contract and index version; never searches across contracts."""

    def __init__(self, k1: float = 1.2, b: float = 0.75):
        self.k1, self.b = k1, b
        self._indexes: dict[tuple[str, str], dict] = {}

    def index(self, hop_dong_id: str, chunks: list[Chunk], index_version: str) -> None:
        foreign = {c.doan_id for c in chunks if c.hop_dong_id != hop_dong_id}
        if foreign:
            raise ValueError(f"Chunks of another contract: {sorted(foreign)[:3]}")
        docs = [(c.doan_id, Counter(tokenize(c.noi_dung))) for c in chunks]
        frequency = Counter(term for _, terms in docs for term in terms)
        lengths = [sum(terms.values()) for _, terms in docs]
        self._indexes[(hop_dong_id, index_version)] = {
            "docs": docs,
            "lengths": lengths,
            "average": (sum(lengths) / len(lengths)) if lengths else 0.0,
            "idf": {
                term: math.log(1 + (len(docs) - n + 0.5) / (n + 0.5))
                for term, n in frequency.items()
            },
        }

    def search(
        self, hop_dong_id: str, query: str, limit: int, index_version: str
    ) -> list[SearchCandidate]:
        state = self._indexes.get((hop_dong_id, index_version))
        if state is None:
            raise KeyError(f"No index {index_version} for contract {hop_dong_id}")
        terms = set(tokenize(query))
        scored = []
        for (doan_id, counts), length in zip(state["docs"], state["lengths"], strict=True):
            score = 0.0
            for term in terms & counts.keys():
                tf = counts[term]
                norm = tf + self.k1 * (1 - self.b + self.b * length / (state["average"] or 1))
                score += state["idf"][term] * tf * (self.k1 + 1) / norm
            if score > 0:
                scored.append((score, doan_id))
        scored.sort(key=lambda item: (-item[0], item[1]))
        return [SearchCandidate(doan_id, score, index_version) for score, doan_id in scored[:limit]]
