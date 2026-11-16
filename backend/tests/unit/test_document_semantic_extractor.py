"""Hybrid extraction keeps exact provenance and never self-approves model proposals."""

import hashlib
import json
from dataclasses import replace

import httpx
import pytest
from legal_checker.api.dependencies import document_semantic_extractor
from legal_checker.core.config import Settings
from legal_checker.modules.documents.chunker import chunk_document
from legal_checker.modules.documents.ollama_client import (
    DocumentModelError,
    OllamaDocumentClient,
    OllamaOptions,
)
from legal_checker.modules.documents.parser import DocumentPage, DocumentText
from legal_checker.modules.documents.profile_extractor import extract_profile
from legal_checker.modules.documents.semantic_extractor import (
    FactProposal,
    FactProposals,
    SemanticDocumentExtractor,
    SemanticOptions,
    normalize,
)
from legal_checker.modules.documents.service import PdfDocumentIntelligence
from legal_checker.shared.contracts.common import Context
from test_document_service import PDF, FakeStorage, _case

DIGEST = "b" * 64
CONTEXT = Context(
    ca_id="CA_TEST",
    phien_ban_id="P",
    rule_version="R",
    legal_knowledge_version="L",
    knowledge_snapshot_sha256="a" * 64,
    run_id="RUN_TEST",
    trace_id="TRACE_TEST",
)


class Sink:
    def __init__(self):
        self.events = []

    def append(self, event):
        self.events.append(event)


class Model:
    options = OllamaOptions()

    def __init__(self, values=("60",)):
        self.calls = 0
        self.values = values

    def digest(self):
        return DIGEST

    def complete(self, context, payload, schema, instructions):
        self.calls += 1
        return {
            "model": self.options.model,
            "done": True,
            "done_reason": "stop",
            "message": {
                "content": json.dumps(
                    {
                        "facts": [
                            {
                                "field": "warranty_months",
                                "value": v,
                                "quote": payload["text"],
                                "source_id": payload["source_id"],
                            }
                            for v in self.values
                        ]
                    },
                    ensure_ascii=False,
                )
            },
        }


def source(text="Trong 60 tháng, bên bán phải bảo hành căn hộ theo thỏa thuận."):
    doc = DocumentText("a" * 64, (DocumentPage(1, text, "TEXT", True),))
    chunks = chunk_document(doc, hop_dong_id="HD_TEST", version="base")
    profile = extract_profile(chunks, hop_dong_id="HD_TEST", version="base")
    return chunks, profile


def run(extractor, chunks, profile):
    return extractor.extract(chunks, profile, CONTEXT, source_sha256="a" * 64)


def test_semantic_fact_missed_by_rules_is_grounded_pending_and_cached(tmp_path):
    chunks, profile = source()
    assert not any(f.ten_truong == "warranty_months" for f in profile.facts)
    model = Model()
    extractor = SemanticDocumentExtractor(
        model, tmp_path, SemanticOptions(fields=("warranty_months",))
    )
    result = run(extractor, chunks, profile)
    merged = extractor.merge(profile, chunks, result, "new")
    fact = next(f for f in merged.facts if f.ten_truong == "warranty_months")
    assert fact.gia_tri_chuan_json == "60"
    assert fact.trang_thai == "DERIVED_REVIEW_PENDING" and not fact.human_verified
    evidence = next(e for e in merged.evidence if e.bang_chung_id in fact.evidence_ids)
    assert (
        chunks[0].noi_dung[evidence.ky_tu_bat_dau : evidence.ky_tu_ket_thuc] == evidence.trich_dan
    )
    assert not profile.facts  # merge did not mutate the producer output
    again = run(extractor, chunks, profile)
    assert model.calls == 1 and result.fingerprint == again.fingerprint
    assert any(d["code"] == "DOCUMENT_LLM_CACHE_HIT" for d in again.diagnostics)


@pytest.mark.parametrize(
    "change",
    [
        {"value": "120"},
        {"quote": "Bảo hành 60 tháng"},
        {"source_id": "FOREIGN"},
        {"field": "ten_ben_mua"},
    ],
)
def test_forged_field_quote_source_or_value_does_not_create_a_fact(tmp_path, change):
    class Bad(Model):
        def complete(self, *args):
            response = super().complete(*args)
            obj = json.loads(response["message"]["content"])
            obj["facts"][0].update(change)
            response["message"]["content"] = json.dumps(obj)
            return response

    chunks, profile = source()
    extractor = SemanticDocumentExtractor(
        Bad(), tmp_path, SemanticOptions(fields=("warranty_months",))
    )
    result = run(extractor, chunks, profile)
    assert not result.proposals and result.diagnostics


def test_two_semantic_values_preserve_conflict_without_inventing_a_winner(tmp_path):
    chunks, profile = source("Trong 60 tháng hoặc 36 tháng, bên bán phải bảo hành căn hộ.")
    extractor = SemanticDocumentExtractor(Model(("60", "36")), tmp_path)
    result = run(extractor, chunks, profile)
    merged = extractor.merge(profile, chunks, result, "v")
    fact = next(f for f in merged.facts if f.ten_truong == "warranty_months")
    assert fact.trang_thai == "CONFLICT"
    assert set(fact.gia_tri_chuan_json) == {"36", "60"}


def test_rule_fact_and_conflict_are_not_overwritten_or_auto_resolved(tmp_path):
    chunks, profile = source(
        "Thời hạn bảo hành nhà ở: 60 tháng.\nThời hạn bảo hành nhà ở: 36 tháng."
    )
    before = profile.model_dump()
    extractor = SemanticDocumentExtractor(Model(), tmp_path, SemanticOptions(recheck_existing=True))
    result = run(extractor, chunks, profile)
    merged = extractor.merge(profile, chunks, result, "v")
    assert merged.model_dump() == before
    assert any(d["code"] == "DOCUMENT_LLM_RULE_VALUE_PRESERVED" for d in result.diagnostics)


def test_existing_fields_are_skipped_by_default(tmp_path):
    chunks, profile = source("Thời hạn bảo hành nhà ở: 60 tháng.")
    model = Model()
    extractor = SemanticDocumentExtractor(
        model, tmp_path, SemanticOptions(fields=("warranty_months",))
    )
    assert not run(extractor, chunks, profile).proposals
    assert model.calls == 0


@pytest.mark.parametrize(
    "value,quote",
    [
        ("60", "Trong 160 tháng, bên bán bảo hành căn hộ."),
        ("5", "Bên bán bảo hành căn hộ trong 5 năm."),
        ("60", "Bảo hành: thanh toán trong 60 ngày."),
        ("60", "Bên bán bảo hành căn hộ; 60% giá trị phải thanh toán."),
    ],
)
def test_wrong_units_or_partial_number_are_rejected(value, quote):
    with pytest.raises(ValueError):
        normalize(FactProposal(field="warranty_months", value=value, quote=quote, source_id="D"))


def test_model_unavailable_preserves_rules_and_records_a_diagnostic(tmp_path):
    class Offline(Model):
        def digest(self):
            raise DocumentModelError("DOCUMENT_LLM_UNAVAILABLE")

    chunks, profile = source()
    result = run(SemanticDocumentExtractor(Offline(), tmp_path), chunks, profile)
    assert not result.proposals and result.fingerprint
    assert result.diagnostics == [{"code": "DOCUMENT_LLM_UNAVAILABLE"}]


def test_call_limit_is_explicit_not_proof_of_missing_content(tmp_path):
    text = "Trong 60 tháng, bên bán bảo hành căn hộ.\n" * 15
    chunks, profile = source("ĐIỀU 1. A\n" + text + "ĐIỀU 2. B\n" + text)
    model = Model()
    extractor = SemanticDocumentExtractor(model, tmp_path, SemanticOptions(max_calls=1))
    result = run(extractor, chunks, profile)
    assert model.calls == 1
    assert any(d["code"] == "DOCUMENT_LLM_BUDGET_LIMIT" for d in result.diagnostics)


def test_service_versions_bind_model_output_and_keep_chunk_bytes(tmp_path):
    class Empty(Model):
        def complete(self, *args):
            response = super().complete(*args)
            response["message"]["content"] = '{"facts": []}'
            return response

    case = _case(hashlib.sha256(PDF).hexdigest())
    base = PdfDocumentIntelligence(FakeStorage(PDF)).run(case)
    hybrid = PdfDocumentIntelligence(
        FakeStorage(PDF),
        semantic=SemanticDocumentExtractor(
            Empty(), tmp_path, SemanticOptions(fields=("ten_ben_ban",))
        ),
    ).run(case, context=CONTEXT)
    assert base.version != hybrid.version
    assert [c.noi_dung for c in base.chunks] == [c.noi_dung for c in hybrid.chunks]
    assert base.document.source_sha256 == hybrid.document.source_sha256
    assert hybrid.semantic_diagnostics


def test_actual_transport_uses_schema_and_records_metadata_without_prompt_in_audit():
    sink = Sink()

    def handler(request):
        if request.url.path == "/api/tags":
            return httpx.Response(
                200, json={"models": [{"name": OllamaOptions().model, "digest": DIGEST}]}
            )
        body = json.loads(request.content)
        assert body["format"] == FactProposals.model_json_schema()
        assert body["think"] is False and body["stream"] is False
        return httpx.Response(
            200,
            json={
                "model": OllamaOptions().model,
                "done": True,
                "done_reason": "stop",
                "message": {"content": '{"facts":[]}'},
                "prompt_eval_count": 20,
                "eval_count": 5,
            },
        )

    client = OllamaDocumentClient(OllamaOptions(), sink, transport=httpx.MockTransport(handler))
    client.complete(CONTEXT, {"text": "source"}, FactProposals.model_json_schema(), "instructions")
    assert len(sink.events) == 1
    event = sink.events[0]
    assert event.provider == "OLLAMA_LOCAL" and event.trang_thai == "SUCCESS"
    assert event.model_version.endswith(DIGEST) and event.trace_id == CONTEXT.trace_id
    assert "source" not in event.model_dump_json()


@pytest.mark.parametrize(
    "options",
    [
        {"base_url": "https://user:secret@example.com"},
        {"model": "model:cloud"},
        {"output_tokens": 9000},
        {"timeout_seconds": 0},
    ],
)
def test_invalid_resource_or_provider_settings_fail_early(options):
    with pytest.raises(ValueError):
        OllamaOptions(**options)


def test_composition_is_opt_in_and_independent_of_compliance_provider():
    settings = Settings(database_url="postgresql://unused")
    assert document_semantic_extractor(settings) is None
    hybrid = document_semantic_extractor(replace(settings, documents_extractor="hybrid"))
    assert hybrid.client.options.model == "qwen3.5:9b-q4_K_M"
    assert settings.assessment_llm == "offline"
    with pytest.raises(ValueError):
        document_semantic_extractor(replace(settings, documents_extractor="bad"))


@pytest.mark.parametrize("done_reason", ["length", None])
def test_truncated_transport_result_is_not_accepted(done_reason):
    sink = Sink()

    def handler(request):
        if request.url.path == "/api/tags":
            return httpx.Response(
                200, json={"models": [{"name": OllamaOptions().model, "digest": DIGEST}]}
            )
        return httpx.Response(
            200,
            json={
                "model": OllamaOptions().model,
                "done": True,
                "done_reason": done_reason,
                "message": {"content": '{"facts":[]}'},
            },
        )

    client = OllamaDocumentClient(OllamaOptions(), sink, transport=httpx.MockTransport(handler))
    with pytest.raises(DocumentModelError, match="DOCUMENT_LLM_INCOMPLETE"):
        client.complete(CONTEXT, {}, FactProposals.model_json_schema(), "instructions")
    assert sink.events[0].trang_thai == "ERROR"
    assert sink.events[0].ma_loi == "DOCUMENT_LLM_INCOMPLETE"


def test_corrupt_cache_never_supplies_a_fact(tmp_path):
    chunks, profile = source()
    extractor = SemanticDocumentExtractor(Model(), tmp_path)
    run(extractor, chunks, profile)
    path = next(tmp_path.glob("*.json"))
    envelope = json.loads(path.read_text())
    envelope["response"]["message"]["content"] = '{"facts": []}'
    path.write_text(json.dumps(envelope))
    result = run(extractor, chunks, profile)
    assert not result.proposals
    assert any(d["code"] == "DOCUMENT_LLM_INVALID_OUTPUT" for d in result.diagnostics)


def test_pending_llm_fact_is_not_an_independently_verified_numeric_fact(tmp_path):
    from types import SimpleNamespace

    from legal_checker.modules.compliance.source_verifier import SourceFactVerifier

    chunks, profile = source()
    extractor = SemanticDocumentExtractor(Model(), tmp_path)
    result = run(extractor, chunks, profile)
    merged = extractor.merge(profile, chunks, result, "v")
    requirement = SimpleNamespace(
        requirement_version_id="V",
        version_status="RESOLVED",
        confirmed=True,
        yeu_cau_ca_id="R",
        assessment_review={},
    )

    class Knowledge:
        def criteria_for(self, version):
            return [{"tieu_chi_id": "CR", "dieu_kien": {}}]

    # No requirement receipt: keep all review-scope adaptation disabled for this unit check.
    requirement.nguon_snapshot_json = {}
    verification = SourceFactVerifier().verify(
        CONTEXT, merged, [requirement], [c.to_contract() for c in chunks], Knowledge()
    )
    assert "warranty_months" not in verification[0].facts
    assert not verification[0].facts_verified


def test_numeric_window_is_prioritized_over_an_earlier_generic_mention(tmp_path):
    chunks, profile = source(
        "ĐIỀU 1. Quy định chung\nBên bán có nghĩa vụ bảo hành căn hộ, diện tích 60 m2.\n"
        "ĐIỀU 2. Chi tiết\nTrong 60 tháng, bên bán phải bảo hành căn hộ."
    )
    extractor = SemanticDocumentExtractor(
        Model(), tmp_path, SemanticOptions(max_calls=1, fields=("warranty_months",))
    )
    result = run(extractor, chunks, profile)
    assert result.proposals
    assert "60 tháng" in result.proposals[0].quote


def test_persistence_uses_only_current_semantic_chunk_ids(tmp_path):
    from pathlib import Path

    from fpdf import FPDF

    font = Path("/usr/share/fonts/liberation/LiberationSans-Regular.ttf")
    if not font.exists():
        pytest.skip("Local PDF integration fixture needs LiberationSans")
    p = tmp_path / "source.pdf"
    pdf = FPDF()
    pdf.add_font("SemanticTest", fname=str(font))
    pdf.add_page()
    pdf.set_font("SemanticTest", size=12)
    pdf.multi_cell(w=170, h=7, text="Trong 60 tháng, bên bán có trách nhiệm bảo hành căn hộ.")
    pdf.output(str(p))
    content = p.read_bytes()
    case = _case(hashlib.sha256(content).hexdigest())
    hybrid = PdfDocumentIntelligence(
        FakeStorage(content), semantic=SemanticDocumentExtractor(Model(), tmp_path / "cache")
    ).run(case, context=CONTEXT)
    active = {c.doan_id for c in hybrid.chunks}
    assert hybrid.result.contract_profile.facts
    assert all(e.doan_id in active for e in hybrid.result.contract_profile.evidence)
    assert all(d["source_id"] in active for d in hybrid.semantic_diagnostics if "source_id" in d)


@pytest.mark.parametrize(
    "value,quote,field,expected",
    [
        ("60 tháng", "Thời hạn bảo hành nhà ở: 60 tháng", "warranty_months", "60"),
        ("62,4 m²", "Diện tích sử dụng căn hộ: 62,4 m²", "dien_tich", "62.4"),
    ],
)
def test_quantity_with_copied_unit_is_normalized_without_conversion(value, quote, field, expected):
    assert normalize(FactProposal(field=field, value=value, quote=quote, source_id="D")) == expected


@pytest.mark.parametrize(
    "value,quote,field",
    [
        ("60 m2", "Bảo hành căn hộ diện tích 60 m2", "warranty_months"),
        ("60 tháng", "Diện tích 60 tháng", "dien_tich"),
    ],
)
def test_explicit_mismatched_unit_is_rejected(value, quote, field):
    with pytest.raises(ValueError):
        normalize(FactProposal(field=field, value=value, quote=quote, source_id="D"))
