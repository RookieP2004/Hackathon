"""
Structured logging + request correlation, shared across every service so logs
from different services for the same request can be joined by correlation ID
(ARCHITECTURE.md §25.3 — "logs correlated across service boundaries by a
single log store using a shared correlation ID convention").
"""

from __future__ import annotations

import logging
import sys
import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

CORRELATION_ID_HEADER = "X-Correlation-ID"


def configure_logging(log_level: str = "info") -> None:
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=log_level.upper())
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Assigns/propagates a correlation ID, binds it (plus method/path) to
    structlog's contextvars for the duration of the request so every log line
    emitted anywhere during that request — including deep in a domain
    service's business logic — carries it automatically, and logs one
    request-completed line with status/duration.
    """

    def __init__(self, app, service_name: str) -> None:
        super().__init__(app)
        self.service_name = service_name
        self.logger = get_logger(f"{service_name}.request")

    async def dispatch(self, request: Request, call_next) -> Response:
        correlation_id = request.headers.get(CORRELATION_ID_HEADER) or str(uuid.uuid4())
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            correlation_id=correlation_id,
            method=request.method,
            path=request.url.path,
            service=self.service_name,
        )

        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            self.logger.error("request_failed", duration_ms=duration_ms)
            raise

        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        response.headers[CORRELATION_ID_HEADER] = correlation_id
        self.logger.info("request_completed", status_code=response.status_code, duration_ms=duration_ms)
        return response
