"""C07 acceptance and rejection tests for all four findings and trusted provenance."""

import json
from copy import deepcopy

import pytest
from legal_checker.modules.compliance.criterion_reasoner import reason
from legal_checker.shared.contracts.reasoning import ReasoningRequest
from test_criterion_reasoner import assert_unknown, only_result
from test_criterion_reasoner import reasoning_case as reasoning_case
from test_numeric_rules import NUMERIC_CASES


def register_external(data):
    """Synthetic backend registration; no actual document or DB needed."""
    evidence = {
        "bang_chung_id": "EXTERNAL_1",
        "object_uri": "memory://receipt",
        "sha256": "c" * 64,
        "verified": True,
    }
    entry = {key: value for key, value in data.items() if key != "payload"}
    entry.update(
        hop_dong_id=data["payload"]["hop_dong_id"],
        yeu_cau_ca_id="CASE_REQUIREMENT_1",
        tieu_chi_id="CRITERION_1",
        verification_reference="memory://backend-review/1",
        **evidence,
    )
    data["payload"]["external_evidence_registry"] = [entry]
    data["payload"]["observations"][0]["external_evidence"] = [evidence]


def missing_case(data):
    observation = data["payload"]["observations"][0]
    observation.update(proposed_finding="MISSING", evidence=[])
    observation["gates"].update(coverage_complete=True, absence_verified=True)
    data["payload"]["retrieval"] = []
    return observation


def test_missing_accepts_verified_absence_without_fabricated_quote(reasoning_case):
    knowledge, data = reasoning_case
    missing_case(data)
    rule = knowledge.decision("CRITERION_1", "MISSING")["dieu_kien_json"]
    rule["gate"].update(
        mandatory_contract_content=True,
        criterion_content_absent=True,
        template_field_unfilled=False,
    )
    result = only_result(knowledge, data)
    assert result.finding == "MISSING"
    assert result.evidence == []
    assert result.gates.missing_allowed()
    assert result.review_status == "PENDING"


@pytest.mark.parametrize(
    "field",
    [
        "coverage_complete",
        "absence_verified",
        "evidence_validated",
        "source_verified",
        "scope_confirmed",
        "version_resolved",
        "exceptions_resolved",
    ],
)
def test_missing_requires_each_absence_and_reliability_gate(reasoning_case, field):
    knowledge, data = reasoning_case
    missing_case(data)["gates"][field] = False
    assert_unknown(only_result(knowledge, data), field)


@pytest.mark.parametrize(
    "field,value",
    [
        ("mandatory_confirmed", False),
        ("all_pages_readable", False),
        ("all_related_documents_received", False),
        ("template_field_unfilled", True),
    ],
)
def test_missing_does_not_mean_unfilled_template_or_incomplete_ocr(reasoning_case, field, value):
    knowledge, data = reasoning_case
    missing_case(data)[field] = value
    assert_unknown(only_result(knowledge, data))


@pytest.mark.parametrize(
    "field,value",
    [
        ("missing_policy", "NO_MISSING_FOR_CONDITIONAL_PERFORMANCE_FORMAT_OR_CONSISTENCY"),
        ("missing_policy", "UNSUPPORTED_POLICY"),
        ("bat_buoc", False),
        ("noi_dung_bat_buoc_trong_hd", False),
        ("loai_kiem_tra", "PERFORMANCE_WITH_DOCUMENTS"),
    ],
)
def test_missing_requires_explicit_catalog_permission(reasoning_case, field, value):
    knowledge, data = reasoning_case
    missing_case(data)
    knowledge.criteria["CRITERION_1"][field] = value
    assert_unknown(only_result(knowledge, data))


def test_missing_cannot_be_proved_from_no_contract_text(reasoning_case):
    knowledge, data = reasoning_case
    missing_case(data)
    data["payload"]["chunks"] = []
    assert_unknown(only_result(knowledge, data), "document")


@pytest.mark.parametrize("finding", ["SATISFIED", "VIOLATED", "MISSING", "UNKNOWN"])
def test_attempted_rule_snapshot_and_metadata_for_each_finding(reasoning_case, finding):
    knowledge, data = reasoning_case
    observation = missing_case(data) if finding == "MISSING" else data["payload"]["observations"][0]
    observation["proposed_finding"] = finding
    snapshot_before = deepcopy(vars(knowledge))
    request = ReasoningRequest.model_validate(data)
    request_before = request.model_dump()
    first = reason(request, knowledge)[0]
    second = reason(request, knowledge)[0]
    assert first.finding == finding
    assert first.ket_qua_id == second.ket_qua_id
    assert first.tieu_chi_snapshot_json["decision_rule_snapshot_json"]["finding"] == finding
    assert first.model_version == observation["model_version"]
    assert first.prompt_version == observation["prompt_version"]
    assert first.lan_chay_id == data["run_id"]
    assert first.review_status == "PENDING"
    assert first.pham_vi_ket_luan == "CURRENT_CRITERION"
    assert request.model_dump() == request_before
    assert vars(knowledge) == snapshot_before


@pytest.mark.parametrize("finding", ["SATISFIED", "VIOLATED"])
def test_empty_evidence_cannot_become_content_finding(reasoning_case, finding):
    knowledge, data = reasoning_case
    data["payload"]["observations"][0].update(proposed_finding=finding, evidence=[])
    data["payload"]["retrieval"] = []
    assert_unknown(only_result(knowledge, data), "evidence")


def test_violation_requires_its_own_enabled_rule(reasoning_case):
    knowledge, data = reasoning_case
    data["payload"]["observations"][0]["proposed_finding"] = "VIOLATED"
    knowledge.decision("CRITERION_1", "VIOLATED")["dieu_kien_json"]["enabled"] = False
    result = only_result(knowledge, data)
    assert_unknown(result, "disabled")
    assert result.tieu_chi_snapshot_json["decision_rule_snapshot_json"]["finding"] == "VIOLATED"


@pytest.mark.parametrize("finding", ["SATISFIED", "VIOLATED", "MISSING", "UNKNOWN"])
@pytest.mark.parametrize(
    "problem", ["missing", "duplicate", "bad-json", "disabled", "unknown-gate"]
)
def test_rule_errors_are_explicit_for_every_proposal(reasoning_case, finding, problem):
    knowledge, data = reasoning_case
    observation = missing_case(data) if finding == "MISSING" else data["payload"]["observations"][0]
    observation["proposed_finding"] = finding
    rule = knowledge.decision("CRITERION_1", finding)
    if problem == "missing":
        knowledge.tables["quy_tac_quyet_dinh"].remove(rule)
    elif problem == "duplicate":
        knowledge.tables["quy_tac_quyet_dinh"].append(deepcopy(rule))
    elif problem == "bad-json":
        rule["dieu_kien_json"] = "{nope"
    elif problem == "disabled":
        rule["dieu_kien_json"]["enabled"] = False
    else:
        rule["dieu_kien_json"]["gate"]["invented_condition"] = True
    assert_unknown(only_result(knowledge, data), "rule", "gate")


@pytest.mark.parametrize(
    "raw",
    [
        '{"enabled":true,"enabled":false}',
        '{"enabled":true,"numeric_rule":NaN}',
        {"enabled": True, "numeric_rule": float("inf")},
    ],
)
def test_rule_rejects_ambiguous_json_or_nonfinite_values(reasoning_case, raw):
    knowledge, data = reasoning_case
    knowledge.decision("CRITERION_1", "SATISFIED")["dieu_kien_json"] = raw
    assert_unknown(only_result(knowledge, data), "json")


@pytest.mark.parametrize("index", range(len(NUMERIC_CASES)))
def test_numeric_findings_are_accepted_only_when_proposal_agrees(reasoning_case, index):
    knowledge, data = reasoning_case
    numeric, facts, field, values, outcomes = NUMERIC_CASES[index]
    observation = data["payload"]["observations"][0]
    register_external(data)
    if index in {0, 1, 2, 5}:
        knowledge.criteria["CRITERION_1"]["loai_kiem_tra"] = "PERFORMANCE_WITH_DOCUMENTS"
    for value, outcome in zip(values, outcomes, strict=True):
        proposal = "SATISFIED" if outcome else "VIOLATED"
        observation.update(
            proposed_finding=proposal, facts={**facts, field: value}, facts_verified=True
        )
        for finding in ("SATISFIED", "VIOLATED"):
            rule = knowledge.decision("CRITERION_1", finding)
            conditions = deepcopy(knowledge.decision("CRITERION_1", "UNKNOWN")["dieu_kien_json"])
            conditions["numeric_rule"] = numeric
            rule["dieu_kien_json"] = json.dumps(conditions)
        assert only_result(knowledge, data).finding == proposal
        observation["proposed_finding"] = "VIOLATED" if outcome else "SATISFIED"
        assert_unknown(only_result(knowledge, data), "disagrees")


def test_unverified_numeric_facts_remain_unknown_even_with_reliable_gates(reasoning_case):
    knowledge, data = reasoning_case
    rule, facts, *_ = NUMERIC_CASES[4]
    knowledge.decision("CRITERION_1", "SATISFIED")["dieu_kien_json"]["numeric_rule"] = rule
    data["payload"]["observations"][0].update(facts=facts, facts_verified=False)
    assert_unknown(only_result(knowledge, data), "unverified")


@pytest.mark.parametrize(
    "criterion_type",
    [
        "PERFORMANCE_OR_CONDITIONAL",
        "DOI_CHIEU_CO_DIEU_KIEN",
        "PROHIBITED_CLAUSE",
        "CONTRACT_CLAUSE_AND_PERFORMANCE",
    ],
)
def test_extended_catalog_types_require_their_type_specific_proofs(reasoning_case, criterion_type):
    knowledge, data = reasoning_case
    knowledge.criteria["CRITERION_1"]["loai_kiem_tra"] = criterion_type
    assert_unknown(only_result(knowledge, data), "evaluation_target", "coverage_complete")


def test_performance_evidence_uses_registry_without_contract_c06(reasoning_case):
    knowledge, data = reasoning_case
    knowledge.criteria["CRITERION_1"]["loai_kiem_tra"] = "PERFORMANCE_WITH_DOCUMENTS"
    register_external(data)
    data["payload"]["observations"][0]["evidence"] = []
    data["payload"]["retrieval"] = []
    result = only_result(knowledge, data)
    assert result.finding == "SATISFIED"
    assert result.evidence == [] and len(result.external_evidence) == 1


@pytest.mark.parametrize(
    "problem", ["no-registry", "unverified-registry", "unverified-evidence", "promise-only"]
)
def test_performance_cannot_use_provider_verified_flag_alone(reasoning_case, problem):
    knowledge, data = reasoning_case
    knowledge.criteria["CRITERION_1"]["loai_kiem_tra"] = "PERFORMANCE_WITH_DOCUMENTS"
    register_external(data)
    if problem == "no-registry":
        data["payload"]["external_evidence_registry"] = []
    elif problem == "unverified-registry":
        data["payload"]["external_evidence_registry"][0]["verified"] = False
    elif problem == "unverified-evidence":
        data["payload"]["observations"][0]["external_evidence"][0]["verified"] = False
    else:
        data["payload"]["observations"][0]["external_evidence"] = []
    assert_unknown(only_result(knowledge, data), "external", "performance")


def test_resolved_c05_not_applicable_is_excluded_with_reason(reasoning_case):
    knowledge, data = reasoning_case
    data["payload"]["requirements"][0].update(
        applicability_status="NOT_APPLICABLE",
        scope_status="NO_MATCH",
        reason={"scope": "Reviewed different transaction type"},
    )
    result = only_result(knowledge, data)
    assert_unknown(result)
    assert result.excluded and "C05" in result.exclusion_reason


@pytest.mark.parametrize("problem", ["scope-unknown", "version-unknown", "no-reason"])
def test_c05_knowledge_gap_is_never_hidden_by_exclusion(reasoning_case, problem):
    knowledge, data = reasoning_case
    requirement = data["payload"]["requirements"][0]
    requirement.update(
        applicability_status="NOT_APPLICABLE", scope_status="NO_MATCH", reason={"scope": "A reason"}
    )
    if problem == "scope-unknown":
        requirement["scope_status"] = "UNKNOWN"
    elif problem == "version-unknown":
        requirement["version_status"] = "UNKNOWN"
    else:
        requirement["reason"] = {}
    if problem == "version-unknown":
        assert reason(ReasoningRequest.model_validate(data), knowledge) == []
        return
    result = only_result(knowledge, data)
    assert_unknown(result)
    assert not result.excluded


def test_local_no_match_requires_review_and_preserves_exclusion_reason(reasoning_case):
    knowledge, data = reasoning_case
    observation = data["payload"]["observations"][0]
    observation.update(
        local_applicability="NO_MATCH", exclusion_reason="Reviewed optional branch not selected"
    )
    result = only_result(knowledge, data)
    assert result.excluded and "optional" in result.exclusion_reason
    observation["gates"]["exceptions_resolved"] = False
    assert not only_result(knowledge, data).excluded


def test_unresolved_version_does_not_generate_fake_criterion_ids(reasoning_case):
    knowledge, data = reasoning_case
    data["payload"]["requirements"][0].update(
        requirement_version_id=None, version_status="UNKNOWN", applicability_status="UNKNOWN"
    )
    data["payload"]["retrieval"] = []
    data["payload"]["observations"] = []
    assert reason(ReasoningRequest.model_validate(data), knowledge) == []


def test_local_exclusion_cannot_hide_missing_grounding(reasoning_case):
    knowledge, data = reasoning_case
    data["payload"]["observations"][0].update(
        local_applicability="NO_MATCH", exclusion_reason="Unattributed scope proposal"
    )
    data["payload"]["retrieval"] = []
    result = only_result(knowledge, data)
    assert_unknown(result, "c06")
    assert not result.excluded


@pytest.mark.parametrize("finding", ["MISSING", "VIOLATED"])
def test_conflict_blocks_absence_and_violation(reasoning_case, finding):
    knowledge, data = reasoning_case
    observation = missing_case(data) if finding == "MISSING" else data["payload"]["observations"][0]
    observation["proposed_finding"] = finding
    observation["gates"]["evidence_conflict"] = True
    assert_unknown(only_result(knowledge, data), "conflict")


@pytest.mark.parametrize("numeric,facts,field,values,expected", NUMERIC_CASES)
def test_numeric_malformed_facts_are_not_accepted_in_reasoner(
    reasoning_case, numeric, facts, field, values, expected
):
    knowledge, data = reasoning_case
    knowledge.decision("CRITERION_1", "SATISFIED")["dieu_kien_json"]["numeric_rule"] = numeric
    data["payload"]["observations"][0].update(facts={**facts, field: True}, facts_verified=True)
    assert_unknown(only_result(knowledge, data), "numeric")


def test_stable_id_changes_for_new_run_or_requirement_instance(reasoning_case):
    knowledge, data = reasoning_case
    first = only_result(knowledge, data).ket_qua_id
    data["run_id"] = "NEW_RUN"
    data["payload"]["retrieval"][0]["lan_chay_id"] = "NEW_RUN"
    second = only_result(knowledge, data).ket_qua_id
    data["payload"]["requirements"][0]["yeu_cau_ca_id"] = "NEW_INSTANCE"
    data["payload"]["retrieval"][0]["yeu_cau_ca_id"] = "NEW_INSTANCE"
    assert len({first, second, only_result(knowledge, data).ket_qua_id}) == 3
