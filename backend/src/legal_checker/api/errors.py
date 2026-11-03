"""Error envelope from docs/openapi.design.json: {"error": {code, message, trace_id, details}}."""

import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from legal_checker.core.exceptions import ConflictError
from legal_checker.modules.assessments.service import NotFound, ResultNotReady, ReviewRequired
from legal_checker.modules.reviews.service import ReviewError, StaleReview

STATUS = {
    "UNAUTHENTICATED": 401,
    "FORBIDDEN": 403,
    "FILE_TOO_LARGE": 413,
    "UNSUPPORTED_MEDIA_TYPE": 415,
    "NOT_FOUND": 404,
    "CONFLICT": 409,
    "RESULT_NOT_READY": 409,
    "STALE_REVIEW": 409,
    "REVIEW_REQUIRED": 409,
    "VALIDATION_ERROR": 422,
    "INTERNAL_ERROR": 500,
}


class ApiProblem(Exception):
    def __init__(self, code: str, message: str, details: list[dict] | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or []


def envelope(request: Request, code: str, message: str, details: list[dict]) -> JSONResponse:
    trace_id = request.headers.get("X-Request-ID") or f"REQ_{uuid.uuid4().hex}"
    return JSONResponse(
        status_code=STATUS[code],
        content={
            "error": {"code": code, "message": message, "trace_id": trace_id, "details": details}
        },
    )


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiProblem)
    async def api_problem(request: Request, error: ApiProblem):
        return envelope(request, error.code, error.message, error.details)

    @app.exception_handler(NotFound)
    async def not_found(request: Request, error: NotFound):
        return envelope(request, "NOT_FOUND", str(error), [])

    @app.exception_handler(ResultNotReady)
    async def not_ready(request: Request, error: ResultNotReady):
        return envelope(request, "RESULT_NOT_READY", str(error), [])

    @app.exception_handler(ReviewRequired)
    async def review_required(request: Request, error: ReviewRequired):
        return envelope(request, "REVIEW_REQUIRED", str(error), error.details)

    @app.exception_handler(StaleReview)
    async def stale_review(request: Request, error: StaleReview):
        return envelope(request, "STALE_REVIEW", str(error), [])

    @app.exception_handler(ReviewError)
    async def invalid_review(request: Request, error: ReviewError):
        return envelope(request, "VALIDATION_ERROR", str(error), [])

    @app.exception_handler(ConflictError)
    async def conflict(request: Request, error: ConflictError):
        return envelope(request, "CONFLICT", str(error), [])
