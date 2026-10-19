from pathlib import Path

import pytest
from legal_checker.modules.reports import exporter
from legal_checker.shared.contracts.report import FinalReport


def minimal_report(status="DRAFT", module_source="REFERENCE_REPLAY"):
    return FinalReport.model_validate(
        {
            "bao_cao_id": "REPORT_TEST",
            "ca_id": "CA_TEST",
            "phien_ban_bao_cao": "draft-v1",
            "report_status": status,
            "review_status": "PENDING",
            "report_json": {
                "case": {
                    "ca_id": "CA_TEST",
                    "hop_dong_id": "HD_TEST",
                    "source": {
                        "tep_id": "TEP",
                        "object_uri": "fixture://c.pdf",
                        "mime_type": "application/pdf",
                        "sha256": "a" * 64,
                    },
                    "assessment_context": {"ngay_danh_gia": "2026-10-12"},
                    "deployment": {
                        "phien_ban_id": "D",
                        "rule_version": "R",
                        "legal_knowledge_version": "L",
                    },
                    "tenant_id": "T",
                    "created_by": "U",
                },
                "contract_profile": {"hop_dong_id": "HD_TEST", "profile": {}},
                "applicable_legal_scope": [],
                "checklist": [],
                "compliance": {"requirement_results": [], "criterion_results": []},
                "citation_validation": {"citations": [], "findings": []},
                "risks": {"compliance": [], "citation": [], "verification": []},
                "recommendations": [],
                "overall_summary": {},
                "audit": {"context": {"run_id": "RUN_TEST"}, "module_source": module_source},
            },
        }
    )


def paragraphs(document):
    return [block[1] for block in document.blocks if block[0] == "paragraph"]


def test_unpublished_and_replayed_reports_are_marked_on_every_export():
    text = " ".join(paragraphs(exporter.report_document(minimal_report())))
    assert "DRAFT / review PENDING" in text
    assert "REFERENCE_REPLAY" in text
    clean = exporter.report_document(minimal_report("PUBLISHED", "MODULES"))
    assert not any("DRAFT" in p or "REFERENCE" in p for p in paragraphs(clean))


def test_unknown_values_stay_visible():
    rows = next(b for b in exporter.report_document(minimal_report()).blocks if b[0] == "table")[2]
    assert ["Ngày đánh giá", "2026-10-12"] in rows
    profile = [b for b in exporter.report_document(minimal_report()).blocks if b[0] == "table"][2]
    assert all(value == "chưa có" for _, value in profile[2])


def test_docx_export_is_a_word_document():
    assert exporter.export_report(minimal_report(), "docx")[:2] == b"PK"


def test_pdf_export_needs_a_unicode_font(monkeypatch, tmp_path):
    monkeypatch.setattr(exporter, "FONT_CANDIDATES", ())
    monkeypatch.delenv("REPORT_PDF_FONT", raising=False)
    with pytest.raises(exporter.ExportUnavailable, match="REPORT_PDF_FONT"):
        exporter.export_report(minimal_report(), "pdf")


def test_pdf_export_renders_vietnamese_when_a_font_exists():
    if not any(Path(regular).is_file() for regular, _ in exporter.FONT_CANDIDATES):
        pytest.skip("No system Unicode font")
    assert exporter.export_report(minimal_report(), "pdf")[:5] == b"%PDF-"


def test_word_symbol_font_glyphs_are_mapped_one_to_one():
    # Word bullet U+F0B7, check U+F0FC, line separator U+2028, unknown private-use U+F064.
    raw = "".join(map(chr, (0xF0B7, 0x20, 0x43, 0x0103, 0x6E, 0xF0FC, 0x2028, 0xF064)))
    cleaned = exporter._clean(raw)
    assert cleaned == "• Căn✓\n?"
    assert len(cleaned) == len(raw)
    assert exporter._clean([raw, 1]) == [cleaned, 1]


def test_exported_docx_has_no_undrawable_glyphs():
    report = minimal_report()
    profile = report.report_json.contract_profile.profile.model_copy(
        update={"doi_tuong": chr(0xF0B7) + " NHA_O"}
    )
    report.report_json.contract_profile.profile = profile
    content = exporter.export_report(report, "docx")
    from io import BytesIO

    from docx import Document

    text = "\n".join(
        cell.text
        for table in Document(BytesIO(content)).tables
        for row in table.rows
        for cell in row.cells
    )
    assert "• NHA_O" in text and chr(0xF0B7) not in text


def test_unknown_format_is_rejected():
    with pytest.raises(ValueError):
        exporter.export_report(minimal_report(), "html")
