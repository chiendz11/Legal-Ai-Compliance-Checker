"""Independent C09 → C10 branch; citation findings never change C07/C08."""

from legal_checker.modules.legal_knowledge.models import KnowledgeSnapshot
from legal_checker.modules.risks.policy import (
    Diagnostics,
    deduplicate,
    diagnostic,
    make_risk,
    rule_trigger,
)
from legal_checker.shared.contracts.citation import CitationValidation
from legal_checker.shared.contracts.common import Context
from legal_checker.shared.contracts.risk import RiskResult, RiskSource
from legal_checker.shared.validation import validate_citations, validate_context

PRODUCTION_GATE = "NON_UNKNOWN_REQUIRES_VERIFIED_FINDING_AND_REVIEWED_KNOWLEDGE"
# These flags constrain what this mapper does; they are not evidence attestations.
STRUCTURAL_GUARDS = {
    "backend_adapter_required",
    "no_automatic_compliance_effect",
    "demo_override_requires_explicit_mode",
    "db_no_match_alone_is_not_invalid",
    "current_expiry_alone_is_not_trigger",
}
ATTESTATIONS = {
    "identity_confirmed",
    "temporal_source_complete",
    "transition_context_resolved",
    "context_mismatch_proven",
    "identity_or_context_invalidity_proven",
}


def _matches(rule, trigger, finding, knowledge, diagnostics):
    supported = (
        {
            "enabled",
            "schema",
            "branch",
            "citation_status",
            "reason_code",
            "domain_status",
            "domain_status_not",
            "knowledge_version",
            "production_gate",
            "relevant_date_required",
            "official_evidence_required",
            "no_violation_assertion",
            "missing_or_ambiguous_identity_date_source_or_domain",
            "finding_verified",
        }
        | STRUCTURAL_GUARDS
        | ATTESTATIONS
    )
    unknown = set(trigger) - supported
    if unknown:
        diagnostic(
            diagnostics, "UNSUPPORTED_CITATION_GUARD", rule["quy_tac_id"], str(sorted(unknown))
        )
        return False
    if trigger.get("schema") != "CITATION_RULE_V1_1" or trigger.get("branch") != "CITATION":
        diagnostic(
            diagnostics, "UNSUPPORTED_CITATION_POLICY", rule["quy_tac_id"], "Unknown schema/branch"
        )
        return False
    if trigger.get("production_gate") != PRODUCTION_GATE:
        diagnostic(
            diagnostics,
            "UNSUPPORTED_CITATION_POLICY",
            rule["quy_tac_id"],
            "Unknown production gate",
        )
        return False
    if "knowledge_version" in trigger and (
        not isinstance(trigger["knowledge_version"], str)
        or not trigger["knowledge_version"].strip()
    ):
        diagnostic(diagnostics, "INVALID_CITATION_GUARD", rule["quy_tac_id"], "knowledge_version")
        return False
    if rule.get("hanh_dong") != "CREATE_CITATION_RISK":
        diagnostic(
            diagnostics, "UNSUPPORTED_RISK_ACTION", rule["quy_tac_id"], "Unknown citation action"
        )
        return False
    for key in STRUCTURAL_GUARDS:
        if key in trigger and trigger[key] is not True:
            diagnostic(diagnostics, "UNSUPPORTED_CITATION_POLICY", rule["quy_tac_id"], key)
            return False
    for key, actual in {
        "citation_status": finding.status,
        "reason_code": finding.reason_code,
        "domain_status": finding.domain_status,
        "finding_verified": finding.finding_verified,
    }.items():
        if key == "finding_verified" and key in trigger and type(trigger[key]) is not bool:
            diagnostic(diagnostics, "INVALID_CITATION_GUARD", rule["quy_tac_id"], key)
            return False
        if key in trigger and trigger[key] != actual:
            return False
    if trigger.get("domain_status_not") == finding.domain_status:
        return False
    source = finding.source_snapshot_json
    for key in ATTESTATIONS:
        if key in trigger and (trigger[key] is not True or source.get(key) is not True):
            diagnostic(diagnostics, "CITATION_GUARD_UNVERIFIED", finding.finding_id, key)
            return False
    for key in (
        "relevant_date_required",
        "official_evidence_required",
        "no_violation_assertion",
        "missing_or_ambiguous_identity_date_source_or_domain",
    ):
        if key in trigger and type(trigger[key]) is not bool:
            diagnostic(diagnostics, "INVALID_CITATION_GUARD", rule["quy_tac_id"], key)
            return False
    if trigger.get("relevant_date_required") and finding.relevant_date is None:
        return False
    if (
        trigger.get("official_evidence_required")
        and source.get("official_evidence_verified") is not True
    ):
        diagnostic(
            diagnostics,
            "CITATION_GUARD_UNVERIFIED",
            finding.finding_id,
            "official_evidence_verified",
        )
        return False
    if finding.status == "UNKNOWN":
        return (
            trigger.get("no_violation_assertion") is True
            and trigger.get("missing_or_ambiguous_identity_date_source_or_domain") is True
            and bool(finding.ly_do.strip())
        )
    if not finding.finding_verified or source.get("reviewed_knowledge") is not True:
        diagnostic(
            diagnostics,
            "CITATION_PRODUCTION_GATE",
            finding.finding_id,
            "Verified finding and reviewed knowledge required",
        )
        return False
    document = knowledge.documents.get(finding.normalized_van_ban_id)
    # An explicit false review flag in the pinned source cannot be overridden by C09.
    if document is not None and document.get("human_verified") is False:
        diagnostic(
            diagnostics,
            "CITATION_PRODUCTION_GATE",
            finding.finding_id,
            "Pinned source is unreviewed",
        )
        return False
    return finding.status in {"STALE", "INVALID"}


def citation_risks(
    request: Context,
    knowledge: KnowledgeSnapshot,
    citations: list[CitationValidation],
    *,
    diagnostics: Diagnostics = None,
) -> list[RiskResult]:
    validate_context(request, knowledge)
    validate_citations(request, citations)
    risks = []
    for finding in citations:
        CitationValidation.model_validate(finding.model_dump())
        source = finding.source_snapshot_json
        missing_provenance = []
        if "knowledge_snapshot_sha256" not in source:
            missing_provenance.append("knowledge_snapshot_sha256")
        elif source["knowledge_snapshot_sha256"] != knowledge.sha256:
            raise ValueError("C09 knowledge snapshot mismatch")
        if "context" not in source:
            missing_provenance.append("context")
        else:
            context = source["context"]
            expected_context = request.model_dump(
                mode="json", include=set(Context.model_fields) - {"trace_id"}
            )
            if not isinstance(context, dict) or any(
                context.get(key) != value for key, value in expected_context.items()
            ):
                raise ValueError("C09 context/run/snapshot mismatch")
        contract_id = source.get("hop_dong_id")
        if "hop_dong_id" not in source:
            missing_provenance.append("hop_dong_id")
        elif not isinstance(contract_id, str) or not contract_id.strip():
            raise ValueError("C09 contract ownership pin is invalid")
        payload = getattr(request, "payload", None)
        if payload is not None and contract_id is not None and contract_id != payload.hop_dong_id:
            raise ValueError("C09 contract ownership mismatch")
        if missing_provenance:
            diagnostic(
                diagnostics,
                "C09_PROVENANCE_UNAVAILABLE",
                finding.finding_id,
                "Missing upstream provenance: " + ", ".join(missing_provenance),
            )
            if finding.status in {"STALE", "INVALID"}:
                continue
        if finding.status == "VALID":
            continue
        candidates = [
            rule
            for rule in knowledge.tables.get("quy_tac_rui_ro", [])
            if rule.get("nhanh") == "CITATION" and rule.get("trigger_status") == finding.status
        ]
        if not candidates:
            diagnostic(diagnostics, "MISSING_RISK_RULE", finding.finding_id, "No citation rule")
        for rule in candidates:
            trigger = rule_trigger(rule, diagnostics)
            if trigger is None or not _matches(rule, trigger, finding, knowledge, diagnostics):
                continue
            evidence_ids = source.get("evidence_ids", [finding.vien_dan_id])
            basis = source.get("legal_basis_ids", [])
            if not isinstance(evidence_ids, list) or not all(
                isinstance(x, str) for x in evidence_ids
            ):
                raise ValueError("C09 evidence IDs must be a list of strings")
            if not isinstance(basis, list) or not all(isinstance(x, str) for x in basis):
                raise ValueError("C09 legal basis IDs must be a list of strings")
            allowed_basis = (
                set(knowledge.documents) | set(knowledge.articles) | set(knowledge.versions)
            )
            if any(item not in allowed_basis for item in basis):
                raise ValueError("C09 legal basis is outside pinned knowledge")
            if finding.normalized_van_ban_id in knowledge.documents:
                basis = [*basis, finding.normalized_van_ban_id]
            risk = make_risk(
                request,
                knowledge,
                rule,
                source=RiskSource(citation_finding_id=finding.finding_id),
                source_snapshot=finding.model_dump(mode="json"),
                finding=finding.status,
                evidence_ids=evidence_ids,
                legal_basis_ids=basis,
                explanation=finding.ly_do,
                diagnostics=diagnostics,
            )
            if risk is not None:
                risks.append(risk)
    return deduplicate(risks)
