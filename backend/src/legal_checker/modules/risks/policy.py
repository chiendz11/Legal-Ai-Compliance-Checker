"""Pure helpers for the finite, pinned C10 rule vocabulary."""

import json
from copy import deepcopy
from typing import Any

from legal_checker.modules.legal_knowledge.models import KnowledgeSnapshot
from legal_checker.shared.contracts.common import Context
from legal_checker.shared.contracts.risk import RiskResult, RiskSource
from legal_checker.shared.ids import stable_id

Diagnostics = list[dict[str, Any]] | None
DISABLED = {"DISABLED", "INACTIVE", "RETIRED", "DELETED"}
SEVERITIES = {"LOW", "MEDIUM", "HIGH", "CRITICAL", "REVIEW_REQUIRED"}


def diagnostic(diagnostics: Diagnostics, code: str, subject: str, detail: str) -> None:
    if diagnostics is not None:
        item = {"module": "C10", "code": code, "subject_id": subject, "detail": detail}
        if item not in diagnostics:
            diagnostics.append(item)


def object_value(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        value = json.loads(value)
    if not isinstance(value, dict):
        raise ValueError("Policy must be a JSON object")
    return value


def rule_trigger(rule: dict, diagnostics: Diagnostics) -> dict | None:
    if rule.get("trang_thai") in DISABLED:
        return None
    try:
        trigger = object_value(rule.get("trigger_json"))
    except (ValueError, TypeError) as exc:
        diagnostic(diagnostics, "INVALID_RISK_POLICY", rule["quy_tac_id"], str(exc))
        return None
    if trigger.get("enabled", True) is False:
        return None
    if "enabled" in trigger and trigger["enabled"] is not True:
        diagnostic(diagnostics, "INVALID_RISK_POLICY", rule["quy_tac_id"], "enabled is not boolean")
        return None
    return trigger


def make_risk(
    request: Context,
    knowledge: KnowledgeSnapshot,
    rule: dict,
    *,
    source: RiskSource,
    source_snapshot: dict,
    finding: str,
    evidence_ids: list[str],
    legal_basis_ids: list[str],
    explanation: str,
    diagnostics: Diagnostics,
) -> RiskResult | None:
    catalog = knowledge.risks.get(rule.get("rui_ro_id"))
    rule_id = rule["quy_tac_id"]
    if catalog is None:
        diagnostic(diagnostics, "MISSING_RISK_CATALOG", rule_id, "Risk catalog mapping is missing")
        return None
    if catalog.get("trang_thai") in DISABLED or catalog.get("trang_thai_ra_soat") in DISABLED:
        diagnostic(diagnostics, "DISABLED_RISK_CATALOG", rule_id, "Risk catalog entry is disabled")
        return None
    if (
        catalog.get("rui_ro_id") != rule.get("rui_ro_id")
        or catalog.get("nhanh") != rule.get("nhanh")
        or (source.ket_qua_tieu_chi_id and catalog.get("tieu_chi_id") != rule.get("tieu_chi_id"))
    ):
        diagnostic(diagnostics, "RISK_CATALOG_CONTEXT_MISMATCH", rule_id, "Catalog target differs")
        return None
    severity = catalog.get("muc_do_co_so")
    if severity not in SEVERITIES:
        diagnostic(diagnostics, "INVALID_SEVERITY", rule_id, "Catalog severity is unsupported")
        return None
    if not isinstance(rule.get("rule_version"), str) or not rule["rule_version"].strip():
        diagnostic(diagnostics, "MISSING_RULE_VERSION", rule_id, "Risk rule has no version")
        return None
    risk_type = "VERIFICATION" if finding == "UNKNOWN" else rule["nhanh"]
    verification_catalog = catalog.get("ban_chat_rui_ro") == "VERIFICATION_ONLY" or (
        rule.get("nhanh") == "CITATION" and catalog.get("ban_chat_rui_ro") == "CITATION_ONLY"
    )
    if finding == "UNKNOWN" and (not verification_catalog or severity != "REVIEW_REQUIRED"):
        diagnostic(
            diagnostics, "UNSAFE_UNKNOWN_POLICY", rule_id, "UNKNOWN needs verification policy"
        )
        return None
    snapshot = deepcopy(rule)
    snapshot.update(
        context=request.model_dump(mode="json", include=set(Context.model_fields)),
        source_finding_snapshot=deepcopy(source_snapshot),
        matched_rules=[deepcopy(rule)],
    )
    source_id = source.ket_qua_tieu_chi_id or source.citation_finding_id
    return RiskResult(
        ket_qua_rui_ro_id=stable_id(
            request, "C10", f"{rule['nhanh']}/{source_id}/{catalog['rui_ro_id']}"
        ),
        ca_id=request.ca_id,
        risk_type=risk_type,
        rui_ro_id=catalog["rui_ro_id"],
        severity=severity,
        source=source,
        quy_tac_id=rule_id,
        giai_thich=explanation,
        risk_snapshot=deepcopy(catalog),
        rule_snapshot_json=snapshot,
        evidence_ids=sorted(set(evidence_ids)),
        legal_basis_ids=sorted(set(legal_basis_ids)),
    )


def deduplicate(risks: list[RiskResult]) -> list[RiskResult]:
    """One source/catalog risk, preserving every matching rule and its version."""
    result: dict[tuple, RiskResult] = {}
    for risk in sorted(risks, key=lambda row: (row.ket_qua_rui_ro_id, row.quy_tac_id)):
        key = (risk.source.ket_qua_tieu_chi_id, risk.source.citation_finding_id, risk.rui_ro_id)
        previous = result.get(key)
        if previous is None:
            result[key] = risk.model_copy(deep=True)
            continue
        if (
            previous.ca_id != risk.ca_id
            or previous.ket_qua_rui_ro_id != risk.ket_qua_rui_ro_id
            or previous.rule_snapshot_json.get("context") != risk.rule_snapshot_json.get("context")
            or previous.severity != risk.severity
            or previous.risk_type != risk.risk_type
            or previous.source != risk.source
            or previous.risk_snapshot != risk.risk_snapshot
            or previous.rule_snapshot_json["source_finding_snapshot"]
            != risk.rule_snapshot_json["source_finding_snapshot"]
        ):
            raise ValueError("Conflicting duplicate risk business identity")
        rules = previous.rule_snapshot_json["matched_rules"]
        for rule in risk.rule_snapshot_json["matched_rules"]:
            if rule not in rules:
                rules.append(deepcopy(rule))
        previous.evidence_ids = sorted(set(previous.evidence_ids + risk.evidence_ids))
        previous.legal_basis_ids = sorted(set(previous.legal_basis_ids + risk.legal_basis_ids))
    return list(result.values())
