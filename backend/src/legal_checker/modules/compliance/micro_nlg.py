"""Deterministic Micro-NLG and audit separation for compliance criteria.

Translates technical rule engine results, decimal assertions, and gate diagnostics
into natural Vietnamese business explanations, while isolating low-level developer
traces for audit and verification.
"""

from __future__ import annotations

import ast
import json
from typing import Any

from legal_checker.modules.compliance.numeric_rules import NumericInputError, number


def _extract_dict_string(text: str, prefix: str) -> dict[str, Any] | None:
    """Safely extracts dictionary content from patterns like Rule={...} or dữ kiện={...}."""
    idx = text.find(prefix)
    if idx == -1:
        return None
    raw = text[idx + len(prefix) :].lstrip()
    if not raw.startswith("{") or len(raw) > 16000:
        return None
    # JSON is the normal format; legacy Python literals are read without eval.
    try:
        value, _ = json.JSONDecoder().raw_decode(raw)
        return value if isinstance(value, dict) else None
    except (ValueError, RecursionError):
        pass
    depth, quoted, escaped = 0, None, False
    for index, char in enumerate(raw):
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quoted:
                quoted = None
        elif char in ("'", '"'):
            quoted = char
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                try:
                    value = ast.literal_eval(raw[: index + 1])
                    return value if isinstance(value, dict) else None
                except (ValueError, SyntaxError, RecursionError):
                    return None
    return None


def numeric_explanation(rule: dict, facts: dict, finding: str) -> str:
    """Describe the stored finding; never infer a label or supply missing numbers.

    NumericInputError uses the same bounded Decimal parsing as the rule engine.
    This is a presentation function, not a second legal decision engine.
    """
    if finding == "UNKNOWN":
        return "Chưa đủ căn cứ để kết luận về tiêu chí số liệu; cần làm rõ dữ kiện hoặc điều kiện."
    if finding == "MISSING":
        return "Thiếu nội dung cần có cho tiêu chí số liệu theo kết quả rà soát đã lưu."
    if finding not in {"SATISFIED", "VIOLATED"}:
        return "Chưa có kết quả đối chiếu số liệu hợp lệ cho tiêu chí này."

    result = (
        "Kết quả đối chiếu đã lưu: đáp ứng tiêu chí."
        if finding == "SATISFIED"
        else "Kết quả đối chiếu đã lưu: không đáp ứng tiêu chí."
    )
    try:
        if "warranty_min_months" in rule:
            months = number(facts.get("warranty_months"), "warranty_months")
            minimum = number(rule.get("warranty_min_months"), "warranty_min_months")
            if finding == "SATISFIED" and months < minimum:
                return "Số liệu bảo hành không nhất quán với kết quả đã lưu; cần rà soát lại."
            return (
                f"Thời hạn bảo hành ghi nhận: {months:f} tháng; "
                f"mức tối thiểu trong quy tắc đã chọn: {minimum:f} tháng. {result}"
            )
        for fact, ratio, label in (
            ("maintenance_amount", "maintenance_ratio", "Kinh phí bảo trì"),
            ("deposit", "deposit_lte_ratio", "Số tiền đặt cọc"),
        ):
            if ratio not in rule:
                continue
            amount = number(facts.get(fact), fact)
            threshold = number(rule.get(ratio), ratio)
            if threshold > 1:
                raise NumericInputError("Ratio outside fraction units")
            return (
                f"{label} ghi nhận: {amount:f} VND; tỷ lệ trong quy tắc đã chọn: "
                f"{threshold * 100:f}% trên cơ sở tính của quy tắc. {result}"
            )
    except NumericInputError:
        return result + " Chưa đủ dữ liệu cấu trúc để trình bày phép đối chiếu chi tiết."
    return result


def synthesize_criterion_explanation(criterion: Any) -> tuple[str, list[str]]:
    """Separates natural Vietnamese explanation from technical audit trace.

    Returns:
        (natural_explanation, audit_traces)
    """
    raw_explanation = getattr(criterion, "giai_thich", "") or ""
    raw_uncertainty = getattr(criterion, "uncertainty_reason", "") or ""
    model_version = getattr(criterion, "model_version", "") or ""
    prompt_version = getattr(criterion, "prompt_version", "") or ""
    finding = getattr(criterion, "finding", "") or ""

    audit_traces: list[str] = []

    # 1. Capture model & prompt provenance if technical
    if model_version in {
        "BACKEND_SCOPE_CHECK_V1",
        "BACKEND_NUMERIC_V1",
        "STRUCTURED_ADAPTER_NO_LLM",
        "NO_LLM",
    }:
        audit_traces.append(f"Engine: {model_version} | Prompt: {prompt_version or 'NONE'}")

    # 2. Check for Numeric Rule Engine string (Decimal comparison)
    if "Backend đối chiếu bằng Decimal" in raw_explanation or "Rule=" in raw_explanation:
        audit_traces.append(f"Decimal rule audit: {raw_explanation}")
        rule_dict = _extract_dict_string(raw_explanation, "Rule=") or {}
        facts_dict = _extract_dict_string(raw_explanation, "dữ kiện=") or {}

        return numeric_explanation(rule_dict, facts_dict, finding), audit_traces

    # 3. Check for Scope / Upstream checks (BACKEND_SCOPE_CHECK_V1)
    if (
        "UPSTREAM_SCOPE_UNRESOLVED" in raw_explanation
        or "co_thoa_thuan_trong_tai" in raw_explanation
        or "co_thoa_thuan_trong_tai" in raw_uncertainty
    ):
        audit_traces.append(f"Scope gate: {raw_explanation or raw_uncertainty}")
        if "co_thoa_thuan_trong_tai" in (raw_explanation + raw_uncertainty):
            return (
                (
                    "Chưa đủ dữ kiện về thỏa thuận trọng tài thương mại để xác định "
                    "phạm vi áp dụng của tiêu chí."
                ),
                audit_traces,
            )
        return (
            (
                "Phạm vi áp dụng hoặc phiên bản quy định pháp luật chưa đủ cơ sở "
                "xác nhận áp dụng đối với hợp đồng này."
            ),
            audit_traces,
        )

    # 4. Check for Draft review execution boundaries
    if "DRAFT_REVIEW does not verify execution" in (raw_explanation + raw_uncertainty):
        audit_traces.append(f"Execution boundary: {raw_explanation or raw_uncertainty}")
        return (
            (
                "Nội dung thuộc nhóm chứng từ thực tế ngoài đời hoặc nghiệm thu "
                "bàn giao thực tế, ngoài phạm vi rà soát dự thảo hợp đồng trước "
                "khi ký kết."
            ),
            audit_traces,
        )

    # 5. Check for Gate failures on prohibited clauses or missing conditions
    if any(
        k in (raw_explanation + raw_uncertainty)
        for k in (
            "Decision rule gate not met",
            "PROHIBITED_CLAUSE",
            "absence_verified",
            "coverage_complete",
        )
    ):
        audit_traces.append(f"Gate evaluation: {raw_explanation or raw_uncertainty}")
        return (
            (
                "Cần rà soát toàn bộ văn bản và phụ lục kèm theo để xác nhận "
                "không tồn tại điều khoản cấm hoặc bất lợi cho người mua nhà."
            ),
            audit_traces,
        )

    # 6. Check for Semantic predicate pending review
    if "Semantic predicate has not been reviewed" in (raw_explanation + raw_uncertainty):
        combined = raw_explanation + " " + raw_uncertainty
        parts = combined.split("reviewed:")
        audit_traces.append(f"Semantic review: {combined.strip()}")
        detail = parts[1].strip() if len(parts) > 1 and parts[1].strip() else ""
        if detail:
            return (
                f"Nội dung điều khoản cần chuyên viên pháp chế rà soát trực tiếp: {detail}",
                audit_traces,
            )
        return (
            (
                "Nội dung điều khoản cần được chuyên viên pháp chế rà soát trực "
                "tiếp để xác định tính phù hợp theo quy định."
            ),
            audit_traces,
        )

    # 7. Check for general technical tags/patterns and clean them
    clean_text = raw_explanation
    for tech_term in (
        "NOT_REQUESTED: Criterion chưa được chọn để gọi AI trong lần này.",
        "OFFLINE_NO_CLIENT: Chế độ offline: chưa gọi AI phân tích ngữ nghĩa.",
        "CALL_LIMIT: Đã đạt giới hạn số criterion được gọi AI trong lần này.",
    ):
        if tech_term in clean_text:
            audit_traces.append(f"Execution flag: {clean_text}")
            return (
                (
                    "Tiêu chí chưa hoàn tất rà soát tự động trong phiên này; đề nghị "
                    "chuyên viên pháp chế kiểm tra trực tiếp."
                ),
                audit_traces,
            )

    if raw_uncertainty:
        if any(
            t in raw_uncertainty
            for t in ("UPSTREAM", "CRITERION", "RULE", "Rule=", "Decimal", "gate", "PROHIBITED")
        ):
            audit_traces.append(f"Uncertainty gate: {raw_uncertainty}")
        else:
            # Human readable uncertainty
            if raw_uncertainty not in clean_text:
                clean_text = f"{clean_text} ({raw_uncertainty})"

    return (clean_text, audit_traces)
