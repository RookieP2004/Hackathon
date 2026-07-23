from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

_STATUSES = "draft|active|suspended|closed|revoked"


class PermitRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    permit_number: str
    permit_type_id: int
    worker_id: int
    zone_id: int
    equipment_id: int | None
    issued_by: int
    cosigned_by: int | None
    status: str
    valid_from: datetime
    valid_to: datetime
    conditions: str | None
    created_at: datetime
    updated_at: datetime


class PermitCreate(BaseModel):
    permit_number: str = Field(min_length=1, max_length=100)
    permit_type_id: int
    worker_id: int
    zone_id: int
    equipment_id: int | None = None
    cosigned_by: int | None = None
    valid_from: datetime
    valid_to: datetime
    conditions: str | None = None

    @model_validator(mode="after")
    def _validity_window_must_be_positive(self) -> "PermitCreate":
        if self.valid_to <= self.valid_from:
            raise ValueError("valid_to must be after valid_from")
        return self


class PermitUpdate(BaseModel):
    status: str | None = Field(default=None, pattern=f"^({_STATUSES})$")
    cosigned_by: int | None = None
    valid_to: datetime | None = None
    conditions: str | None = None


class PermitFilter(BaseModel):
    permit_type_id: int | None = None
    worker_id: int | None = None
    zone_id: int | None = None
    status: str | None = None
    permit_number_ilike: str | None = None
