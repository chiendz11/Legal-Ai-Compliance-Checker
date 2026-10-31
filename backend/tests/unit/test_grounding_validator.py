"""Reusable C07 grounding rejects malformed provenance and reports missing support."""

from copy import deepcopy

import pytest
from legal_checker.modules.compliance.grounding_validator import validate_criteria
from legal_checker.shared.contracts.reasoning import ReasoningRequest
from test_c07_findings import register_external
from test_criterion_reasoner import reasoning_case as reasoning_case


def test_grounding_can_be_used_directly_without_mutation(reasoning_case):
    knowledge, data = reasoning_case
    request = ReasoningRequest.model_validate(data)
    before = request.model_dump()
    assert validate_criteria(request, knowledge) == {"CRITERION_1": []}
    assert request.model_dump() == before


def test_complete_reports_missing_observation_but_allows_unknown(reasoning_case):
    knowledge, data = reasoning_case
    data["payload"]["observations"] = []
    request = ReasoningRequest.model_validate(data)
    assert validate_criteria(request, knowledge) == {"CRITERION_1": []}
    assert (
        "Missing observation"
        in validate_criteria(request, knowledge, complete=True)["CRITERION_1"][0]
    )


@pytest.mark.parametrize("state", ["empty", "unselected", "candidate"])
def test_missing_selected_retrieval_is_uncertain_not_invalid_quote(reasoning_case, state):
    knowledge, data = reasoning_case
    if state == "empty":
        data["payload"]["retrieval"] = []
    elif state == "unselected":
        data["payload"]["retrieval"][0]["duoc_chon"] = False
    else:
        data["payload"]["retrieval"][0]["giai_doan"] = "CANDIDATE"
    issues = validate_criteria(ReasoningRequest.model_validate(data), knowledge)
    assert "selected FINAL" in issues["CRITERION_1"][0]


def test_combining_unicode_is_not_normalized_before_offset_comparison(reasoning_case):
    knowledge, data = reasoning_case
    quote = "Phi\u0301\n  😀"
    data["payload"]["chunks"][0]["noi_dung"] = "x" + quote
    evidence = data["payload"]["observations"][0]["evidence"][0]
    evidence.update(trich_dan=quote, ky_tu_bat_dau=1, ky_tu_ket_thuc=len(quote) + 1)
    assert validate_criteria(ReasoningRequest.model_validate(data), knowledge)["CRITERION_1"] == []
    evidence["trich_dan"] = "Phí\n  😀"
    with pytest.raises(ValueError, match="quote/offset"):
        validate_criteria(ReasoningRequest.model_validate(data), knowledge)


@pytest.mark.parametrize(
    "field,value",
    [
        ("ca_id", "FOREIGN_CASE"),
        ("hop_dong_id", "FOREIGN_CONTRACT"),
        ("phien_ban_id", "FOREIGN_DEPLOYMENT"),
        ("run_id", "FOREIGN_RUN"),
        ("knowledge_snapshot_sha256", "d" * 64),
        ("yeu_cau_ca_id", "FOREIGN_INSTANCE"),
        ("tieu_chi_id", "FOREIGN_CRITERION"),
        ("sha256", "d" * 64),
        ("object_uri", "memory://different-source"),
    ],
)
def test_external_identity_source_and_hash_mismatch_are_rejected(reasoning_case, field, value):
    knowledge, data = reasoning_case
    register_external(data)
    data["payload"]["external_evidence_registry"][0][field] = value
    with pytest.raises(ValueError, match="External"):
        validate_criteria(ReasoningRequest.model_validate(data), knowledge)


def test_duplicate_external_registration_is_rejected(reasoning_case):
    knowledge, data = reasoning_case
    register_external(data)
    entries = data["payload"]["external_evidence_registry"]
    entries.append(deepcopy(entries[0]))
    with pytest.raises(ValueError, match="Duplicate"):
        validate_criteria(ReasoningRequest.model_validate(data), knowledge)


def test_corrupted_catalog_foreign_version_is_rejected(reasoning_case):
    knowledge, data = reasoning_case
    criterion = deepcopy(knowledge.criteria["CRITERION_1"])
    criterion["requirement_version_id"] = "OTHER_VERSION"
    knowledge.criteria_for = lambda version: [criterion]
    with pytest.raises(ValueError, match="foreign version"):
        validate_criteria(ReasoningRequest.model_validate(data), knowledge)


def test_duplicate_catalog_criteria_are_rejected(reasoning_case):
    knowledge, data = reasoning_case
    criterion = knowledge.criteria["CRITERION_1"]
    knowledge.criteria_for = lambda version: [criterion, criterion]
    with pytest.raises(ValueError, match="duplicate"):
        validate_criteria(ReasoningRequest.model_validate(data), knowledge)
