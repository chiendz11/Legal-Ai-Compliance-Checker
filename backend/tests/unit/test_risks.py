"""C10 business boundaries using synthetic C07/C09 inputs, without a database."""

from copy import deepcopy
from types import SimpleNamespace

import pytest
from legal_checker.modules.risks.aggregator import aggregate_risks
from legal_checker.modules.risks.citation_mapper import PRODUCTION_GATE, citation_risks
from legal_checker.modules.risks.compliance_mapper import compliance_risks
from legal_checker.modules.risks.policy import deduplicate
from legal_checker.modules.risks.service import evaluate_risks
from legal_checker.shared.contracts.citation import CitationValidation
from legal_checker.shared.contracts.common import Context
from legal_checker.shared.contracts.modules import RiskRequest
from legal_checker.shared.contracts.reasoning import CriterionResult
from legal_checker.shared.contracts.risk import RiskSource
from legal_checker.shared.contracts.temporal import ApplicableRequirement


@pytest.fixture
def risk_case():
    context = Context(
        ca_id="CASE_A",
        phien_ban_id="DEPLOY_A",
        rule_version="RULES_A",
        legal_knowledge_version="LEGAL_A",
        knowledge_snapshot_sha256="a" * 64,
        run_id="RUN_A",
        trace_id="TRACE_A",
    )
    criterion = {
        "tieu_chi_id": "CRITERION_A",
        "requirement_version_id": "VERSION_A",
        "bat_buoc": True,
        "noi_dung_bat_buoc_trong_hd": True,
        "human_verified": False,
    }
    knowledge = SimpleNamespace(
        sha256=context.knowledge_snapshot_sha256,
        criteria={"CRITERION_A": criterion},
        versions={"VERSION_A": {"requirement_id": "FAMILY_A"}},
        articles={"ARTICLE_A": {"van_ban_id": "LAW_A"}},
        documents={"LAW_A": {"human_verified": True}},
        risks={},
        tables={"quy_tac_rui_ro": []},
    )
    for status in ("VIOLATED", "MISSING", "UNKNOWN"):
        trigger = {
            "enabled": True,
            "criterion_id": criterion["tieu_chi_id"],
            "criterion_target_only": True,
            "scope_of_facts": "CURRENT_CRITERION",
            "finding": status,
            "human_approval_required_for_final": True,
        }
        if status == "UNKNOWN":
            trigger.update(any_unresolved_fact=True, legal_violation_conclusion=False)
        else:
            trigger.update(evidence_validated=True, source_verified=True, exceptions_resolved=True)
        if status == "MISSING":
            trigger.update(
                absence_verified=True, coverage_complete=True, mandatory_contract_content=True
            )
        risk_id = "RISK_" + status
        knowledge.risks[risk_id] = {
            "rui_ro_id": risk_id,
            "nhanh": "COMPLIANCE",
            "tieu_chi_id": criterion["tieu_chi_id"],
            "muc_do_co_so": "REVIEW_REQUIRED" if status == "UNKNOWN" else "HIGH",
            "ban_chat_rui_ro": "VERIFICATION_ONLY"
            if status == "UNKNOWN"
            else "CONDITIONAL_COMPLIANCE",
            "trang_thai_ra_soat": "PENDING_HUMAN",
        }
        knowledge.tables["quy_tac_rui_ro"].append(
            {
                "quy_tac_id": "RULE_" + status,
                "tieu_chi_id": criterion["tieu_chi_id"],
                "nhanh": "COMPLIANCE",
                "trigger_status": status,
                "trigger_json": trigger,
                "rui_ro_id": risk_id,
                "rule_version": "RISK_POLICY_V1",
                "hanh_dong": "REQUEST_VERIFICATION"
                if status == "UNKNOWN"
                else "CREATE_CONDITIONAL_RISK",
            }
        )
    for status, domain in (
        ("STALE", "MATCH"),
        ("INVALID", "MATCH"),
        ("INVALID", "MISMATCH"),
        ("UNKNOWN", "UNKNOWN"),
    ):
        name = status if domain != "MISMATCH" else "DOMAIN_MISMATCH"
        trigger = {
            "schema": "CITATION_RULE_V1_1",
            "branch": "CITATION",
            "production_gate": PRODUCTION_GATE,
            "citation_status": status,
            "knowledge_version": "PINNED_POLICY_A",
            "no_automatic_compliance_effect": True,
        }
        if status == "UNKNOWN":
            trigger.update(
                no_violation_assertion=True,
                missing_or_ambiguous_identity_date_source_or_domain=True,
            )
        elif status == "STALE":
            trigger.update(
                identity_confirmed=True,
                temporal_source_complete=True,
                transition_context_resolved=True,
                relevant_date_required=True,
            )
        elif domain == "MATCH":
            trigger.update(
                domain_status_not="MISMATCH",
                identity_or_context_invalidity_proven=True,
                official_evidence_required=True,
            )
        else:
            trigger.update(
                domain_status="MISMATCH",
                reason_code="DOMAIN_MISMATCH",
                context_mismatch_proven=True,
                official_evidence_required=True,
            )
        risk_id = "CITATION_" + name
        knowledge.risks[risk_id] = {
            "rui_ro_id": risk_id,
            "nhanh": "CITATION",
            "muc_do_co_so": "REVIEW_REQUIRED" if status == "UNKNOWN" else "LOW",
            "ban_chat_rui_ro": "CITATION_ONLY",
        }
        knowledge.tables["quy_tac_rui_ro"].append(
            {
                "quy_tac_id": "RULE_CITATION_" + name,
                "nhanh": "CITATION",
                "trigger_status": status,
                "trigger_json": trigger,
                "rui_ro_id": risk_id,
                "rule_version": "RISK_POLICY_V1",
                "hanh_dong": "CREATE_CITATION_RISK",
            }
        )
    requirement = ApplicableRequirement(
        yeu_cau_ca_id="INSTANCE_A",
        ca_id=context.ca_id,
        phien_ban_id=context.phien_ban_id,
        requirement_id="FAMILY_A",
        requirement_version_id="VERSION_A",
        scope_status="MATCH",
        version_status="RESOLVED",
        applicability_status="CONFIRMED",
        moc_ap_dung="2026-01-01",
    )
    return context, knowledge, requirement


def criterion_finding(case, status="VIOLATED"):
    context, knowledge, requirement = case
    return CriterionResult(
        ket_qua_id="C07_INSTANCE_A",
        ca_id=context.ca_id,
        yeu_cau_ca_id=requirement.yeu_cau_ca_id,
        tieu_chi_id="CRITERION_A",
        finding=status,
        giai_thich="Synthetic criterion finding",
        uncertainty_reason="Need verified payment receipt" if status == "UNKNOWN" else None,
        gates={
            key: True
            for key in (
                "coverage_complete",
                "absence_verified",
                "evidence_validated",
                "source_verified",
                "scope_confirmed",
                "version_resolved",
                "exceptions_resolved",
            )
        },
        evidence=[
            {"doan_id": "CHUNK_A", "trich_dan": "a", "ky_tu_bat_dau": 0, "ky_tu_ket_thuc": 1}
        ],
        legal_basis_ids=["LAW_A", "ARTICLE_A", "VERSION_A"],
        tieu_chi_snapshot_json={
            **deepcopy(knowledge.criteria["CRITERION_A"]),
            "knowledge_snapshot_sha256": knowledge.sha256,
            "context": context.model_dump(mode="json"),
            "hop_dong_id": "CONTRACT_A",
        },
        model_version="SYNTHETIC_TEST_INPUT",
        prompt_version="NOT_USED",
        lan_chay_id=context.run_id,
        mandatory=True,
    )


def citation_finding(case, status="STALE", domain="MATCH"):
    context, knowledge, _ = case
    return CitationValidation(
        finding_id="C09_INSTANCE_A",
        ca_id=context.ca_id,
        vien_dan_id="C03_A",
        normalized_van_ban_id="LAW_A",
        relevant_date="2026-01-01",
        status=status,
        reason_code="DOMAIN_MISMATCH" if domain == "MISMATCH" else status,
        ly_do="Need source identity"
        if status == "UNKNOWN"
        else "Synthetic verified citation finding",
        domain_status=domain,
        finding_verified=status != "UNKNOWN",
        source_snapshot_json={
            "knowledge_snapshot_sha256": knowledge.sha256,
            "context": context.model_dump(mode="json"),
            "hop_dong_id": "CONTRACT_A",
            "reviewed_knowledge": True,
            "official_evidence_verified": True,
            "identity_confirmed": True,
            "temporal_source_complete": True,
            "transition_context_resolved": True,
            "identity_or_context_invalidity_proven": True,
            "context_mismatch_proven": True,
            "evidence_ids": ["C03_A"],
            "legal_basis_ids": ["ARTICLE_A"],
        },
        lan_chay_id=context.run_id,
        knowledge_version=context.legal_knowledge_version,
    )


def request_for(case, criteria=None, citations=None):
    context, _, requirement = case
    return RiskRequest(
        **context.model_dump(),
        payload={
            "hop_dong_id": "CONTRACT_A",
            "requirements": [requirement],
            "criterion_results": criteria or [],
            "citations": citations or [],
        },
    )


def compliance_rule(case, status="VIOLATED"):
    return next(
        row for row in case[1].tables["quy_tac_rui_ro"] if row["quy_tac_id"] == "RULE_" + status
    )


@pytest.mark.parametrize(
    "status,kind,severity",
    [
        ("VIOLATED", "COMPLIANCE", "HIGH"),
        ("MISSING", "COMPLIANCE", "HIGH"),
        ("UNKNOWN", "VERIFICATION", "REVIEW_REQUIRED"),
    ],
)
def test_compliance_mapping_binds_finding_instance_and_pinned_snapshots(
    risk_case, status, kind, severity
):
    context, knowledge, _ = risk_case
    finding = criterion_finding(risk_case, status)
    original = finding.model_dump()
    (risk,) = compliance_risks(context, knowledge, [finding])
    assert risk.source.ket_qua_tieu_chi_id == finding.ket_qua_id
    assert risk.source.citation_finding_id is None
    assert risk.source.yeu_cau_ca_id == finding.yeu_cau_ca_id
    assert risk.risk_type == kind and risk.severity == severity
    assert risk.rule_snapshot_json["source_finding_snapshot"] == finding.model_dump(mode="json")
    assert risk.rule_snapshot_json["context"] == context.model_dump(mode="json")
    assert risk.risk_snapshot == knowledge.risks[risk.rui_ro_id]
    assert risk.review_status == "PENDING"
    assert finding.model_dump() == original
    knowledge.risks[risk.rui_ro_id]["muc_do_co_so"] = "LOW"
    assert risk.risk_snapshot["muc_do_co_so"] == severity


@pytest.mark.parametrize("status", ["SATISFIED", "UNKNOWN"])
def test_satisfied_and_excluded_criteria_do_not_create_risks(risk_case, status):
    finding = criterion_finding(risk_case, status)
    if status == "UNKNOWN":
        finding.excluded = True
        finding.exclusion_reason = "Verified local non-applicability"
    assert compliance_risks(*risk_case[:2], [finding]) == []


@pytest.mark.parametrize(
    "field,value",
    [
        ("ca_id", "FOREIGN"),
        ("lan_chay_id", "FOREIGN"),
        ("tieu_chi_id", "FOREIGN"),
        ("mandatory", False),
    ],
)
def test_c07_ownership_and_criterion_mandatory_mismatch_rejected(risk_case, field, value):
    finding = criterion_finding(risk_case)
    setattr(finding, field, value)
    with pytest.raises(ValueError):
        compliance_risks(*risk_case[:2], [finding])


@pytest.mark.parametrize(
    "key,value",
    [
        ("knowledge_snapshot_sha256", "b" * 64),
        ("bat_buoc", False),
        ("context", {"run_id": "FOREIGN"}),
    ],
)
def test_c07_pinned_snapshot_tampering_rejected(risk_case, key, value):
    finding = criterion_finding(risk_case)
    finding.tieu_chi_snapshot_json[key] = value
    with pytest.raises(ValueError):
        compliance_risks(*risk_case[:2], [finding])


@pytest.mark.parametrize("source", ["criterion", "citation"])
def test_contract_ownership_checked_when_upstream_supplies_contract_pin(risk_case, source):
    finding = criterion_finding(risk_case) if source == "criterion" else citation_finding(risk_case)
    snapshot = (
        finding.tieu_chi_snapshot_json if source == "criterion" else finding.source_snapshot_json
    )
    snapshot["hop_dong_id"] = "FOREIGN_CONTRACT"
    request = request_for(
        risk_case,
        [finding] if source == "criterion" else [],
        [finding] if source == "citation" else [],
    )
    with pytest.raises(ValueError, match="contract ownership"):
        evaluate_risks(request, risk_case[1])


@pytest.mark.parametrize("mutation", ["owner", "version", "unconfirmed"])
def test_service_rejects_foreign_requirement_and_unconfirmed_known_findings(risk_case, mutation):
    request = request_for(risk_case, [criterion_finding(risk_case)])
    if mutation == "owner":
        request.payload.criterion_results[0].yeu_cau_ca_id = "FOREIGN_INSTANCE"
    elif mutation == "version":
        risk_case[1].versions["VERSION_B"] = {"requirement_id": "FAMILY_A"}
        request.payload.requirements[0].requirement_version_id = "VERSION_B"
    else:
        request.payload.requirements[0].applicability_status = "UNKNOWN"
    with pytest.raises(ValueError):
        evaluate_risks(request, risk_case[1])


def test_duplicate_c07_identity_and_unpinned_legal_basis_rejected(risk_case):
    finding = criterion_finding(risk_case)
    with pytest.raises(ValueError, match="Duplicate C07"):
        compliance_risks(*risk_case[:2], [finding, finding.model_copy(deep=True)])
    finding.legal_basis_ids.append("INVENTED_LAW")
    with pytest.raises(ValueError, match="legal basis"):
        compliance_risks(*risk_case[:2], [finding])


@pytest.mark.parametrize(
    "flag",
    [
        "source_verified",
        "evidence_validated",
        "exceptions_resolved",
        "coverage_complete",
        "absence_verified",
    ],
)
def test_missing_requires_all_absence_and_verification_gates(risk_case, flag):
    finding = criterion_finding(risk_case, "MISSING")
    setattr(finding.gates, flag, False)
    with pytest.raises(ValueError):
        compliance_risks(*risk_case[:2], [finding])


@pytest.mark.parametrize(
    "mutation,code",
    [
        ("disabled", None),
        ("enabled_false", None),
        ("enabled_invalid", "INVALID_RISK_POLICY"),
        ("malformed", "INVALID_RISK_POLICY"),
        ("unknown_guard", "UNSUPPORTED_RISK_GUARD"),
        ("invalid_guard", "INVALID_RISK_GUARD"),
        ("missing_catalog", "MISSING_RISK_CATALOG"),
        ("disabled_catalog", "DISABLED_RISK_CATALOG"),
        ("catalog_context", "RISK_CATALOG_CONTEXT_MISMATCH"),
        ("severity", "INVALID_SEVERITY"),
        ("version", "MISSING_RULE_VERSION"),
        ("action", "UNSUPPORTED_RISK_ACTION"),
    ],
)
def test_rule_and_catalog_gaps_fail_closed_with_diagnostics(risk_case, mutation, code):
    context, knowledge, _ = risk_case
    rule = compliance_rule(risk_case)
    catalog = knowledge.risks[rule["rui_ro_id"]]
    if mutation == "disabled":
        rule["trang_thai"] = "DISABLED"
    elif mutation == "enabled_false":
        rule["trigger_json"]["enabled"] = False
    elif mutation == "enabled_invalid":
        rule["trigger_json"]["enabled"] = 1
    elif mutation == "malformed":
        rule["trigger_json"] = "[broken"
    elif mutation == "unknown_guard":
        rule["trigger_json"]["invented_legal_gate"] = True
    elif mutation == "invalid_guard":
        rule["trigger_json"]["source_verified"] = "true"
    elif mutation == "missing_catalog":
        knowledge.risks.pop(rule["rui_ro_id"])
    elif mutation == "disabled_catalog":
        catalog["trang_thai"] = "RETIRED"
    elif mutation == "catalog_context":
        catalog["tieu_chi_id"] = "FOREIGN_CRITERION"
    elif mutation == "severity":
        catalog["muc_do_co_so"] = "EXTREME"
    elif mutation == "version":
        rule.pop("rule_version")
    else:
        rule["hanh_dong"] = "ASSERT_CONTRACT_INVALID"
    diagnostics = []
    assert (
        compliance_risks(
            context, knowledge, [criterion_finding(risk_case)], diagnostics=diagnostics
        )
        == []
    )
    if code:
        assert code in {row["code"] for row in diagnostics}


@pytest.mark.parametrize("mutation", ["severity", "catalog", "assertion", "action"])
def test_unknown_only_creates_explicit_verification_risk(risk_case, mutation):
    rule = compliance_rule(risk_case, "UNKNOWN")
    catalog = risk_case[1].risks[rule["rui_ro_id"]]
    if mutation == "severity":
        catalog["muc_do_co_so"] = "HIGH"
    elif mutation == "catalog":
        catalog["ban_chat_rui_ro"] = "CONDITIONAL_COMPLIANCE"
    elif mutation == "assertion":
        rule["trigger_json"]["legal_violation_conclusion"] = True
    else:
        rule["hanh_dong"] = "CREATE_CONDITIONAL_RISK"
    assert compliance_risks(*risk_case[:2], [criterion_finding(risk_case, "UNKNOWN")]) == []


@pytest.mark.parametrize(
    "status,domain,risk_id",
    [
        ("STALE", "MATCH", "CITATION_STALE"),
        ("INVALID", "MATCH", "CITATION_INVALID"),
        ("INVALID", "MISMATCH", "CITATION_DOMAIN_MISMATCH"),
        ("UNKNOWN", "UNKNOWN", "CITATION_UNKNOWN"),
    ],
)
def test_supported_citation_status_reason_domain_and_source_binding(
    risk_case, status, domain, risk_id
):
    context, knowledge, _ = risk_case
    finding = citation_finding(risk_case, status, domain)
    (risk,) = citation_risks(context, knowledge, [finding])
    assert risk.rui_ro_id == risk_id
    assert risk.source.citation_finding_id == finding.finding_id
    assert risk.source.ket_qua_tieu_chi_id is None and risk.source.yeu_cau_ca_id is None
    assert risk.risk_type == ("VERIFICATION" if status == "UNKNOWN" else "CITATION")
    assert risk.evidence_ids == ["C03_A"]
    assert risk.legal_basis_ids == ["ARTICLE_A", "LAW_A"]


def test_historical_valid_citation_never_creates_risk_due_to_current_expiry(risk_case):
    finding = citation_finding(risk_case, "VALID")
    finding.current_status = "EXPIRED"
    assert citation_risks(*risk_case[:2], [finding]) == []


@pytest.mark.parametrize(
    "field", ["ca_id", "lan_chay_id", "knowledge_version", "snapshot_hash", "context"]
)
def test_citation_foreign_context_and_snapshot_rejected(risk_case, field):
    finding = citation_finding(risk_case)
    if field == "snapshot_hash":
        finding.source_snapshot_json["knowledge_snapshot_sha256"] = "b" * 64
    elif field == "context":
        finding.source_snapshot_json["context"]["run_id"] = "FOREIGN"
    else:
        setattr(finding, field, "FOREIGN")
    with pytest.raises(ValueError):
        citation_risks(*risk_case[:2], [finding])


@pytest.mark.parametrize(
    "mutation",
    ["unverified", "unreviewed", "pinned_unreviewed", "identity", "temporal", "transition", "date"],
)
def test_stale_citation_requires_backend_verification_and_temporal_review(risk_case, mutation):
    finding = citation_finding(risk_case)
    if mutation == "unverified":
        finding.finding_verified = False
    elif mutation == "unreviewed":
        finding.source_snapshot_json["reviewed_knowledge"] = False
    elif mutation == "pinned_unreviewed":
        risk_case[1].documents["LAW_A"]["human_verified"] = False
    elif mutation == "date":
        finding.relevant_date = None
    else:
        key = {
            "identity": "identity_confirmed",
            "temporal": "temporal_source_complete",
            "transition": "transition_context_resolved",
        }[mutation]
        finding.source_snapshot_json[key] = False
    assert citation_risks(*risk_case[:2], [finding]) == []


@pytest.mark.parametrize("mutation", ["official", "identity", "domain_reason"])
def test_invalid_citation_requires_proof_and_matching_reason(risk_case, mutation):
    finding = citation_finding(
        risk_case, "INVALID", "MISMATCH" if mutation == "domain_reason" else "MATCH"
    )
    if mutation == "official":
        finding.source_snapshot_json["official_evidence_verified"] = False
    elif mutation == "identity":
        finding.source_snapshot_json["identity_or_context_invalidity_proven"] = False
    else:
        finding.reason_code = "IDENTITY_AMBIGUOUS"
    assert citation_risks(*risk_case[:2], [finding]) == []


@pytest.mark.parametrize(
    "mutation,code",
    [
        ("schema", "UNSUPPORTED_CITATION_POLICY"),
        ("gate", "UNSUPPORTED_CITATION_POLICY"),
        ("structural", "UNSUPPORTED_CITATION_POLICY"),
        ("unsupported", "UNSUPPORTED_CITATION_GUARD"),
        ("boolean", "INVALID_CITATION_GUARD"),
    ],
)
def test_unsupported_citation_policies_are_diagnostic(risk_case, mutation, code):
    rule = next(
        row
        for row in risk_case[1].tables["quy_tac_rui_ro"]
        if row["quy_tac_id"] == "RULE_CITATION_STALE"
    )
    key, value = {
        "schema": ("schema", "CITATION_RULE_FUTURE"),
        "gate": ("production_gate", "NO_REVIEW"),
        "structural": ("no_automatic_compliance_effect", False),
        "unsupported": ("invented_guard", True),
        "boolean": ("finding_verified", 1),
    }[mutation]
    rule["trigger_json"][key] = value
    diagnostics = []
    assert (
        citation_risks(*risk_case[:2], [citation_finding(risk_case)], diagnostics=diagnostics) == []
    )
    assert code in {row["code"] for row in diagnostics}


def test_missing_rules_and_empty_c09_are_reported(risk_case):
    context, knowledge, _ = risk_case
    knowledge.tables["quy_tac_rui_ro"] = []
    diagnostics = []
    assert (
        aggregate_risks(
            context, knowledge, [criterion_finding(risk_case)], [], diagnostics=diagnostics
        )
        == []
    )
    assert {row["code"] for row in diagnostics} == {"C09_INPUT_EMPTY", "MISSING_RISK_RULE"}
    diagnostics.clear()
    assert (
        citation_risks(context, knowledge, [citation_finding(risk_case)], diagnostics=diagnostics)
        == []
    )
    assert diagnostics[0]["subject_id"] == "C09_INSTANCE_A"


def test_two_branches_are_independent_and_do_not_mutate_upstream(risk_case):
    context, knowledge, _ = risk_case
    criteria = [criterion_finding(risk_case)]
    citations = [citation_finding(risk_case, "INVALID", "MISMATCH")]
    originals = [criteria[0].model_dump(), citations[0].model_dump(), deepcopy(knowledge.tables)]
    first = compliance_risks(context, knowledge, criteria)
    second = citation_risks(context, knowledge, citations)
    together = aggregate_risks(context, knowledge, criteria, citations)
    assert {row.ket_qua_rui_ro_id for row in together} == {
        row.ket_qua_rui_ro_id for row in first + second
    }
    assert [row for row in together if row.source.ket_qua_tieu_chi_id] == first
    assert [row for row in together if row.source.citation_finding_id] == second
    assert [criteria[0].model_dump(), citations[0].model_dump(), knowledge.tables] == originals


def test_multiple_matching_rules_deduplicate_stably_and_preserve_all_rule_versions(risk_case):
    context, knowledge, _ = risk_case
    second = deepcopy(compliance_rule(risk_case))
    second["quy_tac_id"] = "ANOTHER_RULE"
    second["rule_version"] = "OTHER_RULE_VERSION"
    knowledge.tables["quy_tac_rui_ro"].append(second)
    (risk,) = compliance_risks(context, knowledge, [criterion_finding(risk_case)])
    assert {row["quy_tac_id"] for row in risk.rule_snapshot_json["matched_rules"]} == {
        "RULE_VIOLATED",
        "ANOTHER_RULE",
    }
    assert {row["rule_version"] for row in risk.rule_snapshot_json["matched_rules"]} == {
        "RISK_POLICY_V1",
        "OTHER_RULE_VERSION",
    }
    knowledge.tables["quy_tac_rui_ro"].reverse()
    assert compliance_risks(context, knowledge, [criterion_finding(risk_case)]) == [risk]
    another = criterion_finding(risk_case)
    another.ket_qua_id = "C07_OTHER_INSTANCE"
    (other_risk,) = compliance_risks(context, knowledge, [another])
    assert other_risk.ket_qua_rui_ro_id != risk.ket_qua_rui_ro_id


@pytest.mark.parametrize("field", ["severity", "ca_id", "context"])
def test_conflicting_duplicate_business_identity_rejected(risk_case, field):
    (risk,) = compliance_risks(*risk_case[:2], [criterion_finding(risk_case)])
    duplicate = risk.model_copy(deep=True)
    if field == "context":
        duplicate.rule_snapshot_json["context"]["phien_ban_id"] = "FOREIGN"
    else:
        setattr(duplicate, field, "LOW" if field == "severity" else "FOREIGN")
    with pytest.raises(ValueError, match="Conflicting duplicate"):
        deduplicate([risk, duplicate])


@pytest.mark.parametrize("criterion,citation", [(None, None), ("C07_A", "C09_A")])
def test_c10_source_requires_xor(criterion, citation):
    with pytest.raises(ValueError, match="exactly one"):
        RiskSource(ket_qua_tieu_chi_id=criterion, citation_finding_id=citation)


@pytest.mark.parametrize("mutation", ["unknown_severity", "unknown_catalog", "unknown_assertion"])
def test_unknown_citation_never_becomes_a_legal_violation(risk_case, mutation):
    knowledge = risk_case[1]
    if mutation == "unknown_severity":
        knowledge.risks["CITATION_UNKNOWN"]["muc_do_co_so"] = "HIGH"
    elif mutation == "unknown_catalog":
        knowledge.risks["CITATION_UNKNOWN"]["ban_chat_rui_ro"] = "CONDITIONAL_COMPLIANCE"
    else:
        rule = next(
            row
            for row in knowledge.tables["quy_tac_rui_ro"]
            if row["quy_tac_id"] == "RULE_CITATION_UNKNOWN"
        )
        rule["trigger_json"]["no_violation_assertion"] = False
    assert citation_risks(*risk_case[:2], [citation_finding(risk_case, "UNKNOWN", "UNKNOWN")]) == []


@pytest.mark.parametrize(
    "key,value",
    [("evidence_ids", "C03_A"), ("evidence_ids", [123]), ("legal_basis_ids", ["INVENTED_LAW"])],
)
def test_citation_evidence_and_legal_basis_are_well_typed_and_pinned(risk_case, key, value):
    finding = citation_finding(risk_case)
    finding.source_snapshot_json[key] = value
    with pytest.raises(ValueError):
        citation_risks(*risk_case[:2], [finding])


def test_duplicate_citation_finding_is_rejected(risk_case):
    finding = citation_finding(risk_case)
    with pytest.raises(ValueError, match="Duplicate citation"):
        citation_risks(*risk_case[:2], [finding, finding.model_copy(deep=True)])


def test_known_rule_guard_mismatch_and_absence_without_mandatory_content_do_not_map(risk_case):
    finding = criterion_finding(risk_case)
    compliance_rule(risk_case)["trigger_json"]["criterion_id"] = "OTHER_CRITERION"
    assert compliance_risks(*risk_case[:2], [finding]) == []
    criterion = risk_case[1].criteria["CRITERION_A"]
    criterion["noi_dung_bat_buoc_trong_hd"] = False
    finding = criterion_finding(risk_case, "MISSING")
    assert compliance_risks(*risk_case[:2], [finding]) == []


@pytest.mark.parametrize("key", ["knowledge_snapshot_sha256", "context", "hop_dong_id"])
@pytest.mark.parametrize("status", ["VIOLATED", "UNKNOWN"])
def test_c07_missing_provenance_is_rejected_without_adopting_current_pins(risk_case, key, status):
    finding = criterion_finding(risk_case, status)
    finding.tieu_chi_snapshot_json.pop(key)
    with pytest.raises(ValueError):
        compliance_risks(*risk_case[:2], [finding])


@pytest.mark.parametrize(
    "key", ["phien_ban_id", "rule_version", "run_id", "legal_knowledge_version"]
)
def test_c07_incomplete_context_identity_is_rejected(risk_case, key):
    finding = criterion_finding(risk_case)
    finding.tieu_chi_snapshot_json["context"].pop(key)
    with pytest.raises(ValueError, match="context/run/snapshot"):
        compliance_risks(*risk_case[:2], [finding])


@pytest.mark.parametrize("key", ["knowledge_snapshot_sha256", "context", "hop_dong_id"])
@pytest.mark.parametrize("status", ["STALE", "INVALID", "UNKNOWN"])
def test_c09_missing_provenance_is_diagnostic_and_only_allows_verification(risk_case, key, status):
    finding = citation_finding(risk_case, status, "UNKNOWN" if status == "UNKNOWN" else "MATCH")
    finding.source_snapshot_json.pop(key)
    original = finding.model_dump(mode="json")
    diagnostics = []
    risks = evaluate_risks(
        request_for(risk_case, citations=[finding]), risk_case[1], diagnostics=diagnostics
    )
    assert {row["code"] for row in diagnostics} == {"C09_PROVENANCE_UNAVAILABLE"}
    assert key in diagnostics[0]["detail"]
    if status == "UNKNOWN":
        (risk,) = risks
        assert risk.risk_type == "VERIFICATION" and risk.severity == "REVIEW_REQUIRED"
        assert risk.rule_snapshot_json["source_finding_snapshot"] == original
        assert key not in risk.rule_snapshot_json["source_finding_snapshot"]["source_snapshot_json"]
    else:
        assert risks == []
    assert finding.model_dump(mode="json") == original


@pytest.mark.parametrize(
    "key,value",
    [
        ("knowledge_snapshot_sha256", "b" * 64),
        ("context", {"run_id": "FOREIGN"}),
        ("hop_dong_id", "FOREIGN"),
    ],
)
def test_unknown_citation_supplied_wrong_provenance_is_rejected(risk_case, key, value):
    finding = citation_finding(risk_case, "UNKNOWN", "UNKNOWN")
    finding.source_snapshot_json[key] = value
    with pytest.raises(ValueError):
        evaluate_risks(request_for(risk_case, citations=[finding]), risk_case[1])


@pytest.mark.parametrize("branch", ["C07", "C09"])
def test_trace_is_correlation_metadata_not_a_different_business_identity(risk_case, branch):
    finding = criterion_finding(risk_case) if branch == "C07" else citation_finding(risk_case)
    snapshot = finding.tieu_chi_snapshot_json if branch == "C07" else finding.source_snapshot_json
    snapshot["context"]["trace_id"] = "RETRY_TRACE"
    risks = (compliance_risks if branch == "C07" else citation_risks)(*risk_case[:2], [finding])
    assert len(risks) == 1


@pytest.mark.parametrize("branch", ["C07", "C09"])
@pytest.mark.parametrize("contract_id", [None, "", " "])
def test_supplied_empty_contract_pin_is_rejected(risk_case, branch, contract_id):
    finding = criterion_finding(risk_case) if branch == "C07" else citation_finding(risk_case)
    snapshot = finding.tieu_chi_snapshot_json if branch == "C07" else finding.source_snapshot_json
    snapshot["hop_dong_id"] = contract_id
    with pytest.raises(ValueError, match="contract ownership pin"):
        (compliance_risks if branch == "C07" else citation_risks)(*risk_case[:2], [finding])
