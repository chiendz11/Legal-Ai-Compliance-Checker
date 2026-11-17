"""API module identity, provenance and rejection paths without real paid calls."""

import json

import httpx
import pytest
from legal_checker.modules.documents.ollama_client import DocumentModelError
from legal_checker.modules.documents.openai_client import OpenAIDocumentClient
from legal_checker.modules.documents.semantic_extractor import (
    SemanticDocumentExtractor,
    SemanticOptions,
)
from legal_checker.modules.recommendations.personalization.client import C11ModelError
from legal_checker.modules.recommendations.personalization.config import C11PersonalizationOptions
from legal_checker.modules.recommendations.personalization.openai_client import (
    OpenAIRecommendationClient,
)
from legal_checker.shared.contracts.modules import RecommendationRequest
from legal_checker.shared.llm.config import OpenAISettings
from test_document_semantic_extractor import CONTEXT, Sink, source

SETTINGS = OpenAISettings(api_key="test-key-not-a-secret", model="gpt-4.1-mini-2025-04-14")


def response(content):
    return httpx.Response(
        200,
        json={
            "id": "resp_test",
            "model": SETTINGS.model,
            "status": "completed",
            "usage": {"input_tokens": 21, "output_tokens": 12},
            "output": [
                {
                    "type": "message",
                    "content": [{"type": "output_text", "text": json.dumps(content)}],
                }
            ],
        },
    )


def test_c02_api_preserves_exact_source_pending_status_and_module_audit(tmp_path):
    chunks, profile = source()
    bodies, sink = [], Sink()

    def call(request):
        body = json.loads(request.content)
        bodies.append(body)
        payload = json.loads(body["input"][1]["content"])
        return response(
            {
                "facts": [
                    {
                        "field": "warranty_months",
                        "value": "60 tháng",
                        "quote": payload["text"],
                        "source_id": payload["source_id"],
                    }
                ]
            }
        )

    with httpx.Client(transport=httpx.MockTransport(call)) as http:
        client = OpenAIDocumentClient(SETTINGS, sink, http_client=http)
        engine = SemanticDocumentExtractor(client, tmp_path, SemanticOptions(max_calls=1))
        result = engine.extract(chunks, profile, CONTEXT, source_sha256="d" * 64)
        merged = engine.merge(profile, chunks, result, "API_VERSION")
        fact = next(f for f in merged.facts if f.ten_truong == "warranty_months")
        assert fact.gia_tri_chuan_json == "60"
        assert fact.trang_thai == "DERIVED_REVIEW_PENDING" and not fact.human_verified
        assert fact.phuong_phap.startswith("API_LLM_EXACT_QUOTE_V1@API_MODEL:OPENAI:")
        again = engine.extract(chunks, profile, CONTEXT, source_sha256="d" * 64)
        assert again.proposals == result.proposals and len(bodies) == 1
    assert sink.events[0].module == "DOCUMENT_INTELLIGENCE"
    assert sink.events[0].provider == "OPENAI"
    assert bodies[0]["store"] is False and bodies[0]["text"]["format"]["strict"] is True
    assert "test-key" not in json.dumps(client.options.__dict__)
    assert "test-key" not in "".join(p.read_text() for p in tmp_path.glob("*.json"))


def test_c11_uses_api_and_keeps_model_usage_and_audit_identity():
    sink = Sink()
    with httpx.Client(
        transport=httpx.MockTransport(lambda _: response({"personalized_text": "Kiểm tra nguồn."}))
    ) as http:
        client = OpenAIRecommendationClient(SETTINGS, sink, http_client=http)
        content, model = client.complete(CONTEXT, {}, {"type": "object"}, "instructions")
    assert json.loads(content)["personalized_text"] == "Kiểm tra nguồn."
    assert model == SETTINGS.model
    assert sink.events[0].module == "C11" and sink.events[0].provider == "OPENAI"
    assert C11PersonalizationOptions(mode="openai").mode == "openai"


def test_c11_api_accepts_the_recommendation_request_as_run_context():
    """The service hands C11 clients the whole request, not a bare Context."""
    request = RecommendationRequest.model_construct(
        **CONTEXT.model_dump(), contract_name="RecommendationInput", payload=object()
    )
    sink = Sink()
    with httpx.Client(
        transport=httpx.MockTransport(lambda _: response({"personalized_text": "Kiểm tra."}))
    ) as http:
        client = OpenAIRecommendationClient(SETTINGS, sink, http_client=http)
        content, _ = client.complete(request, {}, {"type": "object"}, "instructions")
    assert json.loads(content)["personalized_text"] == "Kiểm tra."
    assert sink.events[0].module == "C11" and sink.events[0].ca_id == CONTEXT.ca_id


@pytest.mark.parametrize(
    "adapter,error,code",
    [
        (OpenAIDocumentClient, DocumentModelError, "DOCUMENT_LLM_AUTHENTICATION"),
        (OpenAIRecommendationClient, C11ModelError, "C11_AUTHENTICATION"),
    ],
)
def test_provider_failure_maps_to_module_fallback(adapter, error, code):
    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(401))) as http:
        client = adapter(SETTINGS, Sink(), http_client=http)
        with pytest.raises(error, match=code):
            client.complete(CONTEXT, {}, {"type": "object"}, "instructions")
