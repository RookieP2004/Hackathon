import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from aegis_api_common import RequestLoggingMiddleware, SecurityHeadersMiddleware, assert_not_placeholder_secret, register_exception_handlers
from app.api.health import router as health_router
from app.config import get_settings
from app.control.router import router as control_router
from app.core.logging import configure_logging, get_logger
from app.domain.engine import SimulationEngine
from app.loop import run_tick_loop
from app.ws.manager import ConnectionManager
from app.ws.router import router as ws_router

settings = get_settings()
configure_logging(settings.log_level)
logger = get_logger(settings.service_name)

TAGS_METADATA = [
    {"name": "health", "description": "Liveness/readiness — no authentication required."},
    {"name": "telemetry", "description": "Live WebSocket sensor feed — one JSON snapshot per tick."},
    {"name": "control", "description": "Set Normal/Warning/Critical mode and trigger emergency scenarios."},
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.engine = SimulationEngine(seed=settings.simulation_seed)
    app.state.manager = ConnectionManager()
    logger.info("service_starting", service=settings.service_name, env=settings.aegis_env)
    assert_not_placeholder_secret(settings.jwt_secret, aegis_env=settings.aegis_env, name="jwt_secret")

    tick_task = asyncio.create_task(
        run_tick_loop(app.state.engine, app.state.manager, settings.tick_interval_seconds)
    )
    yield

    tick_task.cancel()
    try:
        await tick_task
    except asyncio.CancelledError:
        pass
    logger.info("service_stopping", service=settings.service_name)


def create_app() -> FastAPI:
    """
    App-factory pattern, not a bare module-level `app = FastAPI()` — this is
    what lets tests spin up isolated instances (each with its own fresh
    SimulationEngine and ConnectionManager in app.state) without cross-test
    state leaking through a shared module-level singleton.
    """
    application = FastAPI(
        title="AEGIS AI — IoT Simulator",
        description="Physics-informed industrial sensor/scenario simulator streamed over WebSockets.",
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
    application.include_router(control_router)
    application.include_router(ws_router)

    return application


app = create_app()
