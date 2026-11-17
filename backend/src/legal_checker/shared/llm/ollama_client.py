"""Local Ollama native /api/chat client for C07 compliance with X02 audit."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from threading import Lock
from typing import Any
from urllib.parse import urlsplit

import httpx

from legal_checker.shared.contracts.common import Context
from legal_checker.shared.llm.audit import LlmAuditSink, audit_llm_call
from legal_checker.shared.llm.types import LlmClientError, LlmResponse


@dataclass(frozen=True)
class OllamaComplianceSettings:
    """Explicit configuration for local Ollama C07 compliance reasoning."""

    base_url: str = "http://127.0.0.1:11434"
    model: str = "qwen3:4b-q4_K_M"
    timeout_seconds: float = 240.0
    context_tokens: int = 8192
    max_output_tokens: int = 3000
    threads: int = 4
    keep_alive: str = "5m"
    provider: str = "OLLAMA_LOCAL"

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
            raise ValueError("C07_OLLAMA_URL must be a server origin without credentials")
        if not self.model or self.model.endswith(":cloud"):
            raise ValueError("Select an installed local C07 Ollama model")
        if not (1 <= self.timeout_seconds <= 600 and 1 <= self.threads <= 32):
            raise ValueError("Invalid C07 Ollama resource limits")
        if not (1024 <= self.context_tokens <= 32768 and 64 <= self.max_output_tokens <= 8192):
            raise ValueError("Invalid C07 Ollama context/output limits")


class OllamaComplianceClient:
    """Sequential local Ollama client implementing C07 LlmClient with structured output & audit."""

    def __init__(
        self,
        settings: OllamaComplianceSettings,
        audit_sink: LlmAuditSink,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.settings = settings
        self.audit_sink = audit_sink
        self.transport = transport
        self._digest: str | None = None
        self._lock = Lock()

    def close(self) -> None:
        """No persistent socket kept open across calls."""

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict:
        try:
            with httpx.Client(
                timeout=self.settings.timeout_seconds,
                trust_env=False,
                follow_redirects=False,
                transport=self.transport,
            ) as client:
                with client.stream(
                    method, self.settings.base_url.rstrip("/") + path, json=payload
                ) as response:
                    response.raise_for_status()
                    data = bytearray()
                    for part in response.iter_bytes():
                        data.extend(part)
                        if len(data) > 512_000:
                            raise LlmClientError("INVALID_RESPONSE_JSON")
            value = json.loads(data)
            if not isinstance(value, dict):
                raise ValueError
            return value
        except LlmClientError:
            raise
        except httpx.TimeoutException:
            raise LlmClientError("TIMEOUT", retryable=True) from None
        except httpx.HTTPError:
            raise LlmClientError("CONNECTION_ERROR", retryable=True) from None
        except ValueError:
            raise LlmClientError("INVALID_RESPONSE_JSON") from None

    def digest(self) -> str:
        """Fetch real installed local model digest from /api/tags; never hardcode."""
        if self._digest is None:
            tags = self._request("GET", "/api/tags")
            models = tags.get("models", [])
            if not isinstance(models, list):
                raise LlmClientError("INVALID_RESPONSE_JSON")
            row = next(
                (m for m in models if isinstance(m, dict) and m.get("name") == self.settings.model),
                None,
            )
            if (
                not row
                or not re.fullmatch(r"[a-f0-9]{64}", str(row.get("digest", "")))
                or row.get("remote_host")
                or row.get("remote_model")
            ):
                raise LlmClientError("MODEL_NOT_FOUND")
            self._digest = row["digest"]
        return self._digest

    def complete(
        self,
        context: Context,
        *,
        instructions: str,
        payload: dict[str, Any],
        schema: dict[str, Any],
        prompt_version: str,
        schema_version: str,
    ) -> LlmResponse:
        """Run one sequential /api/chat completion under COMPLIANCE X02 audit."""
        context = Context.model_validate(context.model_dump())
        with self._lock:
            digest = self.digest()
            model_version = f"{self.settings.model}@{digest}"
            body = {
                "model": self.settings.model,
                "messages": [
                    {"role": "system", "content": instructions},
                    {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
                ],
                "format": schema,
                "stream": False,
                "think": False,
                "keep_alive": self.settings.keep_alive,
                "options": {
                    "temperature": 0,
                    "seed": 42,
                    "num_ctx": self.settings.context_tokens,
                    "num_predict": self.settings.max_output_tokens,
                    "num_thread": self.settings.threads,
                },
            }
            with audit_llm_call(
                self.audit_sink,
                context=context,
                module="COMPLIANCE",
                provider="OLLAMA_LOCAL",
                model_version=model_version,
                prompt_version=prompt_version,
                schema_version=schema_version,
                input_payload=body,
            ) as call:
                try:
                    response = self._request("POST", "/api/chat", body)
                    if response.get("done") is not True or response.get("done_reason") != "stop":
                        raise LlmClientError("INCOMPLETE_RESPONSE")
                    if response.get("model") != self.settings.model:
                        raise LlmClientError("INVALID_RESPONSE_JSON")
                    message = response.get("message")
                    content = message.get("content") if isinstance(message, dict) else None
                    if not isinstance(content, str) or not content.strip():
                        raise LlmClientError("INVALID_RESPONSE_JSON")
                    in_tok = response.get("prompt_eval_count")
                    out_tok = response.get("eval_count")
                    call.complete(
                        response,
                        input_tokens=in_tok if type(in_tok) is int and in_tok >= 0 else None,
                        output_tokens=out_tok if type(out_tok) is int and out_tok >= 0 else None,
                    )
                    return LlmResponse(
                        content=content,
                        model_version=model_version,
                        input_tokens=in_tok if type(in_tok) is int and in_tok >= 0 else None,
                        output_tokens=out_tok if type(out_tok) is int and out_tok >= 0 else None,
                    )
                except LlmClientError as error:
                    call.set_error_code(error.code)
                    raise
