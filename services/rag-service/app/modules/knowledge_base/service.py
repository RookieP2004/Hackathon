from __future__ import annotations

from datetime import datetime, timezone

from aegis_api_common import InvalidStateError, NotFoundError
from aegis_db.models import KnowledgeDocument
from sqlalchemy import Select, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.knowledge_base.schemas import (
    KnowledgeDocumentCreate,
    KnowledgeDocumentFilter,
    KnowledgeDocumentUpdate,
)


def apply_knowledge_filters(query: Select, filters: KnowledgeDocumentFilter) -> Select:
    # current_only isn't a plain column-equality filter (it maps to
    # "superseded_at IS NULL"), so it's handled here rather than through the
    # generic aegis_api_common.apply_filters — a deliberate, narrow exception,
    # same reasoning as digital-twin's Machine filters.
    if filters.document_class is not None:
        query = query.where(KnowledgeDocument.document_class == filters.document_class)
    if filters.authority is not None:
        query = query.where(KnowledgeDocument.authority == filters.authority)
    if filters.equipment_type_scope is not None:
        query = query.where(KnowledgeDocument.equipment_type_scope == filters.equipment_type_scope)
    if filters.hazard_class_scope is not None:
        query = query.where(KnowledgeDocument.hazard_class_scope == filters.hazard_class_scope)
    if filters.current_only:
        query = query.where(KnowledgeDocument.superseded_at.is_(None))
    return query


async def get_document_or_404(db: AsyncSession, document_id: int) -> KnowledgeDocument:
    document = await db.get(KnowledgeDocument, document_id)
    if document is None:
        raise NotFoundError(f"Knowledge document {document_id} not found")
    return document


async def create_document(db: AsyncSession, payload: KnowledgeDocumentCreate, *, created_by: int) -> KnowledgeDocument:
    document = KnowledgeDocument(
        title=payload.title,
        document_class=payload.document_class,
        authority=payload.authority,
        content=payload.content,
        section_reference=payload.section_reference,
        version=payload.version,
        effective_date=payload.effective_date,
        equipment_type_scope=payload.equipment_type_scope,
        hazard_class_scope=payload.hazard_class_scope,
        created_by=created_by,
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)
    return document


async def update_document(db: AsyncSession, document_id: int, payload: KnowledgeDocumentUpdate) -> KnowledgeDocument:
    document = await get_document_or_404(db, document_id)
    if document.superseded_at is not None:
        raise InvalidStateError(f"Knowledge document {document_id} is superseded and cannot be modified")

    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(document, field, value)

    await db.commit()
    await db.refresh(document)
    return document


async def supersede_document(db: AsyncSession, document_id: int) -> KnowledgeDocument:
    document = await get_document_or_404(db, document_id)
    if document.superseded_at is not None:
        raise InvalidStateError(f"Knowledge document {document_id} is already superseded")
    document.superseded_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(document)
    return document


def search_query(q: str) -> Select:
    # Basic keyword search (ILIKE over title/content) — the full hybrid
    # retrieval/embedding pipeline in RAG_SYSTEM.md is out of scope here; see
    # aegis_db.models.knowledge's module docstring.
    pattern = f"%{q}%"
    return (
        select(KnowledgeDocument)
        .where(
            KnowledgeDocument.superseded_at.is_(None),
            or_(KnowledgeDocument.title.ilike(pattern), KnowledgeDocument.content.ilike(pattern)),
        )
        .order_by(KnowledgeDocument.id.asc())
    )
