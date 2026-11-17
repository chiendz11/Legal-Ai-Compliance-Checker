"""Source-only checks versus explicit, immutable synthetic attestations."""

import json

import pytest
from legal_checker.modules.compliance.criterion_reasoner import reason
from legal_checker.modules.compliance.llm_observations import LLMObservationProvider
from legal_checker.modules.compliance.source_verifier import (
    SourceFactVerifier,
    SyntheticScenarioEvidence,
)
from legal_checker.shared.contracts.common import Context
from legal_checker.shared.contracts.document_intelligence import (
    ContractProfile,
    DocumentReadCoverage,
    ProfileFields,
)
from legal_checker.shared.contracts.reasoning import ReasoningRequest
from test_criterion_reasoner import reasoning_case as reasoning_case
from test_llm_observations import FakeClient, semantic


def scenario(tmp_path, knowledge):
    path = tmp_path / "scenario.json"
    path.write_text(
        json.dumps(
            {
                "kind": "SYNTHETIC_SCENARIO_V1",
                "scenario_id": "TEST_SYNTHETIC",
                "source_sha256": "b" * 64,
                "knowledge_snapshot_sha256": knowledge.sha256,
                "criteria": {
                    "CRITERION_1": {
                        "local_applicability": "MATCH",
                        "exceptions_checked": True,
                        "facts": {"evaluation_target": "CONTRACT_CONTENT"},
                        "external_text": "[SYNTHETIC] Test only.",
                    }
                },
            }
        )
    )
    return SyntheticScenarioEvidence(path)


def inputs(data):
    request = ReasoningRequest.model_validate(data)
    context = Context(**{k: getattr(request, k) for k in Context.model_fields})
    profile = ContractProfile(hop_dong_id=request.payload.hop_dong_id, profile=ProfileFields())
    coverage = DocumentReadCoverage(
        hop_dong_id=profile.hop_dong_id,
        source_sha256="b" * 64,
        extraction_version="test",
        page_count=1,
    )
    return request, context, profile, coverage


def test_source_only_does_not_invent_case_facts_or_full_review(reasoning_case):
    knowledge, data = reasoning_case
    knowledge.criteria["CRITERION_1"]["dieu_kien"] = {"case_facts_required": True}
    request, ctx, profile, coverage = inputs(data)
    rows = SourceFactVerifier().verify(
        ctx,
        profile,
        request.payload.requirements,
        request.payload.chunks,
        knowledge,
        coverage=coverage,
    )
    assert not rows[0].facts_verified
    assert rows[0].local_applicability == "UNKNOWN"
    assert not rows[0].gates.absence_verified
    assert not rows[0].gates.source_verified


def test_synthetic_sources_are_bound_to_pdf_snapshot_and_stored_bytes(tmp_path, reasoning_case):
    knowledge, data = reasoning_case
    request, ctx, profile, coverage = inputs(data)
    provider = scenario(tmp_path, knowledge)
    rows = provider.verify(
        ctx,
        profile,
        request.payload.requirements,
        request.payload.chunks,
        knowledge,
        coverage=coverage,
    )
    assert rows[0].verification_reference.startswith("SYNTHETIC_SCENARIO_V1:")
    assert rows[0].external_excerpts[0].text.startswith("[SYNTHETIC]")
    assert not rows[0].gates.absence_verified
    assert provider.diagnostic("c" * 64, knowledge) is None
    other = coverage.model_copy(update={"source_sha256": "c" * 64})
    assert not provider.verify(
        ctx,
        profile,
        request.payload.requirements,
        request.payload.chunks,
        knowledge,
        coverage=other,
    )[0].facts_verified
    knowledge.sha256 = "c" * 64
    assert provider.diagnostic("b" * 64, knowledge) is None
    provider.path.write_text("{}")
    with pytest.raises(ValueError, match="changed"):
        provider.diagnostic("b" * 64, knowledge)


def test_synthetic_attestation_can_admit_machine_draft_without_human_review(
    tmp_path, reasoning_case
):
    knowledge, data = reasoning_case
    request, ctx, profile, coverage = inputs(data)
    provider = scenario(tmp_path, knowledge)
    knowledge.criteria["CRITERION_1"]["human_verified"] = False
    knowledge.criteria["CRITERION_1"]["trang_thai_nguon"] = "SOURCE_CHECKED"
    for rule in knowledge.tables["quy_tac_quyet_dinh"]:
        rule["human_verified"] = False
    verifications = provider.verify(
        ctx,
        profile,
        request.payload.requirements,
        request.payload.chunks,
        knowledge,
        coverage=coverage,
    )
    # This proposal uses real fixture contract text, not the optional external record.
    verifications[0].external_excerpts = []
    batch = LLMObservationProvider(
        FakeClient([semantic(data)]), automatic_draft_review=True, verifications=verifications
    ).analyze(request, knowledge)
    data["payload"]["observations"] = [x.model_dump() for x in batch.observations]
    result = reason(ReasoningRequest.model_validate(data), knowledge)[0]
    assert result.finding == "SATISFIED"
    assert result.review_status == "PENDING"
    assert knowledge.criteria["CRITERION_1"]["human_verified"] is False


@pytest.mark.parametrize("tamper", [None, "source", "page", "document_set", "method"])
def test_visual_absence_is_source_pinned_and_never_human_approval(tmp_path, reasoning_case, tamper):
    knowledge, data = reasoning_case
    request, ctx, profile, coverage = inputs(data)
    provider = scenario(tmp_path, knowledge)
    item = provider.scenario["criteria"]["CRITERION_1"]
    item["document_set_complete"] = True
    item["visual_absence_review"] = {
        "source_sha256": coverage.source_sha256,
        "method": "SOURCE_PINNED_VISUAL_INSPECTION",
        "content_absent": True,
        "pages": [1],
    }
    if tamper == "source":
        item["visual_absence_review"]["source_sha256"] = "e" * 64
    if tamper == "page":
        item["visual_absence_review"]["pages"] = [2]
    if tamper == "method":
        item["visual_absence_review"]["method"] = "TRUST_ALL"
    if tamper == "document_set":
        item["document_set_complete"] = False
    provider.path.write_text(json.dumps(provider.scenario))
    provider = SyntheticScenarioEvidence(provider.path, artifact_dir=tmp_path / "artifacts")
    record = provider.verify(
        ctx,
        profile,
        request.payload.requirements,
        request.payload.chunks,
        knowledge,
        coverage=coverage,
    )[0]
    assert record.gates.absence_verified is (tamper is None)
    assert "human_verified" not in record.facts
    assert provider.artifact.path.read_bytes() == provider.path.read_bytes()


def test_full_assessment_resolves_absent_exceptions_and_verified_catalog_source(reasoning_case):
    knowledge, data = reasoning_case
    knowledge.review_status = "HUMAN_VERIFIED"
    knowledge.criteria["CRITERION_1"]["dieu_kien"] = {"case_facts_required": True}
    request, ctx, profile, coverage = inputs(data)
    row = SourceFactVerifier().verify(
        ctx,
        profile,
        request.payload.requirements,
        request.payload.chunks,
        knowledge,
        coverage=coverage,
    )[0]
    assert row.gates.source_verified
    assert row.gates.exceptions_resolved
    assert row.local_applicability == "UNKNOWN"

    knowledge.tables["ngoai_le_ap_dung"] = [{"ngoai_le_id": "EX_1", "tieu_chi_id": "CRITERION_1"}]
    blocked = SourceFactVerifier().verify(
        ctx,
        profile,
        request.payload.requirements,
        request.payload.chunks,
        knowledge,
        coverage=coverage,
    )[0]
    assert not blocked.gates.exceptions_resolved


def test_case_create_defaults_match_web_upload_draft_review():
    from legal_checker.api.v1.schemas import CaseCreate

    created = CaseCreate(hop_dong_id="HD_1", ngay_danh_gia="2026-11-17")
    assert created.review_mode == "DRAFT_REVIEW"
    assert created.document_set_complete is False
