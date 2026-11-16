"""Condition exclusions require complete source proof; numeric/date bindings stay explicit."""

from datetime import date
from types import SimpleNamespace

import pytest
from legal_checker.modules.applicable_law.scope_resolver import get_field
from legal_checker.modules.applicable_law.temporal_resolver import CatalogTemporalResolver
from legal_checker.modules.compliance.conditional_review import condition_result
from legal_checker.modules.compliance.document_review import FullDocumentReviewer
from legal_checker.modules.compliance.numeric_rules import evaluate_numeric_for_criterion
from legal_checker.modules.compliance.requirement_aggregator import aggregate
from legal_checker.modules.compliance.source_bindings import (
    bind_maintenance_ratio,
    penalty_special_law_binding,
)
from legal_checker.modules.documents.profile_extractor import extract_profile
from legal_checker.shared.contracts.assessment import AssessmentTiming
from legal_checker.shared.contracts.scope import ScopeResolution
from legal_checker.shared.llm.types import LlmClientError
from test_criterion_reasoner import reasoning_case as reasoning_case
from test_document_profile import BODY, _profile
from test_full_document_review import MatrixClient, evaluate, prepare


def test_arbitration_negative_is_limited_to_complete_supplied_draft():
    body = BODY + "\nĐIỀU 18. TRANH CHẤP\nMột trong hai Bên có quyền yêu cầu Tòa án giải quyết.\n"
    chunks, ordinary = _profile(body)
    assert ordinary.profile.co_thoa_thuan_trong_tai is None
    draft = extract_profile(
        chunks, hop_dong_id=ordinary.hop_dong_id, version="draft", complete_draft_source=True
    )
    assert draft.profile.co_thoa_thuan_trong_tai is False
    assert get_field(draft, "co_thoa_thuan_trong_tai").value == "KHONG"
    fact = next(f for f in draft.facts if f.ten_truong == "profile.co_thoa_thuan_trong_tai")
    assert not fact.human_verified
    assert fact.phuong_phap == "COMPLETE_DRAFT_COURT_ONLY_V1"
    chunks, _ = _profile(body + "\nCác bên sẽ giải quyết bằng trọng tài trong thỏa thuận riêng.\n")
    ambiguous = extract_profile(
        chunks, hop_dong_id=ordinary.hop_dong_id, version="draft", complete_draft_source=True
    )
    assert ambiguous.profile.co_thoa_thuan_trong_tai is None


@pytest.mark.parametrize(
    "assessment,expected", [("ABSENT", "NO_MATCH"), ("PRESENT", "MATCH"), ("UNCERTAIN", "UNKNOWN")]
)
def test_trial_condition_has_source_bound_three_state_result(
    tmp_path, reasoning_case, assessment, expected
):
    prepared = prepare(tmp_path, reasoning_case)
    knowledge, request, ctx, profile, coverage, records = prepared
    key = "TC_PV_DS452_01"
    criterion = knowledge.criteria.pop("CRITERION_1")
    criterion["tieu_chi_id"] = key
    criterion["loai_kiem_tra"] = "DOI_CHIEU_CO_DIEU_KIEN"
    knowledge.criteria[key] = criterion
    knowledge.review_status = "HUMAN_VERIFIED"
    for rule in knowledge.tables["quy_tac_quyet_dinh"]:
        rule["tieu_chi_id"] = key
    for row in request.payload.retrieval:
        row.tieu_chi_id = key
    records[0].tieu_chi_id = key
    records[0].verification_reference = "C02_DRAFT_CONTENT_V2:test-source"
    records[0].local_applicability = "UNKNOWN"
    records[0].facts.update(
        assessment_mode="DRAFT_REVIEW",
        assessment_policy_id="DRAFT_CONTENT_REVIEW_V1",
        evaluation_target="CONTRACT_CONTENT",
        local_condition_policy="DRAFT_LOCAL_CONDITIONS_V1",
        condition_review_required=True,
    )
    bundle = FullDocumentReviewer(MatrixClient(assessment), tmp_path / "review").review(
        ctx,
        profile,
        request.payload.requirements,
        request.payload.chunks,
        knowledge,
        records,
        coverage,
    )
    assert bundle.verifications[0].local_applicability == expected
    if expected == "NO_MATCH":
        result = evaluate(prepared, bundle)
        assert result.finding == "UNKNOWN" and result.excluded
        from legal_checker.modules.compliance.requirement_aggregator import POLICY_ID
        from test_requirement_aggregator import AggregationKnowledge

        knowledge.aggregations = AggregationKnowledge().aggregations
        knowledge.versions["VERSION_1"]["quy_tac_tong_hop_id"] = POLICY_ID
        combined = aggregate(request, knowledge, [result], request.payload.requirements)[0]
        assert combined.requirement_snapshot_json["assessment_disposition"] == "NOT_TRIGGERED"
    else:
        assert not bundle.verifications[0].facts.get("local_non_applicability_reason")


@pytest.mark.parametrize(
    "mode,base,amount,percent,expected",
    [
        ("DRAFT_REVIEW", True, "20", "2", True),
        ("DRAFT_REVIEW", True, "30", "3", False),
        ("DRAFT_REVIEW", False, "20", "2", None),
        ("DRAFT_REVIEW", True, "20", "3", None),
        ("FULL_ASSESSMENT", True, "20", "2", None),
    ],
)
def test_maintenance_source_binding_is_not_a_blanket_review(mode, base, amount, percent, expected):
    numeric = dict(
        denominator="apartment_value",
        denominator_definition="EXPERT_REVIEW_REQUIRED",
        included_in_sale_payment=True,
        maintenance_ratio="0.02",
        scope="DEVELOPER_SALE_MULTI_OWNER_NHAO_2014",
    )
    key = "TC_PV_HYC049_02"

    def decision(criterion_id, finding):
        return dict(
            quy_tac_id="RULE",
            tieu_chi_id=criterion_id,
            finding=finding,
            rule_version="V",
            dieu_kien_json=dict(
                enabled=True, predicate="Current criterion ratio", gate={}, numeric_rule=numeric
            ),
        )

    knowledge = SimpleNamespace(decision=decision)
    record = SimpleNamespace(
        facts=dict(assessment_mode=mode, contract_source_sha256="b" * 64),
        gates=SimpleNamespace(evidence_conflict=False),
    )
    sources = dict(
        gia_ban=({"so_tien": "1000", "don_vi": "VND"}, []),
        maintenance_amount=(
            amount,
            [SimpleNamespace(trich_dan="Số tiền kinh phí bảo trì: " + amount + " VND")],
        ),
        maintenance_percent=(percent, []),
    )
    if base:
        sources["maintenance_base_reference"] = ("STATED_SALE_PRICE", [])
    bind_maintenance_ratio(record, {"tieu_chi_id": key}, sources, knowledge)
    if expected is None:
        assert "numeric_target_reviewed" not in record.facts
    else:
        assert (
            evaluate_numeric_for_criterion(numeric, record.facts, facts_verified=True) is expected
        )
        assert record.facts["numeric_binding_authority"] == "BACKEND_SOURCE_CHECK_DRAFT_ONLY"


def test_c01_marker_only_selects_its_own_legal_event(reasoning_case):
    knowledge, data = reasoning_case
    from legal_checker.shared.contracts.common import Context
    from legal_checker.shared.contracts.document_intelligence import (
        ContractProfile,
        ProfileTimeMarker,
    )

    context = Context.model_validate({k: v for k, v in data.items() if k in Context.model_fields})
    knowledge.versions["VERSION_1"].update(
        hieu_luc_tu="2015-01-01", hieu_luc_den=None, loai_moc_ap_dung="TEMPLATE_USE"
    )
    profile = ContractProfile(hop_dong_id="HD", profile={})
    scope = ScopeResolution(
        yeu_cau_ca_id="R",
        ca_id=context.ca_id,
        requirement_id="REQUIREMENT_1",
        scope_status="MATCH",
        scope_reason="evidenced scope",
    )
    timing = AssessmentTiming(
        ngay_danh_gia=date(2026, 11, 9),
        review_mode="DRAFT_REVIEW",
        moc_ap_dung=date(2017, 2, 16),
        loai_moc_ap_dung="TEMPLATE_USE",
    )
    case = SimpleNamespace(
        ca_id=context.ca_id, hop_dong_id="HD", created_by="CALLER", assessment_context=timing
    )
    resolver = CatalogTemporalResolver(case=case)
    selected = resolver.resolve(context, profile, [scope], knowledge)[0]
    assert selected.confirmed and selected.moc_id is None
    assert selected.nguon_snapshot_json["assessment_marker"]["basis"] == "PLANNED_DRAFT_SCENARIO"
    profile.time_markers = [
        ProfileTimeMarker(
            moc_id="M", loai_moc="TEMPLATE_USE", ngay=date(2018, 1, 1), trang_thai="EXTRACTED"
        )
    ]
    conflict = resolver.resolve(context, profile, [scope], knowledge)[0]
    assert conflict.version_status == "UNKNOWN" and conflict.applicability_status == "UNKNOWN"
    profile.time_markers = []
    timing.loai_moc_ap_dung = "SIGNING"
    unmatched = resolver.resolve(context, profile, [scope], knowledge)[0]
    assert unmatched.moc_ap_dung is None and unmatched.version_status == "UNKNOWN"
    case.ca_id = "FOREIGN_CASE"
    with pytest.raises(ValueError, match="another assessment"):
        resolver.resolve(context, profile, [scope], knowledge)


@pytest.mark.parametrize(
    "assessment,expected",
    [
        ("PRESENT", "NO_MATCH"),
        ("ABSENT", "MATCH"),
        ("UNCERTAIN", "UNKNOWN"),
        ("INVALID", "UNKNOWN"),
    ],
)
def test_default_cost_obligation_only_arises_without_agreement(assessment, expected):
    assert condition_result("TC_PV_DS442_02", assessment)[0] == expected


def test_partial_condition_pass_cannot_exclude_a_legal_obligation(tmp_path, reasoning_case):
    knowledge, request, ctx, profile, coverage, records = prepare(tmp_path, reasoning_case)
    key = "TC_PV_DS452_01"
    criterion = knowledge.criteria.pop("CRITERION_1")
    criterion.update(tieu_chi_id=key, loai_kiem_tra="DOI_CHIEU_CO_DIEU_KIEN")
    knowledge.criteria[key] = criterion
    for rule in knowledge.tables["quy_tac_quyet_dinh"]:
        rule["tieu_chi_id"] = key
    records[0].tieu_chi_id = key
    records[0].local_applicability = "UNKNOWN"
    records[0].facts.update(
        assessment_mode="DRAFT_REVIEW",
        local_condition_policy="DRAFT_LOCAL_CONDITIONS_V1",
        condition_review_required=True,
    )
    with pytest.raises(LlmClientError, match="DOCUMENT_REVIEW_INVALID_MATRIX"):
        FullDocumentReviewer(MatrixClient("ABSENT", invalid="omitted_chunk"), tmp_path).review(
            ctx,
            profile,
            request.payload.requirements,
            request.payload.chunks,
            knowledge,
            records,
            coverage,
        )
    assert records[0].local_applicability == "UNKNOWN"
    assert "local_non_applicability_reason" not in records[0].facts


@pytest.mark.parametrize(
    "day,consumer,expected",
    [
        (date(2017, 2, 16), True, True),
        (date(2025, 1, 1), True, False),
        (date(2017, 2, 16), False, False),
    ],
)
def test_related_penalty_law_binding_keeps_its_regime_and_consumer_scope(day, consumer, expected):
    record = SimpleNamespace(facts={"assessment_mode": "DRAFT_REVIEW"})
    profile = SimpleNamespace(
        profile=SimpleNamespace(
            ben_ban_la_chu_dau_tu=True,
            ben_mua_la_ca_nhan=consumer,
            muc_dich_giao_dich="TIEU_DUNG_KHONG_THUONG_MAI",
            doi_tuong="NHA_O",
        )
    )
    knowledge = SimpleNamespace(
        sha256="b" * 64,
        articles={
            "ART_VBPL010_16": dict(
                van_ban_id="LAW",
                trang_thai_xac_minh="HUMAN_VERIFIED",
                noi_dung_nguon="Việc phạt và bồi thường thiệt hại do các bên thỏa thuận.",
            )
        },
        documents={
            "LAW": dict(so_hieu="66/2014/QH13", hieu_luc_tu="2015-07-01", hieu_luc_den="2024-08-01")
        },
    )
    applied = penalty_special_law_binding(
        record,
        {"tieu_chi_id": "TC_PV_DS418_02"},
        SimpleNamespace(confirmed=True, moc_ap_dung=day),
        profile,
        knowledge,
        [{"ngoai_le_id": "EX_DS418_SPECIAL", "tac_dong": "RESOLVE_SPECIAL_LAW"}],
    )
    assert applied is expected
    assert ("exception_binding_reference" in record.facts) is expected
