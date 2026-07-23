from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aegis_db.models import Role
from app.auth import auth
from app.db import get_db
from app.rag.hallucination import verify_claim
from app.rag.ocr import ocr_engine
from app.rag.pipeline import query_knowledge_base
from app.rag.store import corpus_gap_report, record_feedback

router = APIRouter(prefix="/rag", tags=["rag"])

_READ_ROLES = ("system_admin", "plant_admin", "safety_officer", "maintenance_engineer", "operator", "emergency_team", "government_auditor", "viewer")
_WRITE_ROLES = ("system_admin", "plant_admin", "safety_officer")


async def _resolve_role_name(db: AsyncSession, role_id: int) -> str:
    role = await db.get(Role, role_id)
    return role.name if role else "viewer"


@router.post("/reindex", summary="Rebuild the in-memory chunk index from knowledge_documents")
async def post_reindex(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _principal=Depends(auth.require_roles(*_WRITE_ROLES)),
):
    from app.rag.indexing import rebuild_index

    settings = request.app.state.settings
    dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    return await rebuild_index(request.app.state.chunk_index, dsn)


class QueryRequest(BaseModel):
    query: str = Field(min_length=1)
    as_of: datetime | None = None
    equipment_id: int | None = None
    zone_id: int | None = None
    top_k: int = Field(default=20, ge=1, le=100)
    top_n: int = Field(default=10, ge=1, le=30)


@router.post("/query", summary="Hybrid search + re-rank + hallucination-gated retrieval (RAG_SYSTEM.md §5-9)")
async def post_query(
    payload: QueryRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    principal=Depends(auth.require_roles(*_READ_ROLES)),
):
    settings = request.app.state.settings
    role = await _resolve_role_name(db, principal.default_role_id)
    dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    return await query_knowledge_base(
        request.app.state.chunk_index, payload.query, role=role, dsn=dsn,
        knowledge_graph_url=settings.knowledge_graph_url, token_minter=request.app.state.token_minter, as_of=payload.as_of,
        equipment_id=payload.equipment_id, zone_id=payload.zone_id,
        top_k=payload.top_k, top_n=payload.top_n,
    )


class VerifyClaimRequest(BaseModel):
    query: str = Field(min_length=1, description="The original query, re-run to reproduce the retrieved candidate set")
    claim: str = Field(min_length=1)
    cited_chunk_id: str


@router.post("/verify-claim", summary="§8.3-8.4 — verify one generated claim against its cited chunk (the Copilot's hallucination-check call)")
async def post_verify_claim(
    payload: VerifyClaimRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    principal=Depends(auth.require_roles(*_READ_ROLES)),
):
    settings = request.app.state.settings
    role = await _resolve_role_name(db, principal.default_role_id)
    dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    result = await query_knowledge_base(
        request.app.state.chunk_index, payload.query, role=role, dsn=dsn,
        knowledge_graph_url=settings.knowledge_graph_url, token_minter=request.app.state.token_minter,
    )
    retrieved = [{"chunk": c} for c in _chunks_from_index_by_id(request.app.state.chunk_index, [c["chunk_id"] for c in result["chunks"]])]
    return verify_claim(claim=payload.claim, cited_chunk_id=payload.cited_chunk_id, retrieved_chunks=retrieved)


def _chunks_from_index_by_id(index, chunk_ids: list[str]):
    by_id = {c.metadata.chunk_id: c for c in index.chunks}
    return [by_id[cid] for cid in chunk_ids if cid in by_id]


class FeedbackRequest(BaseModel):
    query: str = Field(min_length=1)
    chunk_id: str
    signal: str = Field(pattern="^(positive|negative)$")


@router.post("/feedback", status_code=201, summary="§10 — record user feedback on a (query, chunk) pair")
async def post_feedback(
    payload: FeedbackRequest,
    request: Request,
    _principal=Depends(auth.require_roles(*_READ_ROLES)),
):
    settings = request.app.state.settings
    dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    await record_feedback(dsn, query_text=payload.query, chunk_id=payload.chunk_id, signal=payload.signal)
    return {"recorded": True}


@router.get("/corpus-gaps", summary="§10.1 — corpus-gap detection: repeatedly-unsatisfied queries")
async def get_corpus_gaps(
    request: Request,
    min_occurrences: int = Query(2, ge=1),
    _principal=Depends(auth.require_roles(*_WRITE_ROLES)),
):
    settings = request.app.state.settings
    dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    return await corpus_gap_report(dsn, min_occurrences=min_occurrences)


@router.post("/ocr", summary="Extract text from a scanned/image document (RAG_SYSTEM.md §2.2's OCR fallback)")
async def post_ocr(file: UploadFile = File(...), _principal=Depends(auth.require_roles(*_WRITE_ROLES))):
    image_bytes = await file.read()
    text, confidence = ocr_engine.extract_text(image_bytes)
    return {"text": text, "ocr_confidence": confidence, "low_confidence": confidence < 0.5}
