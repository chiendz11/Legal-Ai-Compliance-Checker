"""C12 human review of one run and report publication. Machine outputs are never edited."""

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Query
from pydantic import Field

from legal_checker.api.auth import ActorDependency, ServicesDependency, require_role
from legal_checker.api.errors import ApiProblem
from legal_checker.api.v1.cases import _run, accessible_case, report_record
from legal_checker.api.v1.schemas import Page, ReportRecord
from legal_checker.modules.reviews.service import publication_blockers
from legal_checker.shared.contracts.common import Model
from legal_checker.shared.contracts.review import HumanReview, ReviewTarget

router = APIRouter(prefix="/api/v1")
PageNumber = Annotated[int, Query(ge=1)]
PageSize = Annotated[int, Query(ge=1, le=100)]


class ReviewCreate(Model):
    target: ReviewTarget
    action: Literal["CONFIRM", "OVERRIDE", "REQUEST_MORE_EVIDENCE", "REJECT", "COMMENT"]
    after: dict[str, Any] = Field(default_factory=dict)
    reason: str = Field(min_length=1, max_length=4000)
    expected_target_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class ReviewRecord(Model):
    run_id: str = Field(min_length=1)
    target_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    review: HumanReview


class TargetReviewState(Model):
    doi_tuong_loai: str
    doi_tuong_id: str
    target_sha256: str
    overrides: dict[str, Any] = Field(default_factory=dict)
    latest_decision: str | None = None
    review_count: int = 0


class RunReviewState(Model):
    run_id: str
    review_revision: str
    targets: list[TargetReviewState]
    blockers: list[dict[str, str]]


class PublishRequest(Model):
    expected_review_revision: str = Field(min_length=1)


@router.get(
    "/cases/{ca_id}/runs/{run_id}/reviews", response_model=Page[ReviewRecord], tags=["reviews"]
)
def list_reviews(
    ca_id: str,
    run_id: str,
    services: ServicesDependency,
    actor: ActorDependency,
    page: PageNumber = 1,
    page_size: PageSize = 100,
):
    _run(services, actor, ca_id, run_id)
    events = services.assessment_service.reviews.for_run(ca_id, run_id)
    start = (page - 1) * page_size
    items = [
        ReviewRecord(run_id=run_id, target_sha256=sha, review=event)
        for event, sha in events[start : start + page_size]
    ]
    return Page[ReviewRecord](items=items, page=page, page_size=page_size, total=len(events))


@router.post(
    "/cases/{ca_id}/runs/{run_id}/reviews",
    response_model=ReviewRecord,
    status_code=201,
    tags=["reviews"],
)
def add_review(
    ca_id: str,
    run_id: str,
    body: ReviewCreate,
    services: ServicesDependency,
    actor: ActorDependency,
):
    _run(services, actor, ca_id, run_id)
    require_role(actor, "reviewer", "Reviewing findings")
    event, sha = services.assessment_service.add_review(
        ca_id,
        run_id,
        actor,
        body.target,
        body.action,
        body.after,
        body.reason,
        body.expected_target_sha256,
    )
    return ReviewRecord(run_id=run_id, target_sha256=sha, review=event)


@router.get(
    "/cases/{ca_id}/runs/{run_id}/review-state", response_model=RunReviewState, tags=["reviews"]
)
def review_state(ca_id: str, run_id: str, services: ServicesDependency, actor: ActorDependency):
    """Hash and effective overrides of every reviewable finding, for optimistic concurrency."""
    _run(services, actor, ca_id, run_id)
    state = services.assessment_service.review_state(ca_id, run_id)
    return RunReviewState(
        run_id=run_id,
        review_revision=state.revision,
        targets=[
            TargetReviewState(
                doi_tuong_loai=s.kind,
                doi_tuong_id=s.target_id,
                target_sha256=s.sha256,
                overrides=s.overrides,
                latest_decision=s.latest_decision,
                review_count=len(s.reviews),
            )
            for s in state.states.values()
        ],
        blockers=publication_blockers(state.states),
    )


@router.post("/reports/{bao_cao_id}/publish", response_model=ReportRecord, tags=["reports"])
def publish_report(
    bao_cao_id: str, body: PublishRequest, services: ServicesDependency, actor: ActorDependency
):
    stored = services.reports.get(bao_cao_id)
    if stored is None:
        raise ApiProblem("NOT_FOUND", f"Report {bao_cao_id} not found")
    accessible_case(services, actor, stored.report.ca_id)
    require_role(actor, "publisher", "Publishing a report")
    published = services.assessment_service.publish(stored, actor, body.expected_review_revision)
    return report_record(published)
