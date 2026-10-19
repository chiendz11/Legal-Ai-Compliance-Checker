"""HTTP response bodies matching docs/openapi.design.json; domain DTOs stay in shared/contracts."""

from datetime import datetime
from typing import Any, Generic, Literal, TypeVar

from pydantic import Field

from legal_checker.shared.contracts.assessment import AssessmentCase
from legal_checker.shared.contracts.common import Context, Model
from legal_checker.shared.contracts.report import FinalReport
from legal_checker.workflows.states import RunStatus, Stage, StageStatus

T = TypeVar("T")


class Page(Model, Generic[T]):
    items: list[T]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    total: int = Field(ge=0)


class CaseRecord(Model):
    case: AssessmentCase
    latest_run_id: str | None = None
    latest_run_status: RunStatus | None = None


class RunAccepted(Model):
    context: Context
    status: Literal["QUEUED"] = "QUEUED"
    status_url: str
    results_url: str


class StageProgress(Model):
    stage: Stage
    status: StageStatus
    started_at: datetime | None = None
    finished_at: datetime | None = None


class ApiErrorDetail(Model):
    code: str
    message: str = Field(min_length=1)
    trace_id: str = Field(min_length=1)
    details: list[dict[str, Any]] = Field(default_factory=list)


class RunProgress(Model):
    context: Context
    status: RunStatus
    stages: list[StageProgress]
    updated_at: datetime
    error: ApiErrorDetail | None = None


class ReportRecord(Model):
    run_id: str = Field(min_length=1)
    review_revision: str = Field(min_length=1)
    report: FinalReport
