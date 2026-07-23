from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aegis_api_common import (
    Page,
    PaginationParams,
    apply_filters,
    apply_sorting,
    get_logger,
    paginate,
    parse_sort,
)
from aegis_db.models import Sensor, SensorReading
from app.auth import auth
from app.db import get_db
from app.modules.sensors import service
from app.modules.sensors.schemas import (
    SensorCreate,
    SensorFilter,
    SensorRead,
    SensorReadingCreate,
    SensorReadingFilter,
    SensorReadingRead,
    SensorUpdate,
)

router = APIRouter(prefix="/sensors", tags=["sensors"])
logger = get_logger("ingestion-gateway.sensors")

_READ_ROLES = ("system_admin", "plant_admin", "safety_officer", "maintenance_engineer", "operator", "emergency_team")
_WRITE_ROLES = ("system_admin", "plant_admin", "maintenance_engineer")

_SORTABLE_FIELDS = {"id", "tag", "status", "sample_rate_hz", "created_at"}
_READING_SORTABLE_FIELDS = {"id", "recorded_at", "value"}


@router.get("", response_model=Page[SensorRead], summary="List sensors")
async def list_sensors(
    pagination: PaginationParams = Depends(),
    sort_fields: list[tuple[str, bool]] = Depends(parse_sort),
    filters: SensorFilter = Depends(),
    db: AsyncSession = Depends(get_db),
    _principal=Depends(auth.require_roles(*_READ_ROLES)),
) -> Page[SensorRead]:
    query = apply_filters(select(Sensor), Sensor, filters)
    query = apply_sorting(query, Sensor, sort_fields, _SORTABLE_FIELDS, default_field="id")
    return await paginate(db, query, pagination, SensorRead)


@router.get(
    "/{sensor_id}",
    response_model=SensorRead,
    summary="Get a sensor by ID",
    responses={404: {"description": "Sensor not found"}},
)
async def get_sensor(
    sensor_id: int,
    db: AsyncSession = Depends(get_db),
    _principal=Depends(auth.require_roles(*_READ_ROLES)),
) -> SensorRead:
    sensor = await service.get_sensor_or_404(db, sensor_id)
    return SensorRead.model_validate(sensor)


@router.post(
    "",
    response_model=SensorRead,
    status_code=201,
    summary="Register a sensor",
    responses={409: {"description": "A sensor with this tag already exists"}},
)
async def create_sensor(
    payload: SensorCreate,
    db: AsyncSession = Depends(get_db),
    _principal=Depends(auth.require_roles(*_WRITE_ROLES)),
) -> SensorRead:
    sensor = await service.create_sensor(db, payload)
    logger.info("sensor_created", sensor_id=sensor.id, tag=sensor.tag)
    return SensorRead.model_validate(sensor)


@router.patch(
    "/{sensor_id}",
    response_model=SensorRead,
    summary="Update a sensor",
    responses={404: {"description": "Sensor not found"}},
)
async def update_sensor(
    sensor_id: int,
    payload: SensorUpdate,
    db: AsyncSession = Depends(get_db),
    _principal=Depends(auth.require_roles(*_WRITE_ROLES)),
) -> SensorRead:
    sensor = await service.update_sensor(db, sensor_id, payload)
    logger.info("sensor_updated", sensor_id=sensor.id)
    return SensorRead.model_validate(sensor)


@router.delete(
    "/{sensor_id}",
    response_model=SensorRead,
    summary="Decommission a sensor",
    description="Sets status to 'decommissioned' — never physically deletes the row (historical readings reference it).",
    responses={404: {"description": "Sensor not found"}},
)
async def decommission_sensor(
    sensor_id: int,
    db: AsyncSession = Depends(get_db),
    _principal=Depends(auth.require_roles(*_WRITE_ROLES)),
) -> SensorRead:
    sensor = await service.decommission_sensor(db, sensor_id)
    logger.info("sensor_decommissioned", sensor_id=sensor.id)
    return SensorRead.model_validate(sensor)


@router.get(
    "/{sensor_id}/readings",
    response_model=Page[SensorReadingRead],
    summary="List a sensor's readings",
    description="Append-only telemetry history for one sensor — paginated, filterable by time range and quality.",
    responses={404: {"description": "Sensor not found"}},
)
async def list_readings(
    sensor_id: int,
    pagination: PaginationParams = Depends(),
    sort_fields: list[tuple[str, bool]] = Depends(parse_sort),
    filters: SensorReadingFilter = Depends(),
    db: AsyncSession = Depends(get_db),
    _principal=Depends(auth.require_roles(*_READ_ROLES)),
) -> Page[SensorReadingRead]:
    await service.get_sensor_or_404(db, sensor_id)
    query = select(SensorReading).where(SensorReading.sensor_id == sensor_id)
    query = apply_filters(query, SensorReading, filters)
    query = apply_sorting(query, SensorReading, sort_fields, _READING_SORTABLE_FIELDS, default_field="recorded_at")
    return await paginate(db, query, pagination, SensorReadingRead)


@router.post(
    "/{sensor_id}/readings",
    response_model=SensorReadingRead,
    status_code=201,
    summary="Ingest a sensor reading",
    responses={404: {"description": "Sensor not found"}},
)
async def create_reading(
    sensor_id: int,
    payload: SensorReadingCreate,
    db: AsyncSession = Depends(get_db),
    _principal=Depends(auth.require_roles(*_WRITE_ROLES)),
) -> SensorReadingRead:
    reading = await service.create_reading(db, sensor_id, payload)
    logger.info("sensor_reading_ingested", sensor_id=sensor_id, value=reading.value, quality=reading.quality)
    return SensorReadingRead.model_validate(reading)
