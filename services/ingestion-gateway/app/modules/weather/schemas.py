from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class WeatherObservationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    plant_id: int
    temperature_c: float | None
    humidity_pct: float | None
    wind_speed_ms: float | None
    wind_direction_deg: int | None
    precipitation_mm: float | None
    conditions: str | None
    source: str
    observed_at: datetime


class WeatherObservationCreate(BaseModel):
    plant_id: int
    temperature_c: float | None = None
    humidity_pct: float | None = Field(default=None, ge=0, le=100)
    wind_speed_ms: float | None = Field(default=None, ge=0)
    wind_direction_deg: int | None = Field(default=None, ge=0, le=359)
    precipitation_mm: float | None = Field(default=None, ge=0)
    conditions: str | None = None
    source: str = Field(min_length=1, max_length=100)
    observed_at: datetime | None = Field(
        default=None, description="Defaults to server time if omitted — for backfill/replay ingestion."
    )


class WeatherObservationFilter(BaseModel):
    plant_id: int | None = None
    source: str | None = None
    observed_at_gte: datetime | None = None
    observed_at_lte: datetime | None = None
