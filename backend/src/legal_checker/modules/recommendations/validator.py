"""Validate C10 provenance against its pinned source and rules before generating C11."""

from legal_checker.modules.legal_knowledge.models import KnowledgeSnapshot
from legal_checker.modules.risks.service import evaluate_risks
from legal_checker.shared.contracts.citation import CitationValidation
from legal_checker.shared.contracts.common import Context
from legal_checker.shared.contracts.modules import RiskPayload, RiskRequest
from legal_checker.shared.contracts.reasoning import CriterionResult
from legal_checker.shared.contracts.risk import RiskResult
from legal_checker.shared.contracts.temporal import ApplicableRequirement
from legal_checker.shared.validation import validate_context, validate_requirements


def validate_risks(
    context: Context,
    risks: list[RiskResult],
    knowledge: KnowledgeSnapshot,
    requirements: list[ApplicableRequirement],
):
    """Replay only pure C10 policy, never reasoning, providers, storage or HTTP.

    This verifies all deduplicated rule matches as well as the original C07/C09
    source instead of treating a caller's snapshot flags as attestations.
    """
    validate_context(context, knowledge)
    validate_requirements(context, requirements, knowledge)
    identities = set()
    business_identities = set()
    for risk in risks:
        risk = RiskResult.model_validate(risk.model_dump())
        if risk.ket_qua_rui_ro_id in identities:
            raise ValueError("Duplicate risk instance")
        identities.add(risk.ket_qua_rui_ro_id)
        identity = (
            risk.source.ket_qua_tieu_chi_id,
            risk.source.citation_finding_id,
            risk.rui_ro_id,
        )
        if identity in business_identities:
            raise ValueError("Duplicate risk business identity")
        business_identities.add(identity)
        if risk.ca_id != context.ca_id:
            raise ValueError("Risk belongs to another case")
        snapshot = risk.rule_snapshot_json
        if snapshot.get("context") != context.model_dump(
            mode="json", include=set(Context.model_fields)
        ):
            raise ValueError("Risk context/run/snapshot mismatch")
        source = snapshot.get("source_finding_snapshot", {})
        criteria, citations = [], []
        if risk.source.ket_qua_tieu_chi_id:
            finding = CriterionResult.model_validate(source)
            if (
                finding.ket_qua_id != risk.source.ket_qua_tieu_chi_id
                or finding.yeu_cau_ca_id != risk.source.yeu_cau_ca_id
            ):
                raise ValueError("Risk criterion source ownership mismatch")
            criteria.append(finding)
        else:
            finding = CitationValidation.model_validate(source)
            if (
                finding.finding_id != risk.source.citation_finding_id
                or risk.source.yeu_cau_ca_id is not None
            ):
                raise ValueError("Risk citation source ownership mismatch")
            citations.append(finding)
        source_metadata = source.get(
            "tieu_chi_snapshot_json" if criteria else "source_snapshot_json", {}
        )
        contract_id = getattr(getattr(context, "payload", None), "hop_dong_id", None)
        # Older upstream contracts may omit this optional provenance. Keep that
        # absence explicit rather than fabricate a contract identity.
        contract_id = contract_id or source_metadata.get("hop_dong_id", "")
        request = RiskRequest(
            **context.model_dump(include=set(Context.model_fields)),
            payload=RiskPayload(
                hop_dong_id=contract_id,
                requirements=requirements,
                criterion_results=criteria,
                citations=citations,
            ),
        )
        expected = evaluate_risks(request, knowledge)
        matching = [row for row in expected if row.ket_qua_rui_ro_id == risk.ket_qua_rui_ro_id]
        if len(matching) != 1 or matching[0] != risk:
            raise ValueError("C10 risk source, guards or pinned policy snapshot mismatch")
