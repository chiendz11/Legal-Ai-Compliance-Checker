"""Bounded parent/sibling and explicit internal-reference context, never a finding.

Only the current extraction's chunks are accepted. A repeated/ambiguous reference
is left unresolved; context promotion is recorded separately from search relevance.
"""

import re
from collections.abc import Mapping

from legal_checker.shared.contracts.document_intelligence import Chunk

POLICY = "BOUNDED_STRUCTURAL_CONTEXT_V1"
_INTERNAL = re.compile(
    r"(?P<label>Điều\s+\d+[a-z]?|Phụ\s+lục\s+(?:\d+|[IVXLC]+))"
    r"\s+(?:(?:đính|kèm)\s+theo\s+|của\s+)?(?:Hợp\s+đồng(?:\s+này)?|dưới\s+đây|nêu\s+trên)",
    re.I,
)


def _label(value: str) -> str:
    return " ".join(value.casefold().split())


def _parent_path(value: str) -> str:
    parts = re.split(r"\s*(?:>|/)\s*", value)
    parts = [p for p in parts if _label(p) not in {"hợp đồng", "đoạn"}]
    while parts and re.match(r"^(?:khoản|điểm)\s", parts[-1], re.I):
        parts.pop()
    return " > ".join(parts)


def context_chunks(
    chunks: list[Chunk],
    paths: Mapping[str, str],
    selected_ids: list[str],
    *,
    max_chunks: int = 3,
    max_chars: int = 6000,
) -> dict[str, dict[str, float]]:
    """Expand a selected child into a small source-backed structural neighborhood.

    Exact parent path and adjacency are required. In particular, Điều 1 in an annex
    is not merged with Điều 1 in the contract body or a later appendix.
    """
    if max_chunks < 0 or max_chars < 0:
        raise ValueError("Context limits must be non-negative")
    if len({c.hop_dong_id for c in chunks}) > 1:
        raise ValueError("Context chunks belong to several contracts")
    if len({c.doan_id for c in chunks}) != len(chunks):
        raise ValueError("Duplicate chunk IDs in structural context")
    by_id = {c.doan_id: c for c in chunks}
    if not set(selected_ids) <= by_id.keys():
        raise ValueError("Selected context anchor is not in the current extraction")
    groups: list[tuple[str, list[str]]] = []
    owner = {}
    for chunk in chunks:
        path = _parent_path(paths.get(chunk.doan_id, ""))
        if not path:
            continue
        if not groups or groups[-1][0] != path:
            groups.append((path, []))
        groups[-1][1].append(chunk.doan_id)
        owner[chunk.doan_id] = len(groups) - 1
    selected = set(selected_ids)
    candidates = []
    for rank, anchor in enumerate(selected_ids, 1):
        if anchor not in owner:
            continue
        path, peers = groups[owner[anchor]]
        index = peers.index(anchor)
        # Parent introduction, then nearest siblings. Never return an unbounded article.
        ids = [peers[0], *peers[max(0, index - 1) : index + 2]]
        candidates.extend((d, "parent_context", rank) for d in dict.fromkeys(ids))
        for match in _INTERNAL.finditer(by_id[anchor].noi_dung):
            label = _label(match["label"])
            targets = [
                ids
                for target, ids in groups
                if ">" not in target
                and "/" not in target
                and re.match(r"^" + re.escape(label) + r"(?:\b|$)", _label(target))
            ]
            if len(targets) == 1:
                candidates.append((targets[0][0], "internal_reference_context", rank))
    result, used = {}, 0
    for doan_id, role, rank in candidates:
        if doan_id in selected or doan_id in result:
            continue
        size = len(by_id[doan_id].noi_dung)
        if len(result) >= max_chunks or used + size > max_chars:
            continue
        result[doan_id] = {role: 1.0, "context_anchor_rank": float(rank)}
        used += size
    return result
