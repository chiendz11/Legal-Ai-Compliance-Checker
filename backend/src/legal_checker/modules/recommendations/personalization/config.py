"""Configuration options for local Qwen C11 recommendation personalization."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlsplit


@dataclass(frozen=True)
class C11OllamaOptions:
    base_url: str = "http://127.0.0.1:11434"
    model: str = "qwen3.5:9b-q4_K_M"
    timeout_seconds: float = 240
    context_tokens: int = 4096
    output_tokens: int = 512
    threads: int = 4
    keep_alive: str = "5m"

    def __post_init__(self) -> None:
        url = urlsplit(self.base_url)
        if (
            url.scheme not in {"http", "https"}
            or not url.hostname
            or url.username
            or url.password
            or url.query
            or url.fragment
            or url.path not in {"", "/"}
        ):
            raise ValueError("C11_OLLAMA_URL must be a server origin without credentials")
        if not self.model or self.model.endswith(":cloud"):
            raise ValueError("Select an installed local C11 model")
        if not (1 <= self.timeout_seconds <= 600 and 1 <= self.threads <= 32):
            raise ValueError("Invalid C11 model resource limits")
        if not (1024 <= self.context_tokens <= 8192 and 64 <= self.output_tokens <= 1024):
            raise ValueError("Invalid C11 context/output limits")


@dataclass(frozen=True)
class C11PersonalizationOptions:
    mode: Literal["off", "ollama", "openai"] = "off"
    max_calls: int = 10
    max_input_chars: int = 12000
    total_budget_seconds: float = 600
    max_output_chars: int = 4000

    def __post_init__(self) -> None:
        if self.mode not in {"off", "ollama", "openai"}:
            raise ValueError("C11_PERSONALIZATION must be off, ollama or openai")
        if self.max_calls < 0 or self.max_input_chars < 256 or self.max_output_chars < 64:
            raise ValueError("Invalid C11 personalization limits")
        if self.total_budget_seconds <= 0:
            raise ValueError("C11_LLM_TOTAL_BUDGET_SECONDS must be positive")
