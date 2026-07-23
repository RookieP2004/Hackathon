from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from aegis_db.models.knowledge import DOCUMENT_CLASSES

_DOCUMENT_CLASS_PATTERN = f"^({'|'.join(DOCUMENT_CLASSES)})$"


class KnowledgeDocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    document_class: str
    authority: str
    content: str
    section_reference: str | None
    version: str | None
    effective_date: date | None
    superseded_at: datetime | None
    equipment_type_scope: str | None
    hazard_class_scope: str | None
    created_by: int | None
    created_at: datetime
    updated_at: datetime


class KnowledgeDocumentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    document_class: str = Field(pattern=_DOCUMENT_CLASS_PATTERN)
    authority: str = Field(default="internal", min_length=1, max_length=100)
    content: str = Field(min_length=1)
    section_reference: str | None = None
    version: str | None = None
    effective_date: date | None = None
    equipment_type_scope: str | None = None
    hazard_class_scope: str | None = None


class KnowledgeDocumentUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    content: str | None = Field(default=None, min_length=1)
    section_reference: str | None = None
    version: str | None = None
    effective_date: date | None = None
    equipment_type_scope: str | None = None
    hazard_class_scope: str | None = None


class KnowledgeDocumentFilter(BaseModel):
    document_class: str | None = None
    authority: str | None = None
    equipment_type_scope: str | None = None
    hazard_class_scope: str | None = None
    current_only: bool = Field(
        default=False, description="If true, excludes superseded documents (superseded_at IS NOT NULL)."
    )
