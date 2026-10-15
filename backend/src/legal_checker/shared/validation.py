from datetime import date

from legal_checker.modules.legal_knowledge.models import KnowledgeSnapshot
from legal_checker.shared.contracts.citation import CitationValidation
from legal_checker.shared.contracts.common import Context
from legal_checker.shared.contracts.pipeline import PipelineRequest
from legal_checker.shared.contracts.reasoning import ReasoningRequest
from legal_checker.shared.contracts.temporal import ApplicableRequirement


def validate_context(context: Context, knowledge: KnowledgeSnapshot):
    if context.knowledge_snapshot_sha256 != knowledge.sha256:
        raise ValueError("Knowledge snapshot checksum differs from the pinned case")


def validate_requirements(
    context: Context, requirements: list[ApplicableRequirement], knowledge: KnowledgeSnapshot
):
    case_ids = [r.yeu_cau_ca_id for r in requirements]
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("Duplicate applicable requirement IDs")
    if len({r.requirement_id for r in requirements}) != len(requirements):
        raise ValueError("Only one resolved entry per requirement family is permitted")
    for requirement in requirements:
        if requirement.ca_id != context.ca_id or requirement.phien_ban_id != context.phien_ban_id:
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


def validate_citations(context: Context, citations: list[CitationValidation]):
    ids = [c.finding_id for c in citations]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate citation finding IDs")
    for citation in citations:
        if (
            citation.ca_id != context.ca_id
            or citation.knowledge_version != context.legal_knowledge_version
            or citation.lan_chay_id != context.run_id
        ):
            raise ValueError("Citation case, run or knowledge version mismatch")


def validate_request(request: PipelineRequest | ReasoningRequest, knowledge: KnowledgeSnapshot):
    validate_context(request, knowledge)
    payload = request.payload
    validate_requirements(request, payload.requirements, knowledge)
    validate_citations(request, getattr(payload, "citations", []))
    allowed = {
        c["tieu_chi_id"]
        for r in payload.requirements
        for c in knowledge.criteria_for(r.requirement_version_id)
    }
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
