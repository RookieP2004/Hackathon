from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class MachineRead(BaseModel):
    """
    A Machine, per DATABASE_SCHEMA.md §5.2's class-table-inheritance pattern —
    this response flattens the Equipment row and its Machine extension row
    (they share a primary key) into one object, since from an API consumer's
    point of view "a machine" is one thing, not two joined tables.
    """

    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: int = Field(description="Same value as the underlying equipment_id")
    tag: str
    name: str
    zone_id: int
    equipment_type_id: int
    manufacturer: str | None
    model_number: str | None
    serial_number: str | None
    install_date: date | None
    criticality: int
    status: str
    machine_class: str
    rated_power_kw: float | None
    rated_rpm: int | None
    control_system: str | None
    plc_tag: str | None
    created_at: datetime
    updated_at: datetime


class MachineCreate(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    zone_id: int
    equipment_type_id: int
    tag: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    manufacturer: str | None = None
    model_number: str | None = None
    serial_number: str | None = None
    install_date: date | None = None
    criticality: int = Field(default=3, ge=1, le=5)
    machine_class: str = Field(min_length=1, max_length=100)
    rated_power_kw: float | None = Field(default=None, gt=0)
    rated_rpm: int | None = Field(default=None, gt=0)
    control_system: str | None = None
    plc_tag: str | None = None


class MachineUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    criticality: int | None = Field(default=None, ge=1, le=5)
    status: str | None = Field(
        default=None, pattern="^(operational|degraded|under_maintenance|offline|decommissioned)$"
    )
    rated_power_kw: float | None = Field(default=None, gt=0)
    rated_rpm: int | None = Field(default=None, gt=0)
    control_system: str | None = None
    plc_tag: str | None = None


class MachineFilter(BaseModel):
    zone_id: int | None = None
    status: str | None = None
    machine_class: str | None = None
    criticality_gte: int | None = None
    tag_ilike: str | None = None
