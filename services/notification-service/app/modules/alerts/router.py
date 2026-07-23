from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aegis_api_common import Page, PaginationParams, apply_filters, apply_sorting, get_logger, paginate, parse_sort
from aegis_db.models import Alert
from app.auth import auth
from app.db import get_db
from app.modules.alerts import service
from app.modules.alerts.schemas import AlertCreate, AlertFilter, AlertRead

router = APIRouter(prefix="/alerts", tags=["alerts"])
logger = get_logger("notification-service.alerts")

_READ_ROLES = ("system_admin", "plant_admin", "safety_officer", "maintenance_engineer", "operator", "emergency_team")
_WRITE_ROLES = ("system_admin", "plant_admin", "safety_officer", "operator")

_SORTABLE_FIELDS = {"id", "severity", "status", "triggered_at", "created_at"}


@router.get("", response_model=Page[AlertRead], summary="List alerts")
async def list_alerts(
    pagination: PaginationParams = Depends(),
    sort_fields: list[tuple[str, bool]] = Depends(parse_sort),
    filters: AlertFilter = Depends(),
    db: AsyncSession = Depends(get_db),
    _principal=Depends(auth.require_roles(*_READ_ROLES)),
) -> Page[AlertRead]:
    query = apply_filters(select(Alert), Alert, filters)
    query = apply_sorting(query, Alert, sort_fields, _SORTABLE_FIELDS, default_field="id")
    return await paginate(db, query, pagination, AlertRead)


@router.get(
    "/{alert_id}",
    response_model=AlertRead,
    summary="Get an alert by ID",
    responses={404: {"description": "Alert not found"}},
)
async def get_alert(
    alert_id: int,
    db: AsyncSession = Depends(get_db),
    _principal=Depends(auth.require_roles(*_READ_ROLES)),
) -> AlertRead:
    alert = await service.get_alert_or_404(db, alert_id)
    return AlertRead.model_validate(alert)


@router.post(
    "",
    response_model=AlertRead,
    status_code=201,
    summary="Raise an alert",
    description="Created by the system (rule engine / risk fusion) or by a user report — status starts as 'open'.",
)
async def create_alert(
    payload: AlertCreate,
    db: AsyncSession = Depends(get_db),
    _principal=Depends(auth.require_roles(*_READ_ROLES)),
) -> AlertRead:
    alert = await service.create_alert(db, payload)
    logger.info("alert_raised", alert_id=alert.id, severity=alert.severity, alert_type=alert.alert_type)
    return AlertRead.model_validate(alert)


@router.post(
    "/{alert_id}/acknowledge",
    response_model=AlertRead,
    summary="Acknowledge an alert",
    responses={404: {"description": "Alert not found"}, 422: {"description": "Alert is not in 'open' status"}},
)
async def acknowledge_alert(
    alert_id: int,
    db: AsyncSession = Depends(get_db),
    principal=Depends(auth.require_roles(*_WRITE_ROLES)),
) -> AlertRead:
    alert = await service.acknowledge_alert(db, alert_id, actor_user_id=principal.user_id)
    logger.info("alert_acknowledged", alert_id=alert.id)
    return AlertRead.model_validate(alert)


@router.post(
    "/{alert_id}/resolve",
    response_model=AlertRead,
    summary="Resolve an alert",
    responses={404: {"description": "Alert not found"}, 422: {"description": "Alert is already resolved"}},
)
async def resolve_alert(
    alert_id: int,
    db: AsyncSession = Depends(get_db),
    _principal=Depends(auth.require_roles(*_WRITE_ROLES)),
) -> AlertRead:
    alert = await service.resolve_alert(db, alert_id)
    logger.info("alert_resolved", alert_id=alert.id)
    return AlertRead.model_validate(alert)
