"""Compose the four pure cores using synthetic upstream data, without workflow or DB."""

from copy import deepcopy

import pytest
from legal_checker.modules.compliance.criterion_reasoner import reason
from legal_checker.modules.compliance.requirement_aggregator import (
    POLICY_CONDITIONS,
    POLICY_ID,
    POLICY_PRIORITY,
    aggregate,
)
from legal_checker.modules.recommendations.service import generate_recommendations
from legal_checker.modules.risks.citation_mapper import PRODUCTION_GATE
from legal_checker.modules.risks.service import evaluate_risks
from legal_checker.shared.contracts.common import Context
from legal_checker.shared.contracts.modules import RecommendationRequest, RiskRequest
from legal_checker.shared.contracts.reasoning import ReasoningRequest
from test_criterion_reasoner import reasoning_case as reasoning_case


def configure_downstream(knowledge, finding, *, citation=False):
    knowledge.versions["VERSION_1"]["quy_tac_tong_hop_id"] = POLICY_ID
    knowledge.aggregations[POLICY_ID] = {
        "quy_tac_tong_hop_id": POLICY_ID,
        "rule_version": "AGG_TEST",
        "dieu_kien_json": deepcopy(POLICY_CONDITIONS),
        "thu_tu_uu_tien_json": deepcopy(POLICY_PRIORITY),
        "trang_thai": "ENGINE_POLICY",
    }
    if finding == "SATISFIED" and not citation:
        return
    branch = "CITATION" if citation else "COMPLIANCE"
    criterion_id = None if citation else "CRITERION_1"
    risk_id = branch + "_RISK"
    template_id = branch + "_TEMPLATE"
    verification = finding == "UNKNOWN"
    severity = "REVIEW_REQUIRED" if verification else "HIGH"
    trigger = {"finding": finding}
    if verification:
        trigger.update(any_unresolved_fact=True, legal_violation_conclusion=False)
    if citation:
        trigger = {
            "schema": "CITATION_RULE_V1_1",
            "branch": "CITATION",
            "production_gate": PRODUCTION_GATE,
            "citation_status": "UNKNOWN",
            "no_violation_assertion": True,
            "missing_or_ambiguous_identity_date_source_or_domain": True,
        }
    knowledge.risks[risk_id] = {
        "rui_ro_id": risk_id,
        "nhanh": branch,
        "tieu_chi_id": criterion_id,
        "muc_do_co_so": severity,
        "ban_chat_rui_ro": "VERIFICATION_ONLY" if verification else "CONDITIONAL_COMPLIANCE",
        "human_verified": False,
    }
    knowledge.tables.setdefault("quy_tac_rui_ro", []).append(
        {
            "quy_tac_id": branch + "_RULE",
            "nhanh": branch,
            "tieu_chi_id": criterion_id,
            "trigger_status": finding,
            "trigger_json": trigger,
            "hanh_dong": "CREATE_CITATION_RISK"
            if citation
            else ("REQUEST_VERIFICATION" if verification else "CREATE_CONDITIONAL_RISK"),
            "rui_ro_id": risk_id,
            "rule_version": "RISK_TEST",
        }
    )
    knowledge.tables.setdefault("rui_ro_khuyen_nghi", []).append(
        {"lien_ket_id": branch + "_LINK", "rui_ro_id": risk_id, "khuyen_nghi_id": template_id}
    )
    knowledge.recommendations[template_id] = {
        "khuyen_nghi_id": template_id,
        "nhanh": branch,
        "tieu_chi_id": criterion_id,
        "gap_type": finding,
        "noi_dung": "Đối chiếu {finding} theo rủi ro {risk_instance_id}",
        "loai_hanh_dong": "REQUEST_VERIFICATION"
        if verification
        else "AMEND_OR_PERFORM_CORRECTIVE_ACTION",
        "uu_tien": severity,
        "required_elements_json": {"fields": ["risk_instance_id"], "text": []},
        "gioi_han_sinh_json": {"human_review_required": True},
        "trang_thai_ra_soat": "PENDING_HUMAN",
    }


@pytest.mark.parametrize(
    "finding,expected_status",
    [
        ("SATISFIED", "COMPLIANT"),
        ("VIOLATED", "NON_COMPLIANT"),
        ("MISSING", "NON_COMPLIANT"),
        ("UNKNOWN", "INSUFFICIENT"),
    ],
)
@pytest.mark.parametrize("include_citation", [False, True])
def test_real_core_outputs_feed_next_core_without_replacing_uncertainty(
    reasoning_case, finding, expected_status, include_citation
):
    knowledge, data = reasoning_case
    observation = data["payload"]["observations"][0]
    observation["proposed_finding"] = finding
    observation["gates"].update(coverage_complete=True, absence_verified=True)
    if finding == "UNKNOWN":
        data["payload"]["observations"] = []
    elif finding == "MISSING":
        observation["evidence"] = []
        data["payload"]["retrieval"] = []
    configure_downstream(knowledge, finding)
    if include_citation:
        configure_downstream(knowledge, "UNKNOWN", citation=True)
    request = ReasoningRequest.model_validate(data)
    context = request.model_dump(include=set(Context.model_fields))
    before = request.model_dump()

    criteria = reason(request, knowledge)
    requirements = aggregate(request, knowledge, criteria, request.payload.requirements)
    assert [result.finding for result in criteria] == [finding]
    assert [result.status for result in requirements] == [expected_status]

    risk_data = {
        **context,
        "payload": {
            "hop_dong_id": request.payload.hop_dong_id,
            "requirements": request.payload.requirements,
            "criterion_results": criteria,
            "citations": [],
        },
    }
    diagnostics = []
    compliance_risks = evaluate_risks(
        RiskRequest.model_validate(risk_data), knowledge, diagnostics=diagnostics
    )
    assert any(item["code"] == "C09_INPUT_EMPTY" for item in diagnostics)
    if include_citation:
        risk_data["payload"]["citations"] = [
            {
                "finding_id": "C09_TEST",
                "ca_id": request.ca_id,
                "vien_dan_id": "C03_TEST",
                "status": "UNKNOWN",
                "finding_verified": False,
                "ly_do": "Need official source identity and relevant date",
                "reason_code": "MISSING_IDENTITY",
                "domain_status": "UNKNOWN",
                "source_snapshot_json": {
                    "context": request.model_dump(mode="json", include=set(Context.model_fields)),
                    "hop_dong_id": request.payload.hop_dong_id,
                },
                "lan_chay_id": request.run_id,
                "knowledge_version": request.legal_knowledge_version,
            }
        ]
    branch_diagnostics = []
    risks = evaluate_risks(
        RiskRequest.model_validate(risk_data), knowledge, diagnostics=branch_diagnostics
    )
    if include_citation:
        assert any(item["code"] == "C09_PROVENANCE_UNAVAILABLE" for item in branch_diagnostics)
        citation_risk = next(risk for risk in risks if risk.source.citation_finding_id)
        assert citation_risk.risk_type == "VERIFICATION"
        assert (
            "knowledge_snapshot_sha256"
            not in (
                citation_risk.rule_snapshot_json["source_finding_snapshot"]["source_snapshot_json"]
            )
        )
    assert [row for row in risks if row.source.ket_qua_tieu_chi_id] == compliance_risks
    assert aggregate(request, knowledge, criteria, request.payload.requirements) == requirements
    output = generate_recommendations(
        RecommendationRequest(
            **context,
            payload={
                "hop_dong_id": request.payload.hop_dong_id,
                "requirements": request.payload.requirements,
                "risks": risks,
            },
        ),
        knowledge,
    )
    assert len(output) == len(risks) == int(finding != "SATISFIED") + int(include_citation)
    assert {row.ket_qua_rui_ro_id for row in output} == {row.ket_qua_rui_ro_id for row in risks}
    for row in output:
        assert row.knowledge_snapshot_sha256 == knowledge.sha256
        assert row.model_version == "TEMPLATE_ENGINE_NO_LLM"
        assert row.prompt_version == "NOT_USED"
        assert row.review_status == "PENDING"
        source = next(risk for risk in risks if risk.ket_qua_rui_ro_id == row.ket_qua_rui_ro_id)
        assert row.evidence_ids == source.evidence_ids
        assert row.legal_basis_ids == source.legal_basis_ids
        if source.risk_type == "VERIFICATION":
            assert row.loai_hanh_dong == "REQUEST_VERIFICATION"
            assert source.giai_thich in row.noi_dung
    assert request.model_dump() == before
