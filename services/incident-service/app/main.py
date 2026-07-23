from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from aegis_api_common import RequestLoggingMiddleware, SecurityHeadersMiddleware, assert_not_placeholder_secret, register_exception_handlers
from app.api.health import router as health_router
from app.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.modules.incidents.router import router as incidents_router
from app.modules.permits.router import router as permits_router
from app.modules.reports.router import router as reports_router

settings = get_settings()
configure_logging(settings.log_level)
logger = get_logger(settings.service_name)

TAGS_METADATA = [
    {"name": "health", "description": "Liveness/readiness — no authentication required."},
    {"name": "permits", "description": "Permit-to-work lifecycle — DATABASE_SCHEMA.md §7."},
    {"name": "incidents", "description": "Incident lifecycle (open/acknowledge/escalate/close) — DATABASE_SCHEMA.md §9, ARCHITECTURE.md §19."},
    {"name": "reports", "description": "Compliance and operational report requests — DATABASE_SCHEMA.md §18."},
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("service_starting", service=settings.service_name, env=settings.aegis_env)
    assert_not_placeholder_secret(settings.jwt_secret, aegis_env=settings.aegis_env, name="jwt_secret")
    yield
    logger.info("service_stopping", service=settings.service_name)


def create_app() -> FastAPI:
    """
    App-factory pattern, not a bare module-level `app = FastAPI()` — this is what
    lets tests spin up isolated instances with overridden settings/dependencies
    without import-order side effects.
    """
    application = FastAPI(
        title="AEGIS AI — Incident Service",
        description="Permits, incidents, and reports, per ARCHITECTURE.md §19.",
        version="0.1.0",
        openapi_tags=TAGS_METADATA,
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_base_url],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.add_middleware(RequestLoggingMiddleware, service_name=settings.service_name)
    application.add_middleware(SecurityHeadersMiddleware)
    register_exception_handlers(application)

    application.include_router(health_router)
    application.include_router(permits_router)
    application.include_router(incidents_router)
    application.include_router(reports_router)

    return application


app = create_app()
