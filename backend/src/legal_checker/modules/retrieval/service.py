"""Step 4 / BR-07, BR-08: candidate selection interface; no legal finding from a miss."""

import hashlib
import re
from collections.abc import Callable, Mapping
from typing import Any, Protocol

from legal_checker.modules.legal_knowledge.models import KnowledgeSnapshot
from legal_checker.modules.retrieval.fact_evidence import (
    DEFAULT_FACT_PATTERNS,
    FactEvidence,
    matching_chunks,
)
from legal_checker.modules.retrieval.indexer import BM25Index, EvidenceIndex, tokenize
from legal_checker.modules.retrieval.reranker import EvidenceReranker
from legal_checker.shared.contracts.common import Context
from legal_checker.shared.contracts.document_intelligence import Chunk
from legal_checker.shared.contracts.retrieval import RetrievalEvidence
from legal_checker.shared.contracts.temporal import ApplicableRequirement
from legal_checker.shared.ids import retrieval_id


class RetrievalService(Protocol):
    def retrieve(
        self,
        context: Context,
        requirements: list[ApplicableRequirement],
        chunks: list[Chunk],
        knowledge: KnowledgeSnapshot,
    ) -> list[RetrievalEvidence]: ...


RETRIEVAL_VERSION = "BM25_SYLLABLE_BIGRAM_V1"
# Reciprocal Rank Fusion constant from Cormack et al. (2009); robust without tuning.
RRF_K = 60


def search_query(criterion: dict[str, Any]) -> str:
    """The criterion text alone. On DEV, adding `bang_chung_can_thiet` (or its 'Hồ sơ liên
    quan' list) lowered Recall@3/@10 against the reference selections."""
    return criterion["noi_dung"]


_STRUCTURAL_PART = re.compile(r"^(hợp đồng|đoạn|mở đầu|khoản\s+\S+|điểm\s+\S+|mục\s+\S+)$", re.I)


def path_context(section_path: str | None) -> str:
    """'Hợp đồng/ĐIỀU 9. BẢO HÀNH NHÀ Ở/Khoản 5' → 'ĐIỀU 9. BẢO HÀNH NHÀ Ở'. Short chunks
    often lack the words of their article title, which carries the topic."""
    parts = [p.strip() for p in (section_path or "").split("/")]
    return " / ".join(p for p in parts if p and not _STRUCTURAL_PART.match(p))


def term_coverage(query: str, text: str) -> float:
    """Share of the query's content syllables present in the text."""
    wanted = {t for t in tokenize(query) if "_" not in t}
    return len(wanted & set(tokenize(text))) / len(wanted) if wanted else 0.0


def chunk_index_version(chunks: list[Chunk], prefix: str = RETRIEVAL_VERSION) -> str:
    digest = hashlib.sha256()
    for chunk in sorted(chunks, key=lambda c: c.doan_id):
        digest.update(f"{chunk.doan_id}\0{chunk.noi_dung}\0".encode())
    return f"{prefix}:{digest.hexdigest()[:16]}"


class HybridRetrievalService:
    """Per-criterion retrieval over the whole contract (not only cited sections).

    Each index returns `candidate_k` hits; several indexes are fused with Reciprocal Rank
    Fusion; an optional cross-encoder reorders the best `rerank_k`. NOT_APPLICABLE
    requirements are skipped; UNKNOWN ones with a candidate version pointer are searched.
    A criterion without hits yields no rows: an empty result is never a MISSING finding.

    Selection (`duoc_chon`): with a reranker, the top `select_k` rows whose relevance
    probability reaches `min_rerank_score`; otherwise the top row plus rows within
    `min_relative_score` of the best primary score. In both cases a row also needs
    `min_term_coverage` of the criterion's content syllables (0 disables the check).

    `section_paths(hop_dong_id) -> {doan_id: section_path}` adds the article/annex title to
    the searched text (the dataset README recommends indexing chunks with their path).

    `fact_evidence(hop_dong_id) -> [FactEvidence]` puts the evidence chunks of extracted C02
    fields first when the criterion names that field (see `fact_patterns`); those rows are
    selected and scored `fact=1`. Criteria naming no field keep the search ranking, so
    missing or incomplete step-2 extraction only removes the boost.
    """

    def __init__(
        self,
        indexes: Mapping[str, EvidenceIndex] | None = None,
        reranker: EvidenceReranker | None = None,
        *,
        embedding_model: str | None = None,
        rerank_model: str | None = None,
        top_k: int = 10,
        candidate_k: int = 30,
        rerank_k: int = 20,
        select_k: int = 2,
        min_relative_score: float = 0.85,
        min_rerank_score: float = 0.5,
        min_term_coverage: float = 0.0,
        section_paths: Callable[[str], Mapping[str, str]] | None = None,
        fact_evidence: Callable[[str], list[FactEvidence]] | None = None,
        fact_patterns: Mapping[str, str] | None = None,
        max_fact_chunks: int = 3,
    ):
        self.indexes = dict(indexes) if indexes else {"bm25": BM25Index()}
        self.min_term_coverage = min_term_coverage
        self.section_paths = section_paths
        self.fact_evidence = fact_evidence
        self.fact_patterns = DEFAULT_FACT_PATTERNS if fact_patterns is None else fact_patterns
        self.max_fact_chunks = max_fact_chunks
        self.reranker = reranker
        self.embedding_model, self.rerank_model = embedding_model, rerank_model
        self.top_k, self.candidate_k, self.rerank_k = top_k, candidate_k, rerank_k
        self.select_k = select_k
        self.min_relative_score, self.min_rerank_score = min_relative_score, min_rerank_score
        parts = [
            "BM25_SYLLABLE_BIGRAM" if name == "bm25" else name.upper() for name in self.indexes
        ]
        if len(self.indexes) > 1:
            parts.append("RRF")
        if reranker is not None:
            parts.append("RERANK")
        if section_paths is not None:
            parts.append("PATH")
        if fact_evidence is not None:
            parts.append("FACT")
        self.retrieval_version = "+".join(parts) + "_V1"

    def ranked(
        self, hop_dong_id: str, query: str, index_version: str, chunk_by_id: dict[str, Chunk]
    ) -> list[tuple[str, dict[str, float | None]]]:
        """(doan_id, scores) in final order, at most top_k."""
        scores: dict[str, dict[str, float | None]] = {}
        fused: dict[str, float] = {}
        for name, index in self.indexes.items():
            for rank, hit in enumerate(
                index.search(hop_dong_id, query, self.candidate_k, index_version), start=1
            ):
                scores.setdefault(hit.doan_id, {})[name] = round(hit.score, 6)
                fused[hit.doan_id] = fused.get(hit.doan_id, 0.0) + 1 / (RRF_K + rank)
        if len(self.indexes) > 1:
            for doan_id, value in fused.items():
                scores[doan_id]["rrf"] = round(value, 6)
            order = sorted(fused, key=lambda d: (-fused[d], d))
        else:
            [name] = self.indexes
            order = sorted(scores, key=lambda d: (-(scores[d][name] or 0.0), d))
        if self.reranker is not None and order:
            head = order[: self.rerank_k]
            reranked = self.reranker.rank(query, [chunk_by_id[d] for d in head], index_version)
            for hit in reranked:
                scores[hit.doan_id]["rerank"] = round(hit.score, 6)
            order = [hit.doan_id for hit in reranked] + order[self.rerank_k :]
        return [(doan_id, scores[doan_id]) for doan_id in order[: self.top_k]]

    def with_facts(
        self,
        query: str,
        rows: list[tuple[str, dict[str, float | None]]],
        facts: list[FactEvidence],
    ) -> list[tuple[str, dict[str, float | None]]]:
        """Matching field evidence first (search scores kept when the chunk was also found)."""
        promoted = matching_chunks(query, facts, self.fact_patterns, self.max_fact_chunks)
        if not promoted:
            return rows
        found = dict(rows)
        head = [(doan_id, {**found.get(doan_id, {}), "fact": 1.0}) for doan_id, _ in promoted]
        ids = {doan_id for doan_id, _ in promoted}
        return (head + [row for row in rows if row[0] not in ids])[: self.top_k]

    def selected(self, rank: int, row: dict[str, float | None], best: dict) -> bool:
        if row.get("fact"):
            return True
        if rank > self.select_k or (row.get("term_coverage") or 0.0) < self.min_term_coverage:
            return False
        if self.reranker is not None:
            return (row.get("rerank") or 0.0) >= self.min_rerank_score
        [name] = self.indexes if len(self.indexes) == 1 else ["rrf"]
        top = best.get(name) or 0.0
        return rank == 1 or (row.get(name) or 0.0) >= self.min_relative_score * top

    def retrieve(
        self,
        context: Context,
        requirements: list[ApplicableRequirement],
        chunks: list[Chunk],
        knowledge: KnowledgeSnapshot,
    ) -> list[RetrievalEvidence]:
        contracts = {c.hop_dong_id for c in chunks}
        if len(contracts) > 1:
            raise ValueError(f"Chunks from several contracts: {sorted(contracts)}")
        if any(r.ca_id != context.ca_id for r in requirements):
            raise ValueError("Requirements of another case")
        if not chunks:
            return []
        hop_dong_id = contracts.pop()
        if self.section_paths is not None:
            paths = self.section_paths(hop_dong_id)
            # Searched text only: rows still point at the original chunk by doan_id.
            chunks = [
                c.model_copy(update={"noi_dung": f"{title}\n{c.noi_dung}"})
                if (title := path_context(paths.get(c.doan_id)))
                else c
                for c in chunks
            ]
        index_version = chunk_index_version(chunks, self.retrieval_version)
        for index in self.indexes.values():
            index.index(hop_dong_id, chunks, index_version)
        chunk_by_id = {c.doan_id: c for c in chunks}
        # Only evidence chunks of this contract can be promoted.
        facts = [
            FactEvidence(f.ten_truong, tuple(d for d in f.doan_ids if d in chunk_by_id))
            for f in (self.fact_evidence(hop_dong_id) if self.fact_evidence else [])
        ]

        evidence = []
        for requirement in requirements:
            if requirement.applicability_status == "NOT_APPLICABLE":
                continue
            for criterion in knowledge.criteria_for(requirement.requirement_version_id):
                query = search_query(criterion)
                rows = self.ranked(hop_dong_id, query, index_version, chunk_by_id)
                rows = self.with_facts(query, rows, facts)
                for doan_id, scores in rows:
                    scores["term_coverage"] = round(
                        term_coverage(query, chunk_by_id[doan_id].noi_dung), 4
                    )
                best = next((s for _, s in rows if not s.get("fact")), {})
                for rank, (doan_id, scores) in enumerate(rows, start=1):
                    evidence.append(
                        RetrievalEvidence(
                            truy_xuat_id=retrieval_id(
                                requirement.yeu_cau_ca_id, criterion["tieu_chi_id"], rank
                            ),
                            yeu_cau_ca_id=requirement.yeu_cau_ca_id,
                            tieu_chi_id=criterion["tieu_chi_id"],
                            doan_id=doan_id,
                            giai_doan="FINAL",
                            scores=scores,
                            thu_hang=rank,
                            duoc_chon=self.selected(rank, scores, best),
                            query_text=criterion["noi_dung"],
                            retrieval_version=self.retrieval_version,
                            embedding_model=self.embedding_model,
                            index_version=index_version,
                            rerank_model=self.rerank_model,
                            lan_chay_id=context.run_id,
                        )
                    )
        return evidence


class LexicalRetrievalService(HybridRetrievalService):
    """BM25 only: no ML dependencies, the default baseline.

    Selection requires half of the criterion's content syllables and, for the second row,
    70% of the best score. On the 70-target DEV relevance set (scripts/eval_retrieval_
    goldset.py) this selected a directly relevant chunk for 43/60 targets with 77% of
    selected rows relevant, the best balance among the coverage/select_k/ratio settings tried.
    Dense/reranked services keep coverage off; they match meaning, not shared words.
    """

    def __init__(self, index: EvidenceIndex | None = None, **options):
        options.setdefault("min_term_coverage", 0.5)
        options.setdefault("min_relative_score", 0.7)
        super().__init__({"bm25": index or BM25Index()}, None, **options)


def semantic_retrieval_service(
    embedding_model: str | None = None,
    rerank_model: str | None = None,
    cache_dir=None,
    rerank: bool = True,
    dense: bool = True,
    **options,
) -> HybridRetrievalService:
    """BM25 (+ dense embeddings fused with RRF) (+ cross-encoder reranking)."""
    from legal_checker.modules.retrieval.embedding import DEFAULT_EMBEDDING_MODEL, EmbeddingIndex
    from legal_checker.modules.retrieval.reranker import DEFAULT_RERANK_MODEL, CrossEncoderReranker

    indexes: dict[str, EvidenceIndex] = {"bm25": BM25Index()}
    embedding_model = (embedding_model or DEFAULT_EMBEDDING_MODEL) if dense else None
    if embedding_model:
        indexes["vector"] = EmbeddingIndex(embedding_model, cache_dir=cache_dir)
    rerank_model = (rerank_model or DEFAULT_RERANK_MODEL) if rerank else None
    return HybridRetrievalService(
        indexes,
        CrossEncoderReranker(rerank_model) if rerank_model else None,
        embedding_model=embedding_model,
        rerank_model=rerank_model,
        **options,
    )
