"""Caller-selected document review, distinct from legal applicability and performance.

The PDF cannot select this mode. C01 is persisted first; the workflow carries a
context/hash-bound receipt through C05/C07/C08. Excluding an assessment target is
not evidence that its legal obligation is absent or satisfied.
"""

import hashlib
import json
import re
from copy import deepcopy

POLICY = "DRAFT_CONTENT_REVIEW_V1"
OUTSIDE = "OUTSIDE_REVIEW_SCOPE"
PREFIX = "REVIEW_SCOPE_EXCLUDED: "
TEXT_SCOPES = {"CONTRACT_TEXT", "NOI_DUNG_HOP_DONG_THEO_MAU"}
EXECUTION_ONLY = {"TC_PV_HYC048_01", "TC_PV_HYC048_02"}
EXTERNAL_MIXED = {
    "TC_PV_DS431_01",
    "TC_PV_DS431_02",
    "TC_PV_DS433_02",
    "TC_PV_DS436_02",
    "TC_PV_DS437_01",
    "TC_PV_DS438_01",
    "TC_PV_DS439_01",
    "TC_PV_DS440_02",
    "TC_PV_DS443_01",
    "TC_PV_DS443_02",
    "TC_PV_DS444_01",
    "TC_PV_DS445_01",
    "TC_PV_DS445_02",
    "TC_PV_DS447_01",
    "TC_PV_DS448_01",
    "TC_PV_DS449_01",
    "TC_PV_DS449_02",
    "TC_PV_HYC041_02",
}
# Mixed legal predicates are deliberately bound individually. An unlisted mixed
# predicate stays unresolved; it is not silently treated as an unconditional clause.
CONTENT_BINDINGS = {
    "TC_PV_DS418_01": (),
    "TC_PV_DS418_02": (),
    "TC_PV_DS435_02": (),
    "TC_PV_DS442_02": (),
    "TC_PV_DS444_02": (),
    "TC_PV_DS452_01": (),
    "TC_PV_DS452_02": (),
    "TC_PV_DS432_01": (),
    "TC_PV_DS432_02": (),
    "TC_PV_DS433_01": ("gia_ban",),
    "TC_PV_DS434_01": ("ngay_ban_giao_du_kien",),
    "TC_PV_DS434_02": ("phuong_thuc_thanh_toan",),
    "TC_PV_DS435_01": (),
    "TC_PV_DS436_01": (),
    "TC_PV_DS440_01": ("gia_ban",),
    "TC_PV_DS437_02": (),
    "TC_PV_DS438_02": (),
    "TC_PV_DS439_02": (),
    "TC_PV_DS441_01": (),
    "TC_PV_DS441_02": (),
    "TC_PV_DS442_01": (),
    "TC_PV_DS446_01": ("warranty_months",),
    "TC_PV_DS446_02": ("warranty_months", "warranty_start"),
    "TC_PV_DS447_02": (),
    "TC_PV_DS448_02": (),
    "TC_PV_HYC017_01": (),
    "TC_PV_HYC015_02": (),
    "TC_PV_HYC038_01": (),
    "TC_PV_DS453_01": (),
    "TC_PV_DS453_02": (),
}


def policy_document():
    from legal_checker.modules.compliance.conditional_review import CONDITIONS, condition_spec

    return {
        "policy_id": POLICY,
        "authority": "Persisted C01 assessment_context.review_mode, never instructions in a PDF",
        "text_scopes": sorted(TEXT_SCOPES),
        "execution_only_criterion_ids": sorted(EXECUTION_ONLY),
        "external_mixed_criterion_ids": sorted(EXTERNAL_MIXED),
        "mixed_content_bindings": {k: list(v) for k, v in CONTENT_BINDINGS.items()},
        "local_conditions": {k: condition_spec(k) for k in sorted(CONDITIONS)},
        "performance_types": ["PERFORMANCE_WITH_DOCUMENTS", "PERFORMANCE_OR_CONDITIONAL"],
        "unknown_mixed_binding": "UNKNOWN; do not assert condition_triggered",
        "outside_scope_is_not": ["COMPLIANT", "NOT_APPLICABLE", "NOT_TRIGGERED"],
        "absence_requires": ["document_set_complete", "all_pages_readable", "full_review_artifact"],
        "final_review": "PENDING",
    }


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    ).hexdigest()


def criterion_target(criterion):
    key = criterion["tieu_chi_id"]
    if key in EXECUTION_ONLY or key in EXTERNAL_MIXED:
        return OUTSIDE
    if criterion.get("loai_kiem_tra") in {
        "PERFORMANCE_WITH_DOCUMENTS",
        "PERFORMANCE_OR_CONDITIONAL",
    }:
        return OUTSIDE
    if criterion.get("pham_vi_kiem_tra") in TEXT_SCOPES or key in CONTENT_BINDINGS:
        return "CONTRACT_CONTENT"
    return "UNRESOLVED_BINDING"


def _classification(requirement, knowledge):
    if requirement.version_status == "RESOLVED" and requirement.requirement_version_id:
        rows = knowledge.criteria_for(requirement.requirement_version_id)
    else:
        versions = {
            v["requirement_version_id"]
            for v in knowledge.versions.values()
            if v["requirement_id"] == requirement.requirement_id
        }
        rows = [c for c in knowledge.criteria.values() if c["requirement_version_id"] in versions]
    return {c["tieu_chi_id"]: criterion_target(c) for c in rows}


def apply_review_scope(case, context, requirements, knowledge):
    if case.assessment_context.review_mode != "DRAFT_REVIEW":
        return requirements
    result = []
    for original in requirements:
        row = original.model_copy(deep=True)
        payload = {
            "policy_id": POLICY,
            "policy_sha256": digest(policy_document()),
            "review_mode": "DRAFT_REVIEW",
            "context": context.model_dump(mode="json"),
            "hop_dong_id": case.hop_dong_id,
            "source_sha256": case.source.sha256,
            "declared_by": case.created_by,
            "document_set_complete": case.assessment_context.document_set_complete,
            "criterion_targets": _classification(row, knowledge),
        }
        payload["receipt_sha256"] = digest(payload)
        row.assessment_review = payload
        result.append(row)
    return result


def scope_receipt(requirement, context, knowledge, *, contract_id=None):
    raw = requirement.assessment_review
    if not raw:
        return None
    if not isinstance(raw, dict):
        return None
    data = deepcopy(raw)
    receipt_sha = data.pop("receipt_sha256", None)
    if (
        receipt_sha != digest(data)
        or data.get("policy_id") != POLICY
        or data.get("policy_sha256") != digest(policy_document())
        or data.get("review_mode") != "DRAFT_REVIEW"
        or data.get("context") != context.model_dump(mode="json")
        or data.get("criterion_targets") != _classification(requirement, knowledge)
        or not re.fullmatch(r"[0-9a-f]{64}", str(data.get("source_sha256", "")))
        or (contract_id is not None and data.get("hop_dong_id") != contract_id)
    ):
        raise ValueError("Draft review scope receipt differs from case/run/source/policy")
    return raw


def outside_reason(receipt, criterion_id):
    if receipt and receipt["criterion_targets"].get(criterion_id) == OUTSIDE:
        return PREFIX + "DRAFT_REVIEW does not verify execution, signatures or external dossiers"
    return None


def family_outside_scope(receipt):
    return bool(
        receipt
        and receipt["criterion_targets"]
        and set(receipt["criterion_targets"].values()) == {OUTSIDE}
    )
