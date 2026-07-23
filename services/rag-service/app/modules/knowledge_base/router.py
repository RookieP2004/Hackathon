from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aegis_api_common import Page, PaginationParams, apply_sorting, get_logger, paginate, parse_sort
from aegis_db.models import KnowledgeDocument
from app.auth import auth
from app.db import get_db
from app.modules.knowledge_base import service
from app.modules.knowledge_base.schemas import (
    KnowledgeDocumentCreate,
    KnowledgeDocumentFilter,
    KnowledgeDocumentRead,
    KnowledgeDocumentUpdate,
)

router = APIRouter(prefix="/knowledge-base", tags=["knowledge-base"])
logger = get_logger("rag-service.knowledge-base")

_READ_ROLES = ("system_admin", "plant_admin", "safety_officer", "maintenance_engineer", "operator", "emergency_team", "government_auditor", "viewer")
_WRITE_ROLES = ("system_admin", "plant_admin", "safety_officer")

_SORTABLE_FIELDS = {"id", "title", "document_class", "effective_date", "created_at"}


@router.get("/documents", response_model=Page[KnowledgeDocumentRead], summary="List knowledge base documents")
async def list_documents(
    pagination: PaginationParams = Depends(),
    sort_fields: list[tuple[str, bool]] = Depends(parse_sort),
    filters: KnowledgeDocumentFilter = Depends(),
    db: AsyncSession = Depends(get_db),
    _principal=Depends(auth.require_roles(*_READ_ROLES)),
) -> Page[KnowledgeDocumentRead]:
    query = service.apply_knowledge_filters(select(KnowledgeDocument), filters)
    query = apply_sorting(query, KnowledgeDocument, sort_fields, _SORTABLE_FIELDS, default_field="id")
    return await paginate(db, query, pagination, KnowledgeDocumentRead)


@router.get(
    "/search",
    response_model=Page[KnowledgeDocumentRead],
    summary="Keyword-search current knowledge base documents",
    description="Basic ILIKE search over title/content, excluding superseded documents. Full hybrid retrieval (RAG_SYSTEM.md) is future work.",
)
async def search_documents(
    q: str = Query(min_length=1, description="Keyword or phrase to search for"),
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    _principal=Depends(auth.require_roles(*_READ_ROLES)),
) -> Page[KnowledgeDocumentRead]:
    query = service.search_query(q)
    return await paginate(db, query, pagination, KnowledgeDocumentRead)


@router.get(
    "/documents/{document_id}",
    response_model=KnowledgeDocumentRead,
    summary="Get a knowledge base document by ID",
    responses={404: {"description": "Document not found"}},
)
async def get_document(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    _principal=Depends(auth.require_roles(*_READ_ROLES)),
) -> KnowledgeDocumentRead:
    document = await service.get_document_or_404(db, document_id)
    return KnowledgeDocumentRead.model_validate(document)


@router.post(
    "/documents",
    response_model=KnowledgeDocumentRead,
    status_code=201,
    summary="Add a knowledge base document",
)
async def create_document(
    payload: KnowledgeDocumentCreate,
    db: AsyncSession = Depends(get_db),
    principal=Depends(auth.require_roles(*_WRITE_ROLES)),
) -> KnowledgeDocumentRead:
    document = await service.create_document(db, payload, created_by=principal.user_id)
    logger.info("knowledge_document_created", document_id=document.id, document_class=document.document_class)
    return KnowledgeDocumentRead.model_validate(document)


@router.patch(
    "/documents/{document_id}",
    response_model=KnowledgeDocumentRead,
    summary="Update a knowledge base document",
    responses={404: {"description": "Not found"}, 422: {"description": "Document is superseded and cannot be modified"}},
)
async def update_document(
    document_id: int,
    payload: KnowledgeDocumentUpdate,
    db: AsyncSession = Depends(get_db),
    _principal=Depends(auth.require_roles(*_WRITE_ROLES)),
) -> KnowledgeDocumentRead:
    document = await service.update_document(db, document_id, payload)
    logger.info("knowledge_document_updated", document_id=document.id)
    return KnowledgeDocumentRead.model_validate(document)


@router.post(
    "/documents/{document_id}/supersede",
    response_model=KnowledgeDocumentRead,
    summary="Mark a document as superseded",
    description="Never physically deletes the row — superseded documents remain queryable for audit/history.",
    responses={404: {"description": "Not found"}, 422: {"description": "Already superseded"}},
)
async def supersede_document(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    _principal=Depends(auth.require_roles(*_WRITE_ROLES)),
) -> KnowledgeDocumentRead:
    document = await service.supersede_document(db, document_id)
    logger.info("knowledge_document_superseded", document_id=document.id)
    return KnowledgeDocumentRead.model_validate(document)
