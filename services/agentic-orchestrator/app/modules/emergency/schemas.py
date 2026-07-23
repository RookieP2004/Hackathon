from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

_AUTONOMY_TIERS = "tier_0_inform|tier_1_recommend|tier_2_execute_notify|tier_3_execute_veto"
_EVENT_STEP_STATUSES = "pending|approved|rejected|executing|completed|failed"


# ---- Playbooks -------------------------------------------------------------


class PlaybookRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    hazard_class: str
    description: str | None
    version: int
    is_active: bool
    created_by: int | None
    created_at: datetime
    updated_at: datetime


class PlaybookCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    hazard_class: str = Field(min_length=1, max_length=100)
    description: str | None = None


class PlaybookUpdate(BaseModel):
    description: str | None = None
    is_active: bool | None = None


class PlaybookFilter(BaseModel):
    hazard_class: str | None = None
    is_active: bool | None = None
    name_ilike: str | None = None


class PlaybookStepRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    playbook_id: int
    step_order: int
    description: str
    autonomy_tier: str
    tool_name: str
    parameters: dict


class PlaybookStepCreate(BaseModel):
    step_order: int = Field(gt=0)
    description: str = Field(min_length=1)
    autonomy_tier: str = Field(pattern=f"^({_AUTONOMY_TIERS})$")
    tool_name: str = Field(min_length=1, max_length=200)
    parameters: dict = Field(default_factory=dict)


# ---- Emergency Events -------------------------------------------------------


class EmergencyEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    incident_id: int | None
    plant_id: int
    zone_id: int | None
    playbook_id: int | None
    event_type: str
    status: str
    initiated_by_user_id: int | None
    initiated_at: datetime
    resolved_at: datetime | None
    created_at: datetime
    updated_at: datetime


class EmergencyEventCreate(BaseModel):
    plant_id: int
    zone_id: int | None = None
    playbook_id: int | None = None
    incident_id: int | None = None
    event_type: str = Field(min_length=1, max_length=100)


class EmergencyEventFilter(BaseModel):
    plant_id: int | None = None
    zone_id: int | None = None
    playbook_id: int | None = None
    status: str | None = None
    event_type: str | None = None


class EmergencyEventStepRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    emergency_event_id: int
    playbook_step_id: int | None
    status: str
    approved_by: int | None
    approved_at: datetime | None
    executed_at: datetime | None
    result: dict | None
    created_at: datetime


class EmergencyEventStepCreate(BaseModel):
    playbook_step_id: int | None = None


class EmergencyEventStepCompleteRequest(BaseModel):
    result: dict = Field(default_factory=dict)
    success: bool = True
