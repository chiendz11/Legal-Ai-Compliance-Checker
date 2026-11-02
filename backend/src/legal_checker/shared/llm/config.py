"""Explicit OpenAI configuration; secrets never appear in configuration reprs."""

import math
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass, field

from dotenv import load_dotenv

from legal_checker.core.config import PROJECT_ROOT


class LlmConfigurationError(ValueError):
    """Safe configuration error containing a variable name, never its value."""


def _float(value, name: str, lower: float, upper: float) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        raise LlmConfigurationError(f"{name} must be a finite number") from None
    if isinstance(value, bool) or not math.isfinite(result) or not lower <= result <= upper:
        raise LlmConfigurationError(f"{name} must be within [{lower}, {upper}]")
    return result


def _int(value, name: str, lower: int, upper: int) -> int:
    if isinstance(value, bool) or not re.fullmatch(r"[0-9]+", str(value)):
        raise LlmConfigurationError(f"{name} must be an integer")
    result = int(value)
    if not lower <= result <= upper:
        raise LlmConfigurationError(f"{name} must be within [{lower}, {upper}]")
    return result


@dataclass(frozen=True)
class OpenAISettings:
    """No implicit model or key: the application must choose both explicitly."""

    api_key: str = field(repr=False)
    model: str
    timeout_seconds: float = 45.0
    max_output_tokens: int = 3000
    max_attempts: int = 2
    max_retry_delay_seconds: float = 10.0
    total_timeout_seconds: float = 120.0

    def __post_init__(self):
        if not isinstance(self.api_key, str) or not self.api_key.strip():
            raise LlmConfigurationError("OPENAI_API_KEY is required for live calls")
        if any(not 33 <= ord(character) <= 126 for character in self.api_key):
            raise LlmConfigurationError(
                "OPENAI_API_KEY must contain printable ASCII without spaces"
            )
        if not isinstance(self.model, str) or not re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,199}", self.model
        ):
            raise LlmConfigurationError("OPENAI_MODEL is required and must be a model ID")
        for attr, name, lower, upper in (
            ("timeout_seconds", "C07_LLM_TIMEOUT_SECONDS", 0.1, 300.0),
            ("max_retry_delay_seconds", "C07_LLM_MAX_RETRY_DELAY_SECONDS", 0.0, 30.0),
            ("total_timeout_seconds", "C07_LLM_TOTAL_TIMEOUT_SECONDS", 0.1, 600.0),
        ):
            object.__setattr__(self, attr, _float(getattr(self, attr), name, lower, upper))
        object.__setattr__(
            self,
            "max_output_tokens",
            _int(self.max_output_tokens, "C07_LLM_MAX_OUTPUT_TOKENS", 1, 32768),
        )
        object.__setattr__(
            self, "max_attempts", _int(self.max_attempts, "C07_LLM_MAX_ATTEMPTS", 1, 5)
        )

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None):
        """Load local .env only when no explicit mapping is supplied (e.g. in tests)."""
        if environ is None:
            load_dotenv(PROJECT_ROOT / ".env", override=False)
            environ = os.environ
        return cls(
            api_key=environ.get("OPENAI_API_KEY", ""),
            model=environ.get("OPENAI_MODEL", ""),
            timeout_seconds=environ.get("C07_LLM_TIMEOUT_SECONDS", "45"),
            max_output_tokens=environ.get("C07_LLM_MAX_OUTPUT_TOKENS", "3000"),
            max_attempts=environ.get("C07_LLM_MAX_ATTEMPTS", "2"),
            max_retry_delay_seconds=environ.get("C07_LLM_MAX_RETRY_DELAY_SECONDS", "10"),
            total_timeout_seconds=environ.get("C07_LLM_TOTAL_TIMEOUT_SECONDS", "120"),
        )
