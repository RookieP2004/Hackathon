from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class WorkerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int | None
    employer_id: int
    badge_id: str
    full_name: str
    worker_type: str
    certifications: list
    active: bool
    created_at: datetime
    updated_at: datetime


class WorkerCreate(BaseModel):
    employer_id: int
    badge_id: str = Field(min_length=1, max_length=50)
    full_name: str = Field(min_length=1, max_length=200)
    worker_type: str = Field(default="employee", pattern="^(employee|contractor|visitor)$")
    user_id: int | None = None
    certifications: list = Field(default_factory=list)


class WorkerUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    worker_type: str | None = Field(default=None, pattern="^(employee|contractor|visitor)$")
    active: bool | None = None
    certifications: list | None = None


class WorkerFilter(BaseModel):
    employer_id: int | None = None
    worker_type: str | None = None
    active: bool | None = None
    badge_id_ilike: str | None = None
