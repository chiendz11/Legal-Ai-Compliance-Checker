import json

from legal_checker.shared.contracts.document_intelligence import Chunk
from legal_checker.shared.contracts.retrieval import RetrievalEvidence
from legal_checker.shared.contracts.temporal import ApplicableRequirement

#runtime.yeu_cau_ap_dung
def map_requirement(row):
    # Chỉ lấy những cột DTO nhận.
    data = {
        name: row[name]
        for name in ApplicableRequirement.model_fields
        if name != "reason"
    }

    # SQL dùng ly_do, DTO dùng reason dạng dictionary.
    raw_reason = row["ly_do"]
    if not raw_reason:
        reason = {}
    else:
        try:
            reason = json.loads(raw_reason)
        except json.JSONDecodeError:
            reason = {"summary": raw_reason}

        if not isinstance(reason, dict):
            raise ValueError("ly_do phải là văn bản hoặc JSON object")

    data["reason"] = reason
    return ApplicableRequirement.model_validate(data)


#runtime.doan_hop_dong
def map_chunk(row):
    return Chunk(
        doan_id=row["doan_id"],
        hop_dong_id=row["hop_dong_id"],
        noi_dung=row["noi_dung"],
        page_start=row["page_start"],
        page_end=row["page_end"],
    )


#runtime.ket_qua_truy_xuat
def map_retrieval(row):
    data = {
        name: row[name]
        for name in RetrievalEvidence.model_fields
        if name != "scores"
    }

    # Ba cột điểm trong DB được gom vào một dictionary.
    data["scores"] = {
        name: float(row[name]) if row[name] is not None else None
        for name in ("bm25_score", "vector_score", "rerank_score")
    }

    return RetrievalEvidence.model_validate(data)