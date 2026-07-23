from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SensorRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sensor_type_id: int
    equipment_id: int | None
    zone_id: int | None
    tag: str
    unit: str
    protocol: str
    min_range: float | None
    max_range: float | None
    sample_rate_hz: float
    calibration_date: date | None
    status: str
    created_at: datetime
    updated_at: datetime


class SensorCreate(BaseModel):
    sensor_type_id: int
    equipment_id: int | None = None
    zone_id: int | None = None
    tag: str = Field(min_length=1, max_length=100)
    unit: str = Field(min_length=1, max_length=50)
    protocol: str = Field(pattern="^(mqtt|opc_ua|modbus_tcp|simulated)$")
    min_range: float | None = None
    max_range: float | None = None
    sample_rate_hz: float = Field(default=1.0, gt=0)
    calibration_date: date | None = None

    @model_validator(mode="after")
    def _requires_a_monitored_target(self) -> "SensorCreate":
        # Mirrors the DB-level chk_sensor_monitors_something constraint — surfacing
        # this as a 422 here gives a much clearer error than letting it fall
        # through to a raw IntegrityError from the database.
        if self.equipment_id is None and self.zone_id is None:
            raise ValueError("A sensor must monitor either equipment_id or zone_id (or both)")
        return self


class SensorUpdate(BaseModel):
    status: str | None = Field(default=None, pattern="^(active|faulted|decommissioned)$")
    calibration_date: date | None = None
    sample_rate_hz: float | None = Field(default=None, gt=0)
    min_range: float | None = None
    max_range: float | None = None


class SensorFilter(BaseModel):
    equipment_id: int | None = None
    zone_id: int | None = None
    sensor_type_id: int | None = None
    status: str | None = None
    protocol: str | None = None
    tag_ilike: str | None = None


class SensorReadingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sensor_id: int
    value: float
    quality: str
    recorded_at: datetime


class SensorReadingCreate(BaseModel):
    value: float
    quality: str = Field(default="good", pattern="^(good|uncertain|bad)$")
    recorded_at: datetime | None = Field(
        default=None, description="Defaults to server time if omitted — for backfill/replay ingestion."
    )


class SensorReadingFilter(BaseModel):
    quality: str | None = None
    recorded_at_gte: datetime | None = None
    recorded_at_lte: datetime | None = None
