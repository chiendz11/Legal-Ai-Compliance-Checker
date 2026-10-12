import json

from app.application.ports.knowledge import KnowledgeSnapshot
from app.contracts.reasoning import CriterionResult, Observation, ReasoningRequest
from app.core.ids import stable_id
from app.core.validation import validate_request
from app.modules.compliance_reasoning.numeric_rules import numeric_finding


def reason(request: ReasoningRequest, knowledge: KnowledgeSnapshot) -> list[CriterionResult]:
    validate_request(request, knowledge)
    observations = {o.tieu_chi_id: o for o in request.payload.observations}
    chunks = {c.doan_id: c for c in request.payload.chunks}
    results = []
    for requirement in request.payload.requirements:
        if requirement.applicability_status == "NOT_APPLICABLE":
            continue
        for criterion in knowledge.criteria_for(requirement.requirement_version_id):
            cid = criterion["tieu_chi_id"]
            obs = observations.get(cid) or Observation(
                tieu_chi_id=cid, giai_thich="No observation supplied"
            )
            gates = obs.gates.model_copy(deep=True)
            gates.scope_confirmed = gates.scope_confirmed and requirement.confirmed
            gates.version_resolved = gates.version_resolved and requirement.confirmed
            legal_basis = knowledge.legal_basis(criterion)
            gates.source_verified = gates.source_verified and bool(legal_basis)
            selected = {
                r.doan_id
                for r in request.payload.retrieval
                if r.yeu_cau_ca_id == requirement.yeu_cau_ca_id
                and r.tieu_chi_id == cid
                and r.duoc_chon
                and r.giai_doan == "FINAL"
            }
            valid_quotes = all(
                e.doan_id in selected
                and e.doan_id in chunks
                and e.ky_tu_ket_thuc <= len(chunks[e.doan_id].noi_dung)
                and chunks[e.doan_id].noi_dung[e.ky_tu_bat_dau : e.ky_tu_ket_thuc] == e.trich_dan
                for e in obs.evidence
            )
            external_valid = all(e.verified for e in obs.external_evidence)
            gates.evidence_validated = gates.evidence_validated and valid_quotes and external_valid
            excluded = (
                obs.local_applicability == "NO_MATCH"
                and bool(obs.exclusion_reason)
                and requirement.confirmed
                and gates.reliable()
            )
            finding = obs.proposed_finding
            explanation = obs.giai_thich
            uncertainty = None
            decision = knowledge.decision(cid, finding)
            rule = json.loads(decision["dieu_kien_json"])
            numeric = rule.get("numeric_rule")
            if not requirement.confirmed or obs.local_applicability == "UNKNOWN":
                finding, uncertainty = (
                    "UNKNOWN",
                    "Scope, version or criterion applicability unresolved",
                )
            elif excluded:
                finding, uncertainty = (
                    "UNKNOWN",
                    "Excluded from aggregation: " + obs.exclusion_reason,
                )
            elif obs.local_applicability == "NO_MATCH":
                finding, uncertainty = "UNKNOWN", "Criterion exclusion is not verified"
            elif not gates.reliable() or obs.template_field_unfilled:
                finding, uncertainty = (
                    "UNKNOWN",
                    "Unresolved source, evidence, exception or draft field",
                )
            elif numeric:
                finding, explanation = numeric_finding(cid, numeric, obs)
                if finding == "UNKNOWN":
                    uncertainty = explanation
            elif finding == "MISSING":
                absence_policy = bool(
                    gates.missing_allowed()
                    and obs.mandatory_confirmed
                    and criterion["noi_dung_bat_buoc_trong_hd"]
                    and obs.all_pages_readable
                    and obs.all_related_documents_received
                    and rule.get("enabled") is True
                )
                if not absence_policy:
                    finding, uncertainty = (
                        "UNKNOWN",
                        "Absence not verified for mandatory contract content",
                    )
            if finding in ("SATISFIED", "VIOLATED") and not (obs.evidence or obs.external_evidence):
                finding, uncertainty = "UNKNOWN", "No attributable content evidence"
            if finding == "UNKNOWN" and not uncertainty:
                uncertainty = obs.giai_thich
            # Snapshot the rule actually used after any uncertainty downgrade.
            decision = knowledge.decision(cid, finding)
            results.append(
                CriterionResult(
                    ket_qua_id=stable_id(request, "KQ", requirement.yeu_cau_ca_id + cid),
                    ca_id=request.ca_id,
                    yeu_cau_ca_id=requirement.yeu_cau_ca_id,
                    tieu_chi_id=cid,
                    finding=finding,
                    giai_thich=explanation,
                    gates=gates,
                    uncertainty_reason=uncertainty,
                    evidence=obs.evidence,
                    external_evidence=obs.external_evidence,
                    legal_basis_ids=legal_basis,
                    tieu_chi_snapshot_json={
                        "criterion": criterion,
                        "decision_rule": decision,
                        "mandatory_contract_content": obs.mandatory_confirmed,
                        "observation": obs.model_dump(mode="json"),
                    },
                    model_version=obs.model_version,
                    prompt_version=obs.prompt_version,
                    lan_chay_id=request.run_id,
                    mandatory=bool(criterion["bat_buoc"]),
                    excluded=excluded,
                    exclusion_reason=obs.exclusion_reason if excluded else None,
                )
            )
    return results
