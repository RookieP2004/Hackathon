from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

_STATUSES = "scheduled|in_progress|completed|cancelled"


class MaintenanceRecordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    equipment_id: int
    maintenance_type_id: int
    requested_by: int | None
    performed_by: int | None
    related_prediction_id: int | None
    status: str
    scheduled_date: date | None
    completed_at: datetime | None
    description: str
    findings: str | None
    parts_used: list
    cost: float | None
    created_at: datetime
    updated_at: datetime


class MaintenanceRecordCreate(BaseModel):
    equipment_id: int
    maintenance_type_id: int
    performed_by: int | None = None
    related_prediction_id: int | None = None
    scheduled_date: date | None = None
    description: str = Field(min_length=1)


class MaintenanceRecordUpdate(BaseModel):
    performed_by: int | None = None
    scheduled_date: date | None = None
    description: str | None = Field(default=None, min_length=1)
    status: str | None = Field(default=None, pattern=f"^({_STATUSES})$")


class MaintenanceCompleteRequest(BaseModel):
    findings: str = Field(min_length=1)
    parts_used: list = Field(default_factory=list)
    cost: float | None = Field(default=None, ge=0)


class MaintenanceRecordFilter(BaseModel):
    equipment_id: int | None = None
    maintenance_type_id: int | None = None
    status: str | None = None
    performed_by: int | None = None
