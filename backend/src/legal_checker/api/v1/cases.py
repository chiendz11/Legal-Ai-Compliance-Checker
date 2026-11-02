"""Cases, full-assessment runs, progress, pinned results and report versions.

Every route resolves the caller (api.auth) and only touches cases of the caller's tenant;
a case of another tenant is reported as not found.
"""

import asyncio
from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Header, Query, Request, Response
from fastapi.responses import StreamingResponse

from legal_checker.api.auth import ActorDependency, ServicesDependency, require_role
from legal_checker.api.errors import ApiProblem
from legal_checker.api.v1.schemas import (
    ApiErrorDetail,
    CaseCreate,
    CaseRecord,
    Page,
    ReportRecord,
    RunAccepted,
    RunProgress,
    StageProgress,
)
from legal_checker.core.security import Actor
from legal_checker.modules.assessments.cases import CaseFilter, CaseRow
from legal_checker.modules.assessments.runs import RunRecord
from legal_checker.modules.reports.repository import StoredReport
from legal_checker.shared.contracts.assessment import AssessmentTiming
from legal_checker.shared.contracts.workflow import AssessmentDraft

router = APIRouter(prefix="/api/v1")
PageNumber = Annotated[int, Query(ge=1)]
PageSize = Annotated[int, Query(ge=1, le=100)]


def _case_record(row: CaseRow) -> CaseRecord:
    return CaseRecord(
        case=row.case,
        latest_run_id=row.latest_run_id,
        latest_run_status=row.latest_run_status,
        ten_tai_lieu=row.ten_tai_lieu,
        latest_report_id=row.latest_report_id,
        requirement_status_counts=row.requirement_status_counts,
    )


def report_record(stored: StoredReport) -> ReportRecord:
    return ReportRecord(
        run_id=stored.run_id, review_revision=stored.review_revision, report=stored.report
    )


def _progress(record: RunRecord) -> RunProgress:
    error = None
    if record.error:
        error = ApiErrorDetail(**record.error, trace_id=record.context.trace_id)
    return RunProgress(
        context=record.context,
        status=record.status,
        stages=[StageProgress.model_validate(stage) for stage in record.stages],
        updated_at=record.updated_at,
        error=error,
    )


def accessible_case(services, actor: Actor, ca_id: str) -> CaseRow:
    """The case if it belongs to the caller's tenant; otherwise 404 (no existence leak)."""
    row = services.cases.get(ca_id, actor.tenant_id)
    if row is None:
        raise ApiProblem("NOT_FOUND", f"Case {ca_id} not found")
    return row


def _run(services, actor: Actor, ca_id: str, run_id: str) -> RunRecord:
    accessible_case(services, actor, ca_id)
    return services.assessment_service.get_run(ca_id, run_id)


@router.get("/cases", response_model=Page[CaseRecord], tags=["cases"])
def list_cases(
    services: ServicesDependency,
    actor: ActorDependency,
    page: PageNumber = 1,
    page_size: PageSize = 20,
    q: Annotated[str | None, Query(max_length=200)] = None,
    run_status: Literal["QUEUED", "RUNNING", "COMPLETED", "FAILED", "NONE"] | None = None,
    requirement_status: Literal["COMPLIANT", "PARTIAL", "NON_COMPLIANT", "INSUFFICIENT"]
    | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    sort: Literal["ca_id", "-ngay_danh_gia", "ngay_danh_gia", "-latest_run"] = "ca_id",
):
    """History: the tenant's cases with their latest run/report; filter and sort server-side."""
    filters = CaseFilter(
        tenant_id=actor.tenant_id,
        q=q.strip() if q and q.strip() else None,
        run_status=run_status,
        requirement_status=requirement_status,
        date_from=date_from,
        date_to=date_to,
        sort=sort,
    )
    rows, total = services.cases.list(filters, offset=(page - 1) * page_size, limit=page_size)
    return Page[CaseRecord](
        items=[_case_record(row) for row in rows], page=page, page_size=page_size, total=total
    )


@router.post("/cases", response_model=CaseRecord, status_code=201, tags=["cases"])
def create_case(body: CaseCreate, services: ServicesDependency, actor: ActorDependency):
    require_role(actor, "uploader", "Creating cases")
    if services.contracts.get(body.hop_dong_id, actor.tenant_id) is None:
        raise ApiProblem("NOT_FOUND", f"Contract {body.hop_dong_id} not found")
    try:
        deployment = services.deployments.resolve(body.phien_ban_id)
    except LookupError as error:
        raise ApiProblem("NOT_FOUND", str(error)) from error
    row = services.cases.create(
        body.hop_dong_id,
        AssessmentTiming(
            ngay_danh_gia=body.ngay_danh_gia,
            moc_ap_dung=body.moc_ap_dung,
            loai_moc_ap_dung=body.loai_moc_ap_dung,
        ),
        deployment,
        actor,
    )
    return _case_record(row)


@router.get("/cases/{ca_id}", response_model=CaseRecord, tags=["cases"])
def get_case(ca_id: str, services: ServicesDependency, actor: ActorDependency):
    return _case_record(accessible_case(services, actor, ca_id))


@router.post("/cases/{ca_id}/runs", response_model=RunAccepted, status_code=202, tags=["runs"])
def start_run(
    ca_id: str,
    services: ServicesDependency,
    actor: ActorDependency,
    response: Response,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1)],
):
    accessible_case(services, actor, ca_id)
    require_role(actor, "uploader", "Starting an assessment")
    record = services.assessment_service.start_run(ca_id, idempotency_key)
    base = f"/api/v1/cases/{ca_id}/runs/{record.run_id}"
    response.headers["X-Module-Source"] = record.module_source
    return RunAccepted(
        context=record.context, status_url=f"{base}/status", results_url=f"{base}/results"
    )


@router.get("/cases/{ca_id}/runs/{run_id}/status", response_model=RunProgress, tags=["runs"])
def run_status(
    ca_id: str,
    run_id: str,
    services: ServicesDependency,
    actor: ActorDependency,
    response: Response,
):
    record = _run(services, actor, ca_id, run_id)
    response.headers["X-Module-Source"] = record.module_source
    return _progress(record)


SSE_POLL_SECONDS = 1.0
SSE_HEARTBEAT_SECONDS = 15.0
SSE_MAX_SECONDS = 30 * 60


@router.get(
    "/cases/{ca_id}/runs/{run_id}/events",
    response_class=StreamingResponse,
    responses={200: {"content": {"text/event-stream": {}}}},
    tags=["runs"],
)
async def run_events(
    ca_id: str, run_id: str, request: Request, services: ServicesDependency, actor: ActorDependency
):
    """Server-Sent Events: a `progress` event (RunProgress JSON) on every change, ending once
    the run is COMPLETED or FAILED. Clients fall back to polling /status if the stream drops."""
    service = services.assessment_service
    first = await asyncio.to_thread(_run, services, actor, ca_id, run_id)  # 404 before streaming

    async def stream():
        record, sent, last_write = first, None, 0.0
        loop = asyncio.get_running_loop()
        started = loop.time()
        while not await request.is_disconnected():
            payload = _progress(record).model_dump_json()
            now = loop.time()
            if payload != sent:
                sent, last_write = payload, now
                yield f"event: progress\ndata: {payload}\n\n"
            elif now - last_write >= SSE_HEARTBEAT_SECONDS:
                last_write = now
                yield ": keep-alive\n\n"
            if record.status in ("COMPLETED", "FAILED") or now - started > SSE_MAX_SECONDS:
                return
            await asyncio.sleep(SSE_POLL_SECONDS)
            record = await asyncio.to_thread(service.get_run, ca_id, run_id)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/cases/{ca_id}/runs/{run_id}/results", response_model=AssessmentDraft, tags=["runs"])
def run_results(
    ca_id: str,
    run_id: str,
    services: ServicesDependency,
    actor: ActorDependency,
    response: Response,
):
    record = _run(services, actor, ca_id, run_id)
    draft = services.assessment_service.runs.draft(ca_id, run_id)
    if draft is None:
        raise ApiProblem("RESULT_NOT_READY", f"Run {run_id} is {record.status}")
    response.headers["X-Module-Source"] = record.module_source
    return draft


@router.get(
    "/cases/{ca_id}/runs/{run_id}/reports", response_model=Page[ReportRecord], tags=["reports"]
)
def list_run_reports(
    ca_id: str,
    run_id: str,
    services: ServicesDependency,
    actor: ActorDependency,
    page: PageNumber = 1,
    page_size: PageSize = 20,
):
    _run(services, actor, ca_id, run_id)
    stored, total = services.reports.list_for_run(
        ca_id, run_id, offset=(page - 1) * page_size, limit=page_size
    )
    return Page[ReportRecord](
        items=[report_record(s) for s in stored], page=page, page_size=page_size, total=total
    )


@router.post(
    "/cases/{ca_id}/runs/{run_id}/reports",
    response_model=ReportRecord,
    status_code=201,
    tags=["reports"],
)
def build_run_report(ca_id: str, run_id: str, services: ServicesDependency, actor: ActorDependency):
    _run(services, actor, ca_id, run_id)
    require_role(actor, "uploader", "Rebuilding a report")
    return report_record(services.assessment_service.build_report(ca_id, run_id))
