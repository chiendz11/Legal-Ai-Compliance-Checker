"""Admit source-review proposals through the same C07 gates as model proposals."""

from legal_checker.modules.compliance.automatic_review import automatic_review
from legal_checker.modules.compliance.reviewed_observations import build_verified_observation
from legal_checker.shared.contracts.common import Context
from legal_checker.shared.contracts.document_intelligence import Evidence, ExternalEvidence
from legal_checker.shared.contracts.reasoning import Observation


def admit_document_decisions(
    request, knowledge, decisions, verifications, *, model_version, prompt_version
):
    records = {v.tieu_chi_id: v for v in verifications}
    chunks = {c.doan_id: c for c in request.payload.chunks}
    registry = {
        (r.tieu_chi_id, r.bang_chung_id): r for r in request.payload.external_evidence_registry
    }
    if len(records) != len(verifications):
        raise ValueError("Duplicate criterion verification")
    observations = []
    for key, decision in decisions.items():
        condition_exclusion = (
            decision.get("review_target") == "LOCAL_CONDITION"
            and records[key].local_applicability == "NO_MATCH"
        )
        # A full-document pass identifies candidate clauses. Presence alone is
        # not a semantic judgement (especially for exceptions/prohibited acts).
        # Its candidates stay in C06 for the normal C07 provider to assess.
        if decision.get("review_target") == "LOCAL_CONDITION" and not condition_exclusion:
            continue
        if decision["assessment"] != "ABSENT" and not condition_exclusion:
            continue
        criterion = knowledge.criteria[key]
        record = records[key]
        owner = next(
            (
                r
                for r in request.payload.requirements
                if r.requirement_version_id == criterion["requirement_version_id"]
            ),
            None,
        )
        if (
            not owner
            or record.yeu_cau_ca_id != owner.yeu_cau_ca_id
            or record.hop_dong_id != request.payload.hop_dong_id
            or any(
                getattr(record, k) != getattr(request, k)
                for k in Context.model_fields
                if k != "trace_id"
            )
        ):
            raise ValueError("Document review verification ownership/context mismatch")
        absent = decision["assessment"] == "ABSENT"
        if condition_exclusion:
            finding = "UNKNOWN"
        elif criterion["loai_kiem_tra"] == "PROHIBITED_CLAUSE":
            finding = "SATISFIED" if absent else "VIOLATED"
        else:
            finding = "MISSING" if absent else "SATISFIED"
        entry = registry[(key, decision["evidence_id"])]
        excerpt = next(
            (e for e in record.external_excerpts if e.bang_chung_id == entry.bang_chung_id), None
        )
        if (
            not excerpt
            or not entry.verified
            or excerpt.sha256 != entry.sha256
            or entry.hop_dong_id != request.payload.hop_dong_id
            or entry.yeu_cau_ca_id != owner.yeu_cau_ca_id
            or any(
                getattr(entry, k) != getattr(request, k)
                for k in Context.model_fields
                if k != "trace_id"
            )
        ):
            raise ValueError("Document review evidence registration mismatch")
        evidence = []
        for chunk_id in decision.get("candidate_ids", [])[:6]:
            chunk = chunks[chunk_id]
            evidence.append(
                Evidence(
                    doan_id=chunk_id,
                    trich_dan=chunk.noi_dung,
                    ky_tu_bat_dau=0,
                    ky_tu_ket_thuc=len(chunk.noi_dung),
                )
            )
        proposal = Observation(
            tieu_chi_id=key,
            proposed_finding=finding,
            giai_thich=decision["explanation"],
            evidence=evidence,
            external_evidence=[
                ExternalEvidence(
                    bang_chung_id=entry.bang_chung_id,
                    object_uri=entry.object_uri,
                    sha256=entry.sha256,
                )
            ],
            model_version=model_version,
            prompt_version=prompt_version,
        )
        review = automatic_review(proposal, request, knowledge, verification=records[key])
        observations.append(build_verified_observation(proposal, review, request, knowledge))
    return observations
