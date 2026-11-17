"""Strict backend safety validator for C11 Qwen personalized recommendations."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from legal_checker.modules.recommendations.generator import VERIFICATION_ACTIONS
from legal_checker.modules.recommendations.personalization.contracts import (
    PersonalizedRecommendation,
)
from legal_checker.shared.contracts.recommendation import Recommendation

_CODE_FENCE_RE = re.compile(r"```")
_HTML_TAG_RE = re.compile(
    r"</?\s*(?:html|body|head|script|style|iframe|div|span|p|br|hr|b|i|u|strong|em|a|ul|ol|li|table|tr|td|th|h[1-6]|img|object|embed)\b[^>]*>",
    re.I,
)
_STEP_PREFIX_RE = re.compile(
    r"(?:^[ \t]*(?:\d{1,2}[.)]|bước\s+\d{1,2}\b[:.-]?)\s*|\(\d{1,2}\)\s*)", re.I | re.M
)

_DATE_RE = re.compile(
    r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b"
    r"|\b\d{4}-\d{2}-\d{2}\b"
    r"|ngày\s+\d{1,2}\s+tháng\s+\d{1,2}(?:\s+năm\s+\d{4})?",
    re.I,
)
_PERCENT_RE = re.compile(r"\b\d+(?:[.,]\d+)?\s*%")
_MONEY_UNIT_RE = re.compile(
    r"\b\d+(?:[.,]\d+)*\s*(?:tỷ|triệu|nghìn|ngàn|đồng|vnd|vnđ|usd|tháng|ngày|năm|m2|m²)\b",
    re.I,
)
_LEGAL_CODE_RE = re.compile(r"\b\d{1,4}/\d{4}/[A-ZĐ0-9-]+\b", re.I)
_LEGAL_INSTRUMENT_RE = re.compile(
    r"\b(?:luật|bộ\s+luật|nghị\s+định|thông\s+tư|quyết\s+định|nghị\s+quyết)\s+"
    r"(?:số\s+\d+\S*|(?:[A-ZĐ][\wÀ-ỹ]*\s+){1,5}năm\s+\d{4})\b",
    re.I,
)
_QUOTED_SPAN_RE = re.compile(r'["“]([^"”\n]{4,})["”]')
_NUMBER_RE = re.compile(r"\b\d+(?:[.,]\d+)*\b")
_LONG_DIGIT_RE = re.compile(r"\b\d{7,20}\b")
# The role word must start a word and the name must be capitalised. Without both,
# ordinary prose such as "không đầy đủ" was read as the person "ông đầy đủ" and
# every rewrite containing "không ..." was rejected as a fabricated entity.
_ENTITY_RE = re.compile(
    r"\b(?i:công\s+ty(?:\s+tnhh|\s+cổ\s+phần|\s+cp)?|ngân\s+hàng|chi\s+nhánh|ông|bà)\s+"
    r"[A-ZĐ][\wÀ-ỹ.-]*(?:\s+[A-ZĐ0-9][\wÀ-ỹ.-]*){0,5}"
    r"|(?i:\b(?:tài\s+khoản|stk|mst|cccd|cmnd)\s*(?:số|:)?\s*[A-Z0-9-]{4,20}\b)",
)
_TECH_ID_RE = re.compile(r"\b(?:TC|FAM|KN|RR|CA360|DOC|ART|VB|VBPL)_[A-Z0-9_]+\b")

_VOID_OR_FINE_PATTERNS = (
    re.compile(r"\bvô\s+hiệu\b", re.I),
    re.compile(r"\bkhông\s+có\s+giá\s+trị\s+pháp\s+lý\b", re.I),
    re.compile(r"\bxử\s+phạt\b", re.I),
    re.compile(r"\bphạt\s+hành\s+chính\b", re.I),
    re.compile(r"\bmức\s+phạt\b", re.I),
    re.compile(r"\bbị\s+phạt\b", re.I),
    re.compile(r"\bchế\s+tài\b", re.I),
)

_UNKNOWN_FORBIDDEN_PATTERNS = (
    re.compile(r"\bvi\s+phạm\b", re.I),
    re.compile(r"\btrái\s+luật\b", re.I),
    re.compile(r"(?<!chưa\s)(?<!không\s)\btrái\s+quy\s+định\b", re.I),
    re.compile(r"\bkhông\s+hợp\s+pháp\b", re.I),
    re.compile(r"\bsai\s+quy\s+định\b", re.I),
    re.compile(r"(?<!chưa\s)(?<!không\s)\bkhông\s+tuân\s+thủ\b", re.I),
    re.compile(r"\bvăn\s+bản(?:\s+pháp\s+luật)?\s+cũ\b", re.I),
    re.compile(r"\bluật\s+cũ\b", re.I),
    re.compile(r"\bhết\s+hiệu\s+lực\b", re.I),
    re.compile(r"\bđã\s+bị\s+thay\s+thế\b", re.I),
    re.compile(r"\bkhông\s+còn\s+hiệu\s+lực\b", re.I),
    re.compile(r"\b(?:cần|phải)\s+thay\s+thế\b", re.I),
    re.compile(r"(?<!chưa\s)(?<!không\s)\b(?:cần|phải)\s+sửa(?:\s+đổi)?\b", re.I),
    re.compile(r"\bkhắc\s+phục\s+vi\s+phạm\b", re.I),
)

_PRIORITY_ESCALATION = {
    "LOW": ("MEDIUM", "HIGH", "CRITICAL", "ưu tiên cao", "mức độ cao", "nghiêm trọng", "khẩn cấp"),
    "MEDIUM": ("HIGH", "CRITICAL", "mức độ cao", "khẩn cấp"),
    "HIGH": ("CRITICAL", "khẩn cấp"),
    "REVIEW_REQUIRED": ("HIGH", "CRITICAL", "mức độ cao", "ưu tiên cao", "khẩn cấp"),
    "CRITICAL": (),
}

_REF_MANDATORY_PATTERNS = (
    re.compile(r"\bbắt\s+buộc\s+phải\s+(?:có|bổ\s+sung)\s+(?:tất\s+cả|toàn\s+bộ)\b", re.I),
    re.compile(r"\bnghĩa\s+vụ\s+bắt\s+buộc\b", re.I),
)

_VI_STOPWORDS = {
    "và",
    "của",
    "các",
    "những",
    "cho",
    "với",
    "tại",
    "trong",
    "theo",
    "này",
    "khi",
    "để",
    "hoặc",
    "về",
    "từ",
    "đến",
    "trên",
    "nếu",
    "thì",
    "là",
    "đã",
    "đang",
    "cần",
    "phải",
    "nên",
    "không",
    "chưa",
    "có",
    "được",
    "làm",
    "rõ",
    "bổ",
    "sung",
    "kiểm",
    "tra",
    "xem",
    "lại",
    "gồm",
    "như",
    "sau",
    "trước",
    "một",
    "hai",
    "bước",
    "nội",
    "dung",
    "thông",
    "tin",
    "bằng",
    "chứng",
    "điều",
    "khoản",
    "hợp",
    "đồng",
    "provider",
    "uncertainty",
    "criterion",
    "local_applicability",
    "match",
    "requires",
    "verified",
    "current",
    "case",
    "facts",
    "unresolved",
    "gate",
    "evidence_validated",
    "source_verified",
    "exceptions_resolved",
    "machine_draft_review",
    "semantic",
    "predicate",
    "has",
    "not",
    "been",
    "reviewed",
    "decision",
    "rule",
    "met",
    "absence_verified",
    "coverage_complete",
    "prohibited_clause",
    "satisfied",
    "api",
    "unregistered_external_id",
    "context_limit",
    "call_limit",
}


class PersonalizationValidationError(ValueError):
    """Raised when Qwen structured output fails structure, anchor, or safety validation."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class AnchorInventory:
    dates: frozenset[str]
    percentages: frozenset[str]
    quantities: frozenset[str]
    numbers: frozenset[str]
    long_digits: frozenset[str]
    legal_codes: frozenset[str]
    legal_instruments: frozenset[str]
    quotes: frozenset[str]
    entities: frozenset[str]
    tech_ids: frozenset[str]


def _norm_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


def _parse_json_unique(raw: str) -> dict[str, Any]:
    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result

    parsed = json.loads(raw, object_pairs_hook=unique_object)
    if not isinstance(parsed, dict):
        raise ValueError("Structured output must be a JSON object")
    return parsed


def _strip_step_ordinals(text: str) -> str:
    return _STEP_PREFIX_RE.sub("", text)


def _extract_anchors(text: str, extra_texts: tuple[str, ...] = ()) -> AnchorInventory:
    combined = "\n".join([text, *extra_texts])
    stripped_text = _strip_step_ordinals(text)
    stripped_combined = "\n".join([stripped_text, *(_strip_step_ordinals(t) for t in extra_texts)])

    dates = frozenset(_norm_ws(m.group(0)) for m in _DATE_RE.finditer(combined))
    percentages = frozenset(re.sub(r"\s+", "", m.group(0)) for m in _PERCENT_RE.finditer(combined))
    quantities = frozenset(_norm_ws(m.group(0)) for m in _MONEY_UNIT_RE.finditer(combined))
    numbers = frozenset(m.group(0) for m in _NUMBER_RE.finditer(stripped_combined))
    long_digits = frozenset(m.group(0) for m in _LONG_DIGIT_RE.finditer(combined))
    legal_codes = frozenset(m.group(0).casefold() for m in _LEGAL_CODE_RE.finditer(combined))
    legal_instruments = frozenset(
        _norm_ws(m.group(0)) for m in _LEGAL_INSTRUMENT_RE.finditer(combined)
    )
    quotes = frozenset(_norm_ws(m.group(1)) for m in _QUOTED_SPAN_RE.finditer(combined))
    entities = frozenset(_norm_ws(m.group(0)) for m in _ENTITY_RE.finditer(combined))
    tech_ids = frozenset(m.group(0) for m in _TECH_ID_RE.finditer(combined))
    return AnchorInventory(
        dates=dates,
        percentages=percentages,
        quantities=quantities,
        numbers=numbers,
        long_digits=long_digits,
        legal_codes=legal_codes,
        legal_instruments=legal_instruments,
        quotes=quotes,
        entities=entities,
        tech_ids=tech_ids,
    )


def _source_context_texts(recommendation: Recommendation) -> tuple[str, ...]:
    snap = recommendation.template_snapshot_json or {}
    cond = recommendation.dieu_kien_snapshot or {}
    bindings = snap.get("resolved_bindings") or {}
    extras = [str(v) for v in bindings.values() if isinstance(v, str) and v.strip()]
    if cond.get("uncertainty_reason"):
        extras.append(str(cond["uncertainty_reason"]))
    extras.extend(recommendation.legal_basis_ids)
    extras.extend(recommendation.evidence_ids)
    return tuple(extras)


def _is_verification_mode(recommendation: Recommendation) -> bool:
    cond = recommendation.dieu_kien_snapshot or {}
    risk_snap = cond.get("risk_rule_snapshot") or {}
    finding = str(cond.get("finding") or "").upper()
    risk_type = str(risk_snap.get("nhanh") or "").upper()
    return (
        recommendation.uu_tien == "REVIEW_REQUIRED"
        or recommendation.loai_hanh_dong in VERIFICATION_ACTIONS
        or finding == "UNKNOWN"
        or risk_type == "VERIFICATION"
    )


def _significant_tokens(line: str) -> set[str]:
    tokens = set(re.findall(r"[a-zA-ZÀ-ỹ0-9_]{3,}", line.casefold()))
    return {tok for tok in tokens if tok not in _VI_STOPWORDS}


def _check_required_sections_preserved(original_text: str, personalized_text: str) -> None:
    """Verify checklist bullets, draft suggestions, and clarification clauses are not dropped."""
    norm_out = _norm_ws(personalized_text)
    out_tokens = _significant_tokens(personalized_text)
    all_sig: set[str] = set()
    first_missing_payload = ""
    for raw_line in original_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        is_critical = (
            line.startswith("- ")
            or line.startswith("Dự thảo gợi ý:")
            or line.startswith("Bằng chứng cần lưu:")
            or line.startswith("Kiểm tra sau khắc phục:")
        )
        if not is_critical:
            continue
        payload = line[2:].strip() if line.startswith("- ") else line.split(":", 1)[1].strip()
        if not payload:
            continue
        sig = _significant_tokens(payload)
        all_sig.update(sig)
        if _norm_ws(payload) not in norm_out and sig:
            overlap = len(sig & out_tokens) / len(sig)
            if overlap < 0.3 and not first_missing_payload:
                first_missing_payload = payload
    if all_sig and (len(all_sig & out_tokens) / len(all_sig)) < 0.35:
        raise PersonalizationValidationError(
            "C11_ANCHOR_MISMATCH",
            f"Required content was omitted or altered: {first_missing_payload[:80]}",
        )


def validate_personalized_output(
    recommendation: Recommendation,
    raw_content: str,
    *,
    max_output_chars: int = 4000,
) -> str:
    """Parse structured JSON from Qwen and strictly verify safety before accepting."""
    if not isinstance(raw_content, str) or not raw_content.strip():
        raise PersonalizationValidationError("C11_INVALID_STRUCTURED_OUTPUT", "Empty LLM output")
    if _CODE_FENCE_RE.search(raw_content):
        raise PersonalizationValidationError(
            "C11_INVALID_STRUCTURED_OUTPUT", "Markdown code fences are not allowed"
        )
    try:
        parsed = _parse_json_unique(raw_content)
        model = PersonalizedRecommendation.model_validate(parsed)
    except (ValueError, ValidationError) as error:
        raise PersonalizationValidationError(
            "C11_INVALID_STRUCTURED_OUTPUT", f"Invalid structured recommendation JSON: {error}"
        ) from error

    text = model.personalized_text.strip()
    if len(text) > max_output_chars:
        raise PersonalizationValidationError(
            "C11_INVALID_STRUCTURED_OUTPUT", "Personalized recommendation exceeds length budget"
        )
    if _CODE_FENCE_RE.search(text) or _HTML_TAG_RE.search(text):
        raise PersonalizationValidationError(
            "C11_INVALID_STRUCTURED_OUTPUT", "Unsafe markup or code fence in personalized_text"
        )

    original = recommendation.noi_dung
    extras = _source_context_texts(recommendation)
    allowed = _extract_anchors(original, extras)
    orig_without_diag = "\n".join(
        line
        for line in original.splitlines()
        if not line.strip().startswith("Thông tin cần làm rõ:")
        and not line.strip().startswith("Kiểm tra sau khắc phục:")
    )
    orig_only = _extract_anchors(orig_without_diag)
    out = _extract_anchors(text)

    # 1. No fabricated quantitative values, dates, percentages, long digits, or entities
    if out.dates - allowed.dates:
        raise PersonalizationValidationError("C11_ANCHOR_MISMATCH", "Fabricated date detected")
    if out.percentages - allowed.percentages:
        raise PersonalizationValidationError(
            "C11_ANCHOR_MISMATCH", "Fabricated percentage detected"
        )
    if out.quantities - allowed.quantities:
        raise PersonalizationValidationError("C11_ANCHOR_MISMATCH", "Fabricated quantity detected")
    if out.long_digits - allowed.long_digits:
        raise PersonalizationValidationError(
            "C11_ANCHOR_MISMATCH", "Fabricated account or identifier digits detected"
        )
    if out.numbers - allowed.numbers - {"1", "2", "3", "4", "5"}:
        raise PersonalizationValidationError("C11_ANCHOR_MISMATCH", "Fabricated number detected")
    if out.entities - allowed.entities:
        raise PersonalizationValidationError(
            "C11_ANCHOR_MISMATCH", "Fabricated entity or identity detected"
        )

    # 2. No fabricated legal codes, instruments, or synthetic quoted contract text
    if out.legal_codes - allowed.legal_codes:
        raise PersonalizationValidationError(
            "C11_ANCHOR_MISMATCH", "Fabricated legal document code detected"
        )
    norm_allowed_text = _norm_ws("\n".join([original, *extras]))
    for inst in out.legal_instruments:
        if inst not in allowed.legal_instruments and inst not in norm_allowed_text:
            raise PersonalizationValidationError(
                "C11_ANCHOR_MISMATCH", f"Fabricated legal instrument detected: {inst}"
            )
    for quote in out.quotes:
        if quote not in allowed.quotes and quote not in norm_allowed_text:
            raise PersonalizationValidationError(
                "C11_ANCHOR_MISMATCH", "Modified or fabricated quotation detected"
            )

    # 3. Critical anchors in deterministic text must be preserved in personalized output
    if orig_only.dates - out.dates:
        raise PersonalizationValidationError("C11_ANCHOR_MISMATCH", "Original date was dropped")
    if orig_only.percentages - out.percentages:
        raise PersonalizationValidationError("C11_ANCHOR_MISMATCH", "Original percentage dropped")
    if orig_only.quantities - out.quantities:
        raise PersonalizationValidationError("C11_ANCHOR_MISMATCH", "Original quantity dropped")
    if orig_only.legal_codes - out.legal_codes:
        raise PersonalizationValidationError("C11_ANCHOR_MISMATCH", "Original legal code dropped")
    if orig_only.quotes - out.quotes:
        raise PersonalizationValidationError("C11_ANCHOR_MISMATCH", "Original quote altered")

    bindings = (recommendation.template_snapshot_json or {}).get("resolved_bindings") or {}
    observed_quote = bindings.get("quote")
    if isinstance(observed_quote, str) and observed_quote.strip():
        norm_quote = _norm_ws(observed_quote)
        if norm_quote in _norm_ws(original) and norm_quote not in _norm_ws(text):
            raise PersonalizationValidationError(
                "C11_ANCHOR_MISMATCH", "Observed quote binding was altered or dropped"
            )

    # 4. Forbidden legal conclusions (voidness / fines / priority escalation)
    for pat in _VOID_OR_FINE_PATTERNS:
        if pat.search(text) and not pat.search(original):
            raise PersonalizationValidationError(
                "C11_UNSAFE_CONTENT", f"Forbidden voidness/sanction claim: {pat.pattern}"
            )
    for marker in _PRIORITY_ESCALATION.get(recommendation.uu_tien, ()):
        if marker.casefold() in text.casefold() and marker.casefold() not in original.casefold():
            raise PersonalizationValidationError(
                "C11_UNSAFE_CONTENT", f"Priority escalation marker detected: {marker}"
            )

    # 5. Reference context must not become mandatory obligation
    if "Nội dung tham chiếu để đối chiếu khi áp dụng" in original:
        for pat in _REF_MANDATORY_PATTERNS:
            if pat.search(text) and not pat.search(original):
                raise PersonalizationValidationError(
                    "C11_UNSAFE_CONTENT", "Reference items rewritten as mandatory obligations"
                )

    # 6. Verification / UNKNOWN strict guardrail
    if _is_verification_mode(recommendation):
        for pat in _UNKNOWN_FORBIDDEN_PATTERNS:
            if pat.search(text) and not pat.search(original):
                raise PersonalizationValidationError(
                    "C11_UNSAFE_CONTENT",
                    f"UNKNOWN/VERIFICATION escalated to violation or remedy: {pat.pattern}",
                )

    # 7. Completeness check on critical checklist/draft/clarification lines
    _check_required_sections_preserved(original, text)
    return text
