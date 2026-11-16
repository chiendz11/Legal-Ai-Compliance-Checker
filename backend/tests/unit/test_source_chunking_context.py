"""Source/evidence invariants, not expected legal labels for a demo PDF."""

import hashlib
from dataclasses import replace

import pytest
from legal_checker.modules.documents.chunker import ChunkRecord, chunk_document, join_pages
from legal_checker.modules.documents.citation_extractor import extract_citations
from legal_checker.modules.documents.parser import DocumentPage, DocumentText
from legal_checker.modules.retrieval.structural_context import context_chunks
from legal_checker.shared.contracts.document_intelligence import Chunk


def doc(*pages, unreadable=()):
    return DocumentText(
        "a" * 64,
        tuple(
            DocumentPage(i, text, "TEXT", i not in unreadable) for i, text in enumerate(pages, 1)
        ),
    )


def slices(text, cuts):
    return [
        ChunkRecord(
            str(i),
            "HD",
            i,
            1,
            1,
            None,
            text[a:b],
            hashlib.sha256(text[a:b].encode()).hexdigest(),
            a,
            b,
        )
        for i, (a, b) in enumerate(zip(cuts, cuts[1:], strict=False), 1)
    ]


def test_citation_identity_and_occurrences_are_invariant_to_three_chunk_boundaries():
    text = "Theo Khoản 2 Điều 18 của Luật Nhà ở số 65/2014/QH13. Theo Luật Nhà ở 2014."
    full = extract_citations(slices(text, [0, len(text)]), version="a", document=doc(text))
    split = extract_citations(
        slices(text, [0, 29, 39, 45, len(text)]), version="b", document=doc(text)
    )
    assert [(r.raw_text, r.so_hieu, r.ten_van_ban, r.dieu, r.khoan) for r in split] == [
        (r.raw_text, r.so_hieu, r.ten_van_ban, r.dieu, r.khoan) for r in full
    ]
    assert len(split[0].mentions) > 2
    source = {c.doan_id: c.noi_dung for c in slices(text, [0, 29, 39, 45, len(text)])}
    assert all(source[m.doan_id][m.start : m.end] == m.quote for r in split for m in r.mentions)


def test_source_extraction_rejects_forged_offsets_or_text():
    text = "Theo Luật Nhà ở số 65/2014/QH13."
    [c] = slices(text, [0, len(text)])
    with pytest.raises(ValueError, match="offsets"):
        extract_citations([replace(c, global_end=2)], version="a")
    with pytest.raises(ValueError, match="differs"):
        extract_citations([c], version="a", document=doc(text.replace("65/", "66/")))


def test_unreadable_page_does_not_join_fragments_into_an_identified_citation():
    document = doc(
        "Theo Luật Kinh doanh", "[scan not read]", " Bất động sản số 66/2014/QH13.", unreadable=(2,)
    )
    chunks = chunk_document(document, hop_dong_id="HD", version="a")
    records = extract_citations(chunks, version="a", document=document)
    assert not any(r.so_hieu and r.ten_van_ban for r in records)


def test_citation_is_atomic_and_every_source_character_is_preserved():
    law = "Luật Kinh doanh Bất động sản số 66/2014/QH13"
    text = "ĐIỀU 1. CĂN CỨ\n" + "Một câu hoàn chỉnh. " * 7 + law + ".\n" + "Nội dung khác. " * 12
    document = doc(text)
    chunks = chunk_document(document, hop_dong_id="HD", version="a", max_chars=180)
    assert any(law in c.noi_dung for c in chunks)
    assert "".join(c.noi_dung for c in chunks) == join_pages(document)[0]
    assert all(text[c.global_start : c.global_end] == c.noi_dung for c in chunks)


def test_exception_is_kept_with_its_obligation_when_it_fits_hard_budget():
    obligation = "Bên bán chịu trách nhiệm sửa chữa phần hư hỏng. "
    exception = "Trừ trường hợp hư hỏng do người mua cố ý gây ra. "
    text = "Giới thiệu hợp đồng. " * 8 + obligation + exception + "Điều khoản tiếp theo. " * 10
    chunks = chunk_document(doc(text), hop_dong_id="HD", version="a", max_chars=210)
    assert any(obligation + exception in c.noi_dung for c in chunks)


def test_numbered_subclauses_and_decimals_keep_original_text():
    text = "ĐIỀU 2. GIÁ\n" + "".join(
        f"2.{i}. Diện tích sử dụng 62.4 m², giá 1.996.800.000 đồng. "
        + "Nội dung của khoản. " * 5
        + "\n"
        for i in range(1, 7)
    )
    chunks = chunk_document(doc(text), hop_dong_id="HD", version="a", max_chars=190)
    assert len(chunks) > 1 and "".join(c.noi_dung for c in chunks) == text
    assert all("1.996.800.000" in c.noi_dung for c in chunks)


def c(key, text):
    return Chunk(doan_id=key, hop_dong_id="HD", noi_dung=text, page_start=1, page_end=1)


def test_parent_context_preserves_intro_and_does_not_merge_annex_with_body_article():
    chunks = [
        c("A", "ĐIỀU 2. Có các trường hợp sau đây:"),
        c("B", "a) Trường hợp thứ nhất."),
        c("C", "b) Ngoại lệ đối với nghĩa vụ trên."),
        c("D", "Nội quy có Điều 2 riêng."),
    ]
    paths = {"A": "ĐIỀU 2", "B": "ĐIỀU 2", "C": "ĐIỀU 2", "D": "PHỤ LỤC 1 > ĐIỀU 2"}
    expanded = context_chunks(chunks, paths, ["B"])
    assert set(expanded) == {"A", "C"}
    assert all(v["parent_context"] == 1 for v in expanded.values())


def test_internal_reference_expands_exact_unique_contract_target_only():
    chunks = [
        c("A", "Theo Điều 8 của Hợp đồng này."),
        c("B", "Điều 8. Giao nhận."),
        c("X", "Điều 8 trong phụ lục."),
    ]
    paths = {"A": "ĐIỀU 2", "B": "ĐIỀU 8", "X": "PHỤ LỤC 1 > ĐIỀU 8"}
    assert context_chunks(chunks, paths, ["A"])["B"]["internal_reference_context"] == 1
    chunks[0].noi_dung = "Theo Điều 8 của Luật Nhà ở."
    assert context_chunks(chunks, paths, ["A"]) == {}
    chunks[0].noi_dung = "Theo Điều 8 của Hợp đồng này."
    chunks.append(c("B2", "Một Điều 8 khác."))
    paths["B2"] = "ĐIỀU 8"
    # Nonadjacent duplicate targets must remain ambiguous.
    assert "B" not in context_chunks(chunks, paths, ["A"])


def test_context_caps_and_contract_isolation():
    chunks = [c(str(i), "nội dung " * 10) for i in range(5)]
    paths = {x.doan_id: "ĐIỀU 1" for x in chunks}
    assert len(context_chunks(chunks, paths, ["2"], max_chunks=1)) == 1
    assert context_chunks(chunks, paths, ["2"], max_chars=10) == {}
    chunks[0].hop_dong_id = "FOREIGN"
    with pytest.raises(ValueError, match="several contracts"):
        context_chunks(chunks, paths, ["2"])


def test_legacy_clause_paths_expand_within_article_not_another_appendix():
    chunks = [
        c("A", "ĐIỀU 9. BẢO HÀNH"),
        c("B", "Khoản 2. Thời hạn."),
        c("C", "Khoản 3. Ngoại lệ."),
        c("D", "Một Điều 9 khác."),
    ]
    paths = {
        "A": "Hợp đồng/ĐIỀU 9",
        "B": "Hợp đồng/ĐIỀU 9/Khoản 2",
        "C": "Hợp đồng/ĐIỀU 9/Khoản 3",
        "D": "Phụ lục 1/ĐIỀU 9/Khoản 2",
    }
    assert set(context_chunks(chunks, paths, ["B"])) == {"A", "C"}


def test_repeated_running_banner_is_not_part_of_a_law_name():
    banner = "DỰ THẢO HỢP ĐỒNG - PHIÊN BẢN THỬ NGHIỆM"
    text = banner + "\nNội dung.\n" + banner + "\nNội dung.\nĐiều 57 Luật\n" + banner
    records = extract_citations(slices(text, [0, len(text)]), version="a", document=doc(text))
    assert len(records) == 1
    assert records[0].raw_text == "Điều 57 Luật"
    assert records[0].ten_van_ban is None and records[0].status == "AMBIGUOUS"


def test_generic_applicable_law_terms_are_not_statute_titles():
    text = "Luật Áp Dụng phù hợp; Luật Việt Nam; pháp\nLuật Việt Nam. Theo Luật Nhà ở."
    records = extract_citations(slices(text, [0, len(text)]), version="a", document=doc(text))
    assert [r.ten_van_ban for r in records] == ["Luật Nhà ở"]


def test_view_workbook_escapes_xml_controls_without_turning_source_text_into_formula(tmp_path):
    from devtools.document_methods_eval import _xlsx
    from openpyxl import load_workbook

    path = tmp_path / "inspection.xlsx"
    row = dict(
        contract_id="HD",
        source_id="SOURCE",
        pdf_path="/local/source.pdf",
        split="DEV",
        group="BASELINE",
        pages=1,
        sha256="a" * 64,
        extraction_version="trial",
        before={},
        after={},
        C03_count=0,
        C02_fact_count=0,
        fact_changes=[],
        lost_citation_keys=[],
        source_preserved=True,
        citation_quotes_valid=True,
        unreadable_pages=[],
        citations=[],
        chunks=[
            dict(
                doan_id="A",
                hop_dong_id="HD",
                section_path=None,
                page_start=1,
                page_end=1,
                noi_dung="=text from source\x01",
                sha256_text="b" * 64,
                thu_tu=1,
                phien_ban_chunk="trial",
                global_start=0,
                global_end=19,
                split_reason="TEST",
            )
        ],
    )
    _xlsx(path, [row], {"checked": 1})
    book = load_workbook(path, read_only=True)
    cell = list(book["doan_hop_dong_trial"].rows)[1][5]
    assert cell.data_type == "s" and cell.value == "=text from source\\u0001"
    assert row["chunks"][0]["noi_dung"].endswith("\x01")
    book.close()
