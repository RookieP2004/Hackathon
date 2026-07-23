from contextlib import asynccontextmanager

import asyncpg
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from aegis_api_common import (
    RequestLoggingMiddleware,
    SecurityHeadersMiddleware,
    ServiceActorTokenMinter,
    assert_not_placeholder_secret,
    register_exception_handlers,
)
from app.api.fusion import router as fusion_router
from app.api.health import router as health_router
from app.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.fusion.loop import FusionLoop
from app.fusion.simulator import SensorSimulator
from app.modules.maintenance.router import router as maintenance_router
from app.modules.risk_engine.router import router as risk_engine_router

settings = get_settings()
configure_logging(settings.log_level)
logger = get_logger(settings.service_name)

TAGS_METADATA = [
    {"name": "health", "description": "Liveness/readiness — no authentication required."},
    {"name": "maintenance", "description": "Maintenance work orders — DATABASE_SCHEMA.md §8."},
    {"name": "risk-engine", "description": "Computed risk scores and model predictions — RISK_FUSION_ENGINE.md, DATABASE_SCHEMA.md §10, §12."},
    {"name": "risk-fusion", "description": "The six-stage probabilistic Risk Fusion Engine — RISK_FUSION_ENGINE.md."},
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("service_starting", service=settings.service_name, env=settings.aegis_env)
    assert_not_placeholder_secret(settings.jwt_secret, aegis_env=settings.aegis_env, name="jwt_secret")
    app.state.settings = settings

    dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    simulator = SensorSimulator()
    await simulator.load_sensors(dsn)
    app.state.sensor_simulator = simulator

    token_minter = ServiceActorTokenMinter(postgres_dsn=dsn, jwt_secret=settings.jwt_secret, jwt_algorithm=settings.jwt_algorithm)
    app.state.token_minter = token_minter

    # A shared pool, not a connect-per-call: assess_equipment() alone opens
    # 10-15 short-lived queries, and this runs on every fusion-loop tick plus
    # every /fusion/assess call -- the actual hot path of a live demo.
    pg_pool = await asyncpg.create_pool(dsn, min_size=2, max_size=10)
    app.state.pg_pool = pg_pool

    fusion_loop = FusionLoop(
        simulator, postgres_dsn=dsn, knowledge_graph_url=settings.knowledge_graph_url,
        computer_vision_url=settings.computer_vision_url, tick_seconds=settings.fusion_simulator_tick_seconds,
        token_minter=token_minter, pg_pool=pg_pool,
    )
    app.state.fusion_loop = fusion_loop
    fusion_loop.start()

    yield

    await fusion_loop.stop()
    await pg_pool.close()
    logger.info("service_stopping", service=settings.service_name)


def create_app() -> FastAPI:
    """
    App-factory pattern, not a bare module-level `app = FastAPI()` — this is what
    lets tests spin up isolated instances with overridden settings/dependencies
    without import-order side effects.
    """
    application = FastAPI(
        title="AEGIS AI — Predictive Risk Engine Service",
        description="Maintenance work orders, risk scoring, and predictions (RISK_FUSION_ENGINE.md).",
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
    application.include_router(maintenance_router)
    application.include_router(risk_engine_router)
    application.include_router(fusion_router)

    return application


app = create_app()
