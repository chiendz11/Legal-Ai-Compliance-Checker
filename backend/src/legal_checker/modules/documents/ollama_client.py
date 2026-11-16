"""Ollama native structured-output transport for Documents; never calls a cloud API."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit

if TYPE_CHECKING:
    import httpx

from legal_checker.shared.contracts.common import Context
from legal_checker.shared.llm.audit import LlmAuditSink, audit_llm_call


class DocumentModelError(RuntimeError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class OllamaOptions:
    base_url: str = "http://127.0.0.1:11434"
    model: str = "qwen3.5:9b-q4_K_M"
    timeout_seconds: float = 240
    context_tokens: int = 4096
    output_tokens: int = 512
    threads: int = 4

    def __post_init__(self):
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
            raise ValueError("DOCUMENTS_OLLAMA_URL must be a server origin without credentials")
        if not self.model or self.model.endswith(":cloud"):
            raise ValueError("Select an installed local Documents model")
        if not (1 <= self.timeout_seconds <= 600 and 1 <= self.threads <= 32):
            raise ValueError("Invalid Documents model resource limits")
        if not (1024 <= self.context_tokens <= 8192 and 64 <= self.output_tokens <= 1024):
            raise ValueError("Invalid Documents context/output limits")


class OllamaDocumentClient:
    def __init__(
        self,
        options: OllamaOptions,
        audit: LlmAuditSink,
        *,
        transport: httpx.BaseTransport | None = None,
    ):
        self.options, self.audit, self.transport = options, audit, transport
        self._digest: str | None = None

    def _request(self, method: str, path: str, payload=None) -> dict[str, Any]:
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
                        if len(data) > 256000:
                            raise DocumentModelError("DOCUMENT_LLM_RESPONSE_LIMIT")
            import json

            value = json.loads(data)
            if not isinstance(value, dict):
                raise ValueError
            return value
        except httpx.TimeoutException as error:
            raise DocumentModelError("DOCUMENT_LLM_TIMEOUT") from error
        except httpx.HTTPError as error:
            raise DocumentModelError("DOCUMENT_LLM_UNAVAILABLE") from error
        except ValueError as error:
            raise DocumentModelError("DOCUMENT_LLM_INVALID_RESPONSE") from error

    def digest(self) -> str:
        if self._digest is None:
            models = self._request("GET", "/api/tags").get("models", [])
            if not isinstance(models, list):
                raise DocumentModelError("DOCUMENT_LLM_INVALID_RESPONSE")
            row = next(
                (m for m in models if isinstance(m, dict) and m.get("name") == self.options.model),
                None,
            )
            import re

            if not row or not re.fullmatch(r"[a-f0-9]{64}", row.get("digest", "")):
                raise DocumentModelError("DOCUMENT_LLM_MODEL_NOT_INSTALLED")
            if row.get("remote_host") or row.get("remote_model"):
                raise DocumentModelError("DOCUMENT_LLM_REMOTE_MODEL")
            self._digest = row["digest"]
        return self._digest

    def complete(self, context: Context, payload: dict, schema: dict, instructions: str) -> dict:
        import json

        digest = self.digest()
        body = {
            "model": self.options.model,
            "messages": [
                {"role": "system", "content": instructions},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            "format": schema,
            "stream": False,
            "think": False,
            "keep_alive": "5m",
            "options": {
                "temperature": 0,
                "seed": 42,
                "num_ctx": self.options.context_tokens,
                "num_predict": self.options.output_tokens,
                "num_thread": self.options.threads,
            },
        }
        with audit_llm_call(
            self.audit,
            context=context,
            module="DOCUMENT_INTELLIGENCE",
            provider="OLLAMA_LOCAL",
            model_version=self.options.model + "@" + digest,
            prompt_version="DI_SEMANTIC_V1",
            schema_version="DI_FACT_PROPOSALS_V1",
            input_payload=body,
        ) as call:
            try:
                response = self._request("POST", "/api/chat", body)
                if response.get("done") is not True or response.get("done_reason") != "stop":
                    raise DocumentModelError("DOCUMENT_LLM_INCOMPLETE")
                if response.get("model") != self.options.model:
                    raise DocumentModelError("DOCUMENT_LLM_MODEL_MISMATCH")
                message = response.get("message")
                content = message.get("content") if isinstance(message, dict) else None
                if not isinstance(content, str):
                    raise DocumentModelError("DOCUMENT_LLM_INVALID_RESPONSE")
                call.complete(
                    response,
                    input_tokens=response.get("prompt_eval_count"),
                    output_tokens=response.get("eval_count"),
                )
                return response
            except DocumentModelError as error:
                call.set_error_code(error.code)
                raise
