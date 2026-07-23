from __future__ import annotations

from datetime import datetime, timezone

from aegis_api_common import ConflictError, NotFoundError
from aegis_db.models import Sensor, SensorReading
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.sensors.schemas import SensorCreate, SensorReadingCreate, SensorUpdate


async def get_sensor_or_404(db: AsyncSession, sensor_id: int) -> Sensor:
    sensor = await db.get(Sensor, sensor_id)
    if sensor is None:
        raise NotFoundError(f"Sensor {sensor_id} not found")
    return sensor


async def create_sensor(db: AsyncSession, payload: SensorCreate) -> Sensor:
    existing = await db.execute(select(Sensor).where(Sensor.tag == payload.tag))
    if existing.scalar_one_or_none() is not None:
        raise ConflictError(f"Sensor with tag '{payload.tag}' already exists")

    sensor = Sensor(
        sensor_type_id=payload.sensor_type_id,
        equipment_id=payload.equipment_id,
        zone_id=payload.zone_id,
        tag=payload.tag,
        unit=payload.unit,
        protocol=payload.protocol,
        min_range=payload.min_range,
        max_range=payload.max_range,
        sample_rate_hz=payload.sample_rate_hz,
        calibration_date=payload.calibration_date,
        status="active",
    )
    db.add(sensor)
    await db.commit()
    await db.refresh(sensor)
    return sensor


async def update_sensor(db: AsyncSession, sensor_id: int, payload: SensorUpdate) -> Sensor:
    sensor = await get_sensor_or_404(db, sensor_id)
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(sensor, field, value)
    await db.commit()
    await db.refresh(sensor)
    return sensor


async def decommission_sensor(db: AsyncSession, sensor_id: int) -> Sensor:
    sensor = await get_sensor_or_404(db, sensor_id)
    sensor.status = "decommissioned"
    await db.commit()
    await db.refresh(sensor)
    return sensor


async def create_reading(db: AsyncSession, sensor_id: int, payload: SensorReadingCreate) -> SensorReading:
    # Confirms the sensor exists (404 instead of a raw FK-violation 500) without
    # otherwise touching it — readings are append-only telemetry, never routed
    # through the Sensor entity itself.
    sensor = await get_sensor_or_404(db, sensor_id)

    # min_range/max_range are stored per-sensor but were never actually
    # compared against an incoming value anywhere -- a reading outside the
    # instrument's own calibrated range was accepted at whatever quality flag
    # the caller self-reported. This never overrides an already-"bad" flag,
    # and doesn't exclude the reading from anything downstream (only
    # quality_flag == "missing" is excluded from Risk Fusion Engine scoring)
    # -- it only stops an out-of-range value from being trusted as "good"
    # data when the client claims it is.
    quality = payload.quality
    if quality == "good" and sensor.min_range is not None and sensor.max_range is not None:
        if payload.value < sensor.min_range or payload.value > sensor.max_range:
            quality = "bad"

    reading = SensorReading(
        sensor_id=sensor_id,
        value=payload.value,
        quality=quality,
        recorded_at=payload.recorded_at or datetime.now(timezone.utc),
    )
    db.add(reading)
    await db.commit()
    await db.refresh(reading)
    return reading
