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


def test_explicit_trading_conditions_time_precedes_house_rule_fallback():
    from legal_checker.modules.retrieval.anchors import anchored_chunks

    chunks = [
        CHUNKS[0].model_copy(
            update={
                "doan_id": "HOUSE",
                "noi_dung": "Bản nội quy này có hiệu lực từ ngày ký ban hành.",
            }
        ),
        CHUNKS[0].model_copy(
            update={
                "doan_id": "GTC",
                "noi_dung": "Thời điểm áp dụng điều kiện giao dịch chung: Từ ngày 2017-02-16.",
            }
        ),
    ]
    assert (
        anchored_chunks("Điều kiện giao dịch chung phải xác định rõ thời điểm áp dụng.", chunks)[0]
        == "GTC"
    )


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
    assert warranty[0].retrieval_version == (
        "BM25_SYLLABLE_BIGRAM+VECTOR+RRF+RERANK+SOURCE_ANCHORS_V2"
    )
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
    assert "+PATH+STRUCTURAL_CONTEXT" in rows[0].retrieval_version


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
    assert service.retrieval_version.endswith("+FACT+SOURCE_ANCHORS_V2")
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


def test_explicit_topic_anchors_find_payment_times_and_written_installments():
    from legal_checker.modules.retrieval.anchors import anchored_chunks
    from legal_checker.shared.contracts.document_intelligence import Chunk

    chunks = [
        Chunk(
            doan_id="TIME",
            hop_dong_id="HD",
            noi_dung="Tiến độ thanh toán gồm nhiều đợt.",
            page_start=1,
            page_end=1,
        ),
        Chunk(
            doan_id="TITLE",
            hop_dong_id="HD",
            noi_dung="HỢP ĐỒNG MUA BÁN CĂN HỘ",
            page_start=2,
            page_end=2,
        ),
    ]
    assert "TIME" in anchored_chunks("Phải thỏa thuận thời gian thanh toán", chunks)
    assert "TITLE" in anchored_chunks("Mua trả chậm, trả dần phải lập thành văn bản", chunks)
    assert not anchored_chunks("Số tài khoản bảo trì", chunks)


def test_warranty_remedy_anchor_selects_clause_instead_of_a_price_fact():
    from legal_checker.modules.retrieval.anchors import anchored_chunks

    chunks = [
        Chunk(
            doan_id="W",
            hop_dong_id="HD",
            noi_dung=(
                "Hợp đồng > Chương II > Điều 9. Bảo hành\n"
                "Bên mua có quyền yêu cầu sửa chữa miễn phí."
            ),
            page_start=2,
            page_end=2,
        ),
        Chunk(
            doan_id="P",
            hop_dong_id="HD",
            noi_dung="Giá bán căn hộ: 2000000000 VND",
            page_start=1,
            page_end=1,
        ),
    ]
    assert anchored_chunks(
        "Xét quyền sửa chữa miễn phí, giảm giá, đổi vật hoặc hoàn tiền", chunks
    ) == ["W"]


def test_field_aliases_cover_source_wording_without_promoting_unrelated_fields():
    from legal_checker.modules.retrieval.fact_evidence import FactEvidence, matching_chunks

    samples = [
        ("Hợp đồng phải ghi giá mua bán căn hộ", "gia_ban"),
        ("Hợp đồng phải mô tả đặc điểm của căn hộ giao dịch", "ma_can_ho"),
        ("Xác định thời hạn giao", "ngay_ban_giao_du_kien"),
        ("Hợp đồng phải xác định thời điểm có hiệu lực", "ngay_hieu_luc_hop_dong"),
        ("Hợp đồng phải ghi ngày, tháng, năm ký kết", "ngay_giao_ket"),
    ]
    for query, field in samples:
        assert matching_chunks(query, [FactEvidence(field, ("EXACT",))])[0][0] == "EXACT"
    assert (
        matching_chunks(
            "Không được đơn phương thay đổi hợp đồng", [FactEvidence("gia_ban", ("PRICE",))]
        )
        == []
    )


def test_description_evidence_does_not_let_repeated_code_starve_floor_and_area():
    facts = [
        FactEvidence("ma_can_ho", ("CODE1", "CODE2", "CODE3")),
        FactEvidence("tang_toa", ("FLOOR",)),
        FactEvidence("dien_tich", ("AREA",)),
    ]
    assert {d for d, _ in matching_chunks("Mô tả đặc điểm của căn hộ giao dịch", facts)} == {
        "CODE1",
        "FLOOR",
        "AREA",
    }


def test_warranty_criterion_promotes_its_facts_without_repeating_the_topic():
    key = "TC_PV_DS446_02"
    text = "Xác định thời hạn và mốc bắt đầu khi bên mua có nghĩa vụ nhận vật"
    facts = [FactEvidence("warranty_months", ("C2", "FOREIGN"))]
    assert matching_chunks(text, facts) == []
    assert matching_chunks(text, facts, criterion_id=key)[0] == ("C2", "warranty_months")
    knowledge = SimpleNamespace(criteria_for=lambda _: [{"tieu_chi_id": key, "noi_dung": text}])
    rows = LexicalRetrievalService(fact_evidence=lambda _: facts).retrieve(
        CONTEXT, [requirement()], CHUNKS, knowledge
    )
    assert rows[0].doan_id == "C2" and rows[0].duoc_chon
    assert rows[0].scores["fact"] == 1.0
    assert all(row.doan_id != "FOREIGN" for row in rows)


def test_general_terms_retrieval_reaches_incorporation_and_effective_clause():
    from legal_checker.modules.retrieval.anchors import anchored_chunks

    chunks = [
        CHUNKS[0].model_copy(
            update={
                "doan_id": "RULES",
                "noi_dung": (
                    "Bản nội quy này có hiệu lực kể từ ngày Chủ đầu tư ký ban hành. "
                    "Bản nội quy là một phần không thể tách rời của Hợp đồng."
                ),
            }
        ),
        CHUNKS[0].model_copy(
            update={
                "doan_id": "CONTRACT",
                "noi_dung": (
                    "ĐIỀU 20. NGÀY HIỆU LỰC VÀ SỐ BẢN CỦA HỢP ĐỒNG\n"
                    "Các phụ lục có hiệu lực thi hành đối với hai Bên."
                ),
            }
        ),
        CHUNKS[0],
    ]
    assert anchored_chunks(
        "Điều kiện giao dịch chung phải xác định rõ thời điểm áp dụng", chunks
    ) == ["RULES", "CONTRACT"]
    assert anchored_chunks("Thời hạn bảo hành nhà ở", chunks) == []


def test_delivery_default_retrieval_selects_handover_not_payment_schedule():
    from legal_checker.modules.retrieval.anchors import anchored_chunks

    chunks = [
        CHUNKS[0],
        CHUNKS[1].model_copy(
            update={
                "doan_id": "HANDOVER",
                "noi_dung": "ĐIỀU 8. GIAO NHẬN CĂN HỘ\nBên bán bàn giao căn hộ cho bên mua.",
            }
        ),
    ]
    assert anchored_chunks("Địa điểm giao tài sản khi không thỏa thuận", chunks) == ["HANDOVER"]
    assert anchored_chunks("Phương thức giao tài sản và giao nhiều đợt", chunks) == ["HANDOVER"]
    assert anchored_chunks("Phương thức thanh toán nhiều đợt", chunks) == []


def test_source_heading_is_anchored_even_when_index_text_has_a_parent_path():
    chunks = [
        CHUNKS[0].model_copy(
            update={
                "doan_id": "NOTICE",
                "noi_dung": "ĐIỀU 16. THÔNG BÁO\nPhương thức giao trực tiếp, Fax và thư.",
            }
        ),
        CHUNKS[0].model_copy(
            update={
                "doan_id": "HANDOVER",
                "noi_dung": (
                    "ĐIỀU 8. GIAO NHẬN CĂN HỘ\nBên mua trực tiếp kiểm tra và nhận bàn giao căn hộ."
                ),
            }
        ),
    ]
    knowledge = SimpleNamespace(
        criteria_for=lambda _: [
            {
                "tieu_chi_id": "TC_DELIVERY",
                "noi_dung": "Xác định phương thức giao và các đợt giao đã thỏa thuận",
            }
        ]
    )
    service = LexicalRetrievalService(
        section_paths=lambda _: {
            "HANDOVER": "Hợp đồng/ĐIỀU 8. GIAO NHẬN CĂN HỘ/Khoản 1",
            "NOTICE": "Hợp đồng/ĐIỀU 16. THÔNG BÁO/Khoản 3",
        }
    )
    rows = service.retrieve(CONTEXT, [requirement()], chunks, knowledge)
    handover = next(r for r in rows if r.doan_id == "HANDOVER")
    assert handover.duoc_chon and handover.scores["topic_anchor"] == 1.0
    assert "SOURCE_ANCHORS_V2" in handover.retrieval_version


def test_ownership_and_risk_cues_preserve_both_parts_of_the_clause():
    from legal_checker.modules.retrieval.anchors import anchored_chunks

    chunks = [
        CHUNKS[0].model_copy(
            update={
                "doan_id": "OWNERSHIP",
                "noi_dung": (
                    "Quyền sở hữu căn hộ vẫn thuộc bên bán cho tới khi bên mua thanh toán đủ."
                ),
            }
        ),
        CHUNKS[0].model_copy(
            update={
                "doan_id": "RISK",
                "noi_dung": "Kể từ thời điểm bàn giao, bên mua được sử dụng và chịu rủi ro.",
            }
        ),
    ]
    assert set(anchored_chunks("Xác định bảo lưu sở hữu và phân bổ rủi ro", chunks)) == {
        "OWNERSHIP",
        "RISK",
    }
