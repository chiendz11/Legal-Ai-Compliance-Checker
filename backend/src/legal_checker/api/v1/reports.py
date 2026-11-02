"""Read and export exact report versions. Export never changes the stored report."""

import hashlib
from typing import Annotated, Literal

from fastapi import APIRouter, Query, Response

from legal_checker.api.auth import ActorDependency, ServicesDependency
from legal_checker.api.dependencies import Services, knowledge_snapshot
from legal_checker.api.errors import ApiProblem
from legal_checker.api.v1.cases import accessible_case, report_record
from legal_checker.api.v1.schemas import LegalBasisList, ReportRecord
from legal_checker.core.security import Actor
from legal_checker.modules.reports.exporter import MEDIA_TYPES, ExportUnavailable, export_report
from legal_checker.modules.reports.legal_basis import legal_basis_for

router = APIRouter(prefix="/api/v1")


def _stored(services: Services, actor: Actor, bao_cao_id: str):
    stored = services.reports.get(bao_cao_id)
    if stored is None:
        raise ApiProblem("NOT_FOUND", f"Report {bao_cao_id} not found")
    accessible_case(services, actor, stored.report.ca_id)  # other tenants get the same 404
    return stored


@router.get("/reports/{bao_cao_id}", response_model=ReportRecord, tags=["reports"])
def get_report(bao_cao_id: str, services: ServicesDependency, actor: ActorDependency):
    return report_record(_stored(services, actor, bao_cao_id))


@router.get("/reports/{bao_cao_id}/legal-basis", response_model=LegalBasisList, tags=["reports"])
def get_legal_basis(bao_cao_id: str, services: ServicesDependency, actor: ActorDependency):
    report = _stored(services, actor, bao_cao_id).report
    pinned = report.report_json.audit.get("context", {}).get("knowledge_snapshot_sha256")
    if not pinned:
        raise ApiProblem("CONFLICT", "Report has no pinned knowledge snapshot")
    try:
        knowledge = knowledge_snapshot(services, pinned)
    except ValueError as error:  # snapshot no longer in this DB
        raise ApiProblem("CONFLICT", str(error)) from error
    return LegalBasisList(
        knowledge_snapshot_sha256=pinned, items=legal_basis_for(report, knowledge)
    )


@router.get(
    "/reports/{bao_cao_id}/export",
    response_class=Response,
    responses={200: {"content": {media: {} for media in MEDIA_TYPES.values()}}},
    tags=["reports"],
)
def export(
    bao_cao_id: str,
    services: ServicesDependency,
    actor: ActorDependency,
    format: Annotated[Literal["pdf", "docx"], Query()] = "pdf",
):
    stored = _stored(services, actor, bao_cao_id)
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
