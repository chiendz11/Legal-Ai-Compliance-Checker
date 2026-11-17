"""Live API configuration is explicit; invalid input never leaks its actual value."""

import pytest
from legal_checker.shared.llm.config import LlmConfigurationError, OpenAISettings


def values(**updates):
    return {"OPENAI_API_KEY": "TEST_SECRET_DO_NOT_PRINT", "OPENAI_MODEL": "model-test", **updates}


def test_config_requires_explicit_key_and_model():
    for environment in ({}, {"OPENAI_MODEL": "model-test"}, {"OPENAI_API_KEY": "secret"}):
        with pytest.raises(LlmConfigurationError):
            OpenAISettings.from_env(environment)


def test_config_never_displays_key_and_mapping_does_not_load_real_env(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "OTHER_REAL_SECRET")
    settings = OpenAISettings.from_env(values())
    assert settings.api_key == "TEST_SECRET_DO_NOT_PRINT"
    assert "TEST_SECRET" not in repr(settings)
    assert "OTHER_REAL_SECRET" not in repr(settings)
    assert settings.model == "model-test"
    assert settings.max_attempts == 2
    assert settings.max_output_tokens == 3000


@pytest.mark.parametrize(
    "key,value",
    [
        ("OPENAI_API_KEY", ""),
        ("OPENAI_API_KEY", "unsafe\nSECRET"),
        ("OPENAI_API_KEY", "unsafe\x00SECRET"),
        ("OPENAI_API_KEY", "unsafeéSECRET"),
        ("OPENAI_MODEL", ""),
        ("OPENAI_MODEL", "not a model"),
        ("C07_LLM_TIMEOUT_SECONDS", "NaN"),
        ("C07_LLM_TIMEOUT_SECONDS", "Infinity"),
        ("C07_LLM_TIMEOUT_SECONDS", "0"),
        ("C07_LLM_TIMEOUT_SECONDS", "301"),
        ("C07_LLM_TIMEOUT_SECONDS", "PRIVATE_BAD_CONFIG"),
        ("C07_LLM_MAX_OUTPUT_TOKENS", "0"),
        ("C07_LLM_MAX_OUTPUT_TOKENS", "32769"),
        ("C07_LLM_MAX_OUTPUT_TOKENS", "1.5"),
        ("C07_LLM_MAX_OUTPUT_TOKENS", "true"),
        ("C07_LLM_MAX_ATTEMPTS", "0"),
        ("C07_LLM_MAX_ATTEMPTS", "6"),
        ("C07_LLM_MAX_RETRY_DELAY_SECONDS", "121"),
        ("C07_LLM_MAX_RETRY_DELAY_SECONDS", "-1"),
        ("C07_LLM_TOTAL_TIMEOUT_SECONDS", "0"),
    ],
)
def test_invalid_config_is_rejected_with_only_variable_name(key, value):
    with pytest.raises(LlmConfigurationError) as caught:
        OpenAISettings.from_env(values(**{key: value}))
    assert key in str(caught.value)
    assert "SECRET" not in str(caught.value)
    assert "PRIVATE_BAD_CONFIG" not in str(caught.value)


@pytest.mark.parametrize(
    "field,value",
    [
        ("timeout_seconds", True),
        ("max_output_tokens", True),
        ("max_attempts", False),
    ],
)
def test_direct_settings_constructor_does_not_coerce_bool_to_number(field, value):
    with pytest.raises(LlmConfigurationError):
        OpenAISettings(api_key="secret", model="test-model", **{field: value})


def test_config_reads_numeric_environment_strings():
    settings = OpenAISettings.from_env(
        values(
            C07_LLM_TIMEOUT_SECONDS="12.5",
            C07_LLM_MAX_OUTPUT_TOKENS="800",
            C07_LLM_MAX_ATTEMPTS="3",
            C07_LLM_MAX_RETRY_DELAY_SECONDS="2",
            C07_LLM_TOTAL_TIMEOUT_SECONDS="40",
        )
    )
    assert settings.timeout_seconds == 12.5
    assert settings.max_output_tokens == 800
    assert settings.max_attempts == 3
    assert settings.max_retry_delay_seconds == 2
    assert settings.total_timeout_seconds == 40


def test_groq_selection_prefers_groq_vars_even_when_openai_vars_present():
    settings = OpenAISettings.from_env(
        {
            "ASSESSMENT_LLM": "groq",
            "OPENAI_API_KEY": "AQ.OTHER_KEY",
            "OPENAI_BASE_URL": "https://generativelanguage.googleapis.com/v1beta/openai",
            "OPENAI_MODEL": "gemini-3.5-flash-lite",
            "GROQ_API_KEY": "gsk_TEST_GROQ_SECRET",
            "GROQ_MODEL": "openai/gpt-oss-20b",
        }
    )
    assert settings.provider == "GROQ"
    assert settings.api_key == "gsk_TEST_GROQ_SECRET"
    assert settings.base_url == "https://api.groq.com/openai/v1"
    assert settings.model == "openai/gpt-oss-20b"
    assert settings.api_mode == "chat_completions"


def test_c07_ollama_client_and_factory(monkeypatch):
    import json

    import httpx
    from legal_checker.api.dependencies import llm_client_factory
    from legal_checker.core.config import Settings
    from legal_checker.shared.contracts.common import Context
    from legal_checker.shared.llm.ollama_client import (
        OllamaComplianceClient,
        OllamaComplianceSettings,
    )

    class Sink:
        def __init__(self):
            self.events = []

        def append(self, event):
            self.events.append(event)

    settings = Settings(
        database_url="postgresql://u:p@127.0.0.1:5432/db",
        assessment_llm="ollama",
        c07_ollama_url="http://127.0.0.1:11434",
        c07_ollama_model="qwen3:4b-q4_K_M",
    )
    built = llm_client_factory(settings)()
    assert isinstance(built, OllamaComplianceClient)
    assert built.settings.provider == "OLLAMA_LOCAL"

    digest = "c" * 64

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/tags":
            return httpx.Response(
                200, json={"models": [{"name": "qwen3:4b-q4_K_M", "digest": digest}]}
            )
        body = json.loads(request.content.decode())
        assert body["think"] is False
        assert body["stream"] is False
        return httpx.Response(
            200,
            json={
                "model": "qwen3:4b-q4_K_M",
                "done": True,
                "done_reason": "stop",
                "prompt_eval_count": 42,
                "eval_count": 11,
                "message": {"content": '{"ok": true}'},
            },
        )

    sink = Sink()
    client = OllamaComplianceClient(
        OllamaComplianceSettings(model="qwen3:4b-q4_K_M"),
        sink,
        transport=httpx.MockTransport(handler),
    )
    ctx = Context(
        ca_id="CA_1",
        phien_ban_id="P1",
        rule_version="R1",
        legal_knowledge_version="L1",
        knowledge_snapshot_sha256="a" * 64,
        run_id="RUN_1",
        trace_id="TRACE_1",
    )
    res = client.complete(
        ctx,
        instructions="sys",
        payload={"a": 1},
        schema={"type": "object"},
        prompt_version="P_V1",
        schema_version="S_V1",
    )
    assert res.content == '{"ok": true}'
    assert res.model_version == f"qwen3:4b-q4_K_M@{digest}"
    assert len(sink.events) == 1
    assert sink.events[0].module == "COMPLIANCE"
    assert sink.events[0].provider == "OLLAMA_LOCAL"
