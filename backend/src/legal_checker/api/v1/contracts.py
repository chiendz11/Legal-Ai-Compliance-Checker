"""Contract upload and source access. Upload stores bytes and metadata only: no extraction,
no assessment. Reads are scoped to the caller's tenant."""

from typing import Annotated

from fastapi import APIRouter, File, Form, Query, Response, UploadFile

from legal_checker.api.auth import ActorDependency, ServicesDependency
from legal_checker.api.errors import ApiProblem
from legal_checker.api.v1.schemas import ContractRecord, Page
from legal_checker.modules.assessments.contracts import ContractRow
from legal_checker.shared.storage.http import (
    SourceFormatError,
    SourceStorageError,
    SourceTooLargeError,
)

router = APIRouter(prefix="/api/v1")
PageNumber = Annotated[int, Query(ge=1)]
PageSize = Annotated[int, Query(ge=1, le=100)]


def _record(row: ContractRow) -> ContractRecord:
    return ContractRecord(
        hop_dong_id=row.hop_dong_id,
        ten_tai_lieu=row.ten_tai_lieu,
        source=row.source,
        created_at=row.created_at,
    )


@router.post("/contracts", response_model=ContractRecord, status_code=201, tags=["contracts"])
async def upload_contract(
    services: ServicesDependency,
    actor: ActorDependency,
    file: Annotated[UploadFile, File()],
    ten_tai_lieu: Annotated[str | None, Form(min_length=1)] = None,
):
    if not actor.has("uploader"):
        raise ApiProblem("FORBIDDEN", "Uploading contracts requires the uploader role")
    limit = services.uploads.max_bytes
    payload = await file.read(limit + 1)
    try:
        stored = services.uploads.save(payload)
    except SourceTooLargeError as error:
        raise ApiProblem("FILE_TOO_LARGE", str(error)) from error
    except SourceFormatError as error:
        raise ApiProblem("UNSUPPORTED_MEDIA_TYPE", str(error)) from error
    title = (ten_tai_lieu or file.filename or stored.sha256[:12]).strip()
    return _record(services.contracts.register(stored, title, file.filename, actor))


@router.get("/contracts", response_model=Page[ContractRecord], tags=["contracts"])
def list_contracts(
    services: ServicesDependency,
    actor: ActorDependency,
    page: PageNumber = 1,
    page_size: PageSize = 20,
):
    rows, total = services.contracts.list(
        actor.tenant_id, offset=(page - 1) * page_size, limit=page_size
    )
    return Page[ContractRecord](
        items=[_record(r) for r in rows], page=page, page_size=page_size, total=total
    )


def _contract(services, actor, hop_dong_id: str) -> ContractRow:
    row = services.contracts.get(hop_dong_id, actor.tenant_id)
    if row is None:
        raise ApiProblem("NOT_FOUND", f"Contract {hop_dong_id} not found")
    return row


@router.get("/contracts/{hop_dong_id}", response_model=ContractRecord, tags=["contracts"])
def get_contract(hop_dong_id: str, services: ServicesDependency, actor: ActorDependency):
    return _record(_contract(services, actor, hop_dong_id))


@router.get(
    "/contracts/{hop_dong_id}/source",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}}},
    tags=["contracts"],
)
def contract_source(hop_dong_id: str, services: ServicesDependency, actor: ActorDependency):
    """Original bytes (SHA-256 checked) for the split viewer, served same-origin."""
    row = _contract(services, actor, hop_dong_id)
    try:
        payload = services.document_sources.read(row.source)
    except SourceStorageError as error:
        raise ApiProblem("INTERNAL_ERROR", f"Source unavailable: {error}") from error
    extension = "pdf" if row.source.mime_type == "application/pdf" else "docx"
    return Response(
        payload,
        media_type=row.source.mime_type,
        headers={
            "Content-Disposition": f'inline; filename="{hop_dong_id}.{extension}"',
            "Cache-Control": "private, max-age=3600",
            "X-Content-Type-Options": "nosniff",
        },
    )
