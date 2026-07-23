from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from aegis_api_common import (
    RequestLoggingMiddleware,
    SecurityHeadersMiddleware,
    ServiceActorTokenMinter,
    assert_not_placeholder_secret,
    register_exception_handlers,
)
from app.api.health import router as health_router
from app.api.rag import router as rag_router
from app.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.modules.knowledge_base.router import router as knowledge_base_router
from app.rag.embeddings import embedding_model
from app.rag.hallucination import nli_checker
from app.rag.indexing import rebuild_index
from app.rag.ocr import ocr_engine
from app.rag.reranking import cross_encoder
from app.rag.store import ChunkIndex, ensure_feedback_tables

settings = get_settings()
configure_logging(settings.log_level)
logger = get_logger(settings.service_name)

TAGS_METADATA = [
    {"name": "health", "description": "Liveness/readiness — no authentication required."},
    {"name": "knowledge-base", "description": "Knowledge base documents + basic keyword search (RAG_SYSTEM.md; full hybrid retrieval is future work)."},
    {"name": "rag", "description": "Chunking, embeddings, hybrid search, re-ranking, citation, and hallucination-prevention (RAG_SYSTEM.md §2-9)."},
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("service_starting", service=settings.service_name, env=settings.aegis_env)
    assert_not_placeholder_secret(settings.jwt_secret, aegis_env=settings.aegis_env, name="jwt_secret")
    app.state.settings = settings
    app.state.chunk_index = ChunkIndex()

    embedding_model.warm_up()
    cross_encoder.warm_up()
    nli_checker.warm_up()
    ocr_engine.warm_up()

    dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    await ensure_feedback_tables(dsn)
    await rebuild_index(app.state.chunk_index, dsn)
    app.state.token_minter = ServiceActorTokenMinter(postgres_dsn=dsn, jwt_secret=settings.jwt_secret, jwt_algorithm=settings.jwt_algorithm)

    yield
    logger.info("service_stopping", service=settings.service_name)


def create_app() -> FastAPI:
    """
    App-factory pattern, not a bare module-level `app = FastAPI()` — this is what
    lets tests spin up isolated instances with overridden settings/dependencies
    without import-order side effects.
    """
    application = FastAPI(
        title="AEGIS AI — RAG Service",
        description="Knowledge base documents and retrieval (RAG_SYSTEM.md, AGENT_ARCHITECTURE.md §6).",
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
    application.include_router(knowledge_base_router)
    application.include_router(rag_router)

    return application


app = create_app()
