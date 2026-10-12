import pytest
from pydantic import ValidationError

from app.application.pipelines.steps_5_7 import evaluate
from app.contracts.reasoning import CriterionResult, Gates


def test_all_satisfied_no_remediation(knowledge, request_factory):
    result = evaluate(request_factory(), knowledge).payload
    assert result.requirement_results[0].status == "COMPLIANT"
    assert result.risks == result.recommendations == []


@pytest.mark.parametrize(
    "gate",
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
def test_missing_gates_do_not_create_violation(knowledge, request_factory, gate):
    def mutate(data):
        for obs in data["payload"]["observations"]:
            obs["gates"][gate] = False
            obs["evidence"] = []

    result = evaluate(request_factory(finding="MISSING", mutate=mutate), knowledge).payload
    assert all(r.finding == "UNKNOWN" for r in result.criterion_results)
    assert result.requirement_results[0].status == "INSUFFICIENT"
    assert all(r.risk_type == "VERIFICATION" for r in result.risks)
    assert all(r.loai_hanh_dong == "REQUEST_VERIFICATION" for r in result.recommendations)


@pytest.mark.parametrize("finding", ["SATISFIED", "VIOLATED"])
def test_empty_retrieval_not_content_finding(knowledge, request_factory, finding):
    def mutate(data):
        data["payload"]["retrieval"] = []
        for obs in data["payload"]["observations"]:
            obs["evidence"] = []

    result = evaluate(request_factory(finding=finding, mutate=mutate), knowledge).payload
    assert all(r.finding == "UNKNOWN" for r in result.criterion_results)


@pytest.mark.parametrize(
    "field", ["all_pages_readable", "all_related_documents_received", "mandatory_confirmed"]
)
def test_absence_needs_whole_document_policy(knowledge, request_factory, field):
    def mutate(data):
        for obs in data["payload"]["observations"]:
            obs[field] = False

    result = evaluate(request_factory(finding="MISSING", mutate=mutate), knowledge).payload
    assert all(r.finding == "UNKNOWN" for r in result.criterion_results)


@pytest.mark.parametrize(
    "case,expected",
    [
        ("all_missing", "NON_COMPLIANT"),
        ("mixed", "PARTIAL"),
        ("unknown", "INSUFFICIENT"),
        ("violation_unknown", "NON_COMPLIANT"),
    ],
)
def test_workbook_aggregation_precedence(knowledge, request_factory, case, expected):
    def mutate(data):
        obs = data["payload"]["observations"]
        if case == "all_missing":
            for o in obs:
                o["proposed_finding"] = "MISSING"
        elif case == "mixed":
            obs[0]["proposed_finding"] = "MISSING"
        else:
            obs[0]["proposed_finding"] = "UNKNOWN"
            if case == "violation_unknown":
                obs[1]["proposed_finding"] = "VIOLATED"

    result = evaluate(request_factory(mutate=mutate), knowledge).payload
    assert result.requirement_results[0].status == expected
    if case == "violation_unknown":
        assert result.requirement_results[0].coverage_complete is False


def test_conflicting_evidence_unknown(knowledge, request_factory):
    def mutate(data):
        data["payload"]["observations"][0]["gates"]["evidence_conflict"] = True

    result = evaluate(request_factory(mutate=mutate), knowledge).payload
    assert result.criterion_results[0].finding == "UNKNOWN"


def test_quote_must_match_selected_chunk(knowledge, request_factory):
    def mutate(data):
        data["payload"]["observations"][0]["evidence"][0]["trich_dan"] = "Invented quote"

    result = evaluate(request_factory(mutate=mutate), knowledge).payload
    assert result.criterion_results[0].finding == "UNKNOWN"


def test_unresolved_scope_dominates_violation(knowledge, request_factory):
    def mutate(data):
        req = data["payload"]["requirements"][0]
        req.update(scope_status="UNKNOWN", applicability_status="UNKNOWN")

    result = evaluate(request_factory(finding="VIOLATED", mutate=mutate), knowledge).payload
    assert result.requirement_results[0].status == "INSUFFICIENT"


def test_not_applicable_has_no_compliance_output(knowledge, request_factory):
    def mutate(data):
        data["payload"]["requirements"][0].update(
            scope_status="NO_MATCH", applicability_status="NOT_APPLICABLE"
        )

    result = evaluate(request_factory(mutate=mutate), knowledge).payload
    assert result.criterion_results == result.requirement_results == result.recommendations == []
    assert result.excluded_requirements == ["YCCA_TEST"]


def test_unknown_version_remains_checklist_entry(knowledge, request_factory):
    def mutate(data):
        data["payload"]["requirements"][0].update(
            requirement_version_id=None, version_status="UNKNOWN", applicability_status="UNKNOWN"
        )
        data["payload"]["observations"] = []
        data["payload"]["retrieval"] = []

    result = evaluate(request_factory(mutate=mutate), knowledge).payload
    assert result.requirement_results[0].status == "INSUFFICIENT"
    assert result.requirement_results[0].so_tieu_chi_ap_dung == 0


def test_missing_contract_validation(knowledge, request_factory):
    result = evaluate(request_factory(), knowledge).payload.criterion_results[0]
    data = result.model_dump()
    data.update(finding="MISSING", gates=Gates().model_dump())
    with pytest.raises(ValidationError, match="MISSING requires"):
        CriterionResult.model_validate(data)


def test_non_content_criterion_cannot_be_missing(knowledge, request_factory):
    request = request_factory("PV_GYC062", finding="MISSING")
    result = evaluate(request, knowledge).payload
    assert result.criterion_results[0].finding == "UNKNOWN"


def test_unverified_exclusion_does_not_remove_unknown(knowledge, request_factory):
    def mutate(data):
        for obs in data["payload"]["observations"]:
            obs.update(local_applicability="NO_MATCH", exclusion_reason="Unverified exception")
            obs["gates"]["exceptions_resolved"] = False

    result = evaluate(request_factory(mutate=mutate), knowledge).payload
    assert all(not r.excluded and r.finding == "UNKNOWN" for r in result.criterion_results)
    assert result.requirement_results[0].status == "INSUFFICIENT"


def test_out_of_bounds_quote_is_unknown(knowledge, request_factory):
    def mutate(data):
        data["payload"]["observations"][0]["evidence"][0]["ky_tu_ket_thuc"] = 99999

    result = evaluate(request_factory(mutate=mutate), knowledge).payload
    assert result.criterion_results[0].finding == "UNKNOWN"


def test_quote_whitespace_and_offsets_preserved(knowledge, request_factory):
    def mutate(data):
        chunk = data["payload"]["chunks"][0]
        chunk["noi_dung"] = "  " + chunk["noi_dung"] + "  "
        for obs in data["payload"]["observations"]:
            obs["evidence"][0].update(
                trich_dan=chunk["noi_dung"], ky_tu_bat_dau=0, ky_tu_ket_thuc=len(chunk["noi_dung"])
            )

    result = evaluate(request_factory(mutate=mutate), knowledge).payload
    assert all(r.finding == "SATISFIED" for r in result.criterion_results)
    assert result.criterion_results[0].evidence[0].trich_dan.startswith("  ")
