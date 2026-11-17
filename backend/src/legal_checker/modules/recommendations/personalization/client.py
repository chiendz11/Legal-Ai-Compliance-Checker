"""Ollama native /api/chat client dedicated to C11 personalization with X02 audit."""

from __future__ import annotations

import json
import re
from threading import Lock
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import httpx

from legal_checker.modules.recommendations.personalization.config import C11OllamaOptions
from legal_checker.modules.recommendations.personalization.prompt import (
    PROMPT_VERSION,
    SCHEMA_VERSION,
)
from legal_checker.shared.contracts.common import Context
from legal_checker.shared.llm.audit import (
    AuditPersistenceError,
    LlmAuditSink,
    audit_llm_call,
)

_MAX_RESPONSE_BYTES = 256_000


class C11ModelError(RuntimeError):
    """Typed failure for C11 Ollama transport, model verification, or audit errors."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class OllamaRecommendationClient:
    """Sequential local Ollama client verifying installed digest and recording C11 X02 audit."""

    def __init__(
        self,
        options: C11OllamaOptions,
        audit: LlmAuditSink,
        *,
        transport: httpx.BaseTransport | None = None,
    ):
        self.options = options
        self.audit = audit
        self.transport = transport
        self._digest: str | None = None
        self._lock = Lock()

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict:
        import httpx

        try:
            with httpx.Client(
                timeout=self.options.timeout_seconds,
                trust_env=False,
                follow_redirects=False,
                transport=self.transport,
            ) as client:
                with client.stream(
                    method, self.options.base_url.rstrip("/") + path, json=payload
                ) as response:
                    response.raise_for_status()
                    data = bytearray()
                    for part in response.iter_bytes():
                        data.extend(part)
                        if len(data) > _MAX_RESPONSE_BYTES:
                            raise C11ModelError("C11_INVALID_STRUCTURED_OUTPUT")
            value = json.loads(data)
            if not isinstance(value, dict):
                raise ValueError
            return value
        except C11ModelError:
            raise
        except httpx.TimeoutException as error:
            raise C11ModelError("C11_MODEL_TIMEOUT") from error
        except httpx.HTTPError as error:
            raise C11ModelError("C11_MODEL_UNAVAILABLE") from error
        except ValueError as error:
            raise C11ModelError("C11_INVALID_STRUCTURED_OUTPUT") from error

    def digest(self) -> str:
        """Fetch real installed local model digest from /api/tags; never hardcode."""
        if self._digest is None:
            tags = self._request("GET", "/api/tags")
            models = tags.get("models", [])
            if not isinstance(models, list):
                raise C11ModelError("C11_INVALID_STRUCTURED_OUTPUT")
            row = next(
                (m for m in models if isinstance(m, dict) and m.get("name") == self.options.model),
                None,
            )
            if not row or not re.fullmatch(r"[a-f0-9]{64}", str(row.get("digest", ""))):
                raise C11ModelError("C11_MODEL_NOT_INSTALLED")
            if row.get("remote_host") or row.get("remote_model"):
                raise C11ModelError("C11_MODEL_NOT_INSTALLED")
            self._digest = row["digest"]
        return self._digest

    def complete(
        self,
        context: Context,
        payload: dict[str, Any],
        schema: dict[str, Any],
        instructions: str,
    ) -> tuple[str, str]:
        """Run one sequential /api/chat completion under C11 X02 audit.

        Returns `(raw_message_content, actual_model_version)`.
        """
        with self._lock:
            digest = self.digest()
            model_version = f"{self.options.model}@{digest}"
            body = {
                "model": self.options.model,
                "messages": [
                    {"role": "system", "content": instructions},
                    {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
                ],
                "format": schema,
                "stream": False,
                "think": False,
                "keep_alive": self.options.keep_alive,
                "options": {
                    "temperature": 0,
                    "seed": 42,
                    "num_ctx": self.options.context_tokens,
                    "num_predict": self.options.output_tokens,
                    "num_thread": self.options.threads,
                },
            }
            try:
                with audit_llm_call(
                    self.audit,
                    context=context,
                    module="C11",
                    provider="OLLAMA_LOCAL",
                    model_version=model_version,
                    prompt_version=PROMPT_VERSION,
                    schema_version=SCHEMA_VERSION,
                    input_payload=body,
                ) as call:
                    try:
                        response = self._request("POST", "/api/chat", body)
                        if (
                            response.get("done") is not True
                            or response.get("done_reason") != "stop"
                        ):
                            raise C11ModelError("C11_INVALID_STRUCTURED_OUTPUT")
                        if response.get("model") != self.options.model:
                            raise C11ModelError("C11_INVALID_STRUCTURED_OUTPUT")
                        message = response.get("message")
                        content = message.get("content") if isinstance(message, dict) else None
                        if not isinstance(content, str):
                            raise C11ModelError("C11_INVALID_STRUCTURED_OUTPUT")
                        call.complete(
                            response,
                            input_tokens=response.get("prompt_eval_count"),
                            output_tokens=response.get("eval_count"),
                        )
                        return content, model_version
                    except C11ModelError as error:
                        call.set_error_code(error.code)
                        raise
            except AuditPersistenceError as error:
                raise C11ModelError("C11_AUDIT_PERSISTENCE_FAILED") from error
