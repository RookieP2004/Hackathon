from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aegis_api_common import Page, PaginationParams, apply_filters, apply_sorting, get_logger, paginate, parse_sort
from aegis_db.models import WeatherObservation
from app.auth import auth
from app.db import get_db
from app.modules.weather import service
from app.modules.weather.schemas import WeatherObservationCreate, WeatherObservationFilter, WeatherObservationRead

router = APIRouter(prefix="/weather", tags=["weather"])
logger = get_logger("ingestion-gateway.weather")

_READ_ROLES = ("system_admin", "plant_admin", "safety_officer", "maintenance_engineer", "operator", "emergency_team")
_WRITE_ROLES = ("system_admin", "plant_admin")

_SORTABLE_FIELDS = {"id", "observed_at", "plant_id", "temperature_c"}


@router.get(
    "",
    response_model=Page[WeatherObservationRead],
    summary="List weather observations",
    description="Append-only telemetry — paginated, filterable by plant and time range (RISK_FUSION_ENGINE.md environmental inputs).",
)
async def list_observations(
    pagination: PaginationParams = Depends(),
    sort_fields: list[tuple[str, bool]] = Depends(parse_sort),
    filters: WeatherObservationFilter = Depends(),
    db: AsyncSession = Depends(get_db),
    _principal=Depends(auth.require_roles(*_READ_ROLES)),
) -> Page[WeatherObservationRead]:
    query = apply_filters(select(WeatherObservation), WeatherObservation, filters)
    query = apply_sorting(query, WeatherObservation, sort_fields, _SORTABLE_FIELDS, default_field="observed_at")
    return await paginate(db, query, pagination, WeatherObservationRead)


@router.post(
    "",
    response_model=WeatherObservationRead,
    status_code=201,
    summary="Ingest a weather observation",
)
async def create_observation(
    payload: WeatherObservationCreate,
    db: AsyncSession = Depends(get_db),
    _principal=Depends(auth.require_roles(*_WRITE_ROLES)),
) -> WeatherObservationRead:
    observation = await service.create_observation(db, payload)
    logger.info("weather_observation_ingested", plant_id=observation.plant_id, source=observation.source)
    return WeatherObservationRead.model_validate(observation)
