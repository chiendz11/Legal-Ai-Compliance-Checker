"""Presentation never changes an immutable finding, its hash, or review policy."""

from copy import deepcopy

import pytest
from legal_checker.modules.recommendations.rendering import bind_draft_slots, observed_quote
from legal_checker.modules.reports.exporter import export_report, report_document
from legal_checker.modules.reports.presentation import build_presentation, coverage_view
from legal_checker.modules.reports.repository import report_digest
from legal_checker.shared.contracts.aggregation import RequirementResult
from legal_checker.shared.contracts.reasoning import CriterionResult
from test_report_export import minimal_report


def requirement(disposition="ASSESSED", status="COMPLIANT", **snapshot):
    return RequirementResult(
        tuan_thu_id="R",
        yeu_cau_ca_id="AR",
        status=status,
        so_tieu_chi_ap_dung=1,
        so_tieu_chi_da_danh_gia=1,
        so_unknown=0,
        rule_version="RULE",
        giai_thich="Stored machine explanation",
        coverage_complete=False,
        requirement_snapshot_json={"assessment_disposition": disposition, **snapshot},
    )


def test_partial_fulltext_coverage_is_not_missing_criterion_coverage():
    row = requirement(finding_coverage_complete=True, evidence_coverage_complete=False)
    before = row.model_dump()
    view = coverage_view(row)
    assert view.finding_complete is True
    assert view.full_text_complete is False
    assert "Đã có đủ kết quả tiêu chí" in view.explanation
    assert "không đồng nghĩa thiếu kết quả" in view.explanation
    assert row.model_dump() == before
    assert coverage_view(requirement()).finding_complete is None


@pytest.mark.parametrize(
    "disposition,code",
    [
        ("OUTSIDE_REVIEW_SCOPE", "REQUIREMENT_OUTSIDE_REVIEW_SCOPE"),
        ("NOT_TRIGGERED", "REQUIREMENT_NOT_TRIGGERED"),
        ("NEEDS_EVIDENCE", "INSUFFICIENT_REQUIREMENT"),
    ],
)
def test_legacy_audit_keeps_raw_code_but_displays_correct_disposition(disposition, code):
    report = minimal_report()
    content = report.report_json
    content.compliance.requirement_results = [requirement(disposition, "INSUFFICIENT")]
    content.audit["diagnostics"] = [{"code": "INSUFFICIENT_REQUIREMENT", "yeu_cau_ca_id": "AR"}]
    content.compliance.criterion_results = [
        CriterionResult(
            ket_qua_id="C",
            ca_id="CA_TEST",
            yeu_cau_ca_id="AR",
            tieu_chi_id="CR",
            finding="UNKNOWN",
            giai_thich="Outside draft scope",
            gates={},
            uncertainty_reason="Out of scope",
            tieu_chi_snapshot_json={},
            model_version="NO_LLM",
            prompt_version="NONE",
            lan_chay_id="RUN",
            mandatory=True,
            excluded=True,
            exclusion_reason="REVIEW_SCOPE_EXCLUDED: execution evidence",
        )
    ]
    before, sha = deepcopy(report.model_dump(mode="json")), report_digest(report)
    view = build_presentation(content)
    assert view.diagnostics[0]["code"] == code
    assert view.diagnostics[0]["raw_code"] == "INSUFFICIENT_REQUIREMENT"
    assert view.criteria["C"].display_status == "OUTSIDE_REVIEW_SCOPE"
    assert view.criteria["C"].raw_status == "UNKNOWN"
    if disposition != "NEEDS_EVIDENCE":
        assert view.requirements["R"].display_status == disposition
    assert report_digest(report) == sha
    assert report.model_dump(mode="json") == before
    assert b'"presentation"' not in export_report(report, "json")
    document = str(report_document(report).blocks)
    assert view.requirements["R"].display_status in document
    assert content.audit["diagnostics"][0]["code"] == "INSUFFICIENT_REQUIREMENT"


def test_legacy_slots_bind_only_observed_values_without_guessing_identity():
    source = {
        "source_snapshot_json": {
            "source_occurrence": {
                "observed_title": "Luật bảo vệ người tiêu dùng",
                "observed_number": None,
            }
        }
    }
    quote = observed_quote(source)
    text, missing = bind_draft_slots(
        "[DỰ THẢO] Xác minh [nguyên văn]; bổ sung [thông tin/bằng chứng cụ thể còn thiếu].",
        {"quote": quote, "uncertainty_reason": "Thiếu năm/số hiệu"},
    )
    assert not missing
    assert "Luật bảo vệ người tiêu dùng" in text
    assert "Thiếu năm/số hiệu" in text
    assert "2010" not in text and "2023" not in text
    _, missing = bind_draft_slots("Bổ sung [tên đối tượng chưa biết]", {})
    assert missing == ["tên đối tượng chưa biết"]
    assert bind_draft_slots("[Dự thảo cần xác minh đúng nguồn]; [Điều 3]; [1]", {})[1] == []


def test_micro_nlg_separates_business_explanation_from_audit_trace():
    from legal_checker.shared.contracts.document_intelligence import Evidence
    from legal_checker.shared.contracts.reasoning import Gates

    report = minimal_report()
    content = report.report_json
    content.compliance.criterion_results = [
        CriterionResult(
            ket_qua_id="C_NUMERIC",
            ca_id="CA_TEST",
            yeu_cau_ca_id="AR",
            tieu_chi_id="TC_PV_HYC053_01",
            finding="VIOLATED",
            giai_thich=(
                "Backend đối chiếu bằng Decimal theo rule đã pin: không đạt. "
                'Rule={"scope": "APARTMENT_NEW_BUILD_NHAO_2014", "start": '
                '"COMPLETION_AND_ACCEPTANCE_INTO_USE", "warranty_min_months": '
                '60}; dữ kiện={"maintenance_amount": "58753000", '
                '"warranty_months": "36", "warranty_start": '
                '"COMPLETION_AND_ACCEPTANCE_INTO_USE", "numeric_scope": '
                '"APARTMENT_NEW_BUILD_NHAO_2014"}'
            ),
            gates=Gates(
                evidence_validated=True,
                source_verified=True,
                scope_confirmed=True,
                version_resolved=True,
                exceptions_resolved=True,
            ),
            uncertainty_reason=None,
            evidence=[
                Evidence(
                    doan_id="D1",
                    trich_dan="Thời hạn bảo hành 36 tháng",
                    ky_tu_bat_dau=0,
                    ky_tu_ket_thuc=26,
                )
            ],
            legal_basis_ids=["VB_LUAT_NHA_O_2014"],
            tieu_chi_snapshot_json={},
            model_version="BACKEND_NUMERIC_V1",
            prompt_version="C07_SEMANTIC_V16",
            lan_chay_id="RUN",
            mandatory=True,
            excluded=False,
        ),
        CriterionResult(
            ket_qua_id="C_SCOPE",
            ca_id="CA_TEST",
            yeu_cau_ca_id="AR",
            tieu_chi_id="TC_PV_TT16_01",
            finding="UNKNOWN",
            giai_thich="UPSTREAM_SCOPE_UNRESOLVED: co_thoa_thuan_trong_tai",
            gates=Gates(),
            uncertainty_reason="co_thoa_thuan_trong_tai: false",
            tieu_chi_snapshot_json={},
            model_version="BACKEND_SCOPE_CHECK_V1",
            prompt_version="NOT_USED",
            lan_chay_id="RUN",
            mandatory=True,
            excluded=False,
        ),
    ]
    view = build_presentation(content)

    # Numeric criterion check
    num_view = view.criteria["C_NUMERIC"]
    assert "Rule={" not in num_view.explanation
    assert "dữ kiện={" not in num_view.explanation
    assert "36 tháng" in num_view.explanation
    assert "60 tháng" in num_view.explanation
    assert any("Decimal rule audit:" in trace for trace in num_view.audit_trace)
    assert any("BACKEND_NUMERIC_V1" in trace for trace in num_view.audit_trace)

    # Scope criterion check
    scope_view = view.criteria["C_SCOPE"]
    assert "UPSTREAM_SCOPE_UNRESOLVED" not in scope_view.explanation
    assert "trọng tài thương mại" in scope_view.explanation
    assert any("Scope gate:" in trace for trace in scope_view.audit_trace)
    assert any("BACKEND_SCOPE_CHECK_V1" in trace for trace in scope_view.audit_trace)


@pytest.mark.parametrize("finding", ["UNKNOWN"])
def test_numeric_uncertainty_stays_unknown_in_report_without_changing_stored_content(finding):
    report = minimal_report()
    report.report_json.compliance.criterion_results = [
        CriterionResult(
            ket_qua_id="C_UNKNOWN_NUMERIC",
            ca_id="CA_TEST",
            yeu_cau_ca_id="AR",
            tieu_chi_id="CR",
            finding=finding,
            giai_thich=(
                'Backend đối chiếu bằng Decimal. Rule={"warranty_min_months": 60}; dữ kiện={}'
            ),
            gates={},
            uncertainty_reason="Thiếu thời hạn bảo hành",
            tieu_chi_snapshot_json={},
            model_version="BACKEND_NUMERIC_V1",
            prompt_version="TEST",
            lan_chay_id="RUN",
            mandatory=True,
        )
    ]
    before = report.model_dump(mode="json")
    digest = report_digest(report)
    row = build_presentation(report.report_json).criteria["C_UNKNOWN_NUMERIC"]
    assert row.raw_status == row.display_status == "UNKNOWN"
    assert "đáp ứng" not in row.explanation
    assert "36 tháng" not in row.explanation
    assert row.audit_trace
    assert report.model_dump(mode="json") == before
    assert report_digest(report) == digest
