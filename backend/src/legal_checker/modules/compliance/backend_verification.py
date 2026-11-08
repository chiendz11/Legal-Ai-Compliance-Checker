"""Backend attestations for contract-content criteria, built before any AI call.

Every criterion in the catalogue sets ``case_facts_required``: without a verified fact that
says what is being judged, C07 can never accept a finding, so every run ended with all
requirements INSUFFICIENT. This module attests only what the backend itself has checked:

* the requirement is confirmed to apply (C04 scope MATCH, C05 version RESOLVED, CONFIRMED);
* the criterion judges the contract text itself (CONTRACT_CONTENT / NOI_DUNG_BAT_BUOC), so
  the evaluation target is the contract content, not performance or external documents;
* neither the criterion nor its requirement version has an exception to resolve, and it is
  not an optional mechanism whose selection would need a separate fact.

It does not attest absence (no ``absence_verified``, readable pages or received appendices),
so a MISSING proposal still stays UNKNOWN, and it never approves an AI proposal: the
automatic review still requires reviewed knowledge, an exact contract quote and no open
provider conditions. Performance, conditional and prohibited-clause criteria get nothing.
"""

from legal_checker.modules.compliance.criterion_reasoner import CONTENT_TYPES
from legal_checker.modules.compliance.decision_rules import parse_json_object
from legal_checker.modules.compliance.verification import CriterionVerification
from legal_checker.shared.contracts.common import Context
from legal_checker.shared.contracts.reasoning import Gates

POLICY = "BACKEND_CONTRACT_CONTENT_V1"


def _has_exception(criterion, knowledge) -> bool:
    try:
        conditions = parse_json_object(criterion.get("dieu_kien", {}))
    except ValueError:
        return True  # an unreadable condition is never attested
    if conditions.get("exception_ids") or conditions.get("optional_choice"):
        return True
    return any(
        row.get("tieu_chi_id") == criterion["tieu_chi_id"]
        or (
            not row.get("tieu_chi_id")
            and row.get("requirement_version_id") == criterion["requirement_version_id"]
        )
        for row in knowledge.tables.get("ngoai_le_ap_dung", [])
    )


def contract_content_verifications(context, hop_dong_id, requirements, knowledge):
    """One attestation per eligible criterion of every confirmed requirement."""
    context = Context.model_validate(context.model_dump())
    records = []
    for requirement in requirements:
        if not requirement.confirmed or not requirement.requirement_version_id:
            continue
        for criterion in knowledge.criteria_for(requirement.requirement_version_id):
            if criterion.get("loai_kiem_tra") not in CONTENT_TYPES:
                continue
            if _has_exception(criterion, knowledge):
                continue
            records.append(
                CriterionVerification(
                    **context.model_dump(),
                    hop_dong_id=hop_dong_id,
                    yeu_cau_ca_id=requirement.yeu_cau_ca_id,
                    tieu_chi_id=criterion["tieu_chi_id"],
                    verification_reference=f"{POLICY}:{context.knowledge_snapshot_sha256}",
                    gates=Gates(exceptions_resolved=True),
                    local_applicability="MATCH",
                    mandatory_confirmed=bool(
                        criterion.get("bat_buoc") is True
                        and criterion.get("noi_dung_bat_buoc_trong_hd") is True
                    ),
                    facts={
                        "evaluation_target": "CONTRACT_CONTENT",
                        "requirement_applicability": "CONFIRMED",
                    },
                    facts_verified=True,
                )
            )
    return records


class VerifiedObservationProvider:
    """Builds the backend attestations for each run, then delegates to the C07 provider.

    ``make_provider(verifications)`` returns a configured LLMObservationProvider; it is
    created per call because attestations are bound to the run's context and checklist.
    """

    def __init__(self, make_provider):
        self.make_provider = make_provider

    def observe(self, context, profile, requirements, retrieval, chunks, knowledge):
        verifications = contract_content_verifications(
            context, profile.hop_dong_id, requirements, knowledge
        )
        return self.make_provider(verifications).observe(
            context, profile, requirements, retrieval, chunks, knowledge
        )
