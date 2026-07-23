from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aegis_api_common import Page, PaginationParams, apply_filters, apply_sorting, get_logger, paginate, parse_sort
from aegis_db.models import Incident, IncidentTimelineEvent
from app.auth import auth
from app.db import get_db
from app.modules.incidents import service
from app.modules.incidents.schemas import (
    IncidentCloseRequest,
    IncidentCreate,
    IncidentFilter,
    IncidentRead,
    IncidentTimelineEventCreate,
    IncidentTimelineEventRead,
    IncidentUpdate,
)

router = APIRouter(prefix="/incidents", tags=["incidents"])
logger = get_logger("incident-service.incidents")

_READ_ROLES = ("system_admin", "plant_admin", "safety_officer", "maintenance_engineer", "operator", "emergency_team")
_WRITE_ROLES = ("system_admin", "plant_admin", "safety_officer")

_SORTABLE_FIELDS = {"id", "incident_number", "severity", "status", "opened_at", "created_at"}


@router.get("", response_model=Page[IncidentRead], summary="List incidents")
async def list_incidents(
    pagination: PaginationParams = Depends(),
    sort_fields: list[tuple[str, bool]] = Depends(parse_sort),
    filters: IncidentFilter = Depends(),
    db: AsyncSession = Depends(get_db),
    _principal=Depends(auth.require_roles(*_READ_ROLES)),
) -> Page[IncidentRead]:
    query = apply_filters(select(Incident), Incident, filters)
    query = apply_sorting(query, Incident, sort_fields, _SORTABLE_FIELDS, default_field="id")
    return await paginate(db, query, pagination, IncidentRead)


@router.get(
    "/{incident_id}",
    response_model=IncidentRead,
    summary="Get an incident by ID",
    responses={404: {"description": "Incident not found"}},
)
async def get_incident(
    incident_id: int,
    db: AsyncSession = Depends(get_db),
    _principal=Depends(auth.require_roles(*_READ_ROLES)),
) -> IncidentRead:
    incident = await service.get_incident_or_404(db, incident_id)
    return IncidentRead.model_validate(incident)


@router.post(
    "",
    response_model=IncidentRead,
    status_code=201,
    summary="Open an incident",
    responses={409: {"description": "Incident number already exists"}},
)
async def create_incident(
    payload: IncidentCreate,
    db: AsyncSession = Depends(get_db),
    principal=Depends(auth.require_roles(*_READ_ROLES)),
) -> IncidentRead:
    incident = await service.create_incident(db, payload, opened_by=principal.user_id)
    logger.info("incident_opened", incident_id=incident.id, severity=incident.severity)
    return IncidentRead.model_validate(incident)


@router.patch(
    "/{incident_id}",
    response_model=IncidentRead,
    summary="Update an incident",
    responses={404: {"description": "Incident not found"}},
)
async def update_incident(
    incident_id: int,
    payload: IncidentUpdate,
    db: AsyncSession = Depends(get_db),
    _principal=Depends(auth.require_roles(*_WRITE_ROLES)),
) -> IncidentRead:
    incident = await service.update_incident(db, incident_id, payload)
    logger.info("incident_updated", incident_id=incident.id)
    return IncidentRead.model_validate(incident)


@router.post(
    "/{incident_id}/acknowledge",
    response_model=IncidentRead,
    summary="Acknowledge an incident",
    responses={404: {"description": "Incident not found"}, 422: {"description": "Incident is not in 'open' status"}},
)
async def acknowledge_incident(
    incident_id: int,
    db: AsyncSession = Depends(get_db),
    principal=Depends(auth.require_roles(*_WRITE_ROLES)),
) -> IncidentRead:
    incident = await service.acknowledge_incident(db, incident_id, actor_user_id=principal.user_id)
    logger.info("incident_acknowledged", incident_id=incident.id)
    return IncidentRead.model_validate(incident)


@router.post(
    "/{incident_id}/escalate",
    response_model=IncidentRead,
    summary="Escalate an incident",
    responses={404: {"description": "Incident not found"}, 422: {"description": "Incident cannot be escalated from its current status"}},
)
async def escalate_incident(
    incident_id: int,
    db: AsyncSession = Depends(get_db),
    principal=Depends(auth.require_roles(*_WRITE_ROLES)),
) -> IncidentRead:
    incident = await service.escalate_incident(db, incident_id, actor_user_id=principal.user_id)
    logger.info("incident_escalated", incident_id=incident.id)
    return IncidentRead.model_validate(incident)


@router.post(
    "/{incident_id}/close",
    response_model=IncidentRead,
    summary="Close an incident",
    description="Requires a documented root cause. Never physically deletes the row.",
    responses={404: {"description": "Incident not found"}, 422: {"description": "Incident is already closed"}},
)
async def close_incident(
    incident_id: int,
    payload: IncidentCloseRequest,
    db: AsyncSession = Depends(get_db),
    principal=Depends(auth.require_roles(*_WRITE_ROLES)),
) -> IncidentRead:
    incident = await service.close_incident(db, incident_id, payload.root_cause, actor_user_id=principal.user_id)
    logger.info("incident_closed", incident_id=incident.id)
    return IncidentRead.model_validate(incident)


@router.post(
    "/{incident_id}/timeline",
    response_model=IncidentTimelineEventRead,
    status_code=201,
    summary="Append a timeline event",
    description="For orchestrated automation (Emergency Response Orchestrator) recording events beyond the fixed lifecycle transitions this module logs internally. Append-only — mutation is blocked at the database level.",
    responses={404: {"description": "Incident not found"}},
)
async def add_timeline_event(
    incident_id: int,
    payload: IncidentTimelineEventCreate,
    db: AsyncSession = Depends(get_db),
    principal=Depends(auth.require_roles(*_WRITE_ROLES)),
) -> IncidentTimelineEventRead:
    event = await service.add_timeline_event(db, incident_id, payload, actor_user_id=principal.user_id)
    logger.info("timeline_event_added", incident_id=incident_id, event_type=payload.event_type)
    return IncidentTimelineEventRead.model_validate(event)


@router.get(
    "/{incident_id}/timeline",
    response_model=Page[IncidentTimelineEventRead],
    summary="List an incident's timeline events",
    description="Append-only audit trail — mutation is blocked at the database level, not just the API.",
    responses={404: {"description": "Incident not found"}},
)
async def list_timeline(
    incident_id: int,
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    _principal=Depends(auth.require_roles(*_READ_ROLES)),
) -> Page[IncidentTimelineEventRead]:
    await service.get_incident_or_404(db, incident_id)
    query = (
        select(IncidentTimelineEvent)
        .where(IncidentTimelineEvent.incident_id == incident_id)
        .order_by(IncidentTimelineEvent.occurred_at.asc())
    )
    return await paginate(db, query, pagination, IncidentTimelineEventRead)
