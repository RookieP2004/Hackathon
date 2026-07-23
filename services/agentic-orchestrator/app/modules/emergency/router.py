from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aegis_api_common import Page, PaginationParams, apply_filters, apply_sorting, get_logger, paginate, parse_sort
from aegis_db.models import EmergencyEvent, EmergencyEventStep, Playbook, PlaybookStep
from app.auth import auth
from app.db import get_db
from app.modules.emergency import service
from app.modules.emergency.schemas import (
    EmergencyEventCreate,
    EmergencyEventFilter,
    EmergencyEventRead,
    EmergencyEventStepCompleteRequest,
    EmergencyEventStepCreate,
    EmergencyEventStepRead,
    PlaybookCreate,
    PlaybookFilter,
    PlaybookRead,
    PlaybookStepCreate,
    PlaybookStepRead,
    PlaybookUpdate,
)

router = APIRouter(prefix="/emergency", tags=["emergency"])
logger = get_logger("agentic-orchestrator.emergency")

_READ_ROLES = ("system_admin", "plant_admin", "safety_officer", "maintenance_engineer", "operator", "emergency_team")
_PLAYBOOK_WRITE_ROLES = ("system_admin", "plant_admin", "safety_officer")
_EVENT_WRITE_ROLES = ("system_admin", "plant_admin", "safety_officer", "emergency_team")
_APPROVAL_ROLES = ("system_admin", "plant_admin", "emergency_team")

_PLAYBOOK_SORTABLE_FIELDS = {"id", "name", "hazard_class", "version", "created_at"}
_EVENT_SORTABLE_FIELDS = {"id", "event_type", "status", "initiated_at", "created_at"}


# ---- Playbooks ----------------------------------------------------------------


@router.get("/playbooks", response_model=Page[PlaybookRead], summary="List playbooks")
async def list_playbooks(
    pagination: PaginationParams = Depends(),
    sort_fields: list[tuple[str, bool]] = Depends(parse_sort),
    filters: PlaybookFilter = Depends(),
    db: AsyncSession = Depends(get_db),
    _principal=Depends(auth.require_roles(*_READ_ROLES)),
) -> Page[PlaybookRead]:
    query = apply_filters(select(Playbook), Playbook, filters)
    query = apply_sorting(query, Playbook, sort_fields, _PLAYBOOK_SORTABLE_FIELDS, default_field="id")
    return await paginate(db, query, pagination, PlaybookRead)


@router.get(
    "/playbooks/{playbook_id}",
    response_model=PlaybookRead,
    summary="Get a playbook by ID",
    responses={404: {"description": "Playbook not found"}},
)
async def get_playbook(
    playbook_id: int,
    db: AsyncSession = Depends(get_db),
    _principal=Depends(auth.require_roles(*_READ_ROLES)),
) -> PlaybookRead:
    playbook = await service.get_playbook_or_404(db, playbook_id)
    return PlaybookRead.model_validate(playbook)


@router.post(
    "/playbooks",
    response_model=PlaybookRead,
    status_code=201,
    summary="Create a playbook",
    description="AGENT_ARCHITECTURE.md §9 — reviewed response templates the Emergency Agent executes against.",
    responses={409: {"description": "A playbook with this name already exists"}},
)
async def create_playbook(
    payload: PlaybookCreate,
    db: AsyncSession = Depends(get_db),
    principal=Depends(auth.require_roles(*_PLAYBOOK_WRITE_ROLES)),
) -> PlaybookRead:
    playbook = await service.create_playbook(db, payload, created_by=principal.user_id)
    logger.info("playbook_created", playbook_id=playbook.id, name=playbook.name)
    return PlaybookRead.model_validate(playbook)


@router.patch(
    "/playbooks/{playbook_id}",
    response_model=PlaybookRead,
    summary="Update a playbook",
    responses={404: {"description": "Playbook not found"}},
)
async def update_playbook(
    playbook_id: int,
    payload: PlaybookUpdate,
    db: AsyncSession = Depends(get_db),
    _principal=Depends(auth.require_roles(*_PLAYBOOK_WRITE_ROLES)),
) -> PlaybookRead:
    playbook = await service.update_playbook(db, playbook_id, payload)
    logger.info("playbook_updated", playbook_id=playbook.id)
    return PlaybookRead.model_validate(playbook)


@router.delete(
    "/playbooks/{playbook_id}",
    response_model=PlaybookRead,
    summary="Deactivate a playbook",
    description="Sets is_active to false — never physically deletes the row (past emergency events reference it).",
    responses={404: {"description": "Playbook not found"}, 422: {"description": "Playbook is already inactive"}},
)
async def deactivate_playbook(
    playbook_id: int,
    db: AsyncSession = Depends(get_db),
    _principal=Depends(auth.require_roles(*_PLAYBOOK_WRITE_ROLES)),
) -> PlaybookRead:
    playbook = await service.deactivate_playbook(db, playbook_id)
    logger.info("playbook_deactivated", playbook_id=playbook.id)
    return PlaybookRead.model_validate(playbook)


@router.get(
    "/playbooks/{playbook_id}/steps",
    response_model=Page[PlaybookStepRead],
    summary="List a playbook's steps",
    responses={404: {"description": "Playbook not found"}},
)
async def list_playbook_steps(
    playbook_id: int,
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    _principal=Depends(auth.require_roles(*_READ_ROLES)),
) -> Page[PlaybookStepRead]:
    await service.get_playbook_or_404(db, playbook_id)
    query = select(PlaybookStep).where(PlaybookStep.playbook_id == playbook_id).order_by(PlaybookStep.step_order.asc())
    return await paginate(db, query, pagination, PlaybookStepRead)


@router.post(
    "/playbooks/{playbook_id}/steps",
    response_model=PlaybookStepRead,
    status_code=201,
    summary="Add a step to a playbook",
    responses={404: {"description": "Playbook not found"}, 409: {"description": "A step already exists at this order"}},
)
async def create_playbook_step(
    playbook_id: int,
    payload: PlaybookStepCreate,
    db: AsyncSession = Depends(get_db),
    _principal=Depends(auth.require_roles(*_PLAYBOOK_WRITE_ROLES)),
) -> PlaybookStepRead:
    step = await service.create_playbook_step(db, playbook_id, payload)
    logger.info("playbook_step_created", playbook_id=playbook_id, step_id=step.id)
    return PlaybookStepRead.model_validate(step)


# ---- Emergency Events ------------------------------------------------------------


@router.get("/events", response_model=Page[EmergencyEventRead], summary="List emergency events")
async def list_events(
    pagination: PaginationParams = Depends(),
    sort_fields: list[tuple[str, bool]] = Depends(parse_sort),
    filters: EmergencyEventFilter = Depends(),
    db: AsyncSession = Depends(get_db),
    _principal=Depends(auth.require_roles(*_READ_ROLES)),
) -> Page[EmergencyEventRead]:
    query = apply_filters(select(EmergencyEvent), EmergencyEvent, filters)
    query = apply_sorting(query, EmergencyEvent, sort_fields, _EVENT_SORTABLE_FIELDS, default_field="id")
    return await paginate(db, query, pagination, EmergencyEventRead)


@router.get(
    "/events/{event_id}",
    response_model=EmergencyEventRead,
    summary="Get an emergency event by ID",
    responses={404: {"description": "Emergency event not found"}},
)
async def get_event(
    event_id: int,
    db: AsyncSession = Depends(get_db),
    _principal=Depends(auth.require_roles(*_READ_ROLES)),
) -> EmergencyEventRead:
    event = await service.get_event_or_404(db, event_id)
    return EmergencyEventRead.model_validate(event)


@router.post(
    "/events",
    response_model=EmergencyEventRead,
    status_code=201,
    summary="Initiate an emergency event",
    description="ARCHITECTURE.md §15 — the Emergency Agent's planner-executor entry point. Status starts as 'initiated'.",
    responses={404: {"description": "Referenced playbook not found"}},
)
async def create_event(
    payload: EmergencyEventCreate,
    db: AsyncSession = Depends(get_db),
    principal=Depends(auth.require_roles(*_EVENT_WRITE_ROLES)),
) -> EmergencyEventRead:
    event = await service.create_event(db, payload, initiated_by=principal.user_id)
    logger.info("emergency_event_initiated", event_id=event.id, event_type=event.event_type)
    return EmergencyEventRead.model_validate(event)


@router.post(
    "/events/{event_id}/resolve",
    response_model=EmergencyEventRead,
    summary="Resolve an emergency event",
    responses={404: {"description": "Emergency event not found"}, 422: {"description": "Already resolved"}},
)
async def resolve_event(
    event_id: int,
    db: AsyncSession = Depends(get_db),
    _principal=Depends(auth.require_roles(*_EVENT_WRITE_ROLES)),
) -> EmergencyEventRead:
    event = await service.resolve_event(db, event_id)
    logger.info("emergency_event_resolved", event_id=event.id)
    return EmergencyEventRead.model_validate(event)


@router.get(
    "/events/{event_id}/steps",
    response_model=Page[EmergencyEventStepRead],
    summary="List an emergency event's execution steps",
    responses={404: {"description": "Emergency event not found"}},
)
async def list_event_steps(
    event_id: int,
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    _principal=Depends(auth.require_roles(*_READ_ROLES)),
) -> Page[EmergencyEventStepRead]:
    await service.get_event_or_404(db, event_id)
    query = select(EmergencyEventStep).where(EmergencyEventStep.emergency_event_id == event_id).order_by(EmergencyEventStep.id.asc())
    return await paginate(db, query, pagination, EmergencyEventStepRead)


@router.post(
    "/events/{event_id}/steps",
    response_model=EmergencyEventStepRead,
    status_code=201,
    summary="Queue an execution step for an emergency event",
    responses={404: {"description": "Emergency event or playbook step not found"}},
)
async def create_event_step(
    event_id: int,
    payload: EmergencyEventStepCreate,
    db: AsyncSession = Depends(get_db),
    _principal=Depends(auth.require_roles(*_EVENT_WRITE_ROLES)),
) -> EmergencyEventStepRead:
    step = await service.create_event_step(db, event_id, payload)
    logger.info("emergency_event_step_created", event_id=event_id, step_id=step.id)
    return EmergencyEventStepRead.model_validate(step)


@router.post(
    "/events/steps/{step_id}/approve",
    response_model=EmergencyEventStepRead,
    summary="Approve an execution step (human-in-the-loop for tier_1/tier_2 autonomy)",
    responses={404: {"description": "Step not found"}, 422: {"description": "Step is not pending"}},
)
async def approve_event_step(
    step_id: int,
    db: AsyncSession = Depends(get_db),
    principal=Depends(auth.require_roles(*_APPROVAL_ROLES)),
) -> EmergencyEventStepRead:
    step = await service.approve_event_step(db, step_id, approved_by=principal.user_id)
    logger.info("emergency_event_step_approved", step_id=step.id)
    return EmergencyEventStepRead.model_validate(step)


@router.post(
    "/events/steps/{step_id}/reject",
    response_model=EmergencyEventStepRead,
    summary="Reject an execution step",
    responses={404: {"description": "Step not found"}, 422: {"description": "Step is not pending"}},
)
async def reject_event_step(
    step_id: int,
    db: AsyncSession = Depends(get_db),
    principal=Depends(auth.require_roles(*_APPROVAL_ROLES)),
) -> EmergencyEventStepRead:
    step = await service.reject_event_step(db, step_id, rejected_by=principal.user_id)
    logger.info("emergency_event_step_rejected", step_id=step.id)
    return EmergencyEventStepRead.model_validate(step)


@router.post(
    "/events/steps/{step_id}/complete",
    response_model=EmergencyEventStepRead,
    summary="Record the execution result of an approved step",
    responses={404: {"description": "Step not found"}, 422: {"description": "Step is not approved"}},
)
async def complete_event_step(
    step_id: int,
    payload: EmergencyEventStepCompleteRequest,
    db: AsyncSession = Depends(get_db),
    _principal=Depends(auth.require_roles(*_EVENT_WRITE_ROLES)),
) -> EmergencyEventStepRead:
    step = await service.complete_event_step(db, step_id, payload)
    logger.info("emergency_event_step_completed", step_id=step.id, status=step.status)
    return EmergencyEventStepRead.model_validate(step)
