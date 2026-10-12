from pydantic import Field

from app.contracts.common import Model


class RetrievalEvidence(Model):
    truy_xuat_id: str
    yeu_cau_ca_id: str
    tieu_chi_id: str
    doan_id: str
    giai_doan: str = "FINAL"
    scores: dict[str, float | None] = Field(default_factory=dict)
    thu_hang: int = Field(ge=1)
    duoc_chon: bool
    query_text: str = ""
    retrieval_version: str
    embedding_model: str | None = None
    index_version: str
    rerank_model: str | None = None
    lan_chay_id: str
