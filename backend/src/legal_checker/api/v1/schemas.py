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


class LegalDocumentRef(Model):
    van_ban_id: str
    so_hieu: str | None = None
    ten_van_ban: str | None = None


class LegalBasisItem(Model):
    """Display record for one cited ID; verification flags are shown, never upgraded."""

    id: str
    kind: Literal["DOCUMENT", "ARTICLE", "REQUIREMENT_VERSION", "UNKNOWN"]
    title: str
    number: str | None = None
    excerpt: str | None = None
    requirement_id: str | None = None
    article_id: str | None = None
    effective_from: str | None = None
    effective_to: str | None = None
    status: str | None = None
    pages: list[int | None] | None = None
    url: str | None = None
    verification: str | None = None
    document: LegalDocumentRef | None = None


class LegalBasisList(Model):
    knowledge_snapshot_sha256: str
    items: list[LegalBasisItem]


class ReportRecord(Model):
    run_id: str = Field(min_length=1)
    review_revision: str = Field(min_length=1)
    report: FinalReport
