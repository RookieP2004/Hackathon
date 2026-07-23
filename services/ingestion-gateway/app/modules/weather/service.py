from __future__ import annotations

from datetime import datetime, timezone

from aegis_db.models import WeatherObservation
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.weather.schemas import WeatherObservationCreate


async def create_observation(db: AsyncSession, payload: WeatherObservationCreate) -> WeatherObservation:
    observation = WeatherObservation(
        plant_id=payload.plant_id,
        temperature_c=payload.temperature_c,
        humidity_pct=payload.humidity_pct,
        wind_speed_ms=payload.wind_speed_ms,
        wind_direction_deg=payload.wind_direction_deg,
        precipitation_mm=payload.precipitation_mm,
        conditions=payload.conditions,
        source=payload.source,
        observed_at=payload.observed_at or datetime.now(timezone.utc),
    )
    db.add(observation)
    await db.commit()
    await db.refresh(observation)
    return observation
