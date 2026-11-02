"""OpenAI Responses API transport with bounded attempts and provider-independent audit.

Structured-output schema validation and legal interpretation belong to the caller.
The transport never logs request bodies, credentials, response bodies or raw errors.
"""

import json
import math
import random
import re
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

from legal_checker.shared.contracts.common import Context
from legal_checker.shared.llm.audit import LlmAuditSink, audit_llm_call
from legal_checker.shared.llm.config import OpenAISettings
from legal_checker.shared.llm.types import LlmClient, LlmClientError, LlmResponse

OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
__all__ = ["LlmClient", "LlmClientError", "LlmResponse", "OpenAIResponsesClient"]


def _token_count(value):
    return value if type(value) is int and value >= 0 else None


def _usage(data):
    usage = data.get("usage") if isinstance(data, dict) else None
    if not isinstance(usage, dict):
        return None, None
    return _token_count(usage.get("input_tokens")), _token_count(usage.get("output_tokens"))


def _model_version(value) -> str | None:
    """Accept a provider model identifier, never arbitrary response text as metadata."""
    if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,199}", value):
        return value
    return None


def _retry_after(value: str | None) -> float | None:
    """Retry-After is a minimum delay; excessive valid delays must not be truncated."""
    if value is None:
        return None
    try:
        seconds = float(value)
    except ValueError:
        try:
            date = parsedate_to_datetime(value)
            if date.tzinfo is None:
                date = date.replace(tzinfo=timezone.utc)
            seconds = (date - datetime.now(timezone.utc)).total_seconds()
        except (TypeError, ValueError, OverflowError):
            return None
    return max(0.0, seconds) if math.isfinite(seconds) else None


def _http_error(response: httpx.Response) -> LlmClientError:
    status = response.status_code
    try:
        body = response.json()
        detail = body.get("error", {}) if isinstance(body, dict) else {}
        identifiers = (
            {value for value in (detail.get("code"), detail.get("type")) if isinstance(value, str)}
            if isinstance(detail, dict)
            else set()
        )
    except (TypeError, ValueError):
        identifiers = set()
    if identifiers & {
        "insufficient_quota",
        "billing_hard_limit_reached",
        "billing_not_active",
        "usage_limit_reached",
    }:
        return LlmClientError("QUOTA_EXHAUSTED")
    if status == 401:
        return LlmClientError("AUTHENTICATION")
    if status == 403:
        return LlmClientError("PERMISSION_DENIED")
    if status == 404:
        return LlmClientError("MODEL_NOT_FOUND")
    if status in {408, 409, 429} or status >= 500:
        return LlmClientError(
            "RATE_LIMIT" if status == 429 else "TEMPORARY_HTTP_ERROR",
            retryable=True,
            retry_after=_retry_after(response.headers.get("retry-after")),
        )
    return LlmClientError("INVALID_REQUEST")


def _parse_response(response: httpx.Response, data) -> LlmResponse:
    """Inspect protocol outcome after the completed HTTP attempt has been audited."""
    if not isinstance(data, dict):
        raise LlmClientError("INVALID_RESPONSE_JSON")
    if data.get("status") == "incomplete":
        raise LlmClientError("INCOMPLETE_RESPONSE")
    if data.get("status") != "completed":
        raise LlmClientError("FAILED_RESPONSE")
    output = data.get("output")
    if not isinstance(output, list):
        raise LlmClientError("INVALID_RESPONSE_JSON")
    texts = []
    for item in output:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        content = item.get("content")
        if not isinstance(content, list):
            raise LlmClientError("INVALID_RESPONSE_JSON")
        for part in content:
            if not isinstance(part, dict):
                raise LlmClientError("INVALID_RESPONSE_JSON")
            if part.get("type") == "refusal":
                raise LlmClientError("REFUSAL")
            if part.get("type") == "output_text":
                text = part.get("text")
                if not isinstance(text, str):
                    raise LlmClientError("INVALID_RESPONSE_JSON")
                texts.append(text)
    model = _model_version(data.get("model"))
    if not texts or not "".join(texts).strip() or model is None:
        raise LlmClientError("INVALID_RESPONSE_JSON")
    request_id = response.headers.get("x-request-id")
    if request_id is not None and not re.fullmatch(r"[A-Za-z0-9_-]{1,200}", request_id):
        request_id = None
    input_tokens, output_tokens = _usage(data)
    return LlmResponse("".join(texts), model, request_id, input_tokens, output_tokens)


class OpenAIResponsesClient:
    """One non-streaming request per attempt; retry only transient transport failures.

    HTTPX phase timeouts bound individual socket operations. The total budget is
    checked before each attempt/retry, not advertised as a hard cancellation timer.
    Caller-injected HTTP clients must disable their own retries/redirect handling.
    """

    def __init__(
        self,
        settings: OpenAISettings,
        audit_sink: LlmAuditSink,
        *,
        http_client: httpx.Client | None = None,
        sleep=time.sleep,
        monotonic=time.monotonic,
        jitter=random.random,
    ):
        self.settings = settings
        self.audit_sink = audit_sink
        self._owns_client = http_client is None
        self._http = http_client or httpx.Client(follow_redirects=False)
        self._sleep = sleep
        self._monotonic = monotonic
        self._jitter = jitter

    def close(self) -> None:
        if self._owns_client:
            self._http.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

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
        """Call Responses with strict JSON schema and no server-side response storage."""
        context = Context.model_validate(context.model_dump())
        try:
            body = {
                "model": self.settings.model,
                "input": [
                    {"role": "system", "content": instructions},
                    {
                        "role": "user",
                        "content": json.dumps(payload, ensure_ascii=False, allow_nan=False),
                    },
                ],
                "text": {
                    "format": {
                        "type": "json_schema",
                        "name": "criterion_proposal",
                        "strict": True,
                        "schema": schema,
                    }
                },
                "max_output_tokens": self.settings.max_output_tokens,
                "store": False,
            }
            json.dumps(body, allow_nan=False)
        except (TypeError, ValueError):
            raise LlmClientError("INVALID_INPUT") from None
        deadline = self._monotonic() + self.settings.total_timeout_seconds
        for attempt in range(1, self.settings.max_attempts + 1):
            remaining = deadline - self._monotonic()
            if remaining <= 0:
                raise LlmClientError("DEADLINE_EXCEEDED")
            try:
                return self._attempt(
                    context,
                    body,
                    prompt_version,
                    schema_version,
                    attempt,
                    min(self.settings.timeout_seconds, remaining),
                )
            except LlmClientError as error:
                if (
                    not error.retryable
                    or attempt >= self.settings.max_attempts
                    or getattr(error, "__notes__", None)
                ):
                    raise
                delay = min(
                    2 ** (attempt - 1) + min(1.0, max(0.0, float(self._jitter()))),
                    self.settings.max_retry_delay_seconds,
                )
                if error.retry_after is not None:
                    if error.retry_after > self.settings.max_retry_delay_seconds:
                        raise
                    delay = max(delay, error.retry_after)
                if delay >= deadline - self._monotonic():
                    raise
                self._sleep(delay)
        raise AssertionError("Attempt loop must either return or raise")

    def _attempt(self, context, body, prompt_version, schema_version, attempt, timeout):
        """Audit precisely one HTTP call; semantic parsing never replays a paid call."""
        with audit_llm_call(
            self.audit_sink,
            context=context,
            module="COMPLIANCE",
            provider="OPENAI",
            model_version=self.settings.model,
            prompt_version=prompt_version,
            schema_version=schema_version,
            input_payload=body,
            attempt=attempt,
        ) as call:
            try:
                response = self._http.post(
                    OPENAI_RESPONSES_URL,
                    json=body,
                    headers={"Authorization": f"Bearer {self.settings.api_key}"},
                    timeout=timeout,
                    follow_redirects=False,
                )
            except httpx.TimeoutException:
                call.set_error_code("TIMEOUT")
                raise LlmClientError("TIMEOUT", retryable=True) from None
            except httpx.RequestError:
                call.set_error_code("CONNECTION_ERROR")
                raise LlmClientError("CONNECTION_ERROR", retryable=True) from None
            if not 200 <= response.status_code < 300:
                error = _http_error(response)
                call.set_error_code(error.code)
                raise error
            try:
                data = response.json()
            except ValueError:
                data = None
            input_tokens, output_tokens = _usage(data)
            # A completed HTTP call is audited even if its semantic result is later
            # refused, incomplete or malformed. No response body is persisted.
            actual_model = _model_version(data.get("model")) if isinstance(data, dict) else None
            call.complete(
                response.content,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                model_version=actual_model,
            )
        return _parse_response(response, data)
