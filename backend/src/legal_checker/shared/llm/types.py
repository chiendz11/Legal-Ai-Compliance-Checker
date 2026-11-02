"""Transport-free LLM contracts, usable by offline providers without the ai extra."""

import re
from dataclasses import dataclass
from typing import Any, Protocol

from legal_checker.shared.contracts.common import Context


class LlmClientError(RuntimeError):
    """Safe module-mapped failure; never copy credentials, bodies or raw errors."""

    def __init__(self, code: str, *, retryable: bool = False, retry_after: float | None = None):
        if not re.fullmatch(r"[A-Z][A-Z0-9_]{0,63}", code):
            raise ValueError("LLM error codes must be safe identifiers")
        self.code = code
        self.retryable = retryable
        self.retry_after = retry_after
        super().__init__(f"LLM request failed: {code}")


@dataclass(frozen=True)
class LlmResponse:
    """Provider text, actual model ID and reported usage; unknown metadata stays null."""

    content: str
    model_version: str
    request_id: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None


class LlmClient(Protocol):
    """Inject a fake implementation into ObservationProvider for offline tests."""

    def complete(
        self,
        context: Context,
        *,
        instructions: str,
        payload: dict[str, Any],
        schema: dict[str, Any],
        prompt_version: str,
        schema_version: str,
    ) -> LlmResponse: ...
