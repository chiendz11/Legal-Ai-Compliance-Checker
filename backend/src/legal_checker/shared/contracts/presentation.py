"""Read-only report views, deliberately outside the immutable C13/review digest."""

from typing import Any, Literal

from pydantic import Field

from legal_checker.shared.contracts.common import Model


class CoverageView(Model):
    finding_complete: bool | None = None
    full_text_complete: bool | None = None
    conclusion_complete: bool
    explanation: str


class FindingView(Model):
    raw_status: str
    display_status: str
    coverage: CoverageView | None = None
    explanation: str | None = None
    audit_trace: list[str] = Field(default_factory=list)


class RecommendationView(Model):
    text: str
    unresolved_bindings: list[str] = Field(default_factory=list)


class ReportPresentation(Model):
    policy_id: Literal["REPORT_PRESENTATION_V1"] = "REPORT_PRESENTATION_V1"
    requirements: dict[str, FindingView]
    criteria: dict[str, FindingView]
    applicability_versions: dict[str, str]
    diagnostics: list[dict[str, Any]]
    recommendations: dict[str, RecommendationView]
