"""C08 policy, complete checklist, exclusion and provenance regression tests.

All findings are synthetic test inputs. No seed/reference C08 output is copied.
"""

import json
from copy import deepcopy

import pytest
from legal_checker.modules.compliance.requirement_aggregator import (
    POLICY_CONDITIONS,
    POLICY_ID,
    POLICY_PRIORITY,
    aggregate,
    excluded_requirement_ids,
)
from legal_checker.shared.contracts.common import Context
from legal_checker.shared.contracts.reasoning import CriterionResult, ReasoningRequest
from legal_checker.shared.contracts.temporal import ApplicableRequirement


class AggregationKnowledge:
    def __init__(self):
        self.sha256 = "a" * 64
        self.versions = {
            "VERSION_A": {
                "requirement_version_id": "VERSION_A",
                "requirement_id": "FAMILY_A",
                "quy_tac_tong_hop_id": POLICY_ID,
                "trang_thai_ra_soat": "PENDING_HUMAN",
            }
        }
        self.criteria = {
            key: {
                "tieu_chi_id": key,
                "requirement_version_id": "VERSION_A",
                "bat_buoc": True,
                "human_verified": False,
            }
            for key in ("CRITERION_A", "CRITERION_B", "CRITERION_C")
        }
        self.aggregations = {
            POLICY_ID: {
                "quy_tac_tong_hop_id": POLICY_ID,
                "rule_version": "AGG_TEST_V1",
                "dieu_kien_json": deepcopy(POLICY_CONDITIONS),
                "thu_tu_uu_tien_json": deepcopy(POLICY_PRIORITY),
                "trang_thai": "ENGINE_POLICY",
            }
        }

    def criteria_for(self, version_id):
        return [
            row for row in self.criteria.values() if row["requirement_version_id"] == version_id
        ]


@pytest.fixture
def aggregation_case():
    knowledge = AggregationKnowledge()
    context = Context(
        ca_id="CASE_A",
        phien_ban_id="DEPLOY_A",
        rule_version="DEPLOY_RULES",
        legal_knowledge_version="LEGAL_A",
        knowledge_snapshot_sha256=knowledge.sha256,
        run_id="RUN_A",
        trace_id="TRACE_A",
    )
    requirement = ApplicableRequirement(
        yeu_cau_ca_id="CASE_REQUIREMENT_A",
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


def findings_for(case, findings):
    context, knowledge, requirement = case
    results = []
    for criterion, finding in zip(knowledge.criteria.values(), findings, strict=False):
        results.append(
            CriterionResult(
                ket_qua_id="RESULT_" + criterion["tieu_chi_id"],
                ca_id=context.ca_id,
                yeu_cau_ca_id=requirement.yeu_cau_ca_id,
                tieu_chi_id=criterion["tieu_chi_id"],
                finding=finding,
                giai_thich="Synthetic downstream input; not a legal gold label",
                gates={
                    "coverage_complete": True,
                    "absence_verified": True,
                    "evidence_validated": True,
                    "source_verified": True,
                    "scope_confirmed": True,
                    "version_resolved": True,
                    "exceptions_resolved": True,
                },
                uncertainty_reason="Missing verified fact" if finding == "UNKNOWN" else None,
                evidence=[
                    {
                        "doan_id": "CHUNK_A",
                        "trich_dan": "a",
                        "ky_tu_bat_dau": 0,
                        "ky_tu_ket_thuc": 1,
                    }
                ],
                legal_basis_ids=["ARTICLE_A"],
                tieu_chi_snapshot_json={
                    **deepcopy(criterion),
                    "knowledge_snapshot_sha256": knowledge.sha256,
                    "context": context.model_dump(mode="json"),
                    "hop_dong_id": "CONTRACT_A",
                },
                model_version="SYNTHETIC_TEST",
                prompt_version="NOT_USED",
                lan_chay_id=context.run_id,
                mandatory=criterion["bat_buoc"] is True,
            )
        )
    return results


def only_aggregate(case, findings):
    context, knowledge, requirement = case
    return aggregate(context, knowledge, findings, [requirement])[0]


@pytest.mark.parametrize(
    ("labels", "status", "unknown", "coverage"),
    [
        (["SATISFIED"] * 3, "COMPLIANT", 0, True),
        (["MISSING"] * 3, "NON_COMPLIANT", 0, True),
        (["SATISFIED", "MISSING", "SATISFIED"], "PARTIAL", 0, True),
        (["MISSING", "MISSING", "SATISFIED"], "PARTIAL", 0, True),
        (["VIOLATED", "SATISFIED", "MISSING"], "NON_COMPLIANT", 0, True),
        (["VIOLATED", "UNKNOWN", "MISSING"], "NON_COMPLIANT", 1, False),
        (["UNKNOWN", "SATISFIED", "MISSING"], "INSUFFICIENT", 1, False),
        (["UNKNOWN"] * 3, "INSUFFICIENT", 3, False),
    ],
)
def test_policy_precedence_and_counts(aggregation_case, labels, status, unknown, coverage):
    result = only_aggregate(aggregation_case, findings_for(aggregation_case, labels))
    assert result.status == status
    assert result.so_tieu_chi_ap_dung == result.so_tieu_chi_da_danh_gia == 3
    assert result.so_unknown == unknown
    assert result.coverage_complete is coverage
    assert result.rule_version == "AGG_TEST_V1"


def test_missing_findings_precede_proven_violation(aggregation_case):
    result = only_aggregate(aggregation_case, findings_for(aggregation_case, ["VIOLATED"]))
    assert result.status == "INSUFFICIENT"
    assert result.so_tieu_chi_ap_dung == 3
    assert result.so_tieu_chi_da_danh_gia == 1
    assert result.so_unknown == 0
    assert result.coverage_complete is False
    assert result.requirement_snapshot_json["missing_criterion_ids"] == [
        "CRITERION_B",
        "CRITERION_C",
    ]


@pytest.mark.parametrize("candidate_version", [None, "VERSION_A"])
def test_unresolved_requirement_retained_without_invented_findings(
    aggregation_case, candidate_version
):
    context, knowledge, requirement = aggregation_case
    requirement.requirement_version_id = candidate_version
    requirement.version_status = "UNKNOWN"
    requirement.applicability_status = "UNKNOWN"
    result = aggregate(context, knowledge, [], [requirement])[0]
    assert result.status == "INSUFFICIENT"
    assert result.so_tieu_chi_ap_dung == result.so_tieu_chi_da_danh_gia == result.so_unknown == 0
    assert result.requirement_snapshot_json["expected_criterion_ids"] == []
    assert result.requirement_snapshot_json["applicable_requirement"]["requirement_version_id"] == (
        candidate_version
    )


def test_unconfirmed_scope_precedes_proven_violation(aggregation_case):
    criteria = findings_for(aggregation_case, ["VIOLATED"] * 3)
    aggregation_case[2].scope_status = "UNKNOWN"
    aggregation_case[2].applicability_status = "UNKNOWN"
    assert only_aggregate(aggregation_case, criteria).status == "INSUFFICIENT"


@pytest.mark.parametrize(
    "problem", ["missing", "unknown-id", "conditions", "priority", "json", "disabled"]
)
def test_missing_unsupported_or_conflicting_policy_fails_closed(aggregation_case, problem):
    knowledge = aggregation_case[1]
    policy = knowledge.aggregations[POLICY_ID]
    if problem == "missing":
        knowledge.aggregations.clear()
    elif problem == "unknown-id":
        knowledge.versions["VERSION_A"]["quy_tac_tong_hop_id"] = "NEW_POLICY"
        knowledge.aggregations["NEW_POLICY"] = {**policy, "quy_tac_tong_hop_id": "NEW_POLICY"}
    elif problem == "conditions":
        policy["dieu_kien_json"]["COMPLIANT"] = "A 50 percent majority is enough"
    elif problem == "priority":
        policy["thu_tu_uu_tien_json"].reverse()
    elif problem == "json":
        policy["dieu_kien_json"] = "{"
    else:
        policy["trang_thai"] = "DISABLED"
    result = only_aggregate(aggregation_case, findings_for(aggregation_case, ["VIOLATED"] * 3))
    assert result.status == "INSUFFICIENT"
    assert result.requirement_snapshot_json["diagnostics"]
    assert not result.coverage_complete


def test_json_text_policy_and_snapshot_are_preserved_without_approving_knowledge(aggregation_case):
    context, knowledge, _ = aggregation_case
    policy = knowledge.aggregations[POLICY_ID]
    policy["dieu_kien_json"] = json.dumps(policy["dieu_kien_json"])
    policy["thu_tu_uu_tien_json"] = json.dumps(policy["thu_tu_uu_tien_json"])
    results = findings_for(aggregation_case, ["SATISFIED"] * 3)
    before = deepcopy(knowledge.__dict__)
    output = only_aggregate(aggregation_case, results)
    assert output.status == "COMPLIANT"
    assert output.requirement_snapshot_json["aggregation_policy"] == policy
    assert (
        output.requirement_snapshot_json["knowledge_snapshot_sha256"]
        == context.knowledge_snapshot_sha256
    )
    assert (
        output.requirement_snapshot_json["requirement_version"]["trang_thai_ra_soat"]
        == "PENDING_HUMAN"
    )
    assert knowledge.__dict__ == before
    policy["rule_version"] = "AFTER_CAPTURE"
    assert output.rule_version == "AGG_TEST_V1"
    assert output.requirement_snapshot_json["aggregation_policy"]["rule_version"] == "AGG_TEST_V1"


def test_coverage_does_not_hide_incomplete_evidence_review(aggregation_case):
    criteria = findings_for(aggregation_case, ["VIOLATED", "SATISFIED", "SATISFIED"])
    criteria[1].gates.coverage_complete = False
    result = only_aggregate(aggregation_case, criteria)
    assert result.status == "NON_COMPLIANT"
    assert not result.coverage_complete
    assert result.requirement_snapshot_json["finding_coverage_complete"]
    assert not result.requirement_snapshot_json["evidence_coverage_complete"]


def test_resolved_not_applicable_excluded_with_reason(aggregation_case):
    context, knowledge, requirement = aggregation_case
    requirement.applicability_status = "NOT_APPLICABLE"
    requirement.scope_status = "NO_MATCH"
    requirement.reason = {"scope": "Verified different transaction type"}
    assert aggregate(context, knowledge, [], [requirement]) == []
    assert excluded_requirement_ids(context, knowledge, [requirement]) == [
        requirement.yeu_cau_ca_id
    ]


@pytest.mark.parametrize(
    "gap", ["missing-policy", "unsupported-policy", "empty-criteria", "mandatory"]
)
def test_requirement_exclusion_cannot_conceal_knowledge_gap(aggregation_case, gap):
    context, knowledge, requirement = aggregation_case
    requirement.applicability_status = "NOT_APPLICABLE"
    requirement.scope_status = "NO_MATCH"
    requirement.reason = {"scope": "Verified different transaction type"}
    if gap == "missing-policy":
        knowledge.aggregations.clear()
    elif gap == "unsupported-policy":
        knowledge.aggregations[POLICY_ID]["thu_tu_uu_tien_json"].reverse()
    elif gap == "empty-criteria":
        knowledge.criteria.clear()
    else:
        knowledge.criteria["CRITERION_A"]["bat_buoc"] = None
    assert excluded_requirement_ids(context, knowledge, [requirement]) == []
    result = aggregate(context, knowledge, [], [requirement])[0]
    assert result.status == "INSUFFICIENT"
    assert not result.coverage_complete
    assert result.requirement_snapshot_json["diagnostics"]


def test_ambiguous_json_policy_cannot_override_pinned_conditions(aggregation_case):
    policy = aggregation_case[1].aggregations[POLICY_ID]
    content = json.dumps(POLICY_CONDITIONS)
    policy["dieu_kien_json"] = '{"COMPLIANT":"Different meaning",' + content[1:]
    result = only_aggregate(aggregation_case, findings_for(aggregation_case, ["SATISFIED"] * 3))
    assert result.status == "INSUFFICIENT"
    assert "malformed aggregation JSON" in result.giai_thich


@pytest.mark.parametrize("problem", ["scope", "version", "no-version", "reason"])
def test_not_applicable_cannot_conceal_missing_resolution(aggregation_case, problem):
    context, knowledge, requirement = aggregation_case
    requirement.applicability_status = "NOT_APPLICABLE"
    requirement.scope_status = "NO_MATCH"
    requirement.reason = {"scope": "A reason"}
    if problem == "scope":
        requirement.scope_status = "UNKNOWN"
    elif problem == "version":
        requirement.version_status = "UNKNOWN"
    elif problem == "no-version":
        requirement.requirement_version_id = None
    else:
        requirement.reason = {}
    result = aggregate(context, knowledge, [], [requirement])[0]
    assert result.status == "INSUFFICIENT"
    assert excluded_requirement_ids(context, knowledge, [requirement]) == []


def test_verified_local_exclusion_preserves_reason_and_counts(aggregation_case):
    criteria = findings_for(aggregation_case, ["UNKNOWN", "SATISFIED", "SATISFIED"])
    criteria[0].excluded = True
    criteria[0].exclusion_reason = "Verified local scope does not apply"
    result = only_aggregate(aggregation_case, criteria)
    assert result.status == "COMPLIANT"
    assert result.so_tieu_chi_ap_dung == result.so_tieu_chi_da_danh_gia == 2
    assert result.so_unknown == 0
    assert result.requirement_snapshot_json["excluded_criteria"] == {
        "CRITERION_A": criteria[0].exclusion_reason
    }


@pytest.mark.parametrize("problem", ["gates", "evidence", "basis"])
def test_exclusion_flag_alone_cannot_hide_unknown(aggregation_case, problem):
    criteria = findings_for(aggregation_case, ["UNKNOWN", "SATISFIED", "SATISFIED"])
    criteria[0].excluded = True
    criteria[0].exclusion_reason = "Unsupported exclusion"
    if problem == "gates":
        criteria[0].gates.source_verified = False
    elif problem == "evidence":
        criteria[0].evidence = []
    else:
        criteria[0].legal_basis_ids = []
    result = only_aggregate(aggregation_case, criteria)
    assert result.status == "INSUFFICIENT"
    assert result.so_unknown == 1
    assert result.so_tieu_chi_ap_dung == 3


def test_all_local_exclusions_do_not_create_compliant_result(aggregation_case):
    criteria = findings_for(aggregation_case, ["UNKNOWN"] * 3)
    for result in criteria:
        result.excluded = True
        result.exclusion_reason = "Verified criterion is inapplicable"
    result = only_aggregate(aggregation_case, criteria)
    assert result.status == "INSUFFICIENT"
    assert result.so_tieu_chi_ap_dung == result.so_tieu_chi_da_danh_gia == 0


def test_optional_criterion_kept_in_checklist_but_not_mandatory_policy(aggregation_case):
    aggregation_case[1].criteria["CRITERION_C"]["bat_buoc"] = False
    criteria = findings_for(aggregation_case, ["SATISFIED", "SATISFIED", "UNKNOWN"])
    result = only_aggregate(aggregation_case, criteria)
    assert result.status == "COMPLIANT"
    assert result.so_tieu_chi_ap_dung == result.so_tieu_chi_da_danh_gia == 2
    assert result.requirement_snapshot_json["optional_criterion_ids"] == ["CRITERION_C"]
    assert only_aggregate(aggregation_case, criteria[:2]).status == "INSUFFICIENT"


@pytest.mark.parametrize("field", ["ca_id", "lan_chay_id", "yeu_cau_ca_id", "tieu_chi_id"])
def test_foreign_result_identity_rejected(aggregation_case, field):
    criteria = findings_for(aggregation_case, ["UNKNOWN"] * 3)
    setattr(criteria[0], field, "FOREIGN")
    with pytest.raises(ValueError, match="ownership mismatch"):
        only_aggregate(aggregation_case, criteria)


@pytest.mark.parametrize(
    "problem", ["snapshot-version", "snapshot-pin", "missing-pin", "snapshot-content", "mandatory"]
)
def test_pinned_provenance_mismatch_rejected(aggregation_case, problem):
    criteria = findings_for(aggregation_case, ["UNKNOWN"] * 3)
    if problem == "mandatory":
        criteria[0].mandatory = False
    elif problem == "missing-pin":
        del criteria[0].tieu_chi_snapshot_json["knowledge_snapshot_sha256"]
    else:
        key, value = {
            "snapshot-version": ("requirement_version_id", "FOREIGN"),
            "snapshot-pin": ("knowledge_snapshot_sha256", "b" * 64),
            "snapshot-content": ("human_verified", True),
        }[problem]
        criteria[0].tieu_chi_snapshot_json[key] = value
    with pytest.raises(ValueError, match="pinned"):
        only_aggregate(aggregation_case, criteria)


def test_duplicate_findings_rejected_and_ids_stable_per_run(aggregation_case):
    criteria = findings_for(aggregation_case, ["UNKNOWN"] * 3)
    with pytest.raises(ValueError, match="duplicate"):
        only_aggregate(aggregation_case, criteria + [criteria[0]])
    first = only_aggregate(aggregation_case, criteria)
    assert first == only_aggregate(aggregation_case, criteria)
    aggregation_case[0].run_id = "RUN_B"
    for criterion in criteria:
        criterion.lan_chay_id = "RUN_B"
        criterion.tieu_chi_snapshot_json["context"]["run_id"] = "RUN_B"
    assert only_aggregate(aggregation_case, criteria).tuan_thu_id != first.tuan_thu_id


def test_multiple_requirements_preserve_unresolved_membership(aggregation_case):
    context, knowledge, requirement = aggregation_case
    unresolved = requirement.model_copy(
        update={
            "yeu_cau_ca_id": "CASE_REQUIREMENT_B",
            "requirement_id": "FAMILY_B",
            "requirement_version_id": None,
            "applicability_status": "UNKNOWN",
            "version_status": "UNKNOWN",
        }
    )
    results = aggregate(
        context,
        knowledge,
        findings_for(aggregation_case, ["SATISFIED"] * 3),
        [requirement, unresolved],
    )
    assert [result.yeu_cau_ca_id for result in results] == [
        "CASE_REQUIREMENT_A",
        "CASE_REQUIREMENT_B",
    ]
    assert [result.status for result in results] == ["COMPLIANT", "INSUFFICIENT"]


def test_no_c07_keeps_every_expected_criterion_as_missing_finding(aggregation_case):
    result = only_aggregate(aggregation_case, [])
    assert result.status == "INSUFFICIENT"
    assert result.so_tieu_chi_ap_dung == 3
    assert result.so_tieu_chi_da_danh_gia == result.so_unknown == 0
    assert not result.coverage_complete
    assert result.requirement_snapshot_json["missing_criterion_ids"] == [
        "CRITERION_A",
        "CRITERION_B",
        "CRITERION_C",
    ]
    assert result.requirement_snapshot_json["finding_counts"] == {
        "SATISFIED": 0,
        "VIOLATED": 0,
        "MISSING": 0,
        "UNKNOWN": 0,
    }


@pytest.mark.parametrize("value", [None, "", "   ", 17, False])
def test_unusable_policy_version_retains_gap_without_claiming_policy_version(
    aggregation_case, value
):
    context, knowledge, _ = aggregation_case
    knowledge.aggregations[POLICY_ID]["rule_version"] = value
    result = only_aggregate(aggregation_case, findings_for(aggregation_case, ["SATISFIED"] * 3))
    assert result.status == "INSUFFICIENT"
    assert not result.coverage_complete
    assert result.rule_version == context.rule_version
    assert "aggregation rule_version is missing" in result.giai_thich
    assert result.requirement_snapshot_json["aggregation_policy"]["rule_version"] == value


@pytest.mark.parametrize("policy", [[], "AGG_CAN_HO_V1", False])
def test_malformed_policy_row_has_diagnostics_and_cannot_exclude_requirement(
    aggregation_case, policy
):
    context, knowledge, requirement = aggregation_case
    knowledge.aggregations[POLICY_ID] = policy
    result = only_aggregate(aggregation_case, findings_for(aggregation_case, ["VIOLATED"] * 3))
    assert result.status == "INSUFFICIENT"
    assert "aggregation policy is not an object" in result.giai_thich
    assert result.requirement_snapshot_json["aggregation_policy"] == policy
    requirement.applicability_status = "NOT_APPLICABLE"
    requirement.scope_status = "NO_MATCH"
    requirement.reason = {"scope": "Different transaction type"}
    assert excluded_requirement_ids(context, knowledge, [requirement]) == []


@pytest.mark.parametrize(
    "field",
    [
        "contract_version",
        "ca_id",
        "phien_ban_id",
        "rule_version",
        "legal_knowledge_version",
        "knowledge_snapshot_sha256",
        "run_id",
    ],
)
def test_c07_captured_context_must_match_aggregation_context(aggregation_case, field):
    context, _, _ = aggregation_case
    criteria = findings_for(aggregation_case, ["SATISFIED"] * 3)
    captured = context.model_dump(mode="json")
    captured[field] = "FOREIGN"
    criteria[0].tieu_chi_snapshot_json["context"] = captured
    with pytest.raises(ValueError, match="criterion context differs"):
        only_aggregate(aggregation_case, criteria)


@pytest.mark.parametrize("captured", [None, {}, []])
def test_incomplete_c07_captured_context_is_rejected(aggregation_case, captured):
    criteria = findings_for(aggregation_case, ["SATISFIED"] * 3)
    criteria[0].tieu_chi_snapshot_json["context"] = captured
    with pytest.raises(ValueError, match="criterion context differs"):
        only_aggregate(aggregation_case, criteria)


def test_missing_c07_captured_context_cannot_reuse_current_context(aggregation_case):
    criteria = findings_for(aggregation_case, ["SATISFIED"] * 3)
    del criteria[0].tieu_chi_snapshot_json["context"]
    with pytest.raises(ValueError, match="criterion context differs"):
        only_aggregate(aggregation_case, criteria)


@pytest.mark.parametrize("contract", [None, "", "   ", 17, False])
def test_c07_must_capture_nonempty_contract_ownership(aggregation_case, contract):
    criteria = findings_for(aggregation_case, ["SATISFIED"] * 3)
    criteria[0].tieu_chi_snapshot_json["hop_dong_id"] = contract
    with pytest.raises(ValueError, match="missing contract ownership"):
        only_aggregate(aggregation_case, criteria)


def test_missing_c07_contract_cannot_be_inferred_from_case_membership(aggregation_case):
    criteria = findings_for(aggregation_case, ["SATISFIED"] * 3)
    del criteria[0].tieu_chi_snapshot_json["hop_dong_id"]
    with pytest.raises(ValueError, match="missing contract ownership"):
        only_aggregate(aggregation_case, criteria)


def test_context_only_aggregation_rejects_mixed_contract_sources(aggregation_case):
    criteria = findings_for(aggregation_case, ["SATISFIED"] * 3)
    criteria[1].tieu_chi_snapshot_json["hop_dong_id"] = "FOREIGN_CONTRACT"
    with pytest.raises(ValueError, match="criterion contract differs"):
        only_aggregate(aggregation_case, criteria)


def test_c07_contract_must_match_full_request_contract(aggregation_case):
    context, knowledge, requirement = aggregation_case
    criteria = findings_for(aggregation_case, ["SATISFIED"] * 3)
    request = ReasoningRequest(
        **context.model_dump(),
        payload={"hop_dong_id": "CONTRACT_A", "requirements": [requirement]},
    )
    assert aggregate(request, knowledge, criteria, [requirement])[0].status == "COMPLIANT"
    for criterion in criteria:
        criterion.tieu_chi_snapshot_json["hop_dong_id"] = "FOREIGN_CONTRACT"
    with pytest.raises(ValueError, match="criterion contract differs"):
        aggregate(request, knowledge, criteria, [requirement])


def test_new_trace_does_not_change_c07_context_identity(aggregation_case):
    context, _, _ = aggregation_case
    criteria = findings_for(aggregation_case, ["SATISFIED"] * 3)
    captured = context.model_dump(mode="json")
    captured["trace_id"] = "ORIGINAL_PROVIDER_TRACE"
    for criterion in criteria:
        criterion.tieu_chi_snapshot_json["context"] = captured
    assert only_aggregate(aggregation_case, criteria).status == "COMPLIANT"


@pytest.mark.parametrize("field", ["ca_id", "phien_ban_id"])
def test_foreign_c05_case_or_deployment_is_rejected(aggregation_case, field):
    setattr(aggregation_case[2], field, "FOREIGN")
    with pytest.raises(ValueError, match="different case or deployment"):
        only_aggregate(aggregation_case, [])


def test_foreign_knowledge_pin_is_rejected_before_aggregation(aggregation_case):
    aggregation_case[0].knowledge_snapshot_sha256 = "b" * 64
    with pytest.raises(ValueError, match="checksum differs"):
        only_aggregate(aggregation_case, [])


def test_reused_c07_result_id_cannot_hide_different_criterion(aggregation_case):
    criteria = findings_for(aggregation_case, ["UNKNOWN"] * 3)
    criteria[1].ket_qua_id = criteria[0].ket_qua_id
    with pytest.raises(ValueError, match="duplicate"):
        only_aggregate(aggregation_case, criteria)


def test_conflicting_expected_checklist_is_rejected(aggregation_case):
    knowledge = aggregation_case[1]
    first = knowledge.criteria["CRITERION_A"]
    knowledge.criteria_for = lambda version: [first, first]
    with pytest.raises(ValueError, match="duplicate or foreign criteria"):
        only_aggregate(aggregation_case, [])
