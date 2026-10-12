import json

from app.application.ports.knowledge import KnowledgeSnapshot
from app.contracts.common import Context
from app.contracts.reasoning import CriterionResult
from app.contracts.risk import RiskResult, RiskSource
from app.core.ids import stable_id


def _risk(request, knowledge, rule, source, reason, evidence, basis, risk_type):
    catalog = knowledge.risks[rule["rui_ro_id"]]
    source_id = source.ket_qua_tieu_chi_id or source.citation_finding_id
    return RiskResult(
        ket_qua_rui_ro_id=stable_id(request, "RISK", rule["quy_tac_id"] + source_id),
        ca_id=request.ca_id,
        risk_type=risk_type,
        rui_ro_id=catalog["rui_ro_id"],
        severity=catalog["muc_do_co_so"],
        source=source,
        quy_tac_id=rule["quy_tac_id"],
        giai_thich=reason,
        risk_snapshot=catalog,
        rule_snapshot_json=rule,
        evidence_ids=evidence,
        legal_basis_ids=basis,
    )


def compliance_risks(
    request: Context, knowledge: KnowledgeSnapshot, criteria: list[CriterionResult]
):
    results = []
    for criterion in criteria:
        if criterion.excluded or criterion.finding == "SATISFIED":
            continue
        for rule in knowledge.tables["quy_tac_rui_ro"]:
            if (
                rule["nhanh"] != "COMPLIANCE"
                or rule["tieu_chi_id"] != criterion.tieu_chi_id
                or rule["trigger_status"] != criterion.finding
            ):
                continue
            trigger = json.loads(rule["trigger_json"])
            if trigger.get("enabled") is not True:
                continue
            # Recheck workbook gates; callers cannot turn a retrieval miss into a risk.
            gate_values = criterion.gates.model_dump()
            gate_values["mandatory_contract_content"] = criterion.tieu_chi_snapshot_json[
                "mandatory_contract_content"
            ]
            gate_values["template_field_unfilled"] = False
            if any(k in trigger and trigger[k] != v for k, v in gate_values.items()):
                continue
            verification = criterion.finding == "UNKNOWN"
            results.append(
                _risk(
                    request,
                    knowledge,
                    rule,
                    RiskSource(
                        yeu_cau_ca_id=criterion.yeu_cau_ca_id,
                        ket_qua_tieu_chi_id=criterion.ket_qua_id,
                    ),
                    criterion.uncertainty_reason or criterion.giai_thich,
                    [e.doan_id for e in criterion.evidence]
                    + [e.bang_chung_id for e in criterion.external_evidence],
                    criterion.legal_basis_ids,
                    "VERIFICATION" if verification else "COMPLIANCE",
                )
            )
    return results


def citation_risks(request: Context, knowledge: KnowledgeSnapshot, citations):
    results = []
    rules = {
        r["quy_tac_id"]: r for r in knowledge.tables["quy_tac_rui_ro"] if r["nhanh"] == "CITATION"
    }
    for citation in citations:
        metadata = citation.source_snapshot_json
        reliable = (
            citation.finding_verified
            and citation.domain_status != "UNKNOWN"
            and citation.relevant_date is not None
            and metadata.get("reviewed_knowledge") is True
        )
        status = citation.status
        if status == "STALE":
            reliable = reliable and all(
                metadata.get(k) is True
                for k in (
                    "identity_confirmed",
                    "temporal_source_complete",
                    "transition_context_resolved",
                )
            )
        elif status == "INVALID":
            reliable = reliable and metadata.get("official_evidence_required") is True
            proof = (
                "context_mismatch_proven"
                if citation.domain_status == "MISMATCH"
                else "identity_or_context_invalidity_proven"
            )
            reliable = reliable and metadata.get(proof) is True
        elif status == "VALID":
            reliable = reliable and citation.domain_status == "MATCH"
        if status == "UNKNOWN" or not reliable:
            key = "RULE_CITATION_UNKNOWN"
            risk_type = "VERIFICATION"
        elif status == "VALID":
            # Historical VALID remains VALID even if current_status is REPEALED.
            continue
        elif status == "STALE":
            key, risk_type = "RULE_CITATION_STALE", "CITATION"
        elif citation.domain_status == "MISMATCH":
            if citation.reason_code != "DOMAIN_MISMATCH":
                raise ValueError("Domain mismatch requires DOMAIN_MISMATCH reason code")
            key, risk_type = "RULE_CITATION_DOMAIN_MISMATCH", "CITATION"
        else:
            key, risk_type = "RULE_CITATION_INVALID", "CITATION"
        basis = [
            v
            for v in (citation.normalized_van_ban_id, citation.replacement_van_ban_id)
            if v in knowledge.documents
        ]
        results.append(
            _risk(
                request,
                knowledge,
                rules[key],
                RiskSource(citation_finding_id=citation.finding_id),
                citation.ly_do if reliable else "Citation requires verification: " + citation.ly_do,
                list(metadata.get("evidence_ids", [])),
                basis,
                risk_type,
            )
        )
    return results


def aggregate_risks(request, knowledge, criteria, citations):
    # Separate source IDs remain visible; no mutation of compliance results.
    return compliance_risks(request, knowledge, criteria) + citation_risks(
        request, knowledge, citations
    )
