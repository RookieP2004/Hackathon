"""
Shared exception hierarchy + FastAPI exception handlers, giving every
service's API the same JSON error envelope:
    {"error": {"code": "not_found", "message": "...", "detail": null}}
so a frontend client writes one error-handling code path for the entire
backend, not one per service.
"""

from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from aegis_api_common.logging import get_logger

logger = get_logger("aegis_api_common.exceptions")


class AppError(Exception):
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    code: str = "internal_error"

    def __init__(self, message: str, detail: object | None = None) -> None:
        self.message = message
        self.detail = detail
        super().__init__(message)


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"


class ConflictError(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "conflict"


class PermissionDeniedError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "permission_denied"


class InvalidStateError(AppError):
    """The resource exists and the request is well-formed, but the requested
    transition is not valid given the resource's current state (e.g. closing
    an already-closed incident)."""

    status_code = 422  # named constant renamed across Starlette versions; the numeric code is stable
    code = "invalid_state"


def _envelope(code: str, message: str, detail: object | None = None) -> dict:
    return {"error": {"code": code, "message": message, "detail": detail}}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        logger.info(
            "app_error",
            path=request.url.path,
            code=exc.code,
            message=exc.message,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(exc.code, exc.message, exc.detail),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        # exc.errors() can embed the raw exception instance (e.g. under
        # ctx["error"] when a @model_validator raises ValueError) — that isn't
        # JSON serializable via plain json.dumps, so it must go through
        # jsonable_encoder the same way FastAPI's own default handler does.
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_envelope("validation_error", "Request validation failed", jsonable_encoder(exc.errors())),
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope("http_error", str(exc.detail)),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        # Logged with full detail server-side; the client gets a deliberately
        # generic message -- an unhandled exception's message/traceback can
        # leak internals (table names, query fragments) that must never reach
        # a response body, matching the same principle DATABASE_SCHEMA.md and
        # the auth system apply to error messages throughout this project.
        logger.error("unhandled_exception", path=request.url.path, exc_info=exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_envelope("internal_error", "An unexpected error occurred"),
        )
