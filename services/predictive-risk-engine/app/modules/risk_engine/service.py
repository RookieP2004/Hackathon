from __future__ import annotations

from datetime import datetime, timezone

from aegis_api_common import InvalidStateError, NotFoundError
from aegis_db.models import Prediction, RiskScore
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.risk_engine.schemas import PredictionCreate, RiskScoreCreate


async def create_risk_score(db: AsyncSession, payload: RiskScoreCreate) -> RiskScore:
    risk_score = RiskScore(
        equipment_id=payload.equipment_id,
        zone_id=payload.zone_id,
        score=payload.score,
        confidence=payload.confidence,
        predicted_window_start=payload.predicted_window_start,
        predicted_window_end=payload.predicted_window_end,
        contributing_factors=payload.contributing_factors,
        model_version=payload.model_version,
    )
    db.add(risk_score)
    await db.commit()
    await db.refresh(risk_score)
    return risk_score


async def get_prediction_or_404(db: AsyncSession, prediction_id: int) -> Prediction:
    # Prediction's PK is composite (id, predicted_at) — a TimescaleDB hypertable
    # partitioning requirement (see aegis_db.models.risk's module docstring).
    # `id` alone is still globally unique (one shared sequence).
    result = await db.execute(select(Prediction).where(Prediction.id == prediction_id))
    prediction = result.scalar_one_or_none()
    if prediction is None:
        raise NotFoundError(f"Prediction {prediction_id} not found")
    return prediction


async def create_prediction(db: AsyncSession, payload: PredictionCreate) -> Prediction:
    prediction = Prediction(
        equipment_id=payload.equipment_id,
        model_name=payload.model_name,
        model_version=payload.model_version,
        target_metric=payload.target_metric,
        predicted_value=payload.predicted_value,
        confidence=payload.confidence,
        prediction_horizon_minutes=payload.prediction_horizon_minutes,
    )
    db.add(prediction)
    await db.commit()
    await db.refresh(prediction)
    return prediction


async def record_outcome(db: AsyncSession, prediction_id: int, actual_outcome: float) -> Prediction:
    prediction = await get_prediction_or_404(db, prediction_id)
    if prediction.outcome_recorded_at is not None:
        raise InvalidStateError(f"Prediction {prediction_id} already has a recorded outcome")
    prediction.actual_outcome = actual_outcome
    prediction.outcome_recorded_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(prediction)
    return prediction
