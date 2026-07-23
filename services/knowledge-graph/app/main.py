from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from aegis_api_common import RequestLoggingMiddleware, SecurityHeadersMiddleware, assert_not_placeholder_secret, register_exception_handlers
from app.api.graph import router as graph_router
from app.api.health import router as health_router
from app.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.graph.driver import create_driver
from app.graph.reads import GraphReader
from app.graph.schema import apply_schema

settings = get_settings()
configure_logging(settings.log_level)
logger = get_logger(settings.service_name)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("service_starting", service=settings.service_name, env=settings.aegis_env)
    assert_not_placeholder_secret(settings.jwt_secret, aegis_env=settings.aegis_env, name="jwt_secret")
    assert_not_placeholder_secret(settings.neo4j_password, aegis_env=settings.aegis_env, name="neo4j_password")
    app.state.settings = settings
    app.state.neo4j_driver = create_driver(settings)
    app.state.graph_reader = GraphReader(app.state.neo4j_driver)
    await apply_schema(app.state.neo4j_driver)

    yield

    await app.state.neo4j_driver.close()
    logger.info("service_stopping", service=settings.service_name)


def create_app() -> FastAPI:
    """
    App-factory pattern, not a bare module-level `app = FastAPI()` — this is what
    lets tests spin up isolated instances with overridden settings/dependencies
    without import-order side effects.
    """
    application = FastAPI(
        title=settings.service_name,
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
    application.include_router(graph_router)
    return application


app = create_app()
