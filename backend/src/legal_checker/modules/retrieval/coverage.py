"""Retain the full candidate pool; bound evidence for existential content checks."""

from legal_checker.modules.retrieval.anchors import anchored_chunks
from legal_checker.shared.contracts.retrieval import RetrievalEvidence
from legal_checker.shared.ids import retrieval_id


def add_review_candidates(
    context,
    requirements,
    chunks,
    retrieval,
    candidates,
    knowledge,
    *,
    review_sha256="ACTIVE_EXTRACTION",
    retrieval_version="FULL_DOCUMENT_REVIEW_V2_BOUNDED_CONTENT",
    score_key="full_document_review",
):
    """candidates maps (requirement instance, criterion) to exact active chunk IDs.

    The reviewer locates candidate material; final C07 still checks its legal meaning.
    Foreign IDs fail instead of borrowing a chunk from another run or criterion.
    """
    active = {c.doan_id for c in chunks}
    owners = {r.yeu_cau_ca_id: r for r in requirements}
    updated = list(retrieval)
    for (requirement_id, criterion_id), ids in candidates.items():
        if requirement_id not in owners or not set(ids) <= active:
            raise ValueError("Document review candidate ownership mismatch")
        criterion = knowledge.criteria.get(criterion_id)
        if (
            not criterion
            or criterion["requirement_version_id"] != owners[requirement_id].requirement_version_id
        ):
            raise ValueError("Document review criterion ownership mismatch")
        rows = [
            r
            for r in updated
            if r.yeu_cau_ca_id == requirement_id
            and r.tieu_chi_id == criterion_id
            and r.giai_doan == "FINAL"
        ]
        found = {r.doan_id: r for r in rows}
        for chunk_id in dict.fromkeys(ids):
            if chunk_id in found:
                row = found[chunk_id]
                index = updated.index(row)
                updated[index] = row.model_copy(
                    update={
                        "duoc_chon": True,
                        "scores": {**row.scores, score_key: 1.0},
                    }
                )
            else:
                rank = max((r.thu_hang for r in rows), default=0) + 1
                row = RetrievalEvidence(
                    truy_xuat_id=retrieval_id(requirement_id, criterion_id, rank),
                    yeu_cau_ca_id=requirement_id,
                    tieu_chi_id=criterion_id,
                    doan_id=chunk_id,
                    giai_doan="FINAL",
                    scores={score_key: 1.0},
                    thu_hang=rank,
                    duoc_chon=True,
                    retrieval_version=retrieval_version,
                    query_text=criterion["noi_dung"],
                    index_version=f"{retrieval_version}:{review_sha256}",
                    lan_chay_id=context.run_id,
                )
                updated.append(row)
                rows.append(row)
        # A mandatory-content check asks whether specific content is present. A full
        # pass may locate dozens of mentions; pushing every mention to the semantic
        # request can overflow its context. Keep every located candidate in C06 and
        # in the full-read artifact, but select a bounded representative set. This
        # is NOT absence proof and never applies to prohibited-clause candidates.
        if score_key == "full_document_review" and criterion.get("loai_kiem_tra") in {
            "CONTRACT_CONTENT",
            "NOI_DUNG_BAT_BUOC",
        }:
            anchors = anchored_chunks(criterion["noi_dung"], chunks)
            priority = {key: i for i, key in enumerate(anchors)}
            selected = [
                r
                for r in updated
                if r.yeu_cau_ca_id == requirement_id
                and r.tieu_chi_id == criterion_id
                and r.giai_doan == "FINAL"
                and r.duoc_chon
            ]
            selected.sort(
                key=lambda r: (
                    priority.get(r.doan_id, len(priority)),
                    -r.scores.get("topic_anchor", 0),
                    -r.scores.get("bm25", 0),
                    r.thu_hang,
                    r.doan_id,
                )
            )
            keep = {r.doan_id for r in selected[:6]}
            for row in selected:
                index = updated.index(row)
                updated[index] = row.model_copy(
                    update={
                        "duoc_chon": row.doan_id in keep,
                        "scores": {
                            **row.scores,
                            "bounded_content_selection": float(row.doan_id in keep),
                        },
                    }
                )
    return updated
