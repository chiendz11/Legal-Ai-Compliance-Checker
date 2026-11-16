"""Offline checks for source-bound review coverage and real C06 handoff."""

import hashlib
import json

import pytest
from legal_checker.modules.compliance.criterion_reasoner import reason
from legal_checker.modules.compliance.document_review import FullDocumentReviewer
from legal_checker.modules.compliance.llm_observations import LLMObservationProvider
from legal_checker.modules.compliance.review_admission import admit_document_decisions
from legal_checker.modules.retrieval.coverage import add_review_candidates
from legal_checker.shared.contracts.document_review import DocumentReviewArtifact
from legal_checker.shared.llm.types import LlmClientError, LlmResponse
from legal_checker.shared.storage.artifacts import store_bytes
from test_criterion_reasoner import reasoning_case as reasoning_case
from test_source_verifier import inputs, scenario


class MatrixClient:
    def __init__(self, assessment="ABSENT", invalid=None):
        self.assessment, self.invalid, self.calls = assessment, invalid, []

    def complete(self, context, **kw):
        self.calls.append(kw)
        p = kw["payload"]
        chunks = [c["chunk_alias"] for c in p["chunks"]]
        checks = [
            dict(
                criterion_alias=c["criterion_alias"],
                assessment=self.assessment,
                candidate_chunk_aliases=chunks[:1] if self.assessment == "PRESENT" else [],
                explanation="Synthetic offline comparison only.",
            )
            for c in p["criteria"]
        ]
        if self.invalid == "omitted_chunk":
            chunks = chunks[:-1]
        if self.invalid == "omitted_criterion":
            checks = checks[:-1]
        if self.invalid == "foreign_chunk":
            checks[0]["candidate_chunk_aliases"] = ["FOREIGN"]
        return LlmResponse(json.dumps(dict(reviewed_chunks=chunks, checks=checks)), "TEST_MODEL")


def prepare(tmp_path, reasoning_case, kind="PROHIBITED_CLAUSE"):
    knowledge, data = reasoning_case
    request, ctx, profile, coverage = inputs(data)
    request.payload.chunks[0].page_start = request.payload.chunks[0].page_end = 1
    knowledge.criteria["CRITERION_1"]["loai_kiem_tra"] = kind
    evidence = scenario(tmp_path, knowledge)
    item = evidence.scenario["criteria"]["CRITERION_1"]
    item.update(document_set_complete=True, full_document_review=True)
    evidence.path.write_text(json.dumps(evidence.scenario))
    from legal_checker.modules.compliance.source_verifier import SyntheticScenarioEvidence

    evidence = SyntheticScenarioEvidence(evidence.path, artifact_dir=tmp_path / "artifacts")
    verifications = evidence.verify(
        ctx,
        profile,
        request.payload.requirements,
        request.payload.chunks,
        knowledge,
        coverage=coverage,
    )
    return knowledge, request, ctx, profile, coverage, verifications


def review(tmp_path, prepared, client):
    knowledge, request, ctx, profile, coverage, records = prepared
    return FullDocumentReviewer(client, tmp_path / "artifacts").review(
        ctx,
        profile,
        request.payload.requirements,
        request.payload.chunks,
        knowledge,
        records,
        coverage,
    )


def evaluate(prepared, bundle):
    knowledge, request, ctx, _, _, _ = prepared
    request.payload.external_evidence_registry = bundle.registrations
    request.payload.retrieval = add_review_candidates(
        ctx,
        request.payload.requirements,
        request.payload.chunks,
        [],
        bundle.candidates,
        knowledge,
        review_sha256=bundle.diagnostic["artifact_sha256"],
    )
    request.payload.observations = admit_document_decisions(
        request,
        knowledge,
        bundle.decisions,
        bundle.verifications,
        model_version="TEST_MODEL",
        prompt_version="TEST",
    )
    return reason(request, knowledge)[0]


def semantic_evaluate(prepared, bundle, finding):
    """Presence is a C06 candidate; a separate C07 pass must compare its meaning."""
    knowledge, request, *_ = prepared
    evaluate(prepared, bundle)
    record = bundle.verifications[0].model_copy(deep=True)
    registered = {r.bang_chung_id for r in request.payload.external_evidence_registry}
    record.external_excerpts = [
        e for e in record.external_excerpts if e.bang_chung_id in registered
    ]
    chunk = request.payload.chunks[0]

    class SemanticClient:
        def complete(self, context, **kw):
            return LlmResponse(
                json.dumps(
                    dict(
                        tieu_chi_id="CRITERION_1",
                        proposed_finding=finding,
                        giai_thich="Offline semantic comparison of this exact predicate and quote",
                        checked_conditions=[],
                        missing_conditions=[],
                        verification_requirements=[],
                        evidence=[
                            dict(doan_id=chunk.doan_id, trich_dan=chunk.noi_dung, ky_tu_bat_dau=0)
                        ],
                        external_evidence_ids=[],
                        candidate_facts=[],
                    )
                ),
                "TEST_SEMANTIC",
            )

    result = LLMObservationProvider(
        SemanticClient(), automatic_draft_review=True, verifications=[record]
    ).analyze(request, knowledge)
    request.payload.observations = result.observations
    return reason(request, knowledge)[0]


@pytest.mark.parametrize(
    "kind,finding", [("PROHIBITED_CLAUSE", "VIOLATED"), ("CONTRACT_CONTENT", "SATISFIED")]
)
def test_present_candidates_reach_semantic_c07_with_real_c06(
    tmp_path, reasoning_case, kind, finding
):
    prepared = prepare(tmp_path, reasoning_case, kind)
    bundle = review(tmp_path, prepared, MatrixClient("PRESENT"))
    assert evaluate(prepared, bundle).finding == "UNKNOWN"
    assert semantic_evaluate(prepared, bundle, finding).finding == finding


def test_prohibited_search_uses_violation_predicate_not_compliance_predicate(
    tmp_path, reasoning_case
):
    prepared = prepare(tmp_path, reasoning_case)
    knowledge = prepared[0]
    for finding, predicate in (
        ("SATISFIED", "No clause permits the seller to change price unilaterally."),
        ("VIOLATED", "A clause permits the seller to change price unilaterally."),
    ):
        rule = knowledge.decision("CRITERION_1", finding)
        conditions = dict(rule["dieu_kien_json"])
        conditions["predicate"] = predicate
        rule["dieu_kien_json"] = conditions
    client = MatrixClient("ABSENT")
    review(tmp_path, prepared, client)
    target = client.calls[0]["payload"]["criteria"][0]
    assert target["search_finding"] == "VIOLATED"
    assert target["predicate"] == "A clause permits the seller to change price unilaterally."


def test_local_condition_search_does_not_prime_compliance_answer(
    tmp_path, reasoning_case, monkeypatch
):
    from legal_checker.modules.compliance import conditional_review

    question = "Does the source expressly allow payment after receiving the asset?"
    monkeypatch.setitem(conditional_review.CONDITIONS, "CRITERION_1", (question, True))
    prepared = prepare(tmp_path, reasoning_case, "DOI_CHIEU_CO_DIEU_KIEN")
    prepared[0].criteria["CRITERION_1"]["noi_dung"] = "Determine lawful reservation of title."
    for record in prepared[-1]:
        record.facts.update(
            assessment_mode="DRAFT_REVIEW", local_condition_policy="DRAFT_LOCAL_CONDITIONS_V1"
        )
    client = MatrixClient("ABSENT")
    review(tmp_path, prepared, client)
    target = client.calls[0]["payload"]["criteria"][0]
    assert target["meaning"] == "LOCAL_CONDITION"
    assert target["search_finding"] == "LOCAL_CONDITION_ONLY"
    assert target["criterion"] == target["predicate"] == question
    assert "reservation of title" not in target["criterion"]


@pytest.mark.parametrize(
    "kind,assessment,expected",
    [
        ("PROHIBITED_CLAUSE", "ABSENT", "SATISFIED"),
        ("PROHIBITED_CLAUSE", "PRESENT", "UNKNOWN"),
        ("CONTRACT_CONTENT", "ABSENT", "MISSING"),
        ("CONTRACT_CONTENT", "PRESENT", "UNKNOWN"),
    ],
)
def test_complete_review_admits_draft_with_source_backed_proof(
    tmp_path, reasoning_case, kind, assessment, expected
):
    prepared = prepare(tmp_path, reasoning_case, kind)
    bundle = review(tmp_path, prepared, MatrixClient(assessment))
    raw = (tmp_path / "artifacts" / f"{bundle.diagnostic['artifact_sha256']}.json").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == bundle.diagnostic["artifact_sha256"]
    assert DocumentReviewArtifact.model_validate_json(raw) == bundle.artifact
    assert bundle.verifications[0].gates.absence_verified == (assessment == "ABSENT")
    result = evaluate(prepared, bundle)
    assert result.finding == expected, result.uncertainty_reason
    assert result.review_status == "PENDING"
    if assessment == "PRESENT":
        assert not prepared[1].payload.observations
        assert prepared[1].payload.retrieval[0].doan_id == prepared[1].payload.chunks[0].doan_id


@pytest.mark.parametrize("invalid", ["omitted_chunk", "omitted_criterion", "foreign_chunk"])
def test_partial_or_foreign_model_matrix_never_proves_absence(tmp_path, reasoning_case, invalid):
    prepared = prepare(tmp_path, reasoning_case)
    client = MatrixClient("PRESENT", invalid)
    with pytest.raises(LlmClientError, match="DOCUMENT_REVIEW_INVALID_MATRIX"):
        review(tmp_path, prepared, client)
    assert len(client.calls) == 2
    assert not prepared[-1][0].gates.absence_verified


def test_uncertain_review_has_no_admitted_decision(tmp_path, reasoning_case):
    prepared = prepare(tmp_path, reasoning_case)
    bundle = review(tmp_path, prepared, MatrixClient("UNCERTAIN"))
    assert not bundle.verifications[0].gates.absence_verified
    assert evaluate(prepared, bundle).finding == "UNKNOWN"


def test_unreadable_or_missing_source_page_never_proves_absence(tmp_path, reasoning_case):
    prepared = prepare(tmp_path, reasoning_case)
    prepared[4].page_count = 2
    client = MatrixClient()
    assert review(tmp_path, prepared, client) is None
    assert not client.calls


def test_review_proof_rejects_changed_matrix_or_active_chunk_manifest(tmp_path, reasoning_case):
    bundle = review(tmp_path, prepare(tmp_path, reasoning_case), MatrixClient())
    data = bundle.artifact.model_dump()
    data["chunk_manifest"]["FOREIGN"] = "c" * 64
    with pytest.raises(ValueError, match="omitted active chunks"):
        DocumentReviewArtifact.model_validate(data)
    data = bundle.artifact.model_dump()
    data["parts"][0]["checks"][0]["assessment"] = "UNCERTAIN"
    with pytest.raises(ValueError, match="conclusion differs"):
        DocumentReviewArtifact.model_validate(data)


def test_refinement_returns_c06_without_mutating_original_and_rejects_foreign_owner(
    tmp_path, reasoning_case
):
    knowledge, request, ctx, *_ = prepare(tmp_path, reasoning_case)
    before = request.model_dump()
    ids = {("CASE_REQUIREMENT_1", "CRITERION_1"): ["CHUNK_1"]}
    result = add_review_candidates(
        ctx,
        request.payload.requirements,
        request.payload.chunks,
        request.payload.retrieval,
        ids,
        knowledge,
    )
    assert result[0].scores["full_document_review"] == 1.0
    assert before == request.model_dump()
    ids[("CASE_REQUIREMENT_1", "CRITERION_1")] = ["FOREIGN"]
    with pytest.raises(ValueError, match="ownership"):
        add_review_candidates(
            ctx, request.payload.requirements, request.payload.chunks, [], ids, knowledge
        )


def test_content_addressed_artifacts_preserve_old_revision_and_detect_tampering(tmp_path):
    old = store_bytes(tmp_path, b'{"revision":1}')
    new = store_bytes(tmp_path, b'{"revision":2}')
    assert old.path != new.path and old.path.exists()
    assert store_bytes(tmp_path, old.path.read_bytes()) == old
    old.path.write_bytes(b"changed")
    with pytest.raises(ValueError, match="changed"):
        store_bytes(tmp_path, b'{"revision":1}')


@pytest.mark.parametrize("kind,selected", [("NOI_DUNG_BAT_BUOC", 6), ("PROHIBITED_CLAUSE", 15)])
def test_many_presence_hits_keep_pool_and_bound_only_content_evidence(
    reasoning_case, kind, selected
):
    from legal_checker.shared.contracts.reasoning import ReasoningRequest

    knowledge, data = reasoning_case
    knowledge.criteria["CRITERION_1"].update(
        loai_kiem_tra=kind, noi_dung="Hợp đồng phải có quyền và nghĩa vụ của bên mua."
    )
    request = ReasoningRequest.model_validate(data)
    chunks = [
        request.payload.chunks[0].model_copy(
            update={"doan_id": f"CHUNK_{i}", "noi_dung": "Đoạn có nhắc đến quyền của các bên."}
        )
        for i in range(15)
    ]
    chunks[-1].noi_dung = "ĐIỀU 6. QUYỀN VÀ NGHĨA VỤ CỦA BÊN MUA\nQuyền và nghĩa vụ của bên mua."
    rows = add_review_candidates(
        request,
        request.payload.requirements,
        chunks,
        [],
        {("CASE_REQUIREMENT_1", "CRITERION_1"): [c.doan_id for c in chunks]},
        knowledge,
    )
    assert len(rows) == 15  # Every located candidate remains inspectable.
    assert sum(r.duoc_chon for r in rows) == selected
    assert next(r for r in rows if r.doan_id == "CHUNK_14").duoc_chon


@pytest.mark.parametrize(
    "field,value",
    [
        ("run_id", "FOREIGN"),
        ("ca_id", "FOREIGN"),
        ("knowledge_snapshot_sha256", "d" * 64),
        ("hop_dong_id", "FOREIGN"),
    ],
)
def test_review_admission_rejects_foreign_verification(tmp_path, reasoning_case, field, value):
    prepared = prepare(tmp_path, reasoning_case)
    bundle = review(tmp_path, prepared, MatrixClient())
    setattr(bundle.verifications[0], field, value)
    with pytest.raises(ValueError, match="context mismatch"):
        evaluate(prepared, bundle)


def test_incomplete_missing_gate_is_not_admitted(tmp_path, reasoning_case):
    prepared = prepare(tmp_path, reasoning_case, "CONTRACT_CONTENT")
    bundle = review(tmp_path, prepared, MatrixClient())
    bundle.verifications[0].gates.absence_verified = False
    assert evaluate(prepared, bundle).finding == "UNKNOWN"


def test_full_review_obeys_shared_call_budget(tmp_path, reasoning_case):
    knowledge, request, ctx, profile, coverage, records = prepare(tmp_path, reasoning_case)
    client = MatrixClient()
    reviewer = FullDocumentReviewer(client, tmp_path / "artifacts", max_calls=0)
    with pytest.raises(LlmClientError, match="DOCUMENT_REVIEW_CALL_LIMIT"):
        reviewer.review(
            ctx,
            profile,
            request.payload.requirements,
            request.payload.chunks,
            knowledge,
            records,
            coverage,
        )
    assert not client.calls


def test_land_description_cannot_reuse_apartment_common_area_as_legal_subject(
    tmp_path, reasoning_case
):
    prepared = prepare(tmp_path, reasoning_case, "CONTRACT_CONTENT")
    knowledge, request, *_ = prepared
    knowledge.criteria["CRITERION_1"]["noi_dung"] = "Hợp đồng phải mô tả đặc điểm của thửa đất ở."
    request.payload.chunks[
        0
    ].noi_dung = "Phần diện tích thông thủy căn hộ và hệ thống chung của tòa nhà."
    bundle = review(tmp_path, prepared, MatrixClient("PRESENT"))
    assert bundle.decisions["CRITERION_1"]["assessment"] == "UNCERTAIN"
    assert bundle.verifications[0].facts["content_subject_validated"] is False
    assert evaluate(prepared, bundle).finding == "UNKNOWN"
    assert "SUBJECT_NOT_IN_EVIDENCE:" in bundle.artifact.parts[0].checks[0].explanation


def test_later_positive_cannot_bypass_failed_subject_verification(tmp_path, reasoning_case):
    prepared = prepare(tmp_path, reasoning_case, "CONTRACT_CONTENT")
    bundle = review(tmp_path, prepared, MatrixClient("PRESENT"))
    bundle.verifications[0].facts["content_subject_validated"] = False
    bundle.verifications[0].facts["content_subject_validation_reason"] = "missing land description"
    result = semantic_evaluate(prepared, bundle, "SATISFIED")
    assert result.finding == "UNKNOWN"
    assert "missing land description" in result.uncertainty_reason


def test_criterion_subsets_still_form_a_complete_source_matrix(tmp_path, reasoning_case):
    from copy import deepcopy

    prepared = prepare(tmp_path, reasoning_case)
    knowledge, request, ctx, profile, coverage, records = prepared
    second = deepcopy(knowledge.criteria["CRITERION_1"])
    second["tieu_chi_id"] = "CRITERION_2"
    knowledge.criteria["CRITERION_2"] = second
    for rule in list(knowledge.tables["quy_tac_quyet_dinh"]):
        copied = deepcopy(rule)
        copied["tieu_chi_id"] = "CRITERION_2"
        copied["quy_tac_id"] += "_SECOND"
        knowledge.tables["quy_tac_quyet_dinh"].append(copied)
    records.append(records[0].model_copy(update={"tieu_chi_id": "CRITERION_2"}, deep=True))
    client = MatrixClient("ABSENT")
    bundle = FullDocumentReviewer(client, tmp_path / "artifacts", max_criteria_per_call=1).review(
        ctx,
        profile,
        request.payload.requirements,
        request.payload.chunks,
        knowledge,
        records,
        coverage,
    )
    assert len(client.calls) == 2
    assert bundle.artifact.criterion_ids == ["CRITERION_1", "CRITERION_2"]
    assert {c.tieu_chi_id for c in bundle.artifact.parts[0].checks} == {
        "CRITERION_1",
        "CRITERION_2",
    }
    assert bundle.artifact.parts[0].read_chunk_ids == [c.doan_id for c in request.payload.chunks]
    for call in client.calls:
        schema = call["schema"]["properties"]
        assert schema["checks"]["minItems"] == schema["checks"]["maxItems"] == 1
        assert schema["reviewed_chunks"]["items"]["enum"] == ["D1"]


def test_intermediary_predicate_does_not_accept_buyer_conduct_as_its_subject():
    from legal_checker.modules.compliance.subject_grounding import subject_supported

    assert not subject_supported(
        "TC_PV_HYC010_01",
        "Bên Bán được miễn trừ tranh chấp của bên thứ ba đối với hành vi của Bên Mua, "
        "trừ lỗi của Bên Bán.",
    )
    assert subject_supported(
        "TC_PV_HYC010_01",
        "Bên Bán không chịu trách nhiệm về khoản tiền do đại lý bán căn hộ nhận từ Bên Mua.",
    )


def _two_criterion_review(prepared):
    from copy import deepcopy

    knowledge, _, _, _, _, records = prepared
    second = deepcopy(knowledge.criteria["CRITERION_1"])
    second["tieu_chi_id"] = "CRITERION_2"
    knowledge.criteria["CRITERION_2"] = second
    for rule in list(knowledge.tables["quy_tac_quyet_dinh"]):
        copied = deepcopy(rule)
        copied["tieu_chi_id"] = "CRITERION_2"
        copied["quy_tac_id"] += "_SECOND"
        knowledge.tables["quy_tac_quyet_dinh"].append(copied)
    records.append(records[0].model_copy(update={"tieu_chi_id": "CRITERION_2"}, deep=True))


def test_joint_review_deduplicates_legal_text_and_keeps_every_matrix_cell(tmp_path, reasoning_case):
    prepared = prepare(tmp_path, reasoning_case)
    _two_criterion_review(prepared)
    knowledge, request, ctx, profile, coverage, records = prepared
    article_id = knowledge.criteria["CRITERION_1"].get("source_dieu_khoan_id")
    if article_id:
        knowledge.articles[article_id]["noi_dung_nguon"] = "Exact pinned legal article text."
    client = MatrixClient("ABSENT")
    bundle = review(tmp_path, prepared, client)
    assert len(client.calls) == 1
    assert len(bundle.artifact.parts[0].checks) == 2
    assert bundle.diagnostic["http_requests"] == 1
    if article_id:
        payload = client.calls[0]["payload"]
        assert payload["legal_article_catalog"] == [
            {"article_ref": "A1", "text": "Exact pinned legal article text."}
        ]
        assert all(c["legal_article_ref"] == "A1" for c in payload["criteria"])
        assert all("legal_article" not in c for c in payload["criteria"])
    assert all(v.gates.absence_verified for v in bundle.verifications)


def test_provider_output_budget_caps_joint_review_size(tmp_path):
    from types import SimpleNamespace

    client = MatrixClient()
    client.settings = SimpleNamespace(max_output_tokens=1800)
    reviewer = FullDocumentReviewer(client, tmp_path)
    assert reviewer.max_criteria_per_call == 10


class SplitOnlyClient(MatrixClient):
    def complete(self, context, **kwargs):
        self.invalid = "omitted_criterion" if len(kwargs["payload"]["criteria"]) > 1 else None
        return super().complete(context, **kwargs)


def test_invalid_matrix_recovers_only_from_fully_validated_child_batches(tmp_path, reasoning_case):
    prepared = prepare(tmp_path, reasoning_case)
    _two_criterion_review(prepared)
    knowledge, request, ctx, profile, coverage, records = prepared
    client = SplitOnlyClient()
    bundle = FullDocumentReviewer(client, tmp_path / "artifacts", max_calls=6).review(
        ctx,
        profile,
        request.payload.requirements,
        request.payload.chunks,
        knowledge,
        records,
        coverage,
    )
    assert len(client.calls) == 4
    assert bundle.diagnostic["adaptive_split_count"] == 1
    assert bundle.artifact.criterion_ids == ["CRITERION_1", "CRITERION_2"]
    assert len(bundle.artifact.parts[0].checks) == 2
    assert all(v.gates.absence_verified for v in bundle.verifications)
    assert (
        client.calls[1]["payload"]["repair_manifest"]["validation_error"]
        == "Incomplete criterion matrix"
    )
    assert all(len(call["payload"]["criteria"]) == 1 for call in client.calls[2:])


def test_adaptive_recovery_cannot_exceed_budget_or_store_partial_proof(tmp_path, reasoning_case):
    prepared = prepare(tmp_path, reasoning_case)
    _two_criterion_review(prepared)
    knowledge, request, ctx, profile, coverage, records = prepared
    before = set((tmp_path / "artifacts").rglob("*.json"))
    with pytest.raises(LlmClientError, match="DOCUMENT_REVIEW_CALL_LIMIT"):
        FullDocumentReviewer(SplitOnlyClient(), tmp_path / "artifacts", max_calls=5).review(
            ctx,
            profile,
            request.payload.requirements,
            request.payload.chunks,
            knowledge,
            records,
            coverage,
        )
    assert set((tmp_path / "artifacts").rglob("*.json")) == before
