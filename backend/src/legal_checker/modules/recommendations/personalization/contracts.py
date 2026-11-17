"""Contracts and protocols for C11 recommendation personalization."""

from __future__ import annotations

from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator

from legal_checker.shared.contracts.common import Context
from legal_checker.shared.contracts.recommendation import Recommendation

PersonalizationStatus = Literal["NOT_REQUESTED", "APPLIED", "FALLBACK", "SKIPPED_BUDGET"]


class PersonalizedRecommendation(BaseModel):
    """Structured output returned by Ollama for C11 phrasing personalization."""

    model_config = ConfigDict(extra="forbid", strict=True)

    personalized_text: str = Field(min_length=1, max_length=4000)

    @field_validator("personalized_text")
    @classmethod
    def nonempty_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("personalized_text must not be empty")
        return value


class PersonalizationResult(BaseModel):
    """Outcome of running personalization + validation on one Recommendation."""

    model_config = ConfigDict(extra="forbid")

    personalized_text: str | None = None
    applied: bool = False
    status: PersonalizationStatus = "NOT_REQUESTED"
    model_version: str = "TEMPLATE_ENGINE_NO_LLM"
    prompt_version: str = "NOT_USED"
    error_code: str | None = None
    latency_ms: int | None = None
    diagnostics: list[dict[str, Any]] = Field(default_factory=list)


class RecommendationPersonalizer(Protocol):
    """Injects optional phrasing personalization without changing deterministic logic."""

    def personalize(
        self,
        context: Context,
        recommendation: Recommendation,
    ) -> PersonalizationResult: ...
