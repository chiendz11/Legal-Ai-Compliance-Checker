from legal_checker.modules.legal_knowledge.models import KnowledgeSnapshot
from legal_checker.modules.risks.common import _risk
from legal_checker.shared.contracts.common import Context
from legal_checker.shared.contracts.risk import RiskSource


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
