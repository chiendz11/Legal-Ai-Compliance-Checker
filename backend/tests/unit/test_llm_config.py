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
        ("C07_LLM_MAX_RETRY_DELAY_SECONDS", "31"),
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
