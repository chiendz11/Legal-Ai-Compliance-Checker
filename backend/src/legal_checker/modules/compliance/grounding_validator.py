"""Pure C07 handoff checks; malformed ownership fails, missing support stays uncertain."""

from legal_checker.modules.legal_knowledge.models import KnowledgeSnapshot
from legal_checker.shared.contracts.reasoning import ReasoningRequest
from legal_checker.shared.validation import validate_request


def validate_criteria(
    request: ReasoningRequest, knowledge: KnowledgeSnapshot, complete: bool = False
) -> dict[str, list[str]]:
    """Validate IDs/quotes and return unresolved provenance per checklist criterion.

    Empty retrieval is not absence proof. `complete=True` also reports missing
    observations; neither mode invents observations or requires fake absence quotes.
    External registrations are backend attestations, never provider declarations.
    """
    request = ReasoningRequest.model_validate(request.model_dump())
    validate_request(request, knowledge)
    owners = {}
    for requirement in request.payload.requirements:
        if requirement.requirement_version_id is None:
            continue
        for criterion in knowledge.criteria_for(requirement.requirement_version_id):
            criterion_id = criterion.get("tieu_chi_id")
            if (
                not criterion_id
                or criterion_id in owners
                or criterion.get("requirement_version_id") != requirement.requirement_version_id
                or knowledge.criteria.get(criterion_id) != criterion
            ):
                raise ValueError("Knowledge criteria contain duplicate IDs or a foreign version")
            owners[criterion_id] = requirement.yeu_cau_ca_id
    issues = {key: [] for key in owners}
    chunks = {chunk.doan_id: chunk for chunk in request.payload.chunks}
    selected = {
        (row.yeu_cau_ca_id, row.tieu_chi_id, row.doan_id)
        for row in request.payload.retrieval
        if row.duoc_chon and row.giai_doan == "FINAL"
    }
    registry = {}
    for registration in request.payload.external_evidence_registry:
        if (
            any(
                getattr(registration, key) != getattr(request, key)
                for key in (
                    "ca_id",
                    "phien_ban_id",
                    "run_id",
                    "rule_version",
                    "legal_knowledge_version",
                    "knowledge_snapshot_sha256",
                )
            )
            or registration.hop_dong_id != request.payload.hop_dong_id
        ):
            raise ValueError("External registry case/contract/deployment/run/snapshot mismatch")
        if owners.get(registration.tieu_chi_id) != registration.yeu_cau_ca_id:
            raise ValueError("External registry criterion/requirement ownership mismatch")
        key = (registration.tieu_chi_id, registration.bang_chung_id)
        if key in registry:
            raise ValueError("Duplicate external evidence registration")
        registry[key] = registration
    present = set()
    for observation in request.payload.observations:
        criterion_id = observation.tieu_chi_id
        if criterion_id not in owners:
            raise ValueError("Observation refers to a criterion outside the checklist")
        present.add(criterion_id)
        for evidence in observation.evidence:
            chunk = chunks.get(evidence.doan_id)
            if chunk is None:
                raise ValueError("Evidence refers to a foreign or unknown chunk")
            start, end = evidence.ky_tu_bat_dau, evidence.ky_tu_ket_thuc
            if end > len(chunk.noi_dung) or chunk.noi_dung[start:end] != evidence.trich_dan:
                raise ValueError("Evidence quote/offset does not match the original chunk")
            if (owners[criterion_id], criterion_id, evidence.doan_id) not in selected:
                if any(row[2] == evidence.doan_id for row in selected):
                    raise ValueError("Evidence C06 belongs to another criterion/requirement")
                issues[criterion_id].append(
                    "Evidence lacks selected FINAL C06 for current criterion"
                )
        for evidence in observation.external_evidence:
            entry = registry.get((criterion_id, evidence.bang_chung_id))
            if entry is None:
                issues[criterion_id].append(
                    "External evidence lacks case-bound backend registration"
                )
            elif entry.object_uri != evidence.object_uri or entry.sha256 != evidence.sha256:
                raise ValueError("External evidence source/hash differs from registered evidence")
            elif not entry.verified:
                issues[criterion_id].append("External evidence registration is unverified")
            if not evidence.verified:
                issues[criterion_id].append("External evidence is unverified")
    if complete:
        for criterion_id in owners.keys() - present:
            issues[criterion_id].append("Missing observation for the criterion")
    return issues
