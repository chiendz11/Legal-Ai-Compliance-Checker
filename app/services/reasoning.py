import json
from datetime import date
from decimal import Decimal, InvalidOperation
from uuid import NAMESPACE_URL, uuid5

from app.contracts.models import CriterionResult, Observation, PipelineRequest
from app.knowledge import Knowledge


def stable_id(request: PipelineRequest, kind: str, key: str) -> str:
    return f"{kind}_{uuid5(NAMESPACE_URL, f'{request.ca_id}/{request.run_id}/{kind}/{key}')}"


def numeric_finding(criterion_id: str, rule: dict, observation: Observation):
    """Use Decimal and explicit, verified fields; absent values never become zero."""
    facts = observation.facts
    if not observation.facts_verified:
        return "UNKNOWN", "Numeric facts have not been verified"
    if facts.get("scope") != rule.get("scope") and rule.get("scope"):
        return "UNKNOWN", "Numeric scope is unresolved"

    def amount(name):
        v = facts.get(name)
        if v is None or isinstance(v, bool):
            raise ValueError(f"Missing numeric fact: {name}")
        d = Decimal(str(v))
        if not d.is_finite() or d < 0:
            raise ValueError(f"Invalid numeric fact: {name}")
        return d

    def ratio(numerator, denominator):
        den = amount(denominator)
        if den <= 0:
            raise ValueError("Denominator must be positive")
        return numerator / den

    try:
        if "first_payment_including_deposit_lte_ratio" in rule:
            first = amount("first_payment")
            deposit = amount("deposit")
            included = facts.get("deposit_included_in_first_payment")
            if type(included) is not bool:
                raise ValueError("Deposit inclusion must be explicitly known")
            value = ratio(first + (Decimal(0) if included else deposit), "contract_price")
            passed = value <= Decimal(str(rule["first_payment_including_deposit_lte_ratio"]))
        elif "prehandover_cumulative_lte_ratio" in rule:
            foreign = facts.get("foreign_seller_art10_4")
            if type(foreign) is not bool:
                raise ValueError("Seller classification is unresolved")
            value = ratio(amount("prehandover_cumulative"), "contract_price")
            limit = rule[
                "foreign_seller_art10_4_lte_ratio"
                if foreign
                else "prehandover_cumulative_lte_ratio"
            ]
            passed = value <= Decimal(str(limit))
        elif "before_certificate_cumulative_lte_ratio" in rule:
            value = ratio(amount("before_certificate_cumulative"), "contract_price")
            passed = value <= Decimal(str(rule["before_certificate_cumulative_lte_ratio"]))
        elif "maintenance_ratio" in rule:
            value = ratio(amount("maintenance_amount"), "maintenance_base_price")
            separate = facts.get("separate_from_sale_price")
            if type(separate) is not bool:
                raise ValueError("Maintenance separation is unknown")
            passed = value == Decimal(str(rule["maintenance_ratio"])) and separate
        elif "warranty_min_months" in rule:
            if facts.get("warranty_start") != rule["start"]:
                raise ValueError("Warranty starting event is not resolved")
            value = amount("warranty_months")
            passed = value >= Decimal(str(rule["warranty_min_months"]))
        elif "application_submission_max_days" in rule:
            if facts.get("deadline_start") != rule["start"]:
                raise ValueError("Deadline starting event is not resolved")
            if facts.get("buyer_voluntarily_self_files") is not False:
                raise ValueError("Self-filing exception must be resolved upstream")
            value = amount("application_submission_days")
            passed = value <= Decimal(str(rule["application_submission_max_days"]))
        elif "deposit_lte_ratio" in rule:
            if criterion_id.endswith("DEPOSIT_CAP"):
                value = ratio(amount("deposit"), "sale_price")
                passed = value <= Decimal(str(rule["deposit_lte_ratio"]))
            elif criterion_id.endswith("DEPOSIT_ELIGIBLE"):
                value = facts.get("eligible_before_collection")
                if type(value) is not bool:
                    raise ValueError("Collection eligibility is unresolved")
                passed = value
            elif criterion_id.endswith("DEPOSIT_PRICE"):
                value = facts.get("sale_price_agreed")
                if type(value) is not bool:
                    raise ValueError("Agreed sale price is unresolved")
                passed = value
            else:
                raise ValueError("Unsupported deposit criterion")
        else:
            raise ValueError("Unsupported numeric rule")
    except (ValueError, InvalidOperation) as exc:
        return "UNKNOWN", str(exc)
    return ("SATISFIED" if passed else "VIOLATED"), f"Verified numeric check: {value}"


def validate_request(request: PipelineRequest, knowledge: Knowledge):
    if request.knowledge_snapshot_sha256 != knowledge.sha256:
        raise ValueError("Knowledge snapshot checksum differs from the pinned case")
    payload = request.payload
    allowed = set()
    for requirement in payload.requirements:
        if requirement.ca_id != request.ca_id or requirement.phien_ban_id != request.phien_ban_id:
            raise ValueError("Requirement belongs to a different case or deployment")
        if requirement.requirement_version_id:
            version = knowledge.versions.get(requirement.requirement_version_id)
            if not version or version["requirement_id"] != requirement.requirement_id:
                raise ValueError("Requirement/version identity mismatch")
            if requirement.confirmed:
                start = version.get("hieu_luc_tu")
                end = version.get("hieu_luc_den")
                relevant = requirement.moc_ap_dung
                if (start and relevant < date.fromisoformat(str(start)[:10])) or (
                    end and relevant >= date.fromisoformat(str(end)[:10])
                ):
                    raise ValueError("Resolved version is outside the [from, to) effective range")
            allowed.update(
                r["tieu_chi_id"] for r in knowledge.criteria_for(requirement.requirement_version_id)
            )
    if len({r.requirement_id for r in payload.requirements}) != len(payload.requirements):
        raise ValueError("Only one resolved entry per requirement family is permitted")
    if any(o.tieu_chi_id not in allowed for o in payload.observations):
        raise ValueError("Observation refers to a criterion outside the checklist")
    chunk_ids = {c.doan_id for c in payload.chunks}
    requirements = {r.yeu_cau_ca_id: r for r in payload.requirements}
    for chunk in payload.chunks:
        if chunk.hop_dong_id != payload.hop_dong_id:
            raise ValueError("Chunk belongs to a different contract")
    for retrieval in payload.retrieval:
        req = requirements.get(retrieval.yeu_cau_ca_id)
        criterion = knowledge.criteria.get(retrieval.tieu_chi_id)
        if (
            not req
            or not criterion
            or retrieval.doan_id not in chunk_ids
            or criterion["requirement_version_id"] != req.requirement_version_id
        ):
            raise ValueError("Retrieval references a foreign criterion, requirement or chunk")
        if retrieval.lan_chay_id != request.run_id:
            raise ValueError("Retrieval run does not match envelope")
    for citation in payload.citations:
        if (
            citation.ca_id != request.ca_id
            or citation.knowledge_version != request.legal_knowledge_version
            or citation.lan_chay_id != request.run_id
        ):
            raise ValueError("Citation case, run or knowledge version mismatch")


def reason(request: PipelineRequest, knowledge: Knowledge) -> list[CriterionResult]:
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
