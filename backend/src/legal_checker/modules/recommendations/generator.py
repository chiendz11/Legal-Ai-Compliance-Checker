"""Deterministic C11 template engine with explicit gaps and no invented facts."""

import json
import re
from copy import deepcopy
from string import Formatter

from legal_checker.modules.legal_knowledge.models import KnowledgeSnapshot
from legal_checker.modules.recommendations.validator import validate_risks
from legal_checker.modules.risks.policy import DISABLED, Diagnostics
from legal_checker.shared.contracts.common import Context
from legal_checker.shared.contracts.recommendation import Recommendation
from legal_checker.shared.contracts.risk import RiskResult
from legal_checker.shared.contracts.temporal import ApplicableRequirement
from legal_checker.shared.ids import stable_id

LIMITS = {
    "scope_required",
    "severity_from_db",
    "criterion_target_only",
    "quote_must_match_source",
    "legal_basis_must_resolve",
    "not_applicable_no_remedy",
    "no_auto_invalidity_or_fine",
    "no_invented_names_dates_accounts",
    "recommendation_null_if_satisfied",
    "template_values_are_placeholders",
    "unknown_is_verification_not_violation",
    "related_elements_are_context_not_all_mandatory",
    "human_review_required",
    "unknown_is_not_invalid",
    "no_auto_replace_old_law",
    "no_automatic_invalidity",
    "no_invented_replacement",
    "no_similarity_only_identity",
    "legal_basis_must_be_resolved",
    "citation_does_not_drive_retrieval",
    "current_status_separate_from_historical",
    "official_identity_and_temporal_evidence_required",
}
SEVERITY_ORDER = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}
VERIFICATION_ACTIONS = {"VERIFY", "VERIFY_REFERENCE", "REQUEST_VERIFICATION"}
REMEDY_ACTIONS = {"ADD", "AMEND_OR_PERFORM_CORRECTIVE_ACTION", "CORRECT_REFERENCE"}


def _gap(diagnostics, code, subject, detail):
    if diagnostics is not None:
        item = {"module": "C11", "code": code, "subject_id": subject, "detail": detail}
        if item not in diagnostics:
            diagnostics.append(item)


def _decode(value, expected):
    if isinstance(value, str):

        def unique_object(pairs):
            result = {}
            for key, item in pairs:
                if key in result:
                    raise ValueError("Duplicate template JSON key: " + key)
                result[key] = item
            return result

        value = json.loads(value, object_pairs_hook=unique_object)
    if not isinstance(value, expected):
        raise ValueError("Malformed template JSON")
    return value


def _render(text, values):
    """Only direct named fields: no attribute access, indexing, conversions or formatting."""
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Template content is missing")
    for _, field, format_spec, conversion in Formatter().parse(text):
        if field is None:
            continue
        if not re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]*", field) or format_spec or conversion:
            raise ValueError("Unsupported template expression")
        if field not in values or values[field] in (None, "", []):
            raise ValueError("Missing required fact: " + field)
    return text.format_map(values)


def _required_elements(spec, values):
    """Prose items are requested checklist text; structured fields require existing facts."""
    items = _decode(spec, (list, dict))
    if isinstance(items, dict):
        if set(items) - {"fields", "text"}:
            raise ValueError("Unsupported required-elements schema")
        fields = items.get("fields", [])
        if not isinstance(fields, list) or not all(isinstance(item, str) for item in fields):
            raise ValueError("Required fields must be strings")
        for field in fields:
            if field not in values or values[field] in (None, "", []):
                raise ValueError("Missing required fact: " + field)
        items = items.get("text", [])
    if not isinstance(items, list) or not all(
        isinstance(item, str) and item.strip() for item in items
    ):
        raise ValueError("Required checklist items must be nonempty strings")
    return [_render(item, values) for item in items]


def _values(request, risk, requirement):
    source = risk.rule_snapshot_json["source_finding_snapshot"]
    criterion = source.get("tieu_chi_snapshot_json", {})
    values = {
        "ca_id": request.ca_id,
        "run_id": request.run_id,
        "risk_id": risk.rui_ro_id,
        "risk_instance_id": risk.ket_qua_rui_ro_id,
        "risk_name": risk.risk_snapshot.get("ten_rui_ro"),
        "finding": source.get("finding", source.get("status")),
        "criterion_id": source.get("tieu_chi_id"),
        "criterion_text": criterion.get("noi_dung"),
        "requirement_id": requirement.requirement_id if requirement else None,
        "requirement_version_id": requirement.requirement_version_id if requirement else None,
        "relevant_date": str(requirement.moc_ap_dung)
        if requirement and requirement.moc_ap_dung
        else source.get("relevant_date"),
        "uncertainty_reason": source.get("uncertainty_reason") or source.get("ly_do"),
        "reason_code": source.get("reason_code"),
        "evidence_ids": ", ".join(risk.evidence_ids),
        "legal_basis_ids": ", ".join(risk.legal_basis_ids),
        "quote": "\n".join(item["trich_dan"] for item in source.get("evidence", [])),
    }
    return values


def _build(request, knowledge, risk, requirement, template, mappings):
    limits = _decode(template.get("gioi_han_sinh_json"), dict)
    if set(limits) - LIMITS - {"selection_policy"}:
        raise ValueError("Unsupported generation constraint")
    if any(
        type(value) is not bool or value is not True
        for key, value in limits.items()
        if key in LIMITS
    ):
        raise ValueError("Unsupported disabled/non-boolean generation constraint")
    selection = limits.get("selection_policy", "ALL")
    if selection != "ALL":
        raise ValueError("Unsupported template selection policy")
    branch = risk.rule_snapshot_json["nhanh"]
    source = risk.rule_snapshot_json["source_finding_snapshot"]
    if template.get("nhanh") != branch or template.get("tieu_chi_id") != source.get("tieu_chi_id"):
        raise ValueError("Template target differs from risk source")
    status = source.get("finding", source.get("status"))
    gap = template.get("gap_type")
    if gap != status and not (
        gap == "DOMAIN_MISMATCH"
        and status == "INVALID"
        and source.get("domain_status") == "MISMATCH"
    ):
        raise ValueError("Template finding/domain differs from risk source")
    action = template.get("loai_hanh_dong")
    if action not in VERIFICATION_ACTIONS | REMEDY_ACTIONS:
        raise ValueError("Unsupported template action")
    priority = template.get("uu_tien")
    if risk.risk_type == "VERIFICATION":
        if priority != "REVIEW_REQUIRED" or action not in VERIFICATION_ACTIONS:
            raise ValueError("Verification risk requires a verification action/priority")
    elif priority not in SEVERITY_ORDER or SEVERITY_ORDER[priority] > SEVERITY_ORDER[risk.severity]:
        raise ValueError("Template priority exceeds risk severity")
    if requirement and not requirement.confirmed and risk.risk_type != "VERIFICATION":
        raise ValueError("Unconfirmed/not-applicable requirement cannot receive a remedy")
    allowed_basis = set(knowledge.documents) | set(knowledge.articles) | set(knowledge.versions)
    if set(risk.legal_basis_ids) - allowed_basis:
        raise ValueError("Legal basis does not resolve in pinned knowledge")
    if risk.risk_type != "VERIFICATION" and not risk.legal_basis_ids:
        raise ValueError("Missing required legal basis")
    values = _values(request, risk, requirement)
    text = _render(template.get("noi_dung"), values)
    required = _required_elements(template.get("required_elements_json"), values)
    if risk.risk_type == "VERIFICATION":
        if not values["uncertainty_reason"]:
            raise ValueError("Missing exact verification reason")
        text += "\nThông tin cần làm rõ: " + values["uncertainty_reason"]
    if required:
        label = (
            "Nội dung tham chiếu để đối chiếu khi áp dụng"
            if limits.get("related_elements_are_context_not_all_mandatory")
            else "Các nội dung cần đối chiếu/bổ sung"
        )
        text += "\n" + label + ":\n" + "\n".join("- " + item for item in required)
    for key, label in (
        ("mau_sua_goi_y", "Dự thảo gợi ý"),
        ("bang_chung_khac_phuc_can_luu", "Bằng chứng cần lưu"),
        ("kiem_tra_sau_khac_phuc", "Kiểm tra sau khắc phục"),
    ):
        if template.get(key):
            text += "\n" + label + ": " + _render(template[key], values)
    snapshot = deepcopy(template)
    snapshot.update(
        mapping_snapshots=deepcopy(mappings),
        context=request.model_dump(mode="json", include=set(Context.model_fields)),
        generation_policy="ALL_MAPPED_TEMPLATES",
        resolved_bindings={key: value for key, value in values.items() if value is not None},
    )
    return Recommendation(
        khuyen_nghi_ca_id=stable_id(
            request, "C11", f"{risk.ket_qua_rui_ro_id}/{template['khuyen_nghi_id']}"
        ),
        ket_qua_rui_ro_id=risk.ket_qua_rui_ro_id,
        khuyen_nghi_id=template["khuyen_nghi_id"],
        noi_dung=text,
        loai_hanh_dong=template["loai_hanh_dong"],
        uu_tien=priority,
        dieu_kien_snapshot={
            "risk_source": risk.source.model_dump(mode="json"),
            "finding": values["finding"],
            "uncertainty_reason": values["uncertainty_reason"],
            "requirement": requirement.model_dump(mode="json") if requirement else None,
            "risk_rule_snapshot": deepcopy(risk.rule_snapshot_json),
            "generation_limits": deepcopy(limits),
        },
        evidence_ids=list(risk.evidence_ids),
        legal_basis_ids=list(risk.legal_basis_ids),
        template_snapshot_json=snapshot,
        rule_version=risk.rule_snapshot_json["rule_version"],
        knowledge_snapshot_sha256=knowledge.sha256,
    )


def recommend(
    request: Context,
    knowledge: KnowledgeSnapshot,
    risks: list[RiskResult],
    requirements: list[ApplicableRequirement],
    *,
    diagnostics: Diagnostics = None,
) -> list[Recommendation]:
    validate_risks(request, risks, knowledge, requirements)
    owners = {item.yeu_cau_ca_id: item for item in requirements}
    output = []
    for risk in sorted(risks, key=lambda item: item.ket_qua_rui_ro_id):
        mappings = [
            row
            for row in knowledge.tables.get("rui_ro_khuyen_nghi", [])
            if row.get("rui_ro_id") == risk.rui_ro_id
        ]
        if not mappings:
            _gap(
                diagnostics,
                "MISSING_RECOMMENDATION_MAPPING",
                risk.ket_qua_rui_ro_id,
                risk.rui_ro_id,
            )
            continue
        if any(row.get("selection_policy", "ALL") != "ALL" for row in mappings):
            _gap(
                diagnostics,
                "UNSUPPORTED_TEMPLATE_SELECTION",
                risk.ket_qua_rui_ro_id,
                "Only ALL mapping policy is supported",
            )
            continue
        active_mappings = []
        for mapping in mappings:
            if mapping.get("trang_thai") in DISABLED or mapping.get("enabled") is False:
                _gap(
                    diagnostics,
                    "DISABLED_RECOMMENDATION_MAPPING",
                    risk.ket_qua_rui_ro_id,
                    str(mapping.get("lien_ket_id")),
                )
                continue
            if "enabled" in mapping and mapping["enabled"] is not True:
                _gap(
                    diagnostics,
                    "INVALID_RECOMMENDATION_MAPPING",
                    risk.ket_qua_rui_ro_id,
                    "enabled must be boolean",
                )
                continue
            active_mappings.append(mapping)
        by_template = {}
        for mapping in active_mappings:
            by_template.setdefault(mapping.get("khuyen_nghi_id"), []).append(mapping)
        for template_id, links in sorted(by_template.items(), key=lambda item: str(item[0])):
            template = knowledge.recommendations.get(template_id)
            if template is None:
                _gap(
                    diagnostics,
                    "MISSING_RECOMMENDATION_TEMPLATE",
                    risk.ket_qua_rui_ro_id,
                    str(template_id),
                )
                continue
            if template.get("khuyen_nghi_id") != template_id:
                _gap(
                    diagnostics,
                    "RECOMMENDATION_KNOWLEDGE_GAP",
                    risk.ket_qua_rui_ro_id,
                    "Template identity differs from mapping",
                )
                continue
            if (
                template.get("trang_thai") in DISABLED
                or template.get("trang_thai_ra_soat") in DISABLED
            ):
                _gap(
                    diagnostics,
                    "DISABLED_RECOMMENDATION_TEMPLATE",
                    risk.ket_qua_rui_ro_id,
                    str(template_id),
                )
                continue
            try:
                links = sorted(
                    links, key=lambda row: json.dumps(row, sort_keys=True, ensure_ascii=False)
                )
                output.append(
                    _build(
                        request,
                        knowledge,
                        risk,
                        owners.get(risk.source.yeu_cau_ca_id),
                        template,
                        links,
                    )
                )
            except (ValueError, TypeError, KeyError) as exc:
                _gap(
                    diagnostics,
                    "RECOMMENDATION_KNOWLEDGE_GAP",
                    risk.ket_qua_rui_ro_id,
                    f"{template_id}: {exc}",
                )
    return output
