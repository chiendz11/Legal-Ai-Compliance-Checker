"""Map C07 finding instances to risks using only the pinned policy."""

from legal_checker.modules.legal_knowledge.models import KnowledgeSnapshot
from legal_checker.modules.risks.policy import (
    Diagnostics,
    deduplicate,
    diagnostic,
    make_risk,
    rule_trigger,
)
from legal_checker.shared.contracts.common import Context
from legal_checker.shared.contracts.reasoning import CriterionResult
from legal_checker.shared.contracts.risk import RiskResult, RiskSource
from legal_checker.shared.validation import validate_context


def validate_findings(
    request: Context, knowledge: KnowledgeSnapshot, criteria: list[CriterionResult]
):
    validate_context(request, knowledge)
    seen = set()
    identities = set()
    for result in criteria:
        CriterionResult.model_validate(result.model_dump())
        identity = (result.yeu_cau_ca_id, result.tieu_chi_id)
        if result.ket_qua_id in seen or identity in identities:
            raise ValueError("Duplicate C07 finding or criterion/requirement identity")
        seen.add(result.ket_qua_id)
        identities.add(identity)
        if result.ca_id != request.ca_id or result.lan_chay_id != request.run_id:
            raise ValueError("C07 finding case or run mismatch")
        criterion = knowledge.criteria.get(result.tieu_chi_id)
        snapshot = result.tieu_chi_snapshot_json
        if not criterion or any(snapshot.get(k) != v for k, v in criterion.items()):
            raise ValueError("C07 criterion snapshot differs from pinned knowledge")
        if snapshot.get("knowledge_snapshot_sha256") != knowledge.sha256:
            raise ValueError("C07 knowledge snapshot mismatch")
        context = snapshot.get("context")
        expected_context = request.model_dump(
            mode="json", include=set(Context.model_fields) - {"trace_id"}
        )
        if not isinstance(context, dict) or any(
            context.get(key) != value for key, value in expected_context.items()
        ):
            raise ValueError("C07 context/run/snapshot mismatch")
        contract_id = snapshot.get("hop_dong_id")
        if not isinstance(contract_id, str) or not contract_id.strip():
            raise ValueError("C07 contract ownership pin is missing")
        payload = getattr(request, "payload", None)
        if payload is not None and contract_id != payload.hop_dong_id:
            raise ValueError("C07 contract ownership mismatch")
        if result.mandatory != (criterion.get("bat_buoc") is True):
            raise ValueError("C07 mandatory flag differs from pinned criterion")
        allowed_basis = set(knowledge.documents) | set(knowledge.articles) | set(knowledge.versions)
        if any(item not in allowed_basis for item in result.legal_basis_ids):
            raise ValueError("C07 legal basis is outside pinned knowledge")


def _matches(rule: dict, trigger: dict, result: CriterionResult, diagnostics: Diagnostics) -> bool:
    guards = result.gates.model_dump()
    guards.update(
        criterion_id=result.tieu_chi_id,
        criterion_target_only=result.pham_vi_ket_luan == "CURRENT_CRITERION",
        scope_of_facts=result.pham_vi_ket_luan,
        finding=result.finding,
        mandatory_contract_content=(
            result.mandatory
            and result.tieu_chi_snapshot_json.get("noi_dung_bat_buoc_trong_hd") is True
        ),
        any_unresolved_fact=bool(result.uncertainty_reason),
        legal_violation_conclusion=result.finding == "VIOLATED",
        human_approval_required_for_final=result.review_status == "PENDING",
        template_field_unfilled=result.tieu_chi_snapshot_json.get("template_field_unfilled", False),
        excluded=result.excluded,
    )
    unknown = set(trigger) - set(guards) - {"enabled"}
    if unknown:
        diagnostic(diagnostics, "UNSUPPORTED_RISK_GUARD", rule["quy_tac_id"], str(sorted(unknown)))
        return False
    for key, value in trigger.items():
        if key == "enabled":
            continue
        if isinstance(guards[key], bool) and not isinstance(value, bool):
            diagnostic(diagnostics, "INVALID_RISK_GUARD", rule["quy_tac_id"], key)
            return False
        if value != guards[key]:
            return False
    if result.finding == "UNKNOWN":
        return (
            rule.get("hanh_dong") == "REQUEST_VERIFICATION"
            and trigger.get("legal_violation_conclusion") is False
            and trigger.get("any_unresolved_fact") is True
        )
    if rule.get("hanh_dong") != "CREATE_CONDITIONAL_RISK":
        diagnostic(
            diagnostics, "UNSUPPORTED_RISK_ACTION", rule["quy_tac_id"], str(rule.get("hanh_dong"))
        )
        return False
    if result.finding == "MISSING":
        return (
            result.mandatory
            and result.gates.missing_allowed()
            and guards["mandatory_contract_content"]
        )
    return result.finding == "VIOLATED" and result.gates.reliable()


def compliance_risks(
    request: Context,
    knowledge: KnowledgeSnapshot,
    criteria: list[CriterionResult],
    *,
    diagnostics: Diagnostics = None,
) -> list[RiskResult]:
    validate_findings(request, knowledge, criteria)
    risks = []
    for result in criteria:
        if result.excluded or result.finding == "SATISFIED":
            continue
        candidates = [
            rule
            for rule in knowledge.tables.get("quy_tac_rui_ro", [])
            if rule.get("nhanh") == "COMPLIANCE"
            and rule.get("tieu_chi_id") == result.tieu_chi_id
            and rule.get("trigger_status") == result.finding
        ]
        if not candidates:
            diagnostic(
                diagnostics, "MISSING_RISK_RULE", result.ket_qua_id, "No rule for this finding"
            )
        for rule in candidates:
            trigger = rule_trigger(rule, diagnostics)
            if trigger is None or not _matches(rule, trigger, result, diagnostics):
                continue
            risk = make_risk(
                request,
                knowledge,
                rule,
                source=RiskSource(
                    yeu_cau_ca_id=result.yeu_cau_ca_id, ket_qua_tieu_chi_id=result.ket_qua_id
                ),
                source_snapshot=result.model_dump(mode="json"),
                finding=result.finding,
                evidence_ids=[e.doan_id for e in result.evidence]
                + [e.bang_chung_id for e in result.external_evidence],
                legal_basis_ids=result.legal_basis_ids,
                explanation=result.uncertainty_reason or result.giai_thich,
                diagnostics=diagnostics,
            )
            if risk is not None:
                risks.append(risk)
    return deduplicate(risks)
