from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

_SEVERITIES = "low|medium|high|critical"


class IncidentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    incident_number: str
    plant_id: int
    zone_id: int | None
    equipment_id: int | None
    severity: str
    status: str
    ai_generated_summary: str | None
    root_cause: str | None
    opened_by_user_id: int | None
    acknowledged_by: int | None
    closed_by: int | None
    opened_at: datetime
    acknowledged_at: datetime | None
    escalated_at: datetime | None
    closed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class IncidentCreate(BaseModel):
    incident_number: str = Field(min_length=1, max_length=100)
    plant_id: int
    zone_id: int | None = None
    equipment_id: int | None = None
    severity: str = Field(pattern=f"^({_SEVERITIES})$")
    ai_generated_summary: str | None = None


class IncidentUpdate(BaseModel):
    severity: str | None = Field(default=None, pattern=f"^({_SEVERITIES})$")
    ai_generated_summary: str | None = None
    root_cause: str | None = None


class IncidentCloseRequest(BaseModel):
    root_cause: str = Field(min_length=1, description="Required to close — an incident cannot be closed without a documented root cause.")


class IncidentFilter(BaseModel):
    plant_id: int | None = None
    zone_id: int | None = None
    equipment_id: int | None = None
    severity: str | None = None
    status: str | None = None
    incident_number_ilike: str | None = None


class IncidentTimelineEventCreate(BaseModel):
    """A generic timeline-event append, distinct from the fixed lifecycle-
    transition events (`created`/`acknowledged`/`escalated`/`closed`) the
    service module logs internally — for orchestrated automation (Emergency
    Response Orchestrator) that needs to record its own richer event types
    (`evacuation_activated`, `sensor_data_captured`, `evidence_stored`,
    `report_generated`, ...) against the same append-only trail."""

    event_type: str = Field(min_length=1, max_length=100)
    event_data: dict = Field(default_factory=dict)
    actor_type: str = Field(default="system", pattern="^(user|system|agent)$")


class IncidentTimelineEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    incident_id: int
    event_type: str
    actor_type: str
    actor_user_id: int | None
    event_data: dict
    occurred_at: datetime
