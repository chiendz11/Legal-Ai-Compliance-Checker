"""Read and export exact report versions. Export never changes the stored report."""

import hashlib
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Response

from legal_checker.api.dependencies import Services, get_services
from legal_checker.api.errors import ApiProblem
from legal_checker.api.v1.cases import report_record
from legal_checker.api.v1.schemas import ReportRecord
from legal_checker.modules.reports.exporter import MEDIA_TYPES, ExportUnavailable, export_report

router = APIRouter(prefix="/api/v1")
ServicesDependency = Annotated[Services, Depends(get_services)]


def _stored(services: Services, bao_cao_id: str):
    stored = services.reports.get(bao_cao_id)
    if stored is None:
        raise ApiProblem("NOT_FOUND", f"Report {bao_cao_id} not found")
    return stored


@router.get("/reports/{bao_cao_id}", response_model=ReportRecord, tags=["reports"])
def get_report(bao_cao_id: str, services: ServicesDependency):
    return report_record(_stored(services, bao_cao_id))


@router.get(
    "/reports/{bao_cao_id}/export",
    response_class=Response,
    responses={200: {"content": {media: {} for media in MEDIA_TYPES.values()}}},
    tags=["reports"],
)
def export(
    bao_cao_id: str,
    services: ServicesDependency,
    format: Annotated[Literal["pdf", "docx"], Query()] = "pdf",
):
    stored = _stored(services, bao_cao_id)
    try:
        content = export_report(stored.report, format)
    except ExportUnavailable as error:
        raise ApiProblem("INTERNAL_ERROR", str(error)) from error
    # Keep a copy under the export dir and record it, so the file is traceable to the version.
    directory = services.settings.report_export_dir
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{bao_cao_id}.{format}"
    path.write_bytes(content)
    services.reports.record_export(
        bao_cao_id, format, path.as_uri(), hashlib.sha256(content).hexdigest()
    )
    filename = f"{bao_cao_id}_{stored.report.phien_ban_bao_cao}.{format}"
    return Response(
        content,
        media_type=MEDIA_TYPES[format],
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
