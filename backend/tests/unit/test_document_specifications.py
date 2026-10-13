import hashlib

from devtools.evaluation_documents import document_specifications
from legal_checker.shared.contracts.handoffs import DocumentInput


def test_pdf_sources_hashes_and_grounded_expected_spans(knowledge, tmp_path):
    cases = document_specifications(knowledge, tmp_path)
    assert len(cases) == 8
    for case in cases:
        source = case["input"].case.source
        raw = (tmp_path / "controlled" / (case["case_id"] + ".pdf")).read_bytes()
        assert raw.startswith(b"%PDF-1.4") and raw.endswith(b"%%EOF\n")
        assert hashlib.sha256(raw).hexdigest() == source.sha256
        assert DocumentInput.model_validate(case["input"].model_dump()) == case["input"]
        result = case["output"]
        chunks = {c.doan_id: c for c in result.chunks}
        for evidence in result.contract_profile.evidence:
            text = chunks[evidence.doan_id].noi_dung
            assert text[evidence.ky_tu_bat_dau : evidence.ky_tu_ket_thuc] == evidence.trich_dan
    by_name = {c["rationale"]: c for c in cases}
    assert (
        by_name["KNOWN_DATE_AND_CITATION"][
            "output"
        ].contract_profile.profile.ngay_giao_ket.isoformat()
        == "2024-09-01"
    )
    for name in ("PLACEHOLDER_DATE", "MISSING_DATE", "CONFLICTING_DATE", "AMBIGUOUS_DATE"):
        assert by_name[name]["output"].contract_profile.profile.ngay_giao_ket is None
    assert len(by_name["KNOWN_DATE_AND_CITATION"]["output"].citations) == 1
    assert by_name["NO_CITATION"]["output"].citations == []
    assert (
        by_name["UNKNOWN_BOOLEAN"]["output"].contract_profile.profile.ben_ban_co_von_nuoc_ngoai
        is None
    )
