from datetime import date

from app.application.ports.knowledge import KnowledgeSnapshot
from app.contracts.pipeline import PipelineRequest
from app.contracts.reasoning import ReasoningRequest


def validate_request(request: PipelineRequest | ReasoningRequest, knowledge: KnowledgeSnapshot):
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
    for citation in getattr(payload, "citations", []):
        if (
            citation.ca_id != request.ca_id
            or citation.knowledge_version != request.legal_knowledge_version
            or citation.lan_chay_id != request.run_id
        ):
            raise ValueError("Citation case, run or knowledge version mismatch")
