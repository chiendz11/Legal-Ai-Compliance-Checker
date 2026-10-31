"""Pure run membership checks at the persistence boundary.

Foreign keys prove that an identity exists, not that it belongs to this run.
The writer checks the supplied graph before inserting any normalized output.
"""

import hashlib
import json

from legal_checker.shared.contracts.common import Context
from legal_checker.shared.contracts.pipeline import PipelineRequest, PipelineResponse


def _index(rows, key, label):
    indexed = {getattr(row, key): row for row in rows}
    if len(indexed) != len(rows):
        raise ValueError(f"Duplicate {label} output IDs")
    return indexed


def _runtime_rule(row, json_column):
    """Mirror the reader's JSONB-to-text projection without modifying pinned content."""
    projected = dict(row)
    value = projected[json_column]
    if not isinstance(value, str):
        projected[json_column] = json.dumps(
            value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
        )
    return projected


def validate_membership(request: PipelineRequest, response: PipelineResponse) -> None:
    """Validate contextual links without rerunning reasoning or changing outcomes."""
    if any(getattr(request, key) != getattr(response, key) for key in Context.model_fields):
        raise ValueError("Response context differs from request")
    payload = request.payload
    result = response.payload
    requirements = {row.yeu_cau_ca_id: row for row in payload.requirements}
    chunks = {row.doan_id: row for row in payload.chunks}
    if any(row.hop_dong_id != payload.hop_dong_id for row in chunks.values()):
        raise ValueError("Input chunk belongs to a different contract")
    if any(
        row.ca_id != request.ca_id or row.phien_ban_id != request.phien_ban_id
        for row in requirements.values()
    ):
        raise ValueError("Input requirement belongs to a different case or deployment")
    citations = {row.finding_id: row for row in payload.citations}
    for citation in citations.values():
        if (
            citation.ca_id != request.ca_id
            or citation.lan_chay_id != request.run_id
            or citation.knowledge_version != request.legal_knowledge_version
        ):
            raise ValueError("Input citation case/run/knowledge mismatch")
    for retrieval in payload.retrieval:
        if (
            retrieval.yeu_cau_ca_id not in requirements
            or retrieval.doan_id not in chunks
            or retrieval.lan_chay_id != request.run_id
        ):
            raise ValueError("Input retrieval is outside the case/run")
    criteria = _index(result.criterion_results, "ket_qua_id", "C07")
    aggregates = _index(result.requirement_results, "tuan_thu_id", "C08")
    risks = _index(result.risks, "ket_qua_rui_ro_id", "C10")
    _index(result.recommendations, "khuyen_nghi_ca_id", "C11")
    identities = set()
    context = request.model_dump(mode="json", include=set(Context.model_fields))
    for criterion in criteria.values():
        requirement = requirements.get(criterion.yeu_cau_ca_id)
        snapshot = criterion.tieu_chi_snapshot_json
        if (
            not requirement
            or criterion.ca_id != request.ca_id
            or criterion.lan_chay_id != request.run_id
            or snapshot.get("tieu_chi_id") != criterion.tieu_chi_id
            or snapshot.get("requirement_version_id") != requirement.requirement_version_id
            or snapshot.get("knowledge_snapshot_sha256") != request.knowledge_snapshot_sha256
            or snapshot.get("context") != context
            or snapshot.get("hop_dong_id") != payload.hop_dong_id
            or requirement.version_status != "RESOLVED"
        ):
            raise ValueError("C07 output case/run/requirement/version/snapshot mismatch")
        identity = (criterion.yeu_cau_ca_id, criterion.tieu_chi_id)
        if identity in identities:
            raise ValueError("Duplicate C07 criterion/requirement identity")
        identities.add(identity)
        for evidence in criterion.evidence:
            chunk = chunks.get(evidence.doan_id)
            if (
                not chunk
                or evidence.ky_tu_ket_thuc > len(chunk.noi_dung)
                or chunk.noi_dung[evidence.ky_tu_bat_dau : evidence.ky_tu_ket_thuc]
                != evidence.trich_dan
            ):
                raise ValueError("C07 evidence is outside the contract or quote/offset differs")
        for evidence in criterion.external_evidence:
            matches = [
                registration
                for registration in payload.external_evidence_registry
                if registration.bang_chung_id == evidence.bang_chung_id
                and registration.tieu_chi_id == criterion.tieu_chi_id
                and registration.yeu_cau_ca_id == criterion.yeu_cau_ca_id
            ]
            if len(matches) != 1:
                raise ValueError("C07 external evidence needs one run-bound registration")
            entry = matches[0]
            if (
                entry.object_uri != evidence.object_uri
                or entry.sha256 != evidence.sha256
                or entry.hop_dong_id != payload.hop_dong_id
                or any(getattr(entry, key) != getattr(request, key) for key in Context.model_fields)
                or (evidence.verified and not entry.verified)
            ):
                raise ValueError("C07 external evidence registration context/hash mismatch")
    seen_requirements = set()
    for aggregate in aggregates.values():
        requirement = requirements.get(aggregate.yeu_cau_ca_id)
        snapshot = aggregate.requirement_snapshot_json
        if (
            not requirement
            or aggregate.yeu_cau_ca_id in seen_requirements
            or snapshot.get("knowledge_snapshot_sha256") != request.knowledge_snapshot_sha256
            or snapshot.get("run_id") != request.run_id
            or snapshot.get("phien_ban_id") != request.phien_ban_id
            or snapshot.get("applicable_requirement") != requirement.model_dump(mode="json")
        ):
            raise ValueError("C08 output requirement/run/snapshot mismatch")
        seen_requirements.add(aggregate.yeu_cau_ca_id)
        for finding_id in snapshot.get("evaluated_criterion_result_ids", []):
            if (
                finding_id not in criteria
                or criteria[finding_id].yeu_cau_ca_id != requirement.yeu_cau_ca_id
            ):
                raise ValueError("C08 references a C07 finding outside its requirement/run")
    if not set(result.excluded_requirements) <= set(requirements) or (
        set(result.excluded_requirements) & seen_requirements
    ):
        raise ValueError("Excluded requirements are foreign or also aggregated")
    for risk in risks.values():
        if risk.ca_id != request.ca_id:
            raise ValueError("C10 output belongs to another case")
        source = risk.source
        if source.ket_qua_tieu_chi_id:
            finding = criteria.get(source.ket_qua_tieu_chi_id)
            if (
                not finding
                or source.yeu_cau_ca_id != finding.yeu_cau_ca_id
                or risk.risk_type == "CITATION"
            ):
                raise ValueError("C10 source C07 is outside current run or requirement")
            allowed_evidence = {e.doan_id for e in finding.evidence} | {
                e.bang_chung_id for e in finding.external_evidence
            }
            if not set(risk.evidence_ids) <= allowed_evidence:
                raise ValueError("C10 evidence is outside its C07 source")
            if not set(risk.legal_basis_ids) <= set(finding.legal_basis_ids):
                raise ValueError("C10 legal basis is outside its C07 source")
        else:
            finding = citations.get(source.citation_finding_id)
            if not finding or source.yeu_cau_ca_id or risk.risk_type == "COMPLIANCE":
                raise ValueError("C10 source C09 is outside current run or branch")
        if risk.rule_snapshot_json.get("context") != context or risk.rule_snapshot_json.get(
            "source_finding_snapshot"
        ) != finding.model_dump(mode="json"):
            raise ValueError("C10 source/context snapshot differs from current run")
    for recommendation in result.recommendations:
        risk = risks.get(recommendation.ket_qua_rui_ro_id)
        if (
            not risk
            or recommendation.knowledge_snapshot_sha256 != request.knowledge_snapshot_sha256
            or not set(recommendation.evidence_ids) <= set(risk.evidence_ids)
            or not set(recommendation.legal_basis_ids) <= set(risk.legal_basis_ids)
            or recommendation.template_snapshot_json.get("context") != context
            or recommendation.dieu_kien_snapshot.get("risk_source")
            != risk.source.model_dump(mode="json")
            or recommendation.dieu_kien_snapshot.get("risk_rule_snapshot")
            != risk.rule_snapshot_json
        ):
            raise ValueError("C11 source risk/snapshot/provenance differs from current run")


def validate_pinned_knowledge(request, response, content) -> None:
    """Check identities against the immutable snapshot, not current mutable tables."""
    checksum = hashlib.sha256(
        json.dumps(content, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    ).hexdigest()
    if checksum != request.knowledge_snapshot_sha256:
        raise ValueError("Stored knowledge snapshot checksum is invalid")
    tables = content["tables"]
    criteria = {row["tieu_chi_id"]: row for row in tables["tieu_chi_danh_gia"]}
    versions = {row["requirement_version_id"]: row for row in tables["phien_ban_yeu_cau"]}
    risks = {row["rui_ro_id"]: row for row in tables["danh_muc_rui_ro"]}
    templates = {row["khuyen_nghi_id"]: row for row in tables["danh_muc_khuyen_nghi"]}
    decisions = {
        row["quy_tac_id"]: _runtime_rule(row, "dieu_kien_json")
        for row in tables["quy_tac_quyet_dinh"]
    }
    policies = {row["quy_tac_tong_hop_id"]: row for row in tables["quy_tac_tong_hop"]}
    risk_rules = {
        row["quy_tac_id"]: _runtime_rule(row, "trigger_json") for row in tables["quy_tac_rui_ro"]
    }
    mappings = {row["lien_ket_id"]: row for row in tables["rui_ro_khuyen_nghi"]}
    for requirement in request.payload.requirements:
        if requirement.requirement_version_id:
            version = versions.get(requirement.requirement_version_id)
            if not version or version["requirement_id"] != requirement.requirement_id:
                raise ValueError("Input requirement version differs from pinned knowledge")
    owners = {row.yeu_cau_ca_id: row for row in request.payload.requirements}
    for retrieval in request.payload.retrieval:
        criterion = criteria.get(retrieval.tieu_chi_id)
        if (
            not criterion
            or criterion["requirement_version_id"]
            != owners[retrieval.yeu_cau_ca_id].requirement_version_id
        ):
            raise ValueError("Input retrieval criterion differs from pinned requirement version")
    for result in response.payload.criterion_results:
        criterion = criteria.get(result.tieu_chi_id)
        if not criterion or any(
            result.tieu_chi_snapshot_json.get(key) != value for key, value in criterion.items()
        ):
            raise ValueError("C07 criterion content differs from pinned knowledge")
        decision = result.tieu_chi_snapshot_json.get("decision_rule_snapshot_json")
        if decision is not None and (
            not isinstance(decision, dict)
            or decision != decisions.get(decision.get("quy_tac_id"))
            or decision.get("tieu_chi_id") != result.tieu_chi_id
        ):
            raise ValueError("C07 decision rule differs from pinned knowledge")
    for result in response.payload.requirement_results:
        version_id = owners[result.yeu_cau_ca_id].requirement_version_id
        if result.requirement_snapshot_json.get("requirement_version") != versions.get(version_id):
            raise ValueError("C08 requirement version content differs from pinned knowledge")
        version = versions.get(version_id) or {}
        policy = policies.get(version.get("quy_tac_tong_hop_id"))
        if result.requirement_snapshot_json.get("aggregation_policy") != policy:
            raise ValueError("C08 aggregation policy differs from pinned knowledge")
    for result in response.payload.risks:
        if result.risk_snapshot != risks.get(result.rui_ro_id):
            raise ValueError("C10 catalog snapshot differs from pinned knowledge")
        rule = risk_rules.get(result.quy_tac_id)
        snapshot = result.rule_snapshot_json
        if not rule or any(snapshot.get(key) != value for key, value in rule.items()):
            raise ValueError("C10 rule snapshot differs from pinned knowledge")
        matches = snapshot.get("matched_rules")
        if not isinstance(matches, list) or not matches or rule not in matches:
            raise ValueError("C10 matched rules differ from pinned knowledge")
        for match in matches:
            if not isinstance(match, dict) or match != risk_rules.get(match.get("quy_tac_id")):
                raise ValueError("C10 matched rule differs from pinned knowledge")
    for result in response.payload.recommendations:
        template = templates.get(result.khuyen_nghi_id)
        if not template or any(
            result.template_snapshot_json.get(key) != value for key, value in template.items()
        ):
            raise ValueError("C11 template content differs from pinned knowledge")
        links = result.template_snapshot_json.get("mapping_snapshots")
        risk = next(
            row
            for row in response.payload.risks
            if row.ket_qua_rui_ro_id == result.ket_qua_rui_ro_id
        )
        if not isinstance(links, list) or not links:
            raise ValueError("C11 mappings differ from pinned knowledge")
        for link in links:
            if (
                not isinstance(link, dict)
                or link != mappings.get(link.get("lien_ket_id"))
                or link.get("rui_ro_id") != risk.rui_ro_id
                or link.get("khuyen_nghi_id") != result.khuyen_nghi_id
            ):
                raise ValueError("C11 mapping differs from pinned knowledge")
