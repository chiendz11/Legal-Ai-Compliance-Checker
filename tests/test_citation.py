import pytest

from app.application.pipelines.steps_5_7 import evaluate


def citation(**updates):
    row = {
        "finding_id": "CF_TEST",
        "ca_id": "CA_TEST",
        "vien_dan_id": "VD_TEST",
        "normalized_van_ban_id": "VBPL001",
        "relevant_date": "2026-01-15",
        "status": "STALE",
        "reason_code": "REPLACED_BEFORE_RELEVANT_DATE",
        "ly_do": "Citation fixture",
        "domain_status": "MATCH",
        "finding_verified": True,
        "current_status": "REPEALED",
        "source_snapshot_json": {
            "reviewed_knowledge": True,
            "identity_confirmed": True,
            "temporal_source_complete": True,
            "transition_context_resolved": True,
            "official_evidence_required": True,
            "identity_or_context_invalidity_proven": True,
            "evidence_ids": ["VD_EVIDENCE"],
        },
        "lan_chay_id": "RUN_TEST",
        "knowledge_version": "LEGAL_TEST",
    }
    row.update(updates)
    return row


@pytest.mark.parametrize(
    "status,risk_type",
    [("STALE", "CITATION"), ("INVALID", "CITATION"), ("UNKNOWN", "VERIFICATION")],
)
def test_citation_never_changes_compliance(knowledge, request_factory, status, risk_type):
    def mutate(data):
        data["payload"]["citations"] = [citation(status=status)]

    result = evaluate(request_factory(mutate=mutate), knowledge).payload
    assert result.requirement_results[0].status == "COMPLIANT"
    assert len(result.risks) == 1
    assert result.risks[0].risk_type == risk_type
    assert result.risks[0].source.citation_finding_id == "CF_TEST"
    assert result.risks[0].source.ket_qua_tieu_chi_id is None


def test_historical_valid_current_repealed_has_no_citation_risk(knowledge, request_factory):
    def mutate(data):
        data["payload"]["citations"] = [citation(status="VALID")]

    assert evaluate(request_factory(mutate=mutate), knowledge).payload.risks == []


def test_unverified_citation_routes_to_verification(knowledge, request_factory):
    def mutate(data):
        data["payload"]["citations"] = [citation(finding_verified=False)]

    result = evaluate(request_factory(mutate=mutate), knowledge).payload
    assert result.risks[0].risk_type == "VERIFICATION"
    assert result.recommendations[0].loai_hanh_dong == "REQUEST_VERIFICATION"


def test_domain_mismatch_specific_rule(knowledge, request_factory):
    row = citation(status="INVALID", domain_status="MISMATCH", reason_code="DOMAIN_MISMATCH")
    row["source_snapshot_json"]["context_mismatch_proven"] = True

    def mutate(data):
        data["payload"]["citations"] = [row]

    result = evaluate(request_factory(mutate=mutate), knowledge).payload
    assert result.risks[0].quy_tac_id == "RULE_CITATION_DOMAIN_MISMATCH"


def test_unresolved_domain_requires_verification(knowledge, request_factory):
    def mutate(data):
        data["payload"]["citations"] = [citation(domain_status="UNKNOWN")]

    result = evaluate(request_factory(mutate=mutate), knowledge).payload
    assert result.risks[0].risk_type == "VERIFICATION"
