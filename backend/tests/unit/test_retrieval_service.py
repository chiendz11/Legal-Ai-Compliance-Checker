from datetime import date
from types import SimpleNamespace

import pytest
from legal_checker.modules.retrieval.fact_evidence import FactEvidence, matching_chunks
from legal_checker.modules.retrieval.indexer import BM25Index, tokenize
from legal_checker.modules.retrieval.retriever import SearchCandidate
from legal_checker.modules.retrieval.service import (
    HybridRetrievalService,
    LexicalRetrievalService,
    path_context,
)
from legal_checker.shared.contracts.common import Context
from legal_checker.shared.contracts.document_intelligence import Chunk
from legal_checker.shared.contracts.temporal import ApplicableRequirement

CONTEXT = Context(
    ca_id="CA_T1",
    phien_ban_id="V_TEST",
    rule_version="R_TEST",
    legal_knowledge_version="K_TEST",
    knowledge_snapshot_sha256="0" * 64,
    run_id="CA_T1_B_DEV_001",
    trace_id="CA_T1_TRACE",
)
CHUNKS = [
    Chunk(
        doan_id="C1",
        hop_dong_id="HD_T1",
        noi_dung="Giá bán căn hộ là 2.000.000.000 VND",
        page_start=1,
        page_end=1,
    ),
    Chunk(
        doan_id="C2",
        hop_dong_id="HD_T1",
        noi_dung="Thời hạn bảo hành căn hộ là 60 tháng kể từ ngày nghiệm thu",
        page_start=2,
        page_end=2,
    ),
    Chunk(
        doan_id="C3",
        hop_dong_id="HD_T1",
        noi_dung="Kinh phí bảo trì bằng 2% giá bán",
        page_start=3,
        page_end=3,
    ),
    Chunk(
        doan_id="C4",
        hop_dong_id="HD_T1",
        noi_dung="Các bên ký tên dưới đây",
        page_start=4,
        page_end=4,
    ),
]
CRITERIA = {
    "PV_1": [
        {"tieu_chi_id": "TC_WARRANTY", "noi_dung": "Thời hạn bảo hành tối thiểu 60 tháng"},
        {"tieu_chi_id": "TC_NOTHING", "noi_dung": "Thỏa thuận trọng tài quốc tế"},
    ]
}
KNOWLEDGE = SimpleNamespace(criteria_for=lambda version_id: CRITERIA.get(version_id, []))


def requirement(status="CONFIRMED", version_id="PV_1", family="FAM_X"):
    confirmed = status == "CONFIRMED"
    return ApplicableRequirement(
        yeu_cau_ca_id=f"CA_T1_{family}",
        ca_id="CA_T1",
        requirement_id=family,
        requirement_version_id=version_id,
        scope_status="MATCH" if status != "NOT_APPLICABLE" else "NO_MATCH",
        version_status="RESOLVED" if confirmed else "UNKNOWN",
        applicability_status=status,
        moc_ap_dung=date(2020, 1, 1) if confirmed else None,
        phien_ban_id="V_TEST",
    )


def test_tokenize_keeps_vietnamese_syllables_and_bigrams():
    tokens = tokenize("Thời hạn Bảo hành")
    assert {"thời", "hạn", "bảo", "hành", "bảo_hành", "thời_hạn"} <= set(tokens)


def test_best_chunk_ranks_first_and_ids_follow_convention():
    rows = LexicalRetrievalService().retrieve(CONTEXT, [requirement()], CHUNKS, KNOWLEDGE)
    warranty = [r for r in rows if r.tieu_chi_id == "TC_WARRANTY"]
    assert warranty[0].doan_id == "C2"
    assert warranty[0].thu_hang == 1 and warranty[0].duoc_chon
    assert warranty[0].truy_xuat_id == "CA_T1_FAM_X/TC_WARRANTY/R1"
    assert warranty[0].query_text == "Thời hạn bảo hành tối thiểu 60 tháng"
    assert warranty[0].lan_chay_id == CONTEXT.run_id
    assert [r.thu_hang for r in warranty] == list(range(1, len(warranty) + 1))


def test_criterion_without_hits_yields_no_rows_not_a_finding():
    rows = LexicalRetrievalService().retrieve(CONTEXT, [requirement()], CHUNKS, KNOWLEDGE)
    assert not [r for r in rows if r.tieu_chi_id == "TC_NOTHING"]


def test_not_applicable_is_skipped_and_unknown_with_pointer_is_searched():
    service = LexicalRetrievalService()
    assert service.retrieve(CONTEXT, [requirement("NOT_APPLICABLE")], CHUNKS, KNOWLEDGE) == []
    unknown = service.retrieve(CONTEXT, [requirement("UNKNOWN")], CHUNKS, KNOWLEDGE)
    assert {r.tieu_chi_id for r in unknown} == {"TC_WARRANTY"}


def test_chunks_of_another_contract_are_rejected():
    foreign = Chunk(
        doan_id="X1", hop_dong_id="HD_OTHER", noi_dung="bảo hành", page_start=1, page_end=1
    )
    with pytest.raises(ValueError, match="several contracts"):
        LexicalRetrievalService().retrieve(CONTEXT, [requirement()], [*CHUNKS, foreign], KNOWLEDGE)
    with pytest.raises(ValueError, match="another contract"):
        BM25Index().index("HD_T1", [foreign], "v")


class FixedIndex:
    """Stand-in dense index returning a fixed ranking."""

    def __init__(self, order):
        self.order = order

    def index(self, hop_dong_id, chunks, index_version):
        pass

    def search(self, hop_dong_id, query, limit, index_version):
        return [
            SearchCandidate(d, 1.0 - i / 10, index_version)
            for i, d in enumerate(self.order[:limit])
        ]


class FixedReranker:
    def __init__(self, scores):
        self.scores = scores

    def rank(self, query, chunks, index_version=""):
        ranked = sorted(chunks, key=lambda c: -self.scores.get(c.doan_id, 0.0))
        return [SearchCandidate(c.doan_id, self.scores.get(c.doan_id, 0.0), "") for c in ranked]


def test_hybrid_fuses_indexes_and_reranker_decides_order_and_selection():
    service = HybridRetrievalService(
        {"bm25": BM25Index(), "vector": FixedIndex(["C3", "C2"])},
        FixedReranker({"C2": 0.9, "C3": 0.7, "C1": 0.1}),
        embedding_model="test-embedding",
        rerank_model="test-reranker",
    )
    rows = service.retrieve(CONTEXT, [requirement()], CHUNKS, KNOWLEDGE)
    warranty = [r for r in rows if r.tieu_chi_id == "TC_WARRANTY"]
    assert [r.doan_id for r in warranty[:2]] == ["C2", "C3"]
    assert {"bm25", "vector", "rrf", "rerank"} <= warranty[0].scores.keys()
    assert [r.duoc_chon for r in warranty[:2]] == [True, True]
    assert warranty[0].embedding_model == "test-embedding"
    assert warranty[0].rerank_model == "test-reranker"
    assert warranty[0].retrieval_version == "BM25_SYLLABLE_BIGRAM+VECTOR+RRF+RERANK_V1"
    # The dense index alone surfaces C3 for a criterion BM25 cannot match.
    nothing = [r for r in rows if r.tieu_chi_id == "TC_NOTHING"]
    assert nothing and not any(r.duoc_chon for r in nothing if r.scores["rerank"] < 0.5)


def test_path_context_keeps_titles_and_drops_structural_parts():
    path = "Hợp đồng/ĐIỀU 9. BẢO HÀNH NHÀ Ở/Khoản 5/Điểm a"
    assert path_context(path) == "ĐIỀU 9. BẢO HÀNH NHÀ Ở"
    assert path_context("Hợp đồng/Đoạn") == ""
    assert path_context(None) == ""


def test_article_title_lets_a_chunk_without_the_keyword_be_found():
    chunks = [
        Chunk(
            doan_id="D1",
            hop_dong_id="HD_T1",
            noi_dung="Khung, cột, dầm, sàn trong 60 tháng",
            page_start=1,
            page_end=1,
        ),
        Chunk(
            doan_id="D2",
            hop_dong_id="HD_T1",
            noi_dung="Các bên ký tên dưới đây",
            page_start=2,
            page_end=2,
        ),
    ]
    paths = {"D1": "Hợp đồng/ĐIỀU 9. BẢO HÀNH NHÀ Ở/Khoản 2"}
    criteria = {"PV_1": [{"tieu_chi_id": "TC_W", "noi_dung": "Nội dung bảo hành nhà ở"}]}
    knowledge = SimpleNamespace(criteria_for=lambda v: criteria.get(v, []))
    without = LexicalRetrievalService().retrieve(CONTEXT, [requirement()], chunks, knowledge)
    assert not without
    rows = LexicalRetrievalService(section_paths=lambda hop_dong_id: paths).retrieve(
        CONTEXT, [requirement()], chunks, knowledge
    )
    assert rows[0].doan_id == "D1" and rows[0].duoc_chon
    assert rows[0].retrieval_version.endswith("+PATH_V1")


def test_low_term_coverage_is_ranked_but_not_selected():
    rows = LexicalRetrievalService(min_term_coverage=0.9).retrieve(
        CONTEXT, [requirement()], CHUNKS, KNOWLEDGE
    )
    warranty = [r for r in rows if r.tieu_chi_id == "TC_WARRANTY"]
    assert warranty and warranty[0].scores["term_coverage"] < 0.9
    assert not any(r.duoc_chon for r in warranty)


def test_field_evidence_is_promoted_only_for_criteria_naming_the_field():
    facts = [
        FactEvidence("gia_tri_hop_dong", ("C1",)),
        FactEvidence("warranty_months", ("C2",)),
        FactEvidence("dien_thoai_ben_mua", ("X_OTHER_CONTRACT",)),
    ]
    criteria = {
        "PV_1": [
            {
                "tieu_chi_id": "TC_CAP",
                "noi_dung": "Lần thanh toán đầu không quá 30% giá trị hợp đồng",
            },
            {"tieu_chi_id": "TC_BAN", "noi_dung": "Không được đơn phương thay đổi hợp đồng"},
            {"tieu_chi_id": "TC_PHONE", "noi_dung": "Có số điện thoại các bên"},
        ]
    }
    knowledge = SimpleNamespace(criteria_for=lambda v: criteria.get(v, []))
    service = LexicalRetrievalService(fact_evidence=lambda hop_dong_id: facts)
    rows = service.retrieve(CONTEXT, [requirement()], CHUNKS, knowledge)
    cap = [r for r in rows if r.tieu_chi_id == "TC_CAP"]
    assert cap[0].doan_id == "C1" and cap[0].scores["fact"] == 1.0 and cap[0].duoc_chon
    assert service.retrieval_version.endswith("+FACT_V1")
    # "hợp đồng" alone must not pull the contract-value line into a prohibition criterion.
    assert not any(r.scores.get("fact") for r in rows if r.tieu_chi_id == "TC_BAN")
    # Evidence of another contract is never promoted.
    assert not any(r.doan_id == "X_OTHER_CONTRACT" for r in rows)


def test_fact_patterns_reject_known_false_friends():
    facts = [
        FactEvidence("phuong_thuc_thanh_toan", ("P",)),
        FactEvidence("gia_tri_hop_dong", ("G",)),
        FactEvidence("tang_toa", ("T",)),
        FactEvidence("dien_tich_thong_thuy", ("D",)),
    ]
    assert matching_chunks("Phương thức giải quyết tranh chấp.", facts) == []
    assert matching_chunks("Bên bán tự tăng giá bán căn hộ", facts) == [("G", "gia_tri_hop_dong")]
    assert matching_chunks("ký hiệu/số căn, tầng, tòa/khối", facts) == [("T", "tang_toa")]
    assert matching_chunks("tối thiểu diện tích căn hộ", facts) == [("D", "dien_tich_thong_thuy")]


def test_index_is_scoped_by_contract_and_version():
    index = BM25Index()
    index.index("HD_T1", CHUNKS, "v1")
    with pytest.raises(KeyError):
        index.search("HD_T1", "bảo hành", 5, "v2")
