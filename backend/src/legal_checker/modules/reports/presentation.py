"""One projection for UI/export; never rewrites machine findings or review targets."""

from legal_checker.modules.compliance.micro_nlg import synthesize_criterion_explanation
from legal_checker.modules.recommendations.rendering import (
    bind_draft_slots,
    observed_quote,
    verification_request,
)
from legal_checker.modules.reports.assessment_status import (
    criterion_display_status,
    requirement_display_status,
)
from legal_checker.shared.contracts.presentation import (
    CoverageView,
    FindingView,
    RecommendationView,
    ReportPresentation,
)


def coverage_view(row):
    snapshot = row.requirement_snapshot_json
    finding = snapshot.get("finding_coverage_complete")
    full_text = snapshot.get("evidence_coverage_complete")
    finding = finding if type(finding) is bool else None
    full_text = full_text if type(full_text) is bool else None
    status = requirement_display_status(row)
    if status in {"OUTSIDE_REVIEW_SCOPE", "NOT_TRIGGERED"}:
        explanation = (
            "Không đánh giá trong phạm vi đã chọn."
            if status == "OUTSIDE_REVIEW_SCOPE"
            else "Không có tiêu chí bắt buộc phát sinh sau khi xét điều kiện."
        )
    else:
        labels = [
            "Đã có đủ kết quả tiêu chí."
            if finding is True
            else "Còn thiếu kết quả tiêu chí."
            if finding is False
            else "Báo cáo cũ chưa ghi riêng độ đầy đủ kết quả tiêu chí."
        ]
        labels.append(
            "Đã xác nhận độ phủ bằng chứng toàn văn."
            if full_text is True
            else (
                "Chưa xác nhận độ phủ bằng chứng toàn văn; không đồng nghĩa thiếu kết quả tiêu chí."
            )
            if full_text is False
            else "Chưa có thông tin riêng về độ phủ bằng chứng toàn văn."
        )
        explanation = " ".join(labels)
    return CoverageView(
        finding_complete=finding,
        full_text_complete=full_text,
        conclusion_complete=row.coverage_complete,
        explanation=explanation,
    )


def version_description(row):
    if row.applicability_status == "NOT_APPLICABLE" and not row.requirement_version_id:
        return "Không chọn phiên bản — yêu cầu không áp dụng"
    if row.version_status == "RESOLVED":
        return "Đã xác định phiên bản: " + (row.requirement_version_id or "—")
    return "Chưa phân giải phiên bản" + (
        "; ứng viên: " + row.requirement_version_id if row.requirement_version_id else ""
    )


def requirement_diagnostic_code(row):
    return {
        "OUTSIDE_REVIEW_SCOPE": "REQUIREMENT_OUTSIDE_REVIEW_SCOPE",
        "NOT_TRIGGERED": "REQUIREMENT_NOT_TRIGGERED",
    }.get(requirement_display_status(row), "INSUFFICIENT_REQUIREMENT")


def clean_recommendation_presentation(text: str) -> str:
    if not text:
        return ""
    lines = []
    for line in text.splitlines():
        cleaned_line = line.strip()
        if not cleaned_line:
            continue
        if cleaned_line.startswith("Thông tin cần làm rõ:"):
            val = cleaned_line[len("Thông tin cần làm rõ:") :].strip()
            if any(
                k in val for k in ("PROHIBITED_CLAUSE", "coverage_complete", "absence_verified")
            ):
                clean_val = (
                    "Cần rà soát toàn bộ văn bản và phụ lục hợp đồng để xác nhận "
                    "không tồn tại điều khoản cấm chuyển giao quyền/nghĩa vụ hoặc "
                    "điều khoản bất lợi cho người tiêu dùng."
                )
            elif "Semantic predicate has not been reviewed" in val:
                parts = val.split("reviewed:")
                clean_val = (
                    f"Nội dung cần chuyên viên pháp chế rà soát trực tiếp: {parts[1].strip()}"
                    if len(parts) > 1 and parts[1].strip()
                    else (
                        "Nội dung điều khoản cần được chuyên viên pháp chế rà soát trực "
                        "tiếp để xác định tính phù hợp theo quy định."
                    )
                )
            elif "co_thoa_thuan_trong_tai" in val:
                clean_val = (
                    "Hồ sơ chưa có thông tin về thỏa thuận trọng tài thương mại để "
                    "xác định thẩm quyền áp dụng theo Thông tư 16/2010/TT-BXD."
                )
            elif any(
                k in val
                for k in ("Requirement applicability/scope/version", "UPSTREAM_SCOPE_UNRESOLVED")
            ):
                clean_val = (
                    "Phạm vi áp dụng hoặc phiên bản quy định pháp luật chưa được xác "
                    "nhận đủ điều kiện áp dụng."
                )
            elif "DRAFT_REVIEW does not verify execution" in val:
                clean_val = (
                    "Tiêu chí thuộc nhóm chứng từ thực tế ngoài đời, chưa đánh giá "
                    "trong giai đoạn rà soát dự thảo."
                )
            elif any(k in val for k in ("RATE_LIMIT", "lỗi API")):
                clean_val = (
                    "Hệ thống chưa hoàn tất phân tích tự động trong lần rà soát này; "
                    "đề nghị chuyên viên pháp chế rà soát trực tiếp điều khoản này."
                )
            elif any(
                k in val for k in ("Decision rule gate not met", "Unresolved gate", "requires")
            ):
                clean_val = (
                    "Cần bổ sung hồ sơ và đối chiếu điều kiện để làm rõ căn cứ áp "
                    "dụng đối với tiêu chí này."
                )
            else:
                clean_val = val
            cleaned_line = f"Thông tin cần làm rõ: {clean_val}"

        import re

        cleaned_line = re.sub(r"Mục tiêu chỉ là tiêu chí\s+TC_[A-Z0-9_]+\.?\s*", "", cleaned_line)
        cleaned_line = re.sub(r"chạy lại Citation Validator\.?\s*", "", cleaned_line)
        cleaned_line = re.sub(
            r"Không đổi kết quả Compliance nếu không đánh giá nhánh Applicable Law độc lập\.?\s*",
            "",
            cleaned_line,
        )
        if cleaned_line.startswith("Kiểm tra sau khắc phục:"):
            cleaned_line = re.sub(
                r"Kiểm tra lại\s+TC_[A-Z0-9_]+\s+với\s+", "Kiểm tra lại với ", cleaned_line
            )
        if cleaned_line.strip():
            lines.append(cleaned_line)
    return "\n".join(lines)


def build_presentation(content):
    requirements = {r.yeu_cau_ca_id: r for r in content.compliance.requirement_results}
    diagnostics = []
    for original in content.audit.get("diagnostics", []):
        item = dict(original)
        row = requirements.get(item.get("yeu_cau_ca_id"))
        if row and item.get("code") == "INSUFFICIENT_REQUIREMENT":
            item["raw_code"] = item["code"]
            item["code"] = requirement_diagnostic_code(row)
        diagnostics.append(item)
    risks = {
        r.ket_qua_rui_ro_id: r
        for branch in (content.risks.compliance, content.risks.citation, content.risks.verification)
        for r in branch
    }
    citations = {c.vien_dan_id: c for c in content.citation_validation.citations}
    recommendations = {}
    for row in content.recommendations:
        risk = risks.get(row.ket_qua_rui_ro_id)
        source = risk.rule_snapshot_json.get("source_finding_snapshot", {}) if risk else {}
        citation = citations.get(source.get("vien_dan_id"))
        bindings = row.template_snapshot_json.get("resolved_bindings", {})
        values = {
            **bindings,
            "verification_request": verification_request(source)
            or bindings.get("verification_request"),
            "quote": observed_quote(source)
            or (citation.raw_text if citation else "")
            or bindings.get("quote"),
            "uncertainty_reason": source.get("uncertainty_reason")
            or source.get("ly_do")
            or bindings.get("uncertainty_reason"),
        }
        if row.template_snapshot_json.get("rendering_policy") == "OBSERVED_TEMPLATE_BINDINGS_V1":
            recommendations[row.khuyen_nghi_ca_id] = RecommendationView(
                text=clean_recommendation_presentation(row.noi_dung)
            )
            continue
        lines, missing = [], []
        for line in row.noi_dung.splitlines():
            rendered, gaps = bind_draft_slots(line, values)
            if gaps:
                missing.extend(gaps)
                # Keep the actual action/evidence request; withhold an unbound draft.
                lines.append("Chưa tạo câu sửa gợi ý: cần bổ sung dữ kiện " + ", ".join(gaps) + ".")
            else:
                lines.append(rendered)
        recommendations[row.khuyen_nghi_ca_id] = RecommendationView(
            text=clean_recommendation_presentation("\n".join(lines)),
            unresolved_bindings=sorted(set(missing)),
        )
    return ReportPresentation(
        requirements={
            r.tuan_thu_id: FindingView(
                raw_status=r.status,
                display_status=requirement_display_status(r),
                coverage=coverage_view(r),
            )
            for r in requirements.values()
        },
        criteria={
            r.ket_qua_id: (
                lambda exp, trace: FindingView(
                    raw_status=r.finding,
                    display_status=criterion_display_status(r),
                    explanation=exp,
                    audit_trace=trace,
                )
            )(*synthesize_criterion_explanation(r))
            for r in content.compliance.criterion_results
        },
        applicability_versions={
            r.yeu_cau_ca_id: version_description(r) for r in content.applicable_legal_scope
        },
        diagnostics=diagnostics,
        recommendations=recommendations,
    )
