from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

_SEVERITIES = "low|medium|high|critical"


class AlertRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    alert_type: str
    severity: str
    status: str
    equipment_id: int | None
    zone_id: int | None
    sensor_id: int | None
    related_incident_id: int | None
    message: str
    triggered_at: datetime
    acknowledged_by: int | None
    acknowledged_at: datetime | None
    resolved_at: datetime | None
    created_at: datetime


class AlertCreate(BaseModel):
    alert_type: str = Field(min_length=1, max_length=100)
    severity: str = Field(pattern=f"^({_SEVERITIES})$")
    equipment_id: int | None = None
    zone_id: int | None = None
    sensor_id: int | None = None
    related_incident_id: int | None = None
    message: str = Field(min_length=1)


class AlertFilter(BaseModel):
    alert_type: str | None = None
    severity: str | None = None
    status: str | None = None
    equipment_id: int | None = None
    zone_id: int | None = None
