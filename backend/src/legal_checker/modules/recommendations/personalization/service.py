"""Personalization orchestrator for C11: sequential Qwen calls, validation, and safe fallback."""

from __future__ import annotations

from dataclasses import dataclass
from time import monotonic
from typing import Any, Protocol

from legal_checker.modules.recommendations.personalization.client import C11ModelError
from legal_checker.modules.recommendations.personalization.config import C11PersonalizationOptions
from legal_checker.modules.recommendations.personalization.contracts import (
    PersonalizationResult,
    PersonalizedRecommendation,
)
from legal_checker.modules.recommendations.personalization.prompt import (
    INSTRUCTIONS,
    PROMPT_VERSION,
    build_personalization_payload,
)
from legal_checker.modules.recommendations.personalization.validator import (
    PersonalizationValidationError,
    validate_personalized_output,
)
from legal_checker.shared.contracts.common import Context
from legal_checker.shared.contracts.recommendation import Recommendation


class C11CompletionClient(Protocol):
    def complete(
        self,
        context: Context,
        payload: dict[str, Any],
        schema: dict[str, Any],
        instructions: str,
    ) -> tuple[str, str]: ...


@dataclass
class _RunBudget:
    calls_used: int = 0
    started_at: float = 0.0


def _diag(
    code: str,
    recommendation: Recommendation,
    *,
    model_version: str,
    status: str,
    error_code: str | None = None,
    latency_ms: int | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "module": "C11",
        "code": code,
        "khuyen_nghi_ca_id": recommendation.khuyen_nghi_ca_id,
        "model_version": model_version,
        "status": status,
    }
    if error_code:
        row["error_code"] = error_code
    if latency_ms is not None:
        row["latency_ms"] = latency_ms
    return row


class RecommendationPersonalizationService:
    """Applies optional Qwen phrasing personalization over deterministic Recommendations.

    Any transport, timeout, schema, validator, budget, or audit failure falls back to the
    exact deterministic `Recommendation.noi_dung` with `TEMPLATE_ENGINE_FALLBACK`.
    """

    def __init__(
        self,
        client: C11CompletionClient | None,
        options: C11PersonalizationOptions | None = None,
    ):
        self.client = client
        self.options = options or C11PersonalizationOptions(mode="ollama" if client else "off")
        self._budgets: dict[tuple[str, str], _RunBudget] = {}

    def _budget_for(self, context: Context) -> _RunBudget:
        key = (context.ca_id, context.run_id)
        if key not in self._budgets:
            self._budgets[key] = _RunBudget(started_at=monotonic())
        return self._budgets[key]

    def _fallback(
        self,
        recommendation: Recommendation,
        *,
        status: str,
        error_code: str,
        diagnostics: list[dict[str, Any]],
        latency_ms: int | None = None,
    ) -> PersonalizationResult:
        diagnostics.append(
            _diag(
                "C11_PERSONALIZATION_FALLBACK",
                recommendation,
                model_version="TEMPLATE_ENGINE_FALLBACK",
                status=status,
                error_code=error_code,
                latency_ms=latency_ms,
            )
        )
        return PersonalizationResult(
            personalized_text=None,
            applied=False,
            status=status,
            model_version="TEMPLATE_ENGINE_FALLBACK",
            prompt_version=PROMPT_VERSION,
            error_code=error_code,
            latency_ms=latency_ms,
            diagnostics=diagnostics,
        )

    def personalize(
        self,
        context: Context,
        recommendation: Recommendation,
    ) -> PersonalizationResult:
        if self.options.mode == "off" or self.client is None:
            return PersonalizationResult(
                personalized_text=None,
                applied=False,
                status="NOT_REQUESTED",
                model_version="TEMPLATE_ENGINE_NO_LLM",
                prompt_version="NOT_USED",
                diagnostics=[
                    _diag(
                        "C11_PERSONALIZATION_DISABLED",
                        recommendation,
                        model_version="TEMPLATE_ENGINE_NO_LLM",
                        status="NOT_REQUESTED",
                    )
                ],
            )

        budget = self._budget_for(context)
        if (
            budget.calls_used >= self.options.max_calls
            or (monotonic() - budget.started_at) >= self.options.total_budget_seconds
        ):
            return self._fallback(
                recommendation,
                status="SKIPPED_BUDGET",
                error_code="C11_PERSONALIZATION_BUDGET_EXHAUSTED",
                diagnostics=[
                    _diag(
                        "C11_PERSONALIZATION_BUDGET_EXHAUSTED",
                        recommendation,
                        model_version="TEMPLATE_ENGINE_FALLBACK",
                        status="SKIPPED_BUDGET",
                        error_code="C11_PERSONALIZATION_BUDGET_EXHAUSTED",
                    )
                ],
            )

        payload = build_personalization_payload(recommendation)
        import json

        serialized_len = len(json.dumps(payload, ensure_ascii=False))
        if serialized_len > self.options.max_input_chars:
            return self._fallback(
                recommendation,
                status="FALLBACK",
                error_code="C11_INVALID_STRUCTURED_OUTPUT",
                diagnostics=[
                    _diag(
                        "C11_INVALID_STRUCTURED_OUTPUT",
                        recommendation,
                        model_version="TEMPLATE_ENGINE_FALLBACK",
                        status="FALLBACK",
                        error_code="C11_INVALID_STRUCTURED_OUTPUT",
                    )
                ],
            )

        diagnostics: list[dict[str, Any]] = []
        started = monotonic()
        budget.calls_used += 1
        try:
            raw_content, actual_model_version = self.client.complete(
                context,
                payload,
                PersonalizedRecommendation.model_json_schema(),
                INSTRUCTIONS,
            )
            elapsed_ms = int((monotonic() - started) * 1000)
            diagnostics.append(
                _diag(
                    "C11_PERSONALIZATION_CALLED",
                    recommendation,
                    model_version=actual_model_version,
                    status="CALLED",
                    latency_ms=elapsed_ms,
                )
            )
        except C11ModelError as error:
            elapsed_ms = int((monotonic() - started) * 1000)
            diagnostics.append(
                _diag(
                    error.code,
                    recommendation,
                    model_version="TEMPLATE_ENGINE_FALLBACK",
                    status="FALLBACK",
                    error_code=error.code,
                    latency_ms=elapsed_ms,
                )
            )
            return self._fallback(
                recommendation,
                status="FALLBACK",
                error_code=error.code,
                diagnostics=diagnostics,
                latency_ms=elapsed_ms,
            )
        except Exception:
            elapsed_ms = int((monotonic() - started) * 1000)
            diagnostics.append(
                _diag(
                    "C11_MODEL_UNAVAILABLE",
                    recommendation,
                    model_version="TEMPLATE_ENGINE_FALLBACK",
                    status="FALLBACK",
                    error_code="C11_MODEL_UNAVAILABLE",
                    latency_ms=elapsed_ms,
                )
            )
            return self._fallback(
                recommendation,
                status="FALLBACK",
                error_code="C11_MODEL_UNAVAILABLE",
                diagnostics=diagnostics,
                latency_ms=elapsed_ms,
            )

        try:
            clean_text = validate_personalized_output(
                recommendation,
                raw_content,
                max_output_chars=self.options.max_output_chars,
            )
        except PersonalizationValidationError as error:
            diagnostics.append(
                _diag(
                    error.code,
                    recommendation,
                    model_version=actual_model_version,
                    status="REJECTED",
                    error_code=error.code,
                    latency_ms=elapsed_ms,
                )
            )
            diagnostics.append(
                _diag(
                    "C11_PERSONALIZATION_REJECTED",
                    recommendation,
                    model_version=actual_model_version,
                    status="REJECTED",
                    error_code=error.code,
                    latency_ms=elapsed_ms,
                )
            )
            return self._fallback(
                recommendation,
                status="FALLBACK",
                error_code=error.code,
                diagnostics=diagnostics,
                latency_ms=elapsed_ms,
            )

        diagnostics.append(
            _diag(
                "C11_PERSONALIZATION_APPLIED",
                recommendation,
                model_version=actual_model_version,
                status="APPLIED",
                latency_ms=elapsed_ms,
            )
        )
        return PersonalizationResult(
            personalized_text=clean_text,
            applied=True,
            status="APPLIED",
            model_version=actual_model_version,
            prompt_version=PROMPT_VERSION,
            latency_ms=elapsed_ms,
            diagnostics=diagnostics,
        )
