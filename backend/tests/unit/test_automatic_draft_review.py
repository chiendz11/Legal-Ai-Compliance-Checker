"""Synthetic backend verification regression; no real provider or legal conclusion."""

from copy import deepcopy

import pytest
from legal_checker.modules.compliance.criterion_reasoner import reason
from legal_checker.modules.compliance.llm_observations import LLMObservationProvider
from legal_checker.modules.compliance.requirement_aggregator import requirement_exclusion_reason
from legal_checker.shared.contracts.reasoning import ReasoningRequest
from legal_checker.shared.contracts.temporal import ApplicableRequirement
from test_criterion_reasoner import reasoning_case as reasoning_case
from test_llm_observations import FakeClient, semantic


def analyze(knowledge, data, **changes):
    batch = LLMObservationProvider(
        FakeClient([semantic(data, **changes)]), automatic_draft_review=True
    ).analyze(ReasoningRequest.model_validate(data), knowledge)
    data = deepcopy(data)
    data["payload"]["observations"] = [item.model_dump() for item in batch.observations]
    return batch, reason(ReasoningRequest.model_validate(data), knowledge)[0]


@pytest.mark.parametrize("finding", ["SATISFIED", "VIOLATED"])
def test_reviewed_catalog_and_grounded_content_can_produce_draft(reasoning_case, finding):
    knowledge, data = reasoning_case
    batch, result = analyze(knowledge, data, proposed_finding=finding)
    assert result.finding == finding
    assert result.review_status == "PENDING"
    assert batch.observations[0].gates.reliable()


@pytest.mark.parametrize("blocker", ["source", "scope", "exception", "performance", "numeric"])
def test_automatic_review_never_invents_missing_attestations(reasoning_case, blocker):
    knowledge, data = reasoning_case
    if blocker == "source":
        knowledge.criteria["CRITERION_1"]["human_verified"] = False
    elif blocker == "scope":
        data["payload"]["requirements"][0].update(
            scope_status="UNKNOWN", applicability_status="UNKNOWN"
        )
    elif blocker == "exception":
        knowledge.tables["ngoai_le_ap_dung"] = [{"tieu_chi_id": "CRITERION_1"}]
    elif blocker == "performance":
        knowledge.criteria["CRITERION_1"]["loai_kiem_tra"] = "PERFORMANCE_WITH_DOCUMENTS"
    elif blocker == "numeric":
        for rule in knowledge.tables["quy_tac_quyet_dinh"]:
            rule["dieu_kien_json"]["numeric_rule"] = {"maintenance_ratio": "0.02"}
    _, result = analyze(knowledge, data)
    assert result.finding == "UNKNOWN"


def test_fabricated_quote_stays_unknown_before_automatic_review(reasoning_case):
    knowledge, data = reasoning_case
    evidence = semantic(data)["evidence"]
    evidence[0]["trich_dan"] = "A quote that is not in the contract"
    batch, result = analyze(knowledge, data, evidence=evidence)
    assert batch.analyses[0].error_code == "QUOTE_MISMATCH"
    assert result.finding == "UNKNOWN"


def test_unresolved_date_does_not_become_nonapplicable(reasoning_case):
    knowledge, data = reasoning_case
    row = data["payload"]["requirements"][0]
    row.update(scope_status="MATCH", version_status="UNKNOWN", applicability_status="UNKNOWN")
    assert (
        requirement_exclusion_reason(ApplicableRequirement.model_validate(row), knowledge) is None
    )


def test_real_temporal_shape_excludes_pre_introduction_family(reasoning_case):
    knowledge, data = reasoning_case
    knowledge.versions["VERSION_1"]["hieu_luc_tu"] = "2024-08-01"
    row = data["payload"]["requirements"][0]
    row.update(
        requirement_version_id=None,
        version_status="UNKNOWN",
        applicability_status="NOT_APPLICABLE",
        moc_ap_dung="2017-01-01",
        resolution_method="CATALOG_MARKER_VERSION_INTERVAL",
        nguon_snapshot_json={"knowledge_sha256": knowledge.sha256},
        reason={"version": "Requirement not in force at the relevant date"},
    )
    assert requirement_exclusion_reason(ApplicableRequirement.model_validate(row), knowledge)
    # Multiple catalog versions can mean missing historical coverage. Keep it visible.
    knowledge.versions["OTHER"] = dict(
        knowledge.versions["VERSION_1"], requirement_version_id="OTHER"
    )
    assert (
        requirement_exclusion_reason(ApplicableRequirement.model_validate(row), knowledge) is None
    )


def test_model_pending_verification_is_not_silently_auto_approved(reasoning_case):
    knowledge, data = reasoning_case
    _, result = analyze(knowledge, data, verification_requirements=["Need independent facts"])
    assert result.finding == "UNKNOWN"


def test_unreviewed_rule_cannot_reuse_a_reviewed_criterion_to_auto_approve(reasoning_case):
    knowledge, data = reasoning_case
    for rule in knowledge.tables["quy_tac_quyet_dinh"]:
        rule["human_verified"] = False
    _, result = analyze(knowledge, data)
    assert result.finding == "UNKNOWN"
