"""C11 business tests with synthetic C07/C09 inputs and real pinned C10 mapping.

No expected workbook outputs, database, provider, or model call is used.
"""

import json
from copy import deepcopy

import pytest
from legal_checker.modules.recommendations.generator import LIMITS, recommend
from legal_checker.modules.recommendations.service import generate_recommendations
from legal_checker.modules.risks.citation_mapper import PRODUCTION_GATE
from legal_checker.modules.risks.service import evaluate_risks
from legal_checker.shared.contracts.citation import CitationValidation
from legal_checker.shared.contracts.common import Context
from legal_checker.shared.contracts.modules import RecommendationRequest, RiskRequest
from legal_checker.shared.contracts.reasoning import CriterionResult
from legal_checker.shared.contracts.temporal import ApplicableRequirement


class RecommendationKnowledge:
    def __init__(self):
        self.sha256 = "a" * 64
        self.schema_version = "SYNTHETIC_TEST"
        self.versions = {
            "VERSION_A": {"requirement_version_id": "VERSION_A", "requirement_id": "FAMILY_A"}
        }
        self.criteria = {
            "CRITERION_A": {
                "tieu_chi_id": "CRITERION_A",
                "requirement_version_id": "VERSION_A",
                "noi_dung": "Đối chiếu điều khoản đúng tiêu chí",
                "bat_buoc": True,
                "noi_dung_bat_buoc_trong_hd": True,
            }
        }
        self.documents = {"DOCUMENT_A": {"human_verified": True}}
        self.articles = {"ARTICLE_A": {"van_ban_id": "DOCUMENT_A"}}
        self.risks = {}
        self.recommendations = {}
        self.aggregations = {}
        self.tables = {"quy_tac_rui_ro": [], "rui_ro_khuyen_nghi": []}

    def criteria_for(self, version_id):
        return [c for c in self.criteria.values() if c["requirement_version_id"] == version_id]

    def legal_basis(self, criterion):
        return ["ARTICLE_A"]


@pytest.fixture
def recommendation_case():
    knowledge = RecommendationKnowledge()
    context = Context(
        ca_id="CASE_A",
        phien_ban_id="DEPLOY_A",
        rule_version="RULE_DEPLOY_A",
        legal_knowledge_version="LEGAL_A",
        knowledge_snapshot_sha256=knowledge.sha256,
        run_id="RUN_A",
        trace_id="TRACE_A",
    )
    requirement = ApplicableRequirement(
        yeu_cau_ca_id="REQUIREMENT_INSTANCE_A",
        ca_id=context.ca_id,
        requirement_id="FAMILY_A",
        requirement_version_id="VERSION_A",
        scope_status="MATCH",
        version_status="RESOLVED",
        applicability_status="CONFIRMED",
        moc_ap_dung="2026-01-01",
        phien_ban_id=context.phien_ban_id,
    )
    return context, knowledge, requirement


def mapped_risks(case, finding="VIOLATED", *, citation=False, source_id="FINDING_A"):
    context, knowledge, requirement = case
    branch = "CITATION" if citation else "COMPLIANCE"
    criterion_id = None if citation else "CRITERION_A"
    verification = finding == "UNKNOWN"
    knowledge.risks["RISK_A"] = {
        "rui_ro_id": "RISK_A",
        "ten_rui_ro": "Rủi ro cần đối chiếu",
        "nhanh": branch,
        "tieu_chi_id": criterion_id,
        "muc_do_co_so": "REVIEW_REQUIRED" if verification else ("LOW" if citation else "HIGH"),
        "ban_chat_rui_ro": "VERIFICATION_ONLY" if verification else "CONDITIONAL",
    }
    trigger = {"finding": finding, "criterion_target_only": True}
    if verification:
        trigger.update(any_unresolved_fact=True, legal_violation_conclusion=False)
    if citation:
        trigger = {
            "schema": "CITATION_RULE_V1_1",
            "branch": branch,
            "citation_status": finding,
            "production_gate": PRODUCTION_GATE,
            "official_evidence_required": not verification,
            "relevant_date_required": not verification,
        }
        if verification:
            trigger.update(
                no_violation_assertion=True,
                missing_or_ambiguous_identity_date_source_or_domain=True,
            )
    knowledge.tables["quy_tac_rui_ro"] = [
        {
            "quy_tac_id": "RISK_RULE_A",
            "nhanh": branch,
            "tieu_chi_id": criterion_id,
            "trigger_status": finding,
            "trigger_json": trigger,
            "hanh_dong": "CREATE_CITATION_RISK"
            if citation
            else ("REQUEST_VERIFICATION" if verification else "CREATE_CONDITIONAL_RISK"),
            "rui_ro_id": "RISK_A",
            "rule_version": "RISK_RULE_VERSION_A",
        }
    ]
    knowledge.tables["rui_ro_khuyen_nghi"] = [
        {"lien_ket_id": "MAPPING_A", "rui_ro_id": "RISK_A", "khuyen_nghi_id": "TEMPLATE_A"}
    ]
    knowledge.recommendations["TEMPLATE_A"] = {
        "khuyen_nghi_id": "TEMPLATE_A",
        "nhanh": branch,
        "tieu_chi_id": criterion_id,
        "gap_type": finding,
        "noi_dung": "Đối chiếu {risk_name}; nguồn {finding}; căn cứ {legal_basis_ids}.",
        "loai_hanh_dong": "REQUEST_VERIFICATION"
        if verification
        else ("CORRECT_REFERENCE" if citation else "AMEND_OR_PERFORM_CORRECTIVE_ACTION"),
        "uu_tien": knowledge.risks["RISK_A"]["muc_do_co_so"],
        "required_elements_json": {
            "fields": ["risk_instance_id"],
            "text": ["Nguồn {evidence_ids}"],
        },
        "gioi_han_sinh_json": {
            "no_invented_names_dates_accounts": True,
            "severity_from_db": True,
            "human_review_required": True,
        },
        "mau_sua_goi_y": "[Dự thảo cần xác minh đúng nguồn]",
        "bang_chung_khac_phuc_can_luu": "Nguồn gốc: {evidence_ids}",
        "kiem_tra_sau_khac_phuc": "Đối chiếu lại tại mốc {relevant_date}",
        "trang_thai_ra_soat": "PENDING_HUMAN",
    }
    criteria, citations = [], []
    if citation:
        citations = [
            CitationValidation(
                finding_id=source_id,
                ca_id=context.ca_id,
                vien_dan_id="CITATION_A",
                normalized_van_ban_id="DOCUMENT_A",
                relevant_date="2026-01-01",
                status=finding,
                reason_code="MISSING_OFFICIAL_SOURCE" if verification else "DOMAIN_MISMATCH",
                ly_do="Cần bản nguồn chính thức" if verification else "Nguồn không phù hợp phạm vi",
                domain_status="UNKNOWN" if verification else "MISMATCH",
                finding_verified=not verification,
                source_snapshot_json={
                    "knowledge_snapshot_sha256": knowledge.sha256,
                    "context": context.model_dump(mode="json"),
                    "hop_dong_id": "CONTRACT_A",
                    "reviewed_knowledge": not verification,
                    "official_evidence_verified": not verification,
                    "legal_basis_ids": ["ARTICLE_A"],
                    "evidence_ids": ["CITATION_A"],
                },
                lan_chay_id=context.run_id,
                knowledge_version=context.legal_knowledge_version,
            )
        ]
    else:
        criteria = [
            CriterionResult(
                ket_qua_id=source_id,
                ca_id=context.ca_id,
                yeu_cau_ca_id=requirement.yeu_cau_ca_id,
                tieu_chi_id="CRITERION_A",
                finding=finding,
                giai_thich="Synthetic downstream finding, not legal gold",
                gates={
                    "coverage_complete": True,
                    "absence_verified": True,
                    "evidence_validated": True,
                    "source_verified": True,
                    "scope_confirmed": True,
                    "version_resolved": True,
                    "exceptions_resolved": True,
                },
                uncertainty_reason="Cần chứng từ xác minh việc đã thực hiện"
                if verification
                else None,
                evidence=[
                    {
                        "doan_id": "CHUNK_A",
                        "trich_dan": "Điều khoản gốc",
                        "ky_tu_bat_dau": 0,
                        "ky_tu_ket_thuc": 14,
                    }
                ],
                legal_basis_ids=["ARTICLE_A"],
                tieu_chi_snapshot_json={
                    **deepcopy(knowledge.criteria["CRITERION_A"]),
                    "knowledge_snapshot_sha256": knowledge.sha256,
                    "context": context.model_dump(mode="json"),
                    "hop_dong_id": "CONTRACT_A",
                },
                model_version="SYNTHETIC_TEST",
                prompt_version="NOT_USED",
                lan_chay_id=context.run_id,
                mandatory=True,
            )
        ]
    request = RiskRequest(
        **context.model_dump(),
        payload={
            "hop_dong_id": "CONTRACT_A",
            "requirements": [requirement],
            "criterion_results": criteria,
            "citations": citations,
        },
    )
    risks = evaluate_risks(request, knowledge)
    assert len(risks) == 1, "Synthetic fixture must pass real C10 policy"
    return risks


def generate(case, risks, diagnostics=None):
    context, knowledge, requirement = case
    return generate_recommendations(
        RecommendationRequest(
            **context.model_dump(),
            payload={"hop_dong_id": "CONTRACT_A", "requirements": [requirement], "risks": risks},
        ),
        knowledge,
        diagnostics=diagnostics,
    )


@pytest.mark.parametrize("finding", ["VIOLATED", "MISSING", "UNKNOWN"])
def test_mapping_instance_binding_metadata_and_snapshot(recommendation_case, finding):
    risks = mapped_risks(recommendation_case, finding)
    context, knowledge, requirement = recommendation_case
    before = deepcopy(knowledge.__dict__)
    diagnostics = []
    result = generate(recommendation_case, risks, diagnostics)[0]
    assert result.ket_qua_rui_ro_id == risks[0].ket_qua_rui_ro_id
    assert result.khuyen_nghi_id == "TEMPLATE_A"
    assert result.evidence_ids == risks[0].evidence_ids
    assert result.legal_basis_ids == ["ARTICLE_A"]
    assert result.uu_tien == risks[0].severity
    assert result.rule_version == "RISK_RULE_VERSION_A"
    assert result.knowledge_snapshot_sha256 == context.knowledge_snapshot_sha256
    assert result.model_version == "TEMPLATE_ENGINE_NO_LLM"
    assert result.prompt_version == "NOT_USED"
    assert result.review_status == "PENDING"
    assert result.dieu_kien_snapshot["requirement"] == requirement.model_dump(mode="json")
    assert result.template_snapshot_json["trang_thai_ra_soat"] == "PENDING_HUMAN"
    assert (
        result.template_snapshot_json["mapping_snapshots"] == knowledge.tables["rui_ro_khuyen_nghi"]
    )
    assert "[Dự thảo cần xác minh đúng nguồn]" in result.noi_dung
    assert "Nguồn gốc: CHUNK_A" in result.noi_dung
    assert not diagnostics
    assert knowledge.__dict__ == before
    assert result == generate(recommendation_case, risks)[0]


def test_each_c10_instance_gets_distinct_recommendation(recommendation_case):
    first = mapped_risks(recommendation_case)
    second = mapped_risks(recommendation_case, source_id="FINDING_B")
    results = generate(recommendation_case, first + second)
    assert len({r.khuyen_nghi_ca_id for r in results}) == 2
    assert {r.ket_qua_rui_ro_id for r in results} == {
        first[0].ket_qua_rui_ro_id,
        second[0].ket_qua_rui_ro_id,
    }


def test_multiple_matching_risk_rules_keep_provenance_in_one_recommendation(recommendation_case):
    context, knowledge, requirement = recommendation_case
    initial = mapped_risks(recommendation_case)
    source = initial[0].rule_snapshot_json["source_finding_snapshot"]
    other_rule = deepcopy(knowledge.tables["quy_tac_rui_ro"][0])
    other_rule.update(quy_tac_id="RISK_RULE_B", rule_version="SECOND_RULE_VERSION")
    knowledge.tables["quy_tac_rui_ro"].append(other_rule)
    risks = evaluate_risks(
        RiskRequest(
            **context.model_dump(),
            payload={
                "hop_dong_id": "CONTRACT_A",
                "requirements": [requirement],
                "criterion_results": [source],
                "citations": [],
            },
        ),
        knowledge,
    )
    result = generate(recommendation_case, risks)
    assert len(risks) == len(result) == 1
    rules = result[0].dieu_kien_snapshot["risk_rule_snapshot"]["matched_rules"]
    assert {rule["rule_version"] for rule in rules} == {
        "RISK_RULE_VERSION_A",
        "SECOND_RULE_VERSION",
    }


def test_all_templates_selected_deterministically_and_duplicate_links_preserved(
    recommendation_case,
):
    risks = mapped_risks(recommendation_case)
    knowledge = recommendation_case[1]
    second = deepcopy(knowledge.recommendations["TEMPLATE_A"])
    second.update(khuyen_nghi_id="TEMPLATE_B", noi_dung="Bổ sung bước đối chiếu thứ hai")
    knowledge.recommendations["TEMPLATE_B"] = second
    links = knowledge.tables["rui_ro_khuyen_nghi"]
    links.extend(
        [
            {"lien_ket_id": "LINK_B", "rui_ro_id": "RISK_A", "khuyen_nghi_id": "TEMPLATE_B"},
            {"lien_ket_id": "LINK_A2", "rui_ro_id": "RISK_A", "khuyen_nghi_id": "TEMPLATE_A"},
        ]
    )
    results = generate(recommendation_case, risks)
    assert [r.khuyen_nghi_id for r in results] == ["TEMPLATE_A", "TEMPLATE_B"]
    assert len(results[0].template_snapshot_json["mapping_snapshots"]) == 2
    links.reverse()
    reordered = generate(recommendation_case, risks)
    assert reordered == results


@pytest.mark.parametrize("location", ["mapping", "template"])
def test_unsupported_selection_has_diagnostic_and_no_arbitrary_first(recommendation_case, location):
    risks = mapped_risks(recommendation_case)
    knowledge = recommendation_case[1]
    target = (
        knowledge.tables["rui_ro_khuyen_nghi"][0]
        if location == "mapping"
        else (knowledge.recommendations["TEMPLATE_A"]["gioi_han_sinh_json"])
    )
    target["selection_policy"] = "FIRST"
    diagnostics = []
    assert generate(recommendation_case, risks, diagnostics) == []
    assert "selection" in diagnostics[0]["detail"].lower() or "SELECTION" in diagnostics[0]["code"]


@pytest.mark.parametrize(
    "problem", ["mapping", "template", "template-id", "disabled-template", "disabled-mapping"]
)
def test_missing_or_disabled_knowledge_has_explicit_diagnostic(recommendation_case, problem):
    risks = mapped_risks(recommendation_case)
    knowledge = recommendation_case[1]
    expected = {
        "mapping": "MISSING_RECOMMENDATION_MAPPING",
        "template": "MISSING_RECOMMENDATION_TEMPLATE",
        "template-id": "RECOMMENDATION_KNOWLEDGE_GAP",
        "disabled-template": "DISABLED_RECOMMENDATION_TEMPLATE",
        "disabled-mapping": "DISABLED_RECOMMENDATION_MAPPING",
    }[problem]
    if problem == "mapping":
        knowledge.tables["rui_ro_khuyen_nghi"].clear()
    elif problem == "template":
        knowledge.recommendations.clear()
    elif problem == "template-id":
        knowledge.recommendations["TEMPLATE_A"]["khuyen_nghi_id"] = "FOREIGN"
    elif problem == "disabled-template":
        knowledge.recommendations["TEMPLATE_A"]["trang_thai"] = "DISABLED"
    else:
        knowledge.tables["rui_ro_khuyen_nghi"][0]["enabled"] = False
    diagnostics = []
    assert generate(recommendation_case, risks, diagnostics) == []
    assert diagnostics[0]["code"] == expected
    assert diagnostics[0]["subject_id"] == risks[0].ket_qua_rui_ro_id


def test_required_elements_render_only_available_bindings_and_preserve_quote(recommendation_case):
    risks = mapped_risks(recommendation_case)
    template = recommendation_case[1].recommendations["TEMPLATE_A"]
    template["required_elements_json"] = json.dumps(
        {
            "fields": ["quote", "criterion_id", "requirement_version_id"],
            "text": ["Nguyên văn: {quote}", "Phiên bản {requirement_version_id}"],
        }
    )
    template["gioi_han_sinh_json"] = json.dumps(template["gioi_han_sinh_json"])
    result = generate(recommendation_case, risks)[0]
    assert "Nguyên văn: Điều khoản gốc" in result.noi_dung
    assert "Phiên bản VERSION_A" in result.noi_dung


def test_seed_style_prose_lists_are_context_with_preserved_placeholders(recommendation_case):
    risks = mapped_risks(recommendation_case)
    template = recommendation_case[1].recommendations["TEMPLATE_A"]
    # The seed uses a JSON list of requested prose, not a dictionary of facts.
    template["required_elements_json"] = ["Tên bên bán theo hồ sơ", "Tư cách người đại diện nếu có"]
    template["gioi_han_sinh_json"] = dict.fromkeys(LIMITS, True)
    template["mau_sua_goi_y"] = "Bên bán: [tên theo hồ sơ], [nếu áp dụng]."
    result = generate(recommendation_case, risks)[0]
    assert "Nội dung tham chiếu để đối chiếu khi áp dụng" in result.noi_dung
    assert "Tên bên bán theo hồ sơ" in result.noi_dung
    assert "[tên theo hồ sơ], [nếu áp dụng]" in result.noi_dung
    assert "Invented" not in result.noi_dung


@pytest.mark.parametrize(
    "spec",
    [
        {"fields": ["seller_name"]},
        {"fields": ["amount_due"]},
        {"fields": [12]},
        {"fields": "quote"},
        {"unknown_directive": True},
        [""],
        [None],
        '{"fields": [], "fields": ["quote"]}',
        "{",
    ],
)
def test_missing_or_wrong_required_facts_fail_closed(recommendation_case, spec):
    risks = mapped_risks(recommendation_case)
    template = recommendation_case[1].recommendations["TEMPLATE_A"]
    template["required_elements_json"] = spec
    # Caller-inserted candidate data does not create a supported template binding.
    risks[0].rule_snapshot_json["source_finding_snapshot"]["tieu_chi_snapshot_json"][
        "seller_name"
    ] = "Invented"
    # The unrelated snapshot extra is not used as a fact; C10 snapshot still permits metadata.
    diagnostics = []
    assert generate(recommendation_case, risks, diagnostics) == []
    assert diagnostics[0]["code"] == "RECOMMENDATION_KNOWLEDGE_GAP"


@pytest.mark.parametrize(
    "text",
    [
        "{seller_name}",
        "{risk_name.__class__}",
        "{quote[0]}",
        "{risk_name!r}",
        "{relevant_date:10}",
        "{",
        "",
    ],
)
def test_unsupported_or_unbound_render_expressions_are_not_evaluated(recommendation_case, text):
    risks = mapped_risks(recommendation_case)
    recommendation_case[1].recommendations["TEMPLATE_A"]["noi_dung"] = text
    diagnostics = []
    assert generate(recommendation_case, risks, diagnostics) == []
    assert diagnostics[0]["code"] == "RECOMMENDATION_KNOWLEDGE_GAP"


@pytest.mark.parametrize(
    "constraint",
    [
        {"invent_legal_basis": True},
        {"severity_from_db": False},
        {"scope_required": "true"},
        '{"severity_from_db": false, "severity_from_db": true}',
    ],
)
def test_unsupported_or_ambiguous_generation_constraints_fail_closed(
    recommendation_case, constraint
):
    risks = mapped_risks(recommendation_case)
    recommendation_case[1].recommendations["TEMPLATE_A"]["gioi_han_sinh_json"] = constraint
    diagnostics = []
    assert generate(recommendation_case, risks, diagnostics) == []
    assert diagnostics[0]["code"] == "RECOMMENDATION_KNOWLEDGE_GAP"


@pytest.mark.parametrize("priority", ["CRITICAL", "REVIEW_REQUIRED", "UNSUPPORTED"])
def test_priority_cannot_increase_severity(recommendation_case, priority):
    risks = mapped_risks(recommendation_case)
    recommendation_case[1].recommendations["TEMPLATE_A"]["uu_tien"] = priority
    diagnostics = []
    assert generate(recommendation_case, risks, diagnostics) == []
    assert "priority" in diagnostics[0]["detail"]


@pytest.mark.parametrize("citation", [False, True])
def test_unknown_requests_exact_missing_information(recommendation_case, citation):
    risks = mapped_risks(recommendation_case, "UNKNOWN", citation=citation)
    result = generate(recommendation_case, risks)[0]
    source = risks[0].rule_snapshot_json["source_finding_snapshot"]
    reason = source.get("uncertainty_reason") or source["ly_do"]
    assert reason in result.noi_dung
    assert result.uu_tien == "REVIEW_REQUIRED"
    assert result.loai_hanh_dong == "REQUEST_VERIFICATION"


@pytest.mark.parametrize(
    "field,value",
    [
        ("loai_hanh_dong", "AMEND_OR_PERFORM_CORRECTIVE_ACTION"),
        ("loai_hanh_dong", "PAY_FINE"),
        ("uu_tien", "HIGH"),
    ],
)
def test_verification_risk_cannot_generate_remedy_or_fine(recommendation_case, field, value):
    risks = mapped_risks(recommendation_case, "UNKNOWN")
    recommendation_case[1].recommendations["TEMPLATE_A"][field] = value
    diagnostics = []
    assert generate(recommendation_case, risks, diagnostics) == []
    assert diagnostics[0]["code"] == "RECOMMENDATION_KNOWLEDGE_GAP"


@pytest.mark.parametrize(
    "field,value",
    [
        ("nhanh", "CITATION"),
        ("tieu_chi_id", "FOREIGN"),
        ("gap_type", "MISSING"),
        ("loai_hanh_dong", "PAY_FINE"),
    ],
)
def test_template_cannot_cross_target_finding_or_action(recommendation_case, field, value):
    risks = mapped_risks(recommendation_case)
    recommendation_case[1].recommendations["TEMPLATE_A"][field] = value
    diagnostics = []
    assert generate(recommendation_case, risks, diagnostics) == []
    assert diagnostics[0]["code"] == "RECOMMENDATION_KNOWLEDGE_GAP"


def test_citation_domain_mismatch_template_uses_c09_and_keeps_basis(recommendation_case):
    risks = mapped_risks(recommendation_case, "INVALID", citation=True)
    recommendation_case[1].recommendations["TEMPLATE_A"]["gap_type"] = "DOMAIN_MISMATCH"
    result = generate(recommendation_case, risks)[0]
    assert result.evidence_ids == ["CITATION_A"]
    assert result.legal_basis_ids == ["ARTICLE_A", "DOCUMENT_A"]
    assert result.dieu_kien_snapshot["requirement"] is None
    assert result.dieu_kien_snapshot["risk_source"]["citation_finding_id"] == "FINDING_A"


@pytest.mark.parametrize(
    "problem",
    [
        "case",
        "run",
        "snapshot",
        "instance",
        "catalog",
        "rule",
        "matched-rule",
        "source-id",
        "source-owner",
        "source-pin",
        "missing-source-pin",
        "missing-source-context",
        "missing-source-contract",
        "source-run",
        "evidence",
        "basis",
        "severity",
        "guard",
        "disabled-rule",
        "unconfirmed-owner",
    ],
)
def test_forged_or_foreign_c10_provenance_rejected(recommendation_case, problem):
    risks = mapped_risks(recommendation_case)
    risk = risks[0]
    source = risk.rule_snapshot_json["source_finding_snapshot"]
    if problem == "case":
        risk.ca_id = "FOREIGN"
    elif problem in {"run", "snapshot"}:
        key = "run_id" if problem == "run" else "knowledge_snapshot_sha256"
        risk.rule_snapshot_json["context"][key] = "FOREIGN"
    elif problem == "instance":
        risk.ket_qua_rui_ro_id = "FOREIGN"
    elif problem == "catalog":
        risk.risk_snapshot["ten_rui_ro"] = "Unpinned"
    elif problem == "rule":
        risk.rule_snapshot_json["rule_version"] = "Unpinned"
    elif problem == "matched-rule":
        risk.rule_snapshot_json["matched_rules"][0]["rule_version"] = "Unpinned"
    elif problem == "source-id":
        risk.source.ket_qua_tieu_chi_id = "FOREIGN"
    elif problem == "source-owner":
        source["yeu_cau_ca_id"] = "FOREIGN"
    elif problem == "source-pin":
        source["tieu_chi_snapshot_json"]["knowledge_snapshot_sha256"] = "b" * 64
    elif problem in {"missing-source-pin", "missing-source-context", "missing-source-contract"}:
        key = {
            "missing-source-pin": "knowledge_snapshot_sha256",
            "missing-source-context": "context",
            "missing-source-contract": "hop_dong_id",
        }[problem]
        del source["tieu_chi_snapshot_json"][key]
    elif problem == "source-run":
        source["lan_chay_id"] = "FOREIGN"
    elif problem == "evidence":
        risk.evidence_ids = ["FOREIGN"]
    elif problem == "basis":
        risk.legal_basis_ids = ["FOREIGN"]
    elif problem == "severity":
        risk.severity = "CRITICAL"
    elif problem == "guard":
        recommendation_case[1].tables["quy_tac_rui_ro"][0]["trigger_json"]["source_verified"] = (
            False
        )
    elif problem == "disabled-rule":
        recommendation_case[1].tables["quy_tac_rui_ro"][0]["trang_thai"] = "DISABLED"
    else:
        recommendation_case[2].applicability_status = "UNKNOWN"
        recommendation_case[2].scope_status = "UNKNOWN"
    with pytest.raises(ValueError):
        generate(recommendation_case, risks)


def test_duplicate_risks_rejected_and_empty_input_stays_empty(recommendation_case):
    context, knowledge, requirement = recommendation_case
    risks = mapped_risks(recommendation_case)
    with pytest.raises(ValueError, match="Duplicate"):
        generate(recommendation_case, risks + risks)
    duplicate = risks[0].model_copy(update={"ket_qua_rui_ro_id": "OTHER_INSTANCE"})
    with pytest.raises(ValueError, match="Duplicate risk business"):
        generate(recommendation_case, risks + [duplicate])
    assert recommend(context, knowledge, [], [requirement]) == []


def test_contract_provenance_uses_actual_source_and_rejects_another_input_contract(
    recommendation_case,
):
    context, knowledge, requirement = recommendation_case
    risks = mapped_risks(recommendation_case)
    assert recommend(context, knowledge, risks, [requirement]) == generate(
        recommendation_case, risks
    )
    request = RecommendationRequest(
        **context.model_dump(),
        payload={"hop_dong_id": "FOREIGN_CONTRACT", "requirements": [requirement], "risks": risks},
    )
    with pytest.raises(ValueError, match="contract ownership"):
        generate_recommendations(request, knowledge)


def test_missing_relevant_date_is_a_fact_gap_not_an_invented_date(recommendation_case):
    risks = mapped_risks(recommendation_case, "UNKNOWN")
    requirement = recommendation_case[2]
    requirement.applicability_status = "UNKNOWN"
    requirement.version_status = "UNKNOWN"
    requirement.moc_ap_dung = None
    diagnostics = []
    assert generate(recommendation_case, risks, diagnostics) == []
    assert "Missing required fact: relevant_date" in diagnostics[0]["detail"]


def test_known_citation_without_resolved_basis_gets_knowledge_gap(recommendation_case):
    context, knowledge, requirement = recommendation_case
    risks = mapped_risks(recommendation_case, "INVALID", citation=True)
    source = deepcopy(risks[0].rule_snapshot_json["source_finding_snapshot"])
    source["normalized_van_ban_id"] = None
    source["source_snapshot_json"]["legal_basis_ids"] = []
    request = RiskRequest(
        **context.model_dump(),
        payload={
            "hop_dong_id": "CONTRACT_A",
            "requirements": [requirement],
            "criterion_results": [],
            "citations": [source],
        },
    )
    risks = evaluate_risks(request, knowledge)
    assert len(risks) == 1
    diagnostics = []
    assert generate(recommendation_case, risks, diagnostics) == []
    assert "Missing required legal basis" in diagnostics[0]["detail"]


def test_output_snapshots_are_independent_copies(recommendation_case):
    risks = mapped_risks(recommendation_case)
    result = generate(recommendation_case, risks)[0]
    recommendation_case[1].recommendations["TEMPLATE_A"]["noi_dung"] = "Changed"
    recommendation_case[1].recommendations["TEMPLATE_A"]["gioi_han_sinh_json"][
        "severity_from_db"
    ] = False
    recommendation_case[1].tables["rui_ro_khuyen_nghi"][0]["loai_du_lieu"] = "Changed"
    risks[0].rule_snapshot_json["rule_version"] = "Changed"
    assert result.template_snapshot_json["noi_dung"] != "Changed"
    assert "loai_du_lieu" not in result.template_snapshot_json["mapping_snapshots"][0]
    assert result.dieu_kien_snapshot["risk_rule_snapshot"]["rule_version"] == "RISK_RULE_VERSION_A"
    assert result.dieu_kien_snapshot["generation_limits"]["severity_from_db"] is True
