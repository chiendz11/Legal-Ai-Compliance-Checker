"""Keep scoped independent annotations from becoming misleading benchmark truth."""

import copy

import pytest
from devtools.gold_answers import (
    GoldCase,
    GoldCriterion,
    GoldError,
    GoldFact,
    canonical_sha,
    check_full_gold_coverage,
    validate_gold_case,
    validate_literal_gold,
)
from pydantic import ValidationError

SHA = "a" * 64


def source():
    return {
        "case_id": "CASE",
        "source_sha256": SHA,
        "page_count": 2,
        "text_sparse_pages": [],
        "blocks": [
            {"id": "BODY", "page": 1, "text": "Giá bán căn hộ: 100 VND"},
            {"id": "HEADER", "page": 2, "text": "PHỤ LỤC 01 - THÔNG TIN GIAO DỊCH"},
            {"id": "PRICE", "page": 2, "text": "Giá bán căn hộ: 200 VND"},
        ],
    }


def span():
    text = source()["blocks"][2]["text"]
    return dict(source_sha256=SHA, ref="PRICE", page=2, start=0, end=len(text), quote=text)


def literal():
    return {
        "case_id": "CASE",
        "source_sha256": SHA,
        "scope": "APPENDIX_LITERALS_AND_NUMBERED_MENTIONS",
        "full_document_profile_gold": False,
        "full_document_legal_gold": False,
        "production_outputs_used": False,
        "human_legal_signoff": False,
        "fields": [
            {
                "field": "price",
                "source_label": "Giá bán căn hộ",
                "scope": "SYNTHETIC_TRANSACTION_APPENDIX_ONLY",
                "whole_document_absence_claim": False,
                "annotation_quality": "GOLD",
                "status": "KNOWN",
                "value": "200",
                "evidence": [span()],
            }
        ],
        "numbered_mentions": [],
    }


def criterion(**updates):
    row = {
        "criterion_id": "TC",
        "requirement_id": "REQ",
        "requirement_version_id": "V1",
        "finding": "SATISFIED",
        "reason_code": "SOURCE_SUPPORTED",
        "reason": "A source-supported declared target.",
        "legal_article_ids": ["ARTICLE"],
        "evidence": [span()],
        "annotation_quality": "GOLD",
        "adjudication_ids": ["AI_REVIEW"],
    }
    row.update(updates)
    return row


def case():
    kb = {
        "tables": {
            "tieu_chi_danh_gia": [
                {
                    "tieu_chi_id": "TC",
                    "requirement_version_id": "V1",
                    "source_dieu_khoan_id": "ARTICLE",
                }
            ],
            "phien_ban_yeu_cau": [{"requirement_version_id": "V1", "requirement_id": "REQ"}],
            "dieu_khoan_phap_ly": [{"dieu_khoan_id": "ARTICLE"}],
        }
    }
    row = {
        "gold_version": "G1",
        "case_id": "CASE",
        "source_sha256": SHA,
        "knowledge_snapshot_sha256": canonical_sha(kb),
        "review_mode": "DRAFT_REVIEW",
        "scope": "PROVIDED_PDF_AND_PINNED_KNOWLEDGE",
        "facts": [],
        "requirements": [],
        "criteria": [criterion()],
        "citations": [],
        "requirements_aggregated": [],
        "adjudicator_type": "AI_SOURCE_ADJUDICATED",
        "status": "GOLD",
    }
    return row, kb


def test_scope_is_explicit_even_for_valid_gold():
    row, kb = case()
    answer = GoldCase.model_validate(row)
    assert answer.coverage == "DECLARED_TARGETS_ONLY"
    assert validate_gold_case(answer, source(), kb)["status"] == "PASS"
    assert validate_literal_gold(literal(), source())["status"] == "PASS"


@pytest.mark.parametrize(
    "field,value",
    [
        ("full_document_profile_gold", True),
        ("full_document_legal_gold", True),
        ("production_outputs_used", True),
        ("human_legal_signoff", True),
        ("source_sha256", "b" * 64),
    ],
)
def test_literal_gold_rejects_inflated_claims_or_other_source(field, value):
    row = literal()
    row[field] = value
    with pytest.raises(GoldError):
        validate_literal_gold(row, source())


def test_quote_and_page_must_match_the_actual_pdf():
    row = literal()
    row["fields"][0]["evidence"][0]["quote"] = "Giá bán căn hộ: 300 VND"
    with pytest.raises(GoldError, match="locked source"):
        validate_literal_gold(row, source())
    row = literal()
    row["fields"][0]["evidence"][0]["page"] = 1
    with pytest.raises(GoldError):
        validate_literal_gold(row, source())


def test_quote_cannot_claim_an_offset_beyond_the_source_block():
    row = literal()
    row["fields"][0]["evidence"][0]["end"] += 100
    with pytest.raises(GoldError):
        validate_literal_gold(row, source())


def test_appendix_task_cannot_use_body_value():
    row = literal()
    raw = row["fields"][0]["evidence"][0]
    raw.update(ref="BODY", page=1, quote=source()["blocks"][0]["text"])
    with pytest.raises(GoldError, match="contract body"):
        validate_literal_gold(row, source())


def test_populated_label_is_not_negative_gold():
    row = literal()
    fact = row["fields"][0]
    fact.update(status="NOT_PROVIDED_IN_AUTHORED_APPENDIX", value=None)
    with pytest.raises(GoldError, match="populated field"):
        validate_literal_gold(row, source())


def test_appendix_absence_requires_every_block_of_its_scope():
    row = literal()
    fact = row["fields"][0]
    fact.update(
        field="phone",
        source_label="Điện thoại",
        status="NOT_PROVIDED_IN_AUTHORED_APPENDIX",
        value=None,
        evidence=[],
        negative_source_review={
            "source_sha256": SHA,
            "scope": "AUTHORED_APPENDIX_ONLY",
            "reviewed_block_ids": ["HEADER", "PRICE"],
            "reviewed_pages": [2],
            "searched_label": "Điện thoại",
        },
    )
    assert validate_literal_gold(row, source())["status"] == "PASS"
    fact["negative_source_review"]["reviewed_block_ids"] = ["HEADER"]
    with pytest.raises(GoldError, match="complete scoped"):
        validate_literal_gold(row, source())


def test_conflict_cannot_select_one_price():
    row = literal()
    row["fields"][0].update(status="CONFLICT", alternatives=["100", "200"])
    with pytest.raises(GoldError, match="one convenient value"):
        validate_literal_gold(row, source())


@pytest.mark.parametrize("code", ["MODEL_UNCERTAIN", "NOT_IMPLEMENTED", "ADJUDICATION_FAILED"])
def test_annotation_failure_is_not_a_gold_unknown(code):
    with pytest.raises(ValidationError, match="Annotation uncertainty"):
        GoldCriterion.model_validate(criterion(finding="UNKNOWN", reason_code=code))


def test_missing_is_not_inferred_from_empty_retrieval():
    with pytest.raises(ValidationError, match="negative source review"):
        GoldCriterion.model_validate(criterion(finding="MISSING", evidence=[]))


def test_incomplete_negative_review_cannot_establish_absence():
    row, kb = case()
    row["criteria"] = [
        criterion(
            finding="MISSING",
            evidence=[],
            negative_source_review={
                "source_sha256": SHA,
                "reviewed_pages": [1],
                "scope": "PROVIDED_PDF_ONLY",
            },
        )
    ]
    with pytest.raises(GoldError, match="complete scoped"):
        validate_gold_case(GoldCase.model_validate(row), source(), kb)


def test_criterion_cannot_move_to_a_different_requirement():
    row, kb = case()
    row["criteria"][0]["requirement_id"] = "ANOTHER"
    with pytest.raises(GoldError, match="ownership"):
        validate_gold_case(GoldCase.model_validate(row), source(), kb)


def test_pending_target_cannot_be_hidden_inside_gold_case():
    row, _ = case()
    row["criteria"][0]["annotation_quality"] = "PENDING_ADJUDICATION"
    with pytest.raises(ValidationError, match="partially adjudicated"):
        GoldCase.model_validate(row)


def test_unknown_value_and_false_human_review_are_not_fabricated():
    with pytest.raises(ValidationError):
        GoldFact(field="date", status="UNKNOWN", value="2017-02-16", reason="Unknown date")
    row, _ = case()
    row["human_legal_signoff"] = True
    with pytest.raises(ValidationError):
        GoldCase.model_validate(row)


def test_snapshot_drift_is_rejected():
    row, kb = case()
    changed = copy.deepcopy(kb)
    changed["tables"]["phien_ban_yeu_cau"][0]["requirement_id"] = "NEW"
    with pytest.raises(GoldError, match="knowledge revision"):
        validate_gold_case(GoldCase.model_validate(row), source(), changed)


def test_full_gold_release_cannot_hide_unfinished_cases():
    _, kb = case()
    kb["tables"]["yeu_cau_phap_ly"] = [{"requirement_id": "REQ"}]
    result = check_full_gold_coverage({"CASE": source()}, {}, kb)
    assert result["full_e2e_gold_ready"] is False
    assert result["errors"] == [{"case_id": "CASE", "reason": "MISSING_CASE_GOLD"}]


def test_manual_ready_flag_cannot_replace_layer_adjudication():
    row, kb = case()
    kb["tables"]["yeu_cau_phap_ly"] = [{"requirement_id": "REQ"}]
    row.update(
        annotation_quality="GOLD",
        knowledge_snapshot_sha256=canonical_sha(kb),
        human_legal_signoff=False,
        production_outputs_used=False,
        full_e2e_gold_ready=True,
    )
    result = check_full_gold_coverage({"CASE": source()}, {"CASE": row}, kb)
    assert result["full_e2e_gold_ready"] is False
    reasons = {e["reason"] for e in result["errors"]}
    assert "INCOMPLETE_OR_DUPLICATE_C05" in reasons
    assert "MISSING_OR_UNBOUND_LAYER:FACTS" in reasons


def test_missing_transition_proof_blocks_post_cutoff_confirmation():
    row, kb = case()
    kb["tables"]["yeu_cau_phap_ly"] = [{"requirement_id": "REQ"}]
    kb["tables"]["phien_ban_yeu_cau"][0]["quy_tac_chuyen_tiep"] = {
        "transition": "KDBDS_83",
        "grandfathering": "CASE_REVIEW",
    }
    row.update(
        annotation_quality="GOLD",
        knowledge_snapshot_sha256=canonical_sha(kb),
        human_legal_signoff=False,
        production_outputs_used=False,
        requirements=[
            {
                "requirement_id": "REQ",
                "requirement_version_id": "V1",
                "applicability_status": "CONFIRMED",
                "relevant_date": "2025-01-01",
            }
        ],
        facts=[
            {
                "field": "tinh_trang_tai_san",
                "status": "KNOWN",
                "value": "HINH_THANH_TRONG_TUONG_LAI",
            }
        ],
    )
    result = check_full_gold_coverage({"CASE": source()}, {"CASE": row}, kb)
    assert result["full_e2e_gold_ready"] is False
    assert any(e["reason"].startswith("TRANSITION_FACT_NOT_ADJUDICATED:") for e in result["errors"])


def materialized_release():
    """Small nonlegal fixture to exercise evidence/artifact admission boundaries."""
    row, kb = case()
    kb["tables"]["yeu_cau_phap_ly"] = [{"requirement_id": "REQ"}]
    row.update(
        annotation_quality="GOLD",
        knowledge_snapshot_sha256=canonical_sha(kb),
        human_legal_signoff=False,
        production_outputs_used=False,
        requirements=[
            {
                "requirement_id": "REQ",
                "requirement_version_id": "V1",
                "scope_status": "MATCH",
                "version_status": "RESOLVED",
                "applicability_status": "CONFIRMED",
                "date_provenance": {"kind": "PUBLIC_C01_ASSESSMENT_CONTEXT"},
            }
        ],
        layer_receipts={},
    )
    artifacts = {}
    projections = {
        "FACTS": [],
        "SCOPE_TEMPORAL": row["requirements"],
        "CRITERIA": row["criteria"],
        "CITATION_OCCURRENCES": [],
        "AGGREGATION": [],
        "RISKS": [],
        "RECOMMENDATION_ASSERTIONS": [],
        "REVIEW_POLICY": [],
        "REPORT_ASSERTIONS": [],
        "RETRIEVAL_JUDGED_POOL": [
            {
                "criterion_id": "TC",
                "source_ref": "PRICE",
                "relevance": 2,
                "reason": "A source price witness",
                "evidence": [span()],
            }
        ],
    }
    for layer, judgments in projections.items():
        artifact = dict(
            case_id="CASE",
            layer=layer,
            source_sha256=SHA,
            knowledge_snapshot_sha256=canonical_sha(kb),
            status="ADJUDICATED",
            production_outputs_used=False,
            adjudicator_type="AI_SOURCE_ADJUDICATED",
            review_method="Manually authored test fixture",
            judgments=copy.deepcopy(judgments),
        )
        if layer == "RETRIEVAL_JUDGED_POOL":
            artifact.update(
                pool_definition="One deliberately bounded source pair", outside_pool="UNJUDGED"
            )
        artifacts[layer] = artifact
        row["layer_receipts"][layer] = dict(
            status="ADJUDICATED",
            source_sha256=SHA,
            knowledge_snapshot_sha256=canonical_sha(kb),
            artifact_id=layer,
            artifact_sha256=canonical_sha(artifact),
        )
    return row, kb, artifacts


def test_receipt_strings_alone_do_not_prove_adjudication():
    row, kb, artifacts = materialized_release()
    assert check_full_gold_coverage({"CASE": source()}, {"CASE": row}, kb, artifacts=artifacts)[
        "full_e2e_gold_ready"
    ]
    rejected = check_full_gold_coverage({"CASE": source()}, {"CASE": row}, kb)
    assert not rejected["full_e2e_gold_ready"]
    assert any(
        e["reason"].startswith("MISSING_OR_CHANGED_ADJUDICATION_ARTIFACT:")
        for e in rejected["errors"]
    )


@pytest.mark.parametrize("scope", ["CONDITIONAL_OR_EXTERNAL_FACTS", "CONTRACT_TEXT"])
def test_missing_label_respects_external_duty_scope(scope):
    row, kb, artifacts = materialized_release()
    kb["tables"]["tieu_chi_danh_gia"][0].update(
        pham_vi_kiem_tra=scope,
        noi_dung_bat_buoc_trong_hd=False,
        missing_policy="NO_MISSING_FOR_CONDITIONAL_PERFORMANCE_FORMAT_OR_CONSISTENCY",
    )
    row["criteria"][0].update(finding="MISSING")
    artifacts["CRITERIA"]["judgments"] = copy.deepcopy(row["criteria"])
    row["knowledge_snapshot_sha256"] = canonical_sha(kb)
    for layer, artifact in artifacts.items():
        artifact["knowledge_snapshot_sha256"] = canonical_sha(kb)
        row["layer_receipts"][layer].update(
            knowledge_snapshot_sha256=canonical_sha(kb),
            artifact_sha256=canonical_sha(artifact),
        )
    result = check_full_gold_coverage({"CASE": source()}, {"CASE": row}, kb, artifacts=artifacts)
    if scope == "CONDITIONAL_OR_EXTERNAL_FACTS":
        assert result["errors"] == [
            {"case_id": "CASE", "reason": "EXTERNAL_DUTY_IS_NOT_MISSING_CONTRACT_CONTENT:TC"}
        ]
    else:
        # A contract-content predicate can require a clause even when coarse
        # catalog metadata carries a conditional/performance missing policy.
        assert result["full_e2e_gold_ready"]


def test_tampered_or_foreign_layer_is_rejected():
    row, kb, artifacts = materialized_release()
    artifacts["RISKS"]["case_id"] = "ANOTHER_CASE"
    row["layer_receipts"]["RISKS"]["artifact_sha256"] = canonical_sha(artifacts["RISKS"])
    rejected = check_full_gold_coverage({"CASE": source()}, {"CASE": row}, kb, artifacts=artifacts)
    assert {"case_id": "CASE", "reason": "INVALID_ADJUDICATION_ARTIFACT:RISKS"} in rejected[
        "errors"
    ]


def test_quote_check_covers_retrieval_pool_not_just_c07():
    row, kb, artifacts = materialized_release()
    artifacts["RETRIEVAL_JUDGED_POOL"]["judgments"][0]["evidence"][0]["quote"] = "invented"
    row["layer_receipts"]["RETRIEVAL_JUDGED_POOL"]["artifact_sha256"] = canonical_sha(
        artifacts["RETRIEVAL_JUDGED_POOL"]
    )
    rejected = check_full_gold_coverage({"CASE": source()}, {"CASE": row}, kb, artifacts=artifacts)
    assert any("ARTIFACT_QUOTE_MISMATCH" in e["reason"] for e in rejected["errors"])


def test_c03_occurrence_is_not_a_c09_gold_decision():
    row, kb, artifacts = materialized_release()
    row["citations"] = [{"vien_dan_id": "C03", "raw_text": "A law", "evidence": [span()]}]
    artifacts["CITATION_OCCURRENCES"]["judgments"] = copy.deepcopy(row["citations"])
    row["layer_receipts"]["CITATION_OCCURRENCES"]["artifact_sha256"] = canonical_sha(
        artifacts["CITATION_OCCURRENCES"]
    )
    rejected = check_full_gold_coverage({"CASE": source()}, {"CASE": row}, kb, artifacts=artifacts)
    assert any(e["reason"] == "C03_EXTRACTION_IS_NOT_C09_ADJUDICATION" for e in rejected["errors"])


def test_offline_failure_cannot_be_promoted_by_copying_receipts():
    row, kb, artifacts = materialized_release()
    row["criteria"][0].update(
        finding="UNKNOWN", reason="Chế độ offline: chưa gọi AI phân tích ngữ nghĩa."
    )
    artifacts["CRITERIA"]["judgments"] = copy.deepcopy(row["criteria"])
    row["layer_receipts"]["CRITERIA"]["artifact_sha256"] = canonical_sha(artifacts["CRITERIA"])
    rejected = check_full_gold_coverage({"CASE": source()}, {"CASE": row}, kb, artifacts=artifacts)
    assert any(
        e["reason"].startswith("PROCESSING_FAILURE_IS_NOT_LEGAL_GOLD:") for e in rejected["errors"]
    )
