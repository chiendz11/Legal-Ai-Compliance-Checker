"""Case listing, full-assessment runs, progress, pinned results and report versions.

Authentication/tenant authorization (core.security.AccessPolicy) is not wired yet: these
routes are for local development until the shared access policy exists.
"""

import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from fastapi.responses import StreamingResponse

from legal_checker.api.dependencies import Services, get_services
from legal_checker.api.errors import ApiProblem
from legal_checker.api.v1.schemas import (
    ApiErrorDetail,
    CaseRecord,
    Page,
    ReportRecord,
    RunAccepted,
    RunProgress,
    StageProgress,
)
from legal_checker.modules.assessments.runs import RunRecord
from legal_checker.modules.reports.repository import StoredReport
from legal_checker.shared.contracts.workflow import AssessmentDraft

router = APIRouter(prefix="/api/v1")
ServicesDependency = Annotated[Services, Depends(get_services)]
PageNumber = Annotated[int, Query(ge=1)]
PageSize = Annotated[int, Query(ge=1, le=100)]


def _case_record(row) -> CaseRecord:
    return CaseRecord(
        case=row.case, latest_run_id=row.latest_run_id, latest_run_status=row.latest_run_status
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


@router.get("/cases", response_model=Page[CaseRecord], tags=["cases"])
def list_cases(services: ServicesDependency, page: PageNumber = 1, page_size: PageSize = 20):
    rows, total = services.cases.list(offset=(page - 1) * page_size, limit=page_size)
    return Page[CaseRecord](
        items=[_case_record(row) for row in rows], page=page, page_size=page_size, total=total
    )


@router.get("/cases/{ca_id}", response_model=CaseRecord, tags=["cases"])
def get_case(ca_id: str, services: ServicesDependency):
    row = services.cases.get(ca_id)
    if row is None:
        raise ApiProblem("NOT_FOUND", f"Case {ca_id} not found")
    return _case_record(row)


@router.post("/cases/{ca_id}/runs", response_model=RunAccepted, status_code=202, tags=["runs"])
def start_run(
    ca_id: str,
    services: ServicesDependency,
    response: Response,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1)],
):
    record = services.assessment_service.start_run(ca_id, idempotency_key)
    base = f"/api/v1/cases/{ca_id}/runs/{record.run_id}"
    response.headers["X-Module-Source"] = record.module_source
    return RunAccepted(
        context=record.context, status_url=f"{base}/status", results_url=f"{base}/results"
    )


@router.get("/cases/{ca_id}/runs/{run_id}/status", response_model=RunProgress, tags=["runs"])
def run_status(ca_id: str, run_id: str, services: ServicesDependency, response: Response):
    record = services.assessment_service.get_run(ca_id, run_id)
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
async def run_events(ca_id: str, run_id: str, request: Request, services: ServicesDependency):
    """Server-Sent Events: a `progress` event (RunProgress JSON) on every change, ending once
    the run is COMPLETED or FAILED. Clients fall back to polling /status if the stream drops."""
    service = services.assessment_service
    first = await asyncio.to_thread(service.get_run, ca_id, run_id)  # 404 before streaming

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
def run_results(ca_id: str, run_id: str, services: ServicesDependency, response: Response):
    service = services.assessment_service
    record = service.get_run(ca_id, run_id)
    draft = service.runs.draft(ca_id, run_id)
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
    page: PageNumber = 1,
    page_size: PageSize = 20,
):
    services.assessment_service.get_run(ca_id, run_id)
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
def build_run_report(ca_id: str, run_id: str, services: ServicesDependency):
    return report_record(services.assessment_service.build_report(ca_id, run_id))
