from contextlib import asynccontextmanager

import asyncpg
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from aegis_api_common import RequestLoggingMiddleware, SecurityHeadersMiddleware, assert_not_placeholder_secret, register_exception_handlers
from app.agents.fleet import AgentFleet
from app.api.agents import router as agents_router
from app.api.health import router as health_router
from app.config import get_settings
from app.copilot.router import router as copilot_router
from app.core.logging import configure_logging, get_logger
from app.demo.player import DemoPlayer
from app.demo.router import router as demo_router
from app.modules.emergency.router import router as emergency_router
from app.orchestrator.clients import ServiceClients
from app.reports.router import router as reports_router

settings = get_settings()
configure_logging(settings.log_level)
logger = get_logger(settings.service_name)

TAGS_METADATA = [
    {"name": "health", "description": "Liveness/readiness — no authentication required."},
    {"name": "emergency", "description": "Playbooks and emergency event execution — DATABASE_SCHEMA.md §13, ARCHITECTURE.md §15."},
    {"name": "agents", "description": "The twelve-agent fleet's health, decisions, and reasoning — AGENT_ARCHITECTURE.md."},
    {"name": "copilot", "description": "Conversational queries, every answer grounded in a real backend call and cited."},
    {"name": "reports", "description": "Eleven enterprise report types, real aggregated data, PDF/Excel/CSV export."},
    {"name": "demo", "description": "The scripted demo story -- real stimuli, real autonomous response, replay/pause/fast-forward."},
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("service_starting", service=settings.service_name, env=settings.aegis_env)
    assert_not_placeholder_secret(settings.jwt_secret, aegis_env=settings.aegis_env, name="jwt_secret")

    dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")

    # A shared pool, not a connect-per-call: twelve continuously-running
    # agents (one Postgres round trip or more per tick, most on a
    # 8-20s cadence) previously each opened and closed their own raw
    # connection per query -- the same class of bottleneck the fusion
    # pipeline had (predictive-risk-engine/app/fusion/db.py).
    pg_pool = await asyncpg.create_pool(dsn, min_size=2, max_size=20)
    app.state.pg_pool = pg_pool

    fleet = AgentFleet(
        postgres_dsn=dsn, redis_url=settings.redis_url, knowledge_graph_url=settings.knowledge_graph_url,
        computer_vision_url=settings.computer_vision_url, rag_service_url=settings.rag_service_url,
        predictive_risk_engine_url=settings.predictive_risk_engine_url, incident_service_url=settings.incident_service_url,
        notification_service_url=settings.notification_service_url,
        jwt_secret=settings.jwt_secret, jwt_algorithm=settings.jwt_algorithm, pg_pool=pg_pool,
    )
    app.state.fleet = fleet
    await fleet.start()

    app.state.settings = settings
    app.state.copilot_clients = ServiceClients(
        postgres_dsn=dsn, incident_service_url=settings.incident_service_url,
        notification_service_url=settings.notification_service_url, rag_service_url=settings.rag_service_url,
        predictive_risk_engine_url=settings.predictive_risk_engine_url, knowledge_graph_url=settings.knowledge_graph_url,
        jwt_secret=settings.jwt_secret, jwt_algorithm=settings.jwt_algorithm,
    )
    app.state.demo_player = DemoPlayer(
        clients=app.state.copilot_clients, postgres_dsn=dsn, bus=fleet.bus, iot_simulator_url=settings.iot_simulator_url,
        pg_pool=pg_pool,
    )

    yield

    await fleet.stop()
    await pg_pool.close()
    logger.info("service_stopping", service=settings.service_name)


def create_app() -> FastAPI:
    """
    App-factory pattern, not a bare module-level `app = FastAPI()` — this is what
    lets tests spin up isolated instances with overridden settings/dependencies
    without import-order side effects.
    """
    application = FastAPI(
        title="AEGIS AI — Agentic Orchestrator Service",
        description="Playbook planning and Emergency Agent execution (ARCHITECTURE.md §15, AGENT_ARCHITECTURE.md §9).",
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
    application.include_router(emergency_router)
    application.include_router(agents_router)
    application.include_router(copilot_router)
    application.include_router(reports_router)
    application.include_router(demo_router)

    return application


app = create_app()
