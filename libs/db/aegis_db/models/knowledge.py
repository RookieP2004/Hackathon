"""
Knowledge Base — new table, not part of the original DATABASE_SCHEMA.md list.

RAG_SYSTEM.md specifies a full ingestion/chunking/embedding/hybrid-search
pipeline over ten document classes, backed by a vector store — that full
pipeline is a separate, larger undertaking than this pass. What was missing
and IS in scope here is the underlying relational record: a Knowledge Base
document's metadata and content, queryable and manageable through a real API,
matching RAG_SYSTEM.md §1's ten document classes and §6's metadata schema at
the fields that matter for basic CRUD + keyword search (full hybrid
retrieval/re-ranking/citation-verification remain future work against this
same table, not reimplemented here).
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import BigInteger, Date, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from aegis_db.base import Base, TimestampMixin

DOCUMENT_CLASSES = (
    "safety_sop",
    "equipment_manual",
    "factory_act",
    "dgms",
    "oisd",
    "maintenance_manual",
    "incident_report",
    "near_miss",
    "audit_report",
    "inspection_report",
)


class KnowledgeDocument(Base, TimestampMixin):
    """Owned by: rag-service."""

    __tablename__ = "knowledge_documents"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    document_class: Mapped[str] = mapped_column(String, nullable=False)
    authority: Mapped[str] = mapped_column(String, nullable=False, server_default="internal")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    section_reference: Mapped[str | None] = mapped_column(String)
    version: Mapped[str | None] = mapped_column(String)
    effective_date: Mapped[date | None] = mapped_column(Date)
    superseded_at: Mapped[datetime | None] = mapped_column()
    equipment_type_scope: Mapped[str | None] = mapped_column(String)
    hazard_class_scope: Mapped[str | None] = mapped_column(String)
    created_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"))

    __table_args__ = (
        Index("idx_knowledge_documents_class", "document_class"),
        Index("idx_knowledge_documents_current", "document_class", "superseded_at"),
    )
