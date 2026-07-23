from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from aegis_api_common import RequestLoggingMiddleware, SecurityHeadersMiddleware, assert_not_placeholder_secret, register_exception_handlers
from app.api.auth import router as auth_router
from app.api.health import router as health_router
from app.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.modules.users.router import router as users_router
from app.modules.workers.router import router as workers_router

settings = get_settings()
configure_logging(settings.log_level)
logger = get_logger(settings.service_name)

TAGS_METADATA = [
    {"name": "health", "description": "Liveness/readiness — no authentication required."},
    {"name": "auth", "description": "Login, refresh, logout, forgot/reset password, current session."},
    {"name": "users", "description": "System accounts — ARCHITECTURE.md §20-21."},
    {"name": "workers", "description": "Tracked physical personnel — ARCHITECTURE.md §6.2 in DATABASE_SCHEMA.md."},
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
        title="AEGIS AI — Identity & RBAC Service",
        description="Users, workers, roles, permissions, and sessions (ARCHITECTURE.md §20-21).",
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
    application.include_router(auth_router)
    application.include_router(users_router)
    application.include_router(workers_router)

    return application


app = create_app()
