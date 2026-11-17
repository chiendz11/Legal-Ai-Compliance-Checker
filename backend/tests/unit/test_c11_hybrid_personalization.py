"""Tests for C11 Hybrid Recommendation (Deterministic Template Engine + Local Qwen).

All tests use fake httpx transports and in-memory audit sinks; zero real Ollama/network calls.
"""

from __future__ import annotations

import json
from copy import deepcopy

import httpx
import pytest
from legal_checker.api.dependencies import recommendation_personalizer
from legal_checker.core.config import Settings
from legal_checker.modules.assessments.integrity import validate_membership
from legal_checker.modules.recommendations.personalization import (
    PROMPT_VERSION,
    SCHEMA_VERSION,
    C11OllamaOptions,
    C11PersonalizationOptions,
    OllamaRecommendationClient,
    RecommendationPersonalizationService,
)
from legal_checker.modules.recommendations.service import generate_recommendations
from legal_checker.modules.reports.builder import build_draft_report
from legal_checker.modules.reports.exporter import export_report, report_document
from legal_checker.modules.reports.presentation import build_presentation
from legal_checker.modules.risks.citation_mapper import PRODUCTION_GATE
from legal_checker.modules.risks.service import evaluate_risks
from legal_checker.shared.contracts.assessment import (
    AssessmentCase,
    AssessmentTiming,
    SourceDocument,
)
from legal_checker.shared.contracts.citation import (
    CitationExtraction,
    CitationExtractionMetadata,
    CitationNormalization,
    CitationPosition,
    CitationValidation,
)
from legal_checker.shared.contracts.common import Context, DeploymentPin
from legal_checker.shared.contracts.document_intelligence import (
    Chunk,
    ContractProfile,
    DocumentIntelligenceResult,
    Evidence,
    ProfileFields,
)
from legal_checker.shared.contracts.handoffs import (
    ComplianceOutput,
    IntegrationInput,
    LegalOutput,
)
from legal_checker.shared.contracts.modules import RecommendationRequest, RiskRequest
from legal_checker.shared.contracts.pipeline import PipelinePayload, PipelineRequest
from legal_checker.shared.contracts.reasoning import CriterionResult
from legal_checker.shared.contracts.retrieval import RetrievalEvidence
from legal_checker.shared.contracts.scope import ScopeResolution
from legal_checker.shared.contracts.temporal import ApplicableRequirement
from legal_checker.shared.llm.audit import LlmAudit
from legal_checker.workflows.integrated import IntegratedModulesSource
from legal_checker.workflows.runner import ReferenceReplaySource
from legal_checker.workflows.steps_5_7 import evaluate as evaluate_steps_5_7

DIGEST_64 = "b" * 64


class FakeAuditSink:
    def __init__(self, *, fail_append: bool = False):
        self.events: list[LlmAudit] = []
        self.fail_append = fail_append

    def append(self, event: LlmAudit) -> None:
        if self.fail_append:
            raise RuntimeError("Audit DB unavailable")
        self.events.append(event)


class HybridKnowledge:
    def __init__(self):
        self.sha256 = "a" * 64
        self.schema_version = "SYNTHETIC_TEST"
        self.versions = {
            "VERSION_A": {
                "requirement_version_id": "VERSION_A",
                "requirement_id": "FAMILY_A",
                "source_van_ban_id": "VB_27_2023",
                "quy_tac_tong_hop_id": "AGG_CAN_HO_V1",
            }
        }
        self.criteria = {
            "CRITERION_A": {
                "tieu_chi_id": "CRITERION_A",
                "requirement_version_id": "VERSION_A",
                "source_dieu_khoan_id": "ART_129",
                "noi_dung": "Thời hạn bảo hành nhà chung cư tối thiểu 60 tháng.",
                "loai_kiem_tra": "CONTRACT_CONTENT",
                "bat_buoc": True,
                "noi_dung_bat_buoc_trong_hd": True,
            }
        }
        self.documents = {"VB_27_2023": {"human_verified": True}}
        self.articles = {"ART_129": {"van_ban_id": "VB_27_2023"}}
        self.risks = {}
        self.recommendations = {}
        self.aggregations = {
            "AGG_CAN_HO_V1": {
                "quy_tac_tong_hop_id": "AGG_CAN_HO_V1",
                "rule_version": "AGG_V1",
                "trang_thai": "ENGINE_POLICY",
                "thu_tu_uu_tien_json": [
                    "SCOPE_OR_VERSION_UNRESOLVED=INSUFFICIENT",
                    "PROVEN_VIOLATION=NON_COMPLIANT_WITH_COVERAGE_FLAG",
                    "UNKNOWN=INSUFFICIENT",
                    "ALL_MISSING=NON_COMPLIANT",
                    "MIXED_SATISFIED_MISSING=PARTIAL",
                    "ALL_SATISFIED=COMPLIANT",
                ],
                "dieu_kien_json": {
                    "COMPLIANT": (
                        "all applicable mandatory criteria SATISFIED and no unresolved "
                        "scope/version/evidence"
                    ),
                    "INSUFFICIENT": (
                        "scope/version unresolved OR no applicable evaluated criterion OR any "
                        "remaining UNKNOWN without already-proven violation"
                    ),
                    "NON_COMPLIANT": (
                        "any applicable mandatory criterion VIOLATED; or all applicable mandatory "
                        "criteria MISSING with verified absence"
                    ),
                    "PARTIAL": (
                        "at least one SATISFIED and at least one verified MISSING; "
                        "no VIOLATED/UNKNOWN"
                    ),
                    "excluded": (
                        "NOT_APPLICABLE excluded with reason; "
                        "REVIEW_REQUIRED is not a criterion finding"
                    ),
                },
            }
        }
        self.tables = {
            "quy_tac_rui_ro": [],
            "rui_ro_khuyen_nghi": [],
            "quy_tac_quyet_dinh": [],
        }

    def criteria_for(self, version_id):
        return [c for c in self.criteria.values() if c["requirement_version_id"] == version_id]

    def legal_basis(self, criterion):
        return ["VERSION_A", "ART_129", "VB_27_2023"]

    def decision(self, criterion_id, finding):
        if criterion_id == "CRITERION_A" and finding == "VIOLATED":
            return {
                "quy_tac_id": "DEC_RULE_A",
                "tieu_chi_id": "CRITERION_A",
                "finding": "VIOLATED",
                "rule_version": "DEC_V1",
                "dieu_kien_json": {
                    "enabled": True,
                    "predicate": "WARRANTY_BELOW_MINIMUM",
                    "gate": {
                        "source_available": True,
                        "scope_confirmed": True,
                        "version_resolved": True,
                        "evidence_validated": True,
                        "no_unresolved_conflict": True,
                    },
                },
            }
        return None


def make_case():
    knowledge = HybridKnowledge()
    context = Context(
        ca_id="CA_C11_TEST",
        phien_ban_id="DEPLOY_A",
        rule_version="RULE_DEPLOY_A",
        legal_knowledge_version="LEGAL_A",
        knowledge_snapshot_sha256=knowledge.sha256,
        run_id="RUN_C11_TEST",
        trace_id="TRACE_C11_TEST",
    )
    requirement = ApplicableRequirement(
        yeu_cau_ca_id="REQ_INST_A",
        ca_id=context.ca_id,
        requirement_id="FAMILY_A",
        requirement_version_id="VERSION_A",
        scope_status="MATCH",
        version_status="RESOLVED",
        applicability_status="CONFIRMED",
        moc_ap_dung="2024-09-15",
        phien_ban_id=context.phien_ban_id,
    )
    return context, knowledge, requirement


def make_risks(
    case, finding="VIOLATED", *, citation=False, quote_text="Thời hạn bảo hành 36 tháng."
):
    context, knowledge, requirement = case
    branch = "CITATION" if citation else "COMPLIANCE"
    criterion_id = None if citation else "CRITERION_A"
    verification = finding == "UNKNOWN"
    severity = "REVIEW_REQUIRED" if verification else ("LOW" if citation else "HIGH")
    knowledge.risks["RISK_A"] = {
        "rui_ro_id": "RISK_A",
        "ten_rui_ro": "Bảo hành căn hộ không đạt mức tối thiểu 60 tháng"
        if not citation and not verification
        else (
            "Chưa đủ căn cứ định danh phiên bản luật" if verification else "Viện dẫn hết hiệu lực"
        ),
        "nhanh": branch,
        "tieu_chi_id": criterion_id,
        "muc_do_co_so": severity,
        "ban_chat_rui_ro": "VERIFICATION_ONLY" if verification else "CONDITIONAL",
    }
    trigger = {"finding": finding, "criterion_target_only": True}
    if verification:
        trigger.update(any_unresolved_fact=True, legal_violation_conclusion=False)
    if citation:
        trigger = {
            "schema": "CITATION_RULE_V1_1",
            "branch": branch,
            "citation_status": finding,
            "production_gate": PRODUCTION_GATE,
            "official_evidence_required": not verification,
            "relevant_date_required": not verification,
        }
        if verification:
            trigger.update(
                no_violation_assertion=True,
                missing_or_ambiguous_identity_date_source_or_domain=True,
            )
    knowledge.tables["quy_tac_rui_ro"] = [
        {
            "quy_tac_id": "RISK_RULE_A",
            "nhanh": branch,
            "tieu_chi_id": criterion_id,
            "trigger_status": finding,
            "trigger_json": trigger,
            "hanh_dong": "CREATE_CITATION_RISK"
            if citation
            else ("REQUEST_VERIFICATION" if verification else "CREATE_CONDITIONAL_RISK"),
            "rui_ro_id": "RISK_A",
            "rule_version": "RISK_RULE_VERSION_A",
        }
    ]
    knowledge.tables["rui_ro_khuyen_nghi"] = [
        {"lien_ket_id": "MAPPING_A", "rui_ro_id": "RISK_A", "khuyen_nghi_id": "TEMPLATE_A"}
    ]
    template_text = (
        "Cần kiểm tra lại điều khoản bảo hành với quy định 60 tháng đối với '{quote}'."
        if quote_text and not verification and not citation
        else (
            "Chưa đủ căn cứ xác định chính xác phiên bản văn bản pháp luật."
            if verification
            else "Đối chiếu {risk_name}; nguồn {finding}; căn cứ {legal_basis_ids}."
        )
    )
    knowledge.recommendations["TEMPLATE_A"] = {
        "khuyen_nghi_id": "TEMPLATE_A",
        "nhanh": branch,
        "tieu_chi_id": criterion_id,
        "gap_type": finding,
        "noi_dung": template_text,
        "loai_hanh_dong": "REQUEST_VERIFICATION"
        if verification
        else ("CORRECT_REFERENCE" if citation else "AMEND_OR_PERFORM_CORRECTIVE_ACTION"),
        "uu_tien": severity,
        "required_elements_json": {
            "fields": ["risk_instance_id"],
            "text": (
                ["Cung cấp năm ban hành hoặc số hiệu và bản nguồn"]
                if verification
                else ["Nâng thời hạn bảo hành lên tối thiểu 60 tháng theo VB_27_2023"]
            ),
        },
        "gioi_han_sinh_json": {
            "no_invented_names_dates_accounts": True,
            "severity_from_db": True,
            "human_review_required": True,
        },
        "mau_sua_goi_y": (
            "[Dự thảo cần xác minh đúng nguồn]"
            if verification
            else "Sửa Điều 9: Thời hạn bảo hành căn hộ là 60 tháng kể từ ngày nghiệm thu."
        ),
        "bang_chung_khac_phuc_can_luu": "Nguồn gốc: {evidence_ids}"
        if (quote_text and not verification) or citation
        else None,
        "kiem_tra_sau_khac_phuc": "Đối chiếu lại tại mốc {relevant_date}",
        "trang_thai_ra_soat": "PENDING_HUMAN",
    }

    criteria, citations = [], []
    if citation:
        citations = [
            CitationValidation(
                finding_id="CIT_FIND_A",
                ca_id=context.ca_id,
                vien_dan_id="CITATION_A",
                normalized_van_ban_id="VB_27_2023",
                relevant_date="2024-09-15",
                status=finding,
                reason_code="NAME_ONLY_VERSION_IDENTITY_AMBIGUOUS"
                if verification
                else "STALE_AT_RELEVANT_DATE",
                ly_do="năm ban hành hoặc số hiệu văn bản"
                if verification
                else "Văn bản 65/2014/QH13 đã hết hiệu lực trước ngày 2024-09-15",
                domain_status="UNKNOWN" if verification else "MATCH",
                finding_verified=not verification,
                source_snapshot_json={
                    "knowledge_snapshot_sha256": knowledge.sha256,
                    "context": context.model_dump(mode="json"),
                    "hop_dong_id": "CONTRACT_A",
                    "reviewed_knowledge": not verification,
                    "official_evidence_verified": not verification,
                    "legal_basis_ids": ["ART_129"],
                    "evidence_ids": ["EV_CIT_A"],
                },
                lan_chay_id=context.run_id,
                knowledge_version=context.legal_knowledge_version,
            )
        ]
    else:
        ev = []
        if quote_text:
            ev = [
                Evidence(
                    doan_id="DOAN_44",
                    trich_dan=quote_text,
                    ky_tu_bat_dau=10,
                    ky_tu_ket_thuc=10 + len(quote_text),
                )
            ]
        criteria = [
            CriterionResult(
                ket_qua_id="CRIT_FIND_A",
                ca_id=context.ca_id,
                yeu_cau_ca_id=requirement.yeu_cau_ca_id,
                tieu_chi_id="CRITERION_A",
                finding=finding,
                giai_thich="Synthetic finding",
                uncertainty_reason="Chưa xác định được năm ban hành hoặc số hiệu"
                if verification
                else None,
                gates={
                    "coverage_complete": True,
                    "absence_verified": True,
                    "evidence_validated": True,
                    "source_verified": True,
                    "scope_confirmed": True,
                    "version_resolved": True,
                    "evidence_conflict": False,
                    "exceptions_resolved": True,
                },
                evidence=ev,
                legal_basis_ids=["ART_129"],
                tieu_chi_snapshot_json={
                    **knowledge.criteria["CRITERION_A"],
                    "knowledge_snapshot_sha256": knowledge.sha256,
                    "context": context.model_dump(mode="json"),
                    "hop_dong_id": "CONTRACT_A",
                },
                mandatory=True,
                model_version="STRUCTURED_ADAPTER_NO_LLM",
                prompt_version="NOT_USED",
                lan_chay_id=context.run_id,
            )
        ]

    risk_req = RiskRequest(
        **context.model_dump(include=set(Context.model_fields)),
        payload={
            "hop_dong_id": "CONTRACT_A",
            "requirements": [requirement],
            "criterion_results": criteria,
            "citations": citations,
        },
    )
    risks = evaluate_risks(risk_req, knowledge)
    return risks, criteria, citations


def build_fake_transport(
    *,
    chat_handler,
    model_name="qwen3.5:9b-q4_K_M",
    digest=DIGEST_64,
    tags_override=None,
):
    recorded_bodies: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/tags":
            if tags_override is not None:
                return tags_override()
            return httpx.Response(200, json={"models": [{"name": model_name, "digest": digest}]})
        if request.url.path == "/api/chat":
            body = json.loads(request.content.decode("utf-8"))
            recorded_bodies.append(body)
            return chat_handler(body)
        return httpx.Response(404)

    return httpx.MockTransport(handler), recorded_bodies


def make_service(
    chat_handler, *, sink=None, budget=None, tags_override=None, model="qwen3.5:9b-q4_K_M"
):
    transport, bodies = build_fake_transport(
        chat_handler=chat_handler, model_name=model, tags_override=tags_override
    )
    audit = sink or FakeAuditSink()
    client = OllamaRecommendationClient(
        C11OllamaOptions(model=model),
        audit,
        transport=transport,
    )
    svc = RecommendationPersonalizationService(
        client,
        budget or C11PersonalizationOptions(mode="ollama"),
    )
    return svc, audit, bodies


# ---------------------------------------------------------------------------
# 11.1 Deterministic Baseline & Isolation Tests
# ---------------------------------------------------------------------------


def test_deterministic_baseline_without_personalizer_unchanged():
    case = make_case()
    context, knowledge, requirement = case
    risks, _, _ = make_risks(case, finding="VIOLATED", quote_text="Thời hạn bảo hành 36 tháng.")
    req = RecommendationRequest(
        **context.model_dump(include=set(Context.model_fields)),
        payload={"hop_dong_id": "CONTRACT_A", "requirements": [requirement], "risks": risks},
    )
    diag: list[dict] = []
    recs = generate_recommendations(req, knowledge, diagnostics=diag, personalizer=None)
    assert len(recs) == 1
    assert recs[0].model_version == "TEMPLATE_ENGINE_NO_LLM"
    assert recs[0].prompt_version == "NOT_USED"
    assert recs[0].review_status == "PENDING"
    assert not diag
    assert "personalization" not in recs[0].template_snapshot_json


def test_c11_off_mode_in_service_records_disabled_and_never_calls_ollama():
    case = make_case()
    context, knowledge, requirement = case
    risks, _, _ = make_risks(case, finding="VIOLATED")
    req = RecommendationRequest(
        **context.model_dump(include=set(Context.model_fields)),
        payload={"hop_dong_id": "CONTRACT_A", "requirements": [requirement], "risks": risks},
    )
    calls = 0

    def fail_if_called(body):
        nonlocal calls
        calls += 1
        return httpx.Response(500)

    svc, audit, _ = make_service(fail_if_called, budget=C11PersonalizationOptions(mode="off"))
    diag: list[dict] = []
    recs = generate_recommendations(req, knowledge, diagnostics=diag, personalizer=svc)
    assert calls == 0
    assert not audit.events
    assert recs[0].model_version == "TEMPLATE_ENGINE_NO_LLM"
    assert recs[0].prompt_version == "NOT_USED"
    assert any(d["code"] == "C11_PERSONALIZATION_DISABLED" for d in diag)


def test_dependency_isolation_between_c11_c02_and_c07():
    settings = Settings(
        database_url="postgresql://user:pass@127.0.0.1:5432/db",
        c11_personalization="ollama",
        documents_extractor="rules",
        assessment_llm="offline",
    )
    assert recommendation_personalizer(settings) is not None
    off_settings = Settings(
        database_url="postgresql://user:pass@127.0.0.1:5432/db",
        c11_personalization="off",
    )
    assert recommendation_personalizer(off_settings) is None
    assert settings.documents_extractor == "rules"
    assert settings.assessment_llm == "offline"


# ---------------------------------------------------------------------------
# 11.2 Happy Path across VIOLATED, MISSING, UNKNOWN/VERIFICATION, CITATION
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "scenario",
    [
        ("VIOLATED", False, "Thời hạn bảo hành 36 tháng."),
        ("MISSING", False, None),
        ("UNKNOWN", False, None),
        ("INVALID", True, None),
    ],
)
def test_happy_path_personalization_and_x02_audit(scenario):
    finding, citation, quote = scenario
    case = make_case()
    context, knowledge, requirement = case
    risks, _, _ = make_risks(case, finding=finding, citation=citation, quote_text=quote)
    req = RecommendationRequest(
        **context.model_dump(include=set(Context.model_fields)),
        payload={"hop_dong_id": "CONTRACT_A", "requirements": [requirement], "risks": risks},
    )
    base_recs = generate_recommendations(req, knowledge)
    base_text = base_recs[0].noi_dung

    def chat_ok(body):
        payload = json.loads(body["messages"][1]["content"])
        orig = payload["original_text"]
        rewritten = "Hướng dẫn thực hiện rõ ràng:\n" + orig
        return httpx.Response(
            200,
            json={
                "model": "qwen3.5:9b-q4_K_M",
                "done": True,
                "done_reason": "stop",
                "prompt_eval_count": 120,
                "eval_count": 64,
                "message": {
                    "content": json.dumps({"personalized_text": rewritten}, ensure_ascii=False)
                },
            },
        )

    svc, audit, bodies = make_service(chat_ok)
    diag: list[dict] = []
    final_recs = generate_recommendations(req, knowledge, diagnostics=diag, personalizer=svc)
    assert len(final_recs) == 1
    rec = final_recs[0]
    base = base_recs[0]

    assert rec.noi_dung.startswith("Hướng dẫn thực hiện rõ ràng:")
    assert rec.loai_hanh_dong == base.loai_hanh_dong
    assert rec.uu_tien == base.uu_tien
    assert rec.ket_qua_rui_ro_id == base.ket_qua_rui_ro_id
    assert rec.evidence_ids == base.evidence_ids
    assert rec.legal_basis_ids == base.legal_basis_ids
    assert rec.rule_version == base.rule_version
    assert rec.knowledge_snapshot_sha256 == base.knowledge_snapshot_sha256
    assert rec.review_status == "PENDING"
    assert rec.model_version == f"qwen3.5:9b-q4_K_M@{DIGEST_64}"
    assert rec.prompt_version == PROMPT_VERSION
    assert rec.template_snapshot_json["personalization"]["status"] == "APPLIED"
    assert rec.template_snapshot_json["personalization"]["deterministic_text"] == base_text

    # Request format verification
    req_body = bodies[0]
    assert req_body["stream"] is False
    assert req_body["think"] is False
    assert req_body["format"]["additionalProperties"] is False
    assert req_body["options"] == {
        "temperature": 0,
        "seed": 42,
        "num_ctx": 4096,
        "num_predict": 512,
        "num_thread": 4,
    }

    # X02 Audit check
    assert len(audit.events) == 1
    ev = audit.events[0]
    assert ev.module == "C11"
    assert ev.provider == "OLLAMA_LOCAL"
    assert ev.model_version == f"qwen3.5:9b-q4_K_M@{DIGEST_64}"
    assert ev.prompt_version == PROMPT_VERSION
    assert ev.schema_version == SCHEMA_VERSION
    assert ev.trang_thai == "SUCCESS"
    assert ev.input_tokens == 120
    assert ev.output_tokens == 64

    codes = [d["code"] for d in diag]
    assert "C11_PERSONALIZATION_CALLED" in codes
    assert "C11_PERSONALIZATION_APPLIED" in codes


# ---------------------------------------------------------------------------
# 11.3 Hallucination Rejection Tests (All 12 Required + Section 6.4 Case)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "bad_text_fn", "finding"),
    [
        (
            "added_money",
            lambda orig: orig + "\nMức thanh toán bổ sung là 500.000.000 đồng.",
            "VIOLATED",
        ),
        (
            "added_percentage",
            lambda orig: orig + "\nGiảm tỷ lệ thanh toán xuống 25%.",
            "VIOLATED",
        ),
        (
            "added_date",
            lambda orig: orig + "\nPhải hoàn thành trước ngày 15/08/2025.",
            "VIOLATED",
        ),
        (
            "added_legal_code",
            lambda orig: orig + "\nÁp dụng thêm Luật 27/2023/QH15.",
            "VIOLATED",
        ),
        (
            "added_company_name",
            lambda orig: orig + "\nLiên hệ Công ty TNHH ABC Land để ký phụ lục.",
            "VIOLATED",
        ),
        (
            "added_bank_account",
            lambda orig: orig + "\nChuyển vào tài khoản số 190088899900.",
            "VIOLATED",
        ),
        (
            "dropped_checklist_step",
            lambda orig: "Chỉ cần xem xét sơ bộ quy định 60 tháng và VB_27_2023.",
            "VIOLATED",
        ),
        (
            "modified_quote",
            lambda orig: orig.replace("Thời hạn bảo hành 36 tháng.", "Thời hạn bảo hành 24 tháng."),
            "VIOLATED",
        ),
        (
            "escalated_priority",
            lambda orig: orig + "\nĐánh giá mức độ ưu tiên CRITICAL cần xử lý khẩn cấp.",
            "VIOLATED",
        ),
        (
            "unknown_escalated_to_violation_and_new_law",
            lambda _orig: (
                "Hợp đồng đang viện dẫn văn bản pháp luật cũ. "
                "Cần thay thế bằng Luật Nhà ở năm 2023."
            ),
            "UNKNOWN",
        ),
        (
            "contract_void_claim",
            lambda orig: orig + "\nĐiều khoản này làm hợp đồng vô hiệu toàn bộ.",
            "VIOLATED",
        ),
        (
            "invented_penalty_fine",
            lambda orig: orig + "\nChủ đầu tư sẽ bị phạt hành chính với mức phạt nặng.",
            "VIOLATED",
        ),
    ],
)
def test_hallucination_rejected_and_falls_back_to_deterministic(name, bad_text_fn, finding):
    case = make_case()
    context, knowledge, requirement = case
    risks, _, _ = make_risks(
        case,
        finding=finding,
        quote_text="Thời hạn bảo hành 36 tháng." if finding == "VIOLATED" else None,
    )
    req = RecommendationRequest(
        **context.model_dump(include=set(Context.model_fields)),
        payload={"hop_dong_id": "CONTRACT_A", "requirements": [requirement], "risks": risks},
    )
    expected_base = generate_recommendations(req, knowledge)[0].noi_dung

    def chat_bad(body):
        payload = json.loads(body["messages"][1]["content"])
        bad_text = bad_text_fn(payload["original_text"])
        return httpx.Response(
            200,
            json={
                "model": "qwen3.5:9b-q4_K_M",
                "done": True,
                "done_reason": "stop",
                "message": {
                    "content": json.dumps({"personalized_text": bad_text}, ensure_ascii=False)
                },
            },
        )

    svc, audit, _ = make_service(chat_bad)
    diag: list[dict] = []
    recs = generate_recommendations(req, knowledge, diagnostics=diag, personalizer=svc)
    assert len(recs) == 1
    rec = recs[0]
    assert rec.noi_dung == expected_base, f"Case {name} should have rejected and kept original text"
    assert rec.model_version == "TEMPLATE_ENGINE_FALLBACK"
    assert rec.prompt_version == PROMPT_VERSION
    assert rec.template_snapshot_json["personalization"]["status"] == "FALLBACK"
    assert len(audit.events) == 1
    assert audit.events[0].trang_thai == "SUCCESS"  # HTTP succeeded, validator rejected!
    codes = {d["code"] for d in diag}
    assert "C11_PERSONALIZATION_REJECTED" in codes
    assert "C11_PERSONALIZATION_FALLBACK" in codes


# ---------------------------------------------------------------------------
# 11.4 Failure & Budget Exhaustion Tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("mode", "expected_code"),
    [
        ("connect_error", "C11_MODEL_UNAVAILABLE"),
        ("not_installed", "C11_MODEL_NOT_INSTALLED"),
        ("remote_model", "C11_MODEL_NOT_INSTALLED"),
        ("bad_digest", "C11_MODEL_NOT_INSTALLED"),
        ("timeout", "C11_MODEL_TIMEOUT"),
        ("invalid_json", "C11_INVALID_STRUCTURED_OUTPUT"),
        ("extra_field", "C11_INVALID_STRUCTURED_OUTPUT"),
        ("empty_text", "C11_INVALID_STRUCTURED_OUTPUT"),
        ("code_fence", "C11_INVALID_STRUCTURED_OUTPUT"),
        ("too_long", "C11_INVALID_STRUCTURED_OUTPUT"),
        ("model_mismatch", "C11_INVALID_STRUCTURED_OUTPUT"),
        ("audit_failure", "C11_AUDIT_PERSISTENCE_FAILED"),
    ],
)
def test_failures_fall_back_gracefully_with_diagnostics(mode, expected_code):
    case = make_case()
    context, knowledge, requirement = case
    risks, _, _ = make_risks(case, finding="VIOLATED")
    req = RecommendationRequest(
        **context.model_dump(include=set(Context.model_fields)),
        payload={"hop_dong_id": "CONTRACT_A", "requirements": [requirement], "risks": risks},
    )
    base_text = generate_recommendations(req, knowledge)[0].noi_dung

    tags_override = None
    if mode == "not_installed":

        def tags_override():
            return httpx.Response(200, json={"models": []})
    elif mode == "remote_model":

        def tags_override():
            return httpx.Response(
                200,
                json={
                    "models": [
                        {
                            "name": "qwen3.5:9b-q4_K_M",
                            "digest": DIGEST_64,
                            "remote_host": "https://evil.example",
                        }
                    ]
                },
            )
    elif mode == "bad_digest":

        def tags_override():
            return httpx.Response(
                200, json={"models": [{"name": "qwen3.5:9b-q4_K_M", "digest": "short"}]}
            )

    def chat_handler(body):
        if mode == "connect_error":
            raise httpx.ConnectError("Connection refused")
        if mode == "timeout":
            raise httpx.ReadTimeout("Timed out")
        if mode == "invalid_json":
            return httpx.Response(
                200,
                json={
                    "model": "qwen3.5:9b-q4_K_M",
                    "done": True,
                    "done_reason": "stop",
                    "message": {"content": "{broken json"},
                },
            )
        if mode == "extra_field":
            return httpx.Response(
                200,
                json={
                    "model": "qwen3.5:9b-q4_K_M",
                    "done": True,
                    "done_reason": "stop",
                    "message": {"content": json.dumps({"personalized_text": "OK", "extra": 123})},
                },
            )
        if mode == "empty_text":
            return httpx.Response(
                200,
                json={
                    "model": "qwen3.5:9b-q4_K_M",
                    "done": True,
                    "done_reason": "stop",
                    "message": {"content": json.dumps({"personalized_text": "   "})},
                },
            )
        if mode == "code_fence":
            return httpx.Response(
                200,
                json={
                    "model": "qwen3.5:9b-q4_K_M",
                    "done": True,
                    "done_reason": "stop",
                    "message": {"content": '```json\n{"personalized_text": "ok"}\n```'},
                },
            )
        if mode == "too_long":
            payload = json.loads(body["messages"][1]["content"])
            return httpx.Response(
                200,
                json={
                    "model": "qwen3.5:9b-q4_K_M",
                    "done": True,
                    "done_reason": "stop",
                    "message": {
                        "content": json.dumps(
                            {"personalized_text": payload["original_text"] + (" x" * 2500)}
                        )
                    },
                },
            )
        if mode == "model_mismatch":
            return httpx.Response(
                200,
                json={
                    "model": "other-model",
                    "done": True,
                    "done_reason": "stop",
                    "message": {"content": json.dumps({"personalized_text": "anything"})},
                },
            )
        # audit_failure happy response whose audit fails
        payload = json.loads(body["messages"][1]["content"])
        return httpx.Response(
            200,
            json={
                "model": "qwen3.5:9b-q4_K_M",
                "done": True,
                "done_reason": "stop",
                "message": {"content": json.dumps({"personalized_text": payload["original_text"]})},
            },
        )

    sink = FakeAuditSink(fail_append=(mode == "audit_failure"))
    svc, _, _ = make_service(
        chat_handler,
        sink=sink,
        tags_override=tags_override,
        budget=C11PersonalizationOptions(mode="ollama", max_output_chars=4000),
    )
    diag: list[dict] = []
    recs = generate_recommendations(req, knowledge, diagnostics=diag, personalizer=svc)
    assert len(recs) == 1
    assert recs[0].noi_dung == base_text
    assert recs[0].model_version == "TEMPLATE_ENGINE_FALLBACK"
    assert recs[0].prompt_version == PROMPT_VERSION
    codes = {d["code"] for d in diag}
    assert expected_code in codes
    assert "C11_PERSONALIZATION_FALLBACK" in codes


def test_budget_exhausted_skips_second_call_and_falls_back():
    case = make_case()
    context, knowledge, requirement = case
    risks, _, _ = make_risks(case, finding="VIOLATED")
    # Add a second mapped template so 2 recommendations are generated deterministically
    t2 = deepcopy(knowledge.recommendations["TEMPLATE_A"])
    t2["khuyen_nghi_id"] = "TEMPLATE_B"
    knowledge.recommendations["TEMPLATE_B"] = t2
    knowledge.tables["rui_ro_khuyen_nghi"].append(
        {"lien_ket_id": "MAPPING_B", "rui_ro_id": "RISK_A", "khuyen_nghi_id": "TEMPLATE_B"}
    )

    req = RecommendationRequest(
        **context.model_dump(include=set(Context.model_fields)),
        payload={"hop_dong_id": "CONTRACT_A", "requirements": [requirement], "risks": risks},
    )

    def chat_ok(body):
        payload = json.loads(body["messages"][1]["content"])
        return httpx.Response(
            200,
            json={
                "model": "qwen3.5:9b-q4_K_M",
                "done": True,
                "done_reason": "stop",
                "message": {
                    "content": json.dumps(
                        {"personalized_text": "Cá thể hóa:\n" + payload["original_text"]},
                        ensure_ascii=False,
                    )
                },
            },
        )

    svc, audit, bodies = make_service(
        chat_ok, budget=C11PersonalizationOptions(mode="ollama", max_calls=1)
    )
    diag: list[dict] = []
    recs = generate_recommendations(req, knowledge, diagnostics=diag, personalizer=svc)
    assert len(recs) == 2
    assert len(bodies) == 1
    assert len(audit.events) == 1
    assert recs[0].model_version == f"qwen3.5:9b-q4_K_M@{DIGEST_64}"
    assert recs[1].model_version == "TEMPLATE_ENGINE_FALLBACK"
    assert recs[1].template_snapshot_json["personalization"]["status"] == "SKIPPED_BUDGET"
    assert any(d["code"] == "C11_PERSONALIZATION_BUDGET_EXHAUSTED" for d in diag)


# ---------------------------------------------------------------------------
# 11.5 End-to-End Steps 5-7, Report Presentation, Export & Integrity
# ---------------------------------------------------------------------------


def test_steps_5_7_report_presentation_export_and_integrity_with_qwen():
    case_data = make_case()
    context, knowledge, requirement = case_data
    risks, criteria, citations = make_risks(
        case_data, finding="VIOLATED", quote_text="Thời hạn bảo hành 36 tháng."
    )
    case_obj = AssessmentCase(
        ca_id=context.ca_id,
        hop_dong_id="CONTRACT_A",
        assessment_context=AssessmentTiming(ngay_danh_gia="2024-09-15"),
        tenant_id="TENANT_A",
        created_by="USER_A",
        source=SourceDocument(
            tep_id="TEP_A",
            object_uri="upload://UP_A",
            mime_type="application/pdf",
            sha256="d" * 64,
        ),
        deployment=DeploymentPin(
            phien_ban_id=context.phien_ban_id,
            rule_version=context.rule_version,
            legal_knowledge_version=context.legal_knowledge_version,
        ),
    )
    from legal_checker.shared.contracts.reasoning import Observation

    chunk = Chunk(
        doan_id="DOAN_44",
        hop_dong_id="CONTRACT_A",
        noi_dung="Điều 7.   Thời hạn bảo hành 36 tháng.",
        page_start=44,
        page_end=44,
    )
    retrieval_row = RetrievalEvidence(
        truy_xuat_id="RET_44",
        yeu_cau_ca_id=requirement.yeu_cau_ca_id,
        tieu_chi_id="CRITERION_A",
        doan_id="DOAN_44",
        thu_hang=1,
        duoc_chon=True,
        query_text="Thời hạn bảo hành",
        retrieval_version="BM25_V2",
        index_version="IDX_1",
        lan_chay_id=context.run_id,
    )
    pipeline_req = PipelineRequest(
        **context.model_dump(include=set(Context.model_fields)),
        payload=PipelinePayload(
            hop_dong_id="CONTRACT_A",
            requirements=[requirement],
            chunks=[chunk],
            retrieval=[retrieval_row],
            observations=[
                Observation(
                    tieu_chi_id="CRITERION_A",
                    proposed_finding="VIOLATED",
                    giai_thich="Bảo hành 36 tháng < 60 tháng.",
                    local_applicability="MATCH",
                    mandatory_confirmed=True,
                    gates={
                        "coverage_complete": True,
                        "absence_verified": True,
                        "evidence_validated": True,
                        "source_verified": True,
                        "scope_confirmed": True,
                        "version_resolved": True,
                        "evidence_conflict": False,
                        "exceptions_resolved": True,
                    },
                    evidence=criteria[0].evidence,
                    facts_verified=True,
                )
            ],
            citations=citations,
            citation_branch_status="COMPLETED",
        ),
    )

    def chat_ok(body):
        payload = json.loads(body["messages"][1]["content"])
        return httpx.Response(
            200,
            json={
                "model": "qwen3.5:9b-q4_K_M",
                "done": True,
                "done_reason": "stop",
                "message": {
                    "content": json.dumps(
                        {"personalized_text": "Khuyến nghị dễ hiểu:\n" + payload["original_text"]},
                        ensure_ascii=False,
                    )
                },
            },
        )

    svc, _, _ = make_service(chat_ok)
    resp = evaluate_steps_5_7(pipeline_req, knowledge, recommendation_personalizer=svc)
    validate_membership(pipeline_req, resp)

    assert len(resp.payload.recommendations) == 1
    rec = resp.payload.recommendations[0]
    assert rec.noi_dung.startswith("Khuyến nghị dễ hiểu:")
    assert rec.review_status == "PENDING"

    # Build C13 draft report, presentation & JSON export
    profile = ContractProfile(
        hop_dong_id="CONTRACT_A",
        profile=ProfileFields(),
    )
    doc = DocumentIntelligenceResult(
        contract_profile=profile,
        chunks=[chunk],
        citations=[
            CitationExtraction(
                vien_dan_id="CITATION_A",
                hop_dong_id="CONTRACT_A",
                raw_text="Luật Nhà ở",
                normalized=CitationNormalization(loai_van_ban="LUAT"),
                extraction=CitationExtractionMetadata(status="EXTRACTED"),
                evidence=[CitationPosition(doan_id="DOAN_44", page_start=1, page_end=1)],
            )
        ],
    )
    scope = ScopeResolution(
        yeu_cau_ca_id=requirement.yeu_cau_ca_id,
        ca_id=context.ca_id,
        requirement_id=requirement.requirement_id,
        scope_status="MATCH",
        nhom_phien_ban=requirement.nhom_phien_ban,
        scope_reason="match",
    )
    draft_report = build_draft_report(
        IntegrationInput(
            case=case_obj,
            context=context,
            document=doc,
            legal=LegalOutput(scope=[scope], requirements=[requirement], citations=citations),
            compliance=ComplianceOutput(
                context=context,
                hop_dong_id="CONTRACT_A",
                criterion_results=resp.payload.criterion_results,
                requirement_results=resp.payload.requirement_results,
                risks=resp.payload.risks,
                recommendations=resp.payload.recommendations,
                diagnostics=resp.payload.diagnostics,
            ),
        ),
        knowledge,
        risks=resp.payload.risks,
        recommendations=resp.payload.recommendations,
    )
    presentation = build_presentation(draft_report.report_json)
    assert presentation.recommendations[rec.khuyen_nghi_ca_id].text.startswith(
        "Khuyến nghị dễ hiểu:"
    )
    exported = export_report(draft_report, "json")
    assert "Khuyến nghị dễ hiểu:".encode() in exported
    doc_blocks = report_document(draft_report)
    assert any("Khuyến nghị dễ hiểu:" in str(block) for block in doc_blocks.blocks)


def test_reference_replay_source_and_integrated_default_never_call_qwen():
    ref = ReferenceReplaySource("postgresql://unused")
    assert not hasattr(ref, "recommendation_personalizer")
    source = IntegratedModulesSource("postgresql://unused", None)
    assert source.recommendation_personalizer is None


def test_budget_is_isolated_per_run_id():
    case_1 = make_case()
    ctx1, knowledge1, req1 = case_1
    risks1, _, _ = make_risks(case_1, finding="VIOLATED")
    r_req1 = RecommendationRequest(
        **ctx1.model_dump(include=set(Context.model_fields)),
        payload={"hop_dong_id": "CONTRACT_A", "requirements": [req1], "risks": risks1},
    )
    ctx2 = ctx1.model_copy(update={"run_id": "RUN_C11_SECOND"})
    req2 = req1.model_copy(update={"ca_id": ctx2.ca_id})
    risks2, _, _ = make_risks((ctx2, knowledge1, req2), finding="VIOLATED")
    r_req2 = RecommendationRequest(
        **ctx2.model_dump(include=set(Context.model_fields)),
        payload={"hop_dong_id": "CONTRACT_A", "requirements": [req2], "risks": risks2},
    )

    def chat_ok(body):
        payload = json.loads(body["messages"][1]["content"])
        return httpx.Response(
            200,
            json={
                "model": "qwen3.5:9b-q4_K_M",
                "done": True,
                "done_reason": "stop",
                "message": {
                    "content": json.dumps(
                        {
                            "personalized_text": (
                                "Mỗi run có ngân sách riêng:\n" + payload["original_text"]
                            )
                        },
                        ensure_ascii=False,
                    )
                },
            },
        )

    svc, audit, _ = make_service(
        chat_ok, budget=C11PersonalizationOptions(mode="ollama", max_calls=1)
    )
    out1 = generate_recommendations(r_req1, knowledge1, personalizer=svc)
    assert out1[0].model_version == f"qwen3.5:9b-q4_K_M@{DIGEST_64}"
    out2 = generate_recommendations(r_req2, knowledge1, personalizer=svc)
    assert out2[0].model_version == f"qwen3.5:9b-q4_K_M@{DIGEST_64}"
    assert len(audit.events) == 2


def test_entity_anchor_ignores_ordinary_words_ending_in_a_role_word():
    """ "không đầy đủ" contains "ông đầy đủ" but names no person."""
    from legal_checker.modules.recommendations.personalization.validator import _extract_anchors

    assert not _extract_anchors("Nội dung quét chữ không đầy đủ, không rõ ràng.").entities
    named = _extract_anchors("Công ty TNHH Hoa Sen và ông Nguyễn Văn A, tài khoản số 0123456789")
    assert named.entities == {
        "công ty tnhh hoa sen",
        "ông nguyễn văn a",
        "tài khoản số 0123456789",
    }


def test_post_remedy_footer_statute_code_can_be_paraphrased_without_anchor_mismatch():
    case = make_case()
    context, knowledge, requirement = case
    risks, _, _ = make_risks(case, finding="VIOLATED", quote_text="Thời hạn bảo hành 36 tháng.")
    knowledge.recommendations["TEMPLATE_A"]["kiem_tra_sau_khac_phuc"] = (
        "Đối chiếu lại tại mốc {relevant_date} (59/2010/QH12; Điều 16)."
    )
    req = RecommendationRequest(
        **context.model_dump(include=set(Context.model_fields)),
        payload={"hop_dong_id": "CONTRACT_A", "requirements": [requirement], "risks": risks},
    )

    def chat_paraphrase_footer(body):
        payload = json.loads(body["messages"][1]["content"])
        rewritten = payload["original_text"].replace("(59/2010/QH12; Điều 16)", "(Điều 16)")
        return httpx.Response(
            200,
            json={
                "model": "qwen3.5:9b-q4_K_M",
                "done": True,
                "done_reason": "stop",
                "message": {
                    "content": json.dumps({"personalized_text": rewritten}, ensure_ascii=False)
                },
            },
        )

    svc, _, _ = make_service(chat_paraphrase_footer)
    recs = generate_recommendations(req, knowledge, personalizer=svc)
    assert recs[0].template_snapshot_json["personalization"]["status"] == "APPLIED"
