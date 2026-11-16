"""Draft purpose is explicit, source-bound, and never proof of execution."""

import pytest
from legal_checker.modules.compliance.criterion_reasoner import reason
from legal_checker.modules.compliance.llm_observations import LLMObservationProvider
from legal_checker.modules.compliance.requirement_aggregator import aggregate
from legal_checker.modules.compliance.review_scope import (
    OUTSIDE,
    apply_review_scope,
    criterion_target,
    scope_receipt,
)
from legal_checker.modules.compliance.source_verifier import SourceFactVerifier
from legal_checker.shared.contracts.assessment import AssessmentCase, AssessmentTiming
from legal_checker.shared.contracts.common import Context
from legal_checker.shared.contracts.document_intelligence import (
    ContractProfile,
    DocumentReadCoverage,
)
from legal_checker.shared.contracts.reasoning import ReasoningRequest
from test_criterion_reasoner import reasoning_case as reasoning_case
from test_llm_observations import FakeClient, semantic


def test_machine_policy_document_stays_in_sync():
    import json

    from legal_checker.core.config import PROJECT_ROOT
    from legal_checker.modules.compliance.review_scope import policy_document

    assert (
        json.loads((PROJECT_ROOT / "docs/contracts/draft_review_policy.json").read_text())
        == policy_document()
    )


def test_exception_unknown_is_not_false_and_irrelevant_subject_can_short_circuit():
    from legal_checker.modules.compliance.source_verifier import _exception_match

    row = {
        "dieu_kien_json": {
            "schema": "CONDITION_TREE_V1",
            "match": {
                "all": [
                    {"op": "eq", "field": "legal.applies", "value": True},
                    {"op": "eq", "field": "warranty.subject", "value": "EQUIPMENT"},
                ]
            },
        }
    }
    assert _exception_match(row, {}) is None
    assert _exception_match(row, {"warranty.subject": "BUILDING"}) is False
    assert _exception_match(row, {"warranty.subject": "EQUIPMENT"}) is None


def test_old_report_context_does_not_gain_default_fields_in_its_digest():
    old = {"ngay_danh_gia": "2026-11-08", "moc_ap_dung": None, "loai_moc_ap_dung": None}
    timing = AssessmentTiming.model_validate(old)
    assert timing.review_mode == "FULL_ASSESSMENT"
    assert timing.model_dump(mode="json") == old
    timing = AssessmentTiming.model_validate(
        {**old, "review_mode": "DRAFT_REVIEW", "document_set_complete": True}
    )
    assert timing.model_dump(mode="json")["review_mode"] == "DRAFT_REVIEW"


def setup_draft(knowledge, data, *, mode="DRAFT_REVIEW", complete=True):
    criterion = knowledge.criteria["CRITERION_1"]
    criterion["pham_vi_kiem_tra"] = "CONTRACT_TEXT"
    criterion["dieu_kien"] = {"case_facts_required": True, "exception_ids": []}
    knowledge.review_status = "SOURCE_CHECKED"
    request = ReasoningRequest.model_validate(data)
    ctx = Context(**{k: getattr(request, k) for k in Context.model_fields})
    case = AssessmentCase(
        ca_id=ctx.ca_id,
        hop_dong_id=request.payload.hop_dong_id,
        source={
            "tep_id": "F",
            "object_uri": "upload://test.pdf",
            "sha256": "b" * 64,
            "mime_type": "application/pdf",
        },
        assessment_context={
            "ngay_danh_gia": "2026-11-09",
            "review_mode": mode,
            "document_set_complete": complete,
        },
        deployment={
            k: getattr(ctx, k) for k in ("phien_ban_id", "rule_version", "legal_knowledge_version")
        },
        tenant_id="T",
        created_by="UPLOADER",
    )
    request.payload.requirements = apply_review_scope(
        case, ctx, request.payload.requirements, knowledge
    )
    profile = ContractProfile(hop_dong_id=case.hop_dong_id, profile={})
    coverage = DocumentReadCoverage(
        hop_dong_id=case.hop_dong_id,
        source_sha256=case.source.sha256,
        extraction_version="test",
        page_count=2,
    )
    return request, ctx, case, profile, coverage


def test_case_facts_true_does_not_block_attributed_draft_content(reasoning_case):
    knowledge, data = reasoning_case
    request, ctx, _, profile, coverage = setup_draft(knowledge, data)
    rows = SourceFactVerifier().verify(
        ctx,
        profile,
        request.payload.requirements,
        request.payload.chunks,
        knowledge,
        coverage=coverage,
    )
    assert rows[0].local_applicability == "MATCH"
    assert rows[0].gates.exceptions_resolved
    assert rows[0].facts_verified
    assert not rows[0].gates.absence_verified
    batch = LLMObservationProvider(
        FakeClient([semantic(data)]), automatic_draft_review=True, verifications=rows
    ).analyze(request, knowledge)
    request.payload.observations = batch.observations
    result = reason(request, knowledge)[0]
    assert result.finding == "SATISFIED"
    assert result.review_status == "PENDING"
    assert "synthetic_evaluation" not in rows[0].facts


def test_full_assessment_does_not_inherit_draft_checks(reasoning_case):
    knowledge, data = reasoning_case
    request, ctx, _, profile, coverage = setup_draft(knowledge, data, mode="FULL_ASSESSMENT")
    rows = SourceFactVerifier().verify(
        ctx,
        profile,
        request.payload.requirements,
        request.payload.chunks,
        knowledge,
        coverage=coverage,
    )
    assert rows[0].local_applicability == "UNKNOWN"
    assert not rows[0].facts_verified


def test_draft_receipt_does_not_change_C04_owned_provenance(reasoning_case):
    knowledge, data = reasoning_case
    data["payload"]["requirements"][0]["profile_snapshot_json"] = {"scope_producer": "unaltered"}
    request, _, _, _, _ = setup_draft(knowledge, data)
    requirement = request.payload.requirements[0]
    assert requirement.profile_snapshot_json == {"scope_producer": "unaltered"}
    assert requirement.assessment_review["policy_id"] == "DRAFT_CONTENT_REVIEW_V1"


@pytest.mark.parametrize("semantic_missing", [False, True])
def test_backend_source_checks_resolve_verification_requests_but_not_semantic_gaps(
    reasoning_case, semantic_missing
):
    knowledge, data = reasoning_case
    request, ctx, _, profile, coverage = setup_draft(knowledge, data)
    records = SourceFactVerifier().verify(
        ctx,
        profile,
        request.payload.requirements,
        request.payload.chunks,
        knowledge,
        coverage=coverage,
    )
    response = semantic(data)
    response["verification_requirements"] = ["Check quote attribution and scope/version"]
    response["missing_conditions"] = (
        ["A required semantic condition is unknown"] if semantic_missing else []
    )
    batch = LLMObservationProvider(
        FakeClient([response]), automatic_draft_review=True, verifications=records
    ).analyze(request, knowledge)
    request.payload.observations = batch.observations
    result = reason(request, knowledge)[0]
    assert result.finding == ("UNKNOWN" if semantic_missing else "SATISFIED")


@pytest.mark.parametrize("field", ["context", "criterion_targets", "source_sha256"])
def test_scope_receipt_rejects_changed_handoff(reasoning_case, field):
    knowledge, data = reasoning_case
    request, ctx, _, _, _ = setup_draft(knowledge, data)
    row = request.payload.requirements[0]
    row.assessment_review[field] = {}
    with pytest.raises(ValueError, match="scope receipt"):
        scope_receipt(row, ctx, knowledge)


def test_draft_verification_rejects_other_pdf(reasoning_case):
    knowledge, data = reasoning_case
    request, ctx, _, profile, coverage = setup_draft(knowledge, data)
    coverage.source_sha256 = "c" * 64
    with pytest.raises(ValueError, match="source differs"):
        SourceFactVerifier().verify(
            ctx,
            profile,
            request.payload.requirements,
            request.payload.chunks,
            knowledge,
            coverage=coverage,
        )


def test_outside_review_is_distinct_from_not_applicable_or_compliant(reasoning_case):
    knowledge, data = reasoning_case
    request, ctx, case, _, _ = setup_draft(knowledge, data)
    criterion = knowledge.criteria["CRITERION_1"]
    criterion["loai_kiem_tra"] = "PERFORMANCE_WITH_DOCUMENTS"
    criterion["pham_vi_kiem_tra"] = "PERFORMANCE"
    request.payload.requirements = apply_review_scope(
        case, ctx, request.payload.requirements, knowledge
    )
    request.payload.observations = []
    result = reason(request, knowledge)[0]
    assert criterion_target(criterion) == OUTSIDE
    assert result.finding == "UNKNOWN" and result.excluded
    assert result.model_version == "BACKEND_REVIEW_SCOPE_V1"
    rows = aggregate(request, knowledge, [result], request.payload.requirements)
    assert rows[0].status == "INSUFFICIENT"
    assert rows[0].requirement_snapshot_json["assessment_disposition"] == OUTSIDE
    assert request.payload.requirements[0].applicability_status == "CONFIRMED"


def test_document_set_declaration_alone_never_proves_absence(reasoning_case):
    knowledge, data = reasoning_case
    request, ctx, _, profile, coverage = setup_draft(knowledge, data)
    row = SourceFactVerifier().verify(
        ctx,
        profile,
        request.payload.requirements,
        request.payload.chunks,
        knowledge,
        coverage=coverage,
    )[0]
    assert row.all_related_documents_received
    assert not row.gates.coverage_complete and not row.gates.absence_verified


def test_registered_unknown_exception_is_not_auto_resolved(reasoning_case):
    knowledge, data = reasoning_case
    request, ctx, _, profile, coverage = setup_draft(knowledge, data)
    knowledge.tables["ngoai_le_ap_dung"] = [{"ngoai_le_id": "EX", "tieu_chi_id": "CRITERION_1"}]
    row = SourceFactVerifier().verify(
        ctx,
        profile,
        request.payload.requirements,
        request.payload.chunks,
        knowledge,
        coverage=coverage,
    )[0]
    assert not row.gates.exceptions_resolved


def test_context_budget_has_explicit_model_configuration(monkeypatch):
    from legal_checker.core.config import Settings
    from legal_checker.workflows.integrated import IntegratedModulesSource

    monkeypatch.setenv("ASSESSMENT_LLM_MAX_CONTEXT_CHARS", "70000")
    settings = Settings.from_env()
    source = IntegratedModulesSource(
        "memory://unused",
        cases=None,
        llm_max_context_chars=settings.assessment_llm_max_context_chars,
    )
    assert source.llm_max_context_chars == 70000
