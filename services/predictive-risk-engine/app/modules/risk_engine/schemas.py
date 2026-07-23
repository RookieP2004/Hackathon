from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RiskScoreRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: int
    equipment_id: int | None
    zone_id: int | None
    score: float
    confidence: float
    predicted_window_start: datetime | None
    predicted_window_end: datetime | None
    contributing_factors: list
    model_version: str
    computed_at: datetime


class RiskScoreCreate(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    equipment_id: int | None = None
    zone_id: int | None = None
    score: float = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=1)
    predicted_window_start: datetime | None = None
    predicted_window_end: datetime | None = None
    contributing_factors: list = Field(default_factory=list)
    model_version: str = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def _requires_a_target(self) -> "RiskScoreCreate":
        # Mirrors the DB-level chk_risk_target constraint (aegis_db.models.risk).
        if self.equipment_id is None and self.zone_id is None:
            raise ValueError("A risk score must target either equipment_id or zone_id (or both)")
        return self


class RiskScoreFilter(BaseModel):
    equipment_id: int | None = None
    zone_id: int | None = None
    score_gte: float | None = None
    computed_at_gte: datetime | None = None
    computed_at_lte: datetime | None = None


class PredictionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: int
    equipment_id: int
    model_name: str
    model_version: str
    target_metric: str
    predicted_value: float
    confidence: float
    prediction_horizon_minutes: int
    actual_outcome: float | None
    outcome_recorded_at: datetime | None
    predicted_at: datetime


class PredictionCreate(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    equipment_id: int
    model_name: str = Field(min_length=1, max_length=100)
    model_version: str = Field(min_length=1, max_length=100)
    target_metric: str = Field(min_length=1, max_length=100)
    predicted_value: float
    confidence: float = Field(ge=0, le=1)
    prediction_horizon_minutes: int = Field(gt=0)


class PredictionOutcomeRequest(BaseModel):
    actual_outcome: float


class PredictionFilter(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    equipment_id: int | None = None
    model_name: str | None = None
    target_metric: str | None = None
