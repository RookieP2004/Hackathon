from __future__ import annotations

from datetime import datetime, timezone

from aegis_api_common import ConflictError, InvalidStateError, NotFoundError
from aegis_db.models import EmergencyEvent, EmergencyEventStep, Playbook, PlaybookStep
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.emergency.schemas import (
    EmergencyEventCreate,
    EmergencyEventStepCompleteRequest,
    EmergencyEventStepCreate,
    PlaybookCreate,
    PlaybookStepCreate,
    PlaybookUpdate,
)

# ---- Playbooks --------------------------------------------------------------


async def get_playbook_or_404(db: AsyncSession, playbook_id: int) -> Playbook:
    playbook = await db.get(Playbook, playbook_id)
    if playbook is None:
        raise NotFoundError(f"Playbook {playbook_id} not found")
    return playbook


async def create_playbook(db: AsyncSession, payload: PlaybookCreate, *, created_by: int) -> Playbook:
    existing = await db.execute(
        select(Playbook).where(Playbook.name == payload.name, Playbook.version == 1)
    )
    if existing.scalar_one_or_none() is not None:
        raise ConflictError(f"Playbook '{payload.name}' version 1 already exists")

    playbook = Playbook(
        name=payload.name,
        hazard_class=payload.hazard_class,
        description=payload.description,
        version=1,
        created_by=created_by,
    )
    db.add(playbook)
    await db.commit()
    await db.refresh(playbook)
    return playbook


async def update_playbook(db: AsyncSession, playbook_id: int, payload: PlaybookUpdate) -> Playbook:
    playbook = await get_playbook_or_404(db, playbook_id)
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(playbook, field, value)
    await db.commit()
    await db.refresh(playbook)
    return playbook


async def deactivate_playbook(db: AsyncSession, playbook_id: int) -> Playbook:
    playbook = await get_playbook_or_404(db, playbook_id)
    if not playbook.is_active:
        raise InvalidStateError(f"Playbook {playbook_id} is already inactive")
    playbook.is_active = False
    await db.commit()
    await db.refresh(playbook)
    return playbook


async def create_playbook_step(db: AsyncSession, playbook_id: int, payload: PlaybookStepCreate) -> PlaybookStep:
    await get_playbook_or_404(db, playbook_id)

    existing = await db.execute(
        select(PlaybookStep).where(
            PlaybookStep.playbook_id == playbook_id, PlaybookStep.step_order == payload.step_order
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise ConflictError(f"Playbook {playbook_id} already has a step at order {payload.step_order}")

    step = PlaybookStep(
        playbook_id=playbook_id,
        step_order=payload.step_order,
        description=payload.description,
        autonomy_tier=payload.autonomy_tier,
        tool_name=payload.tool_name,
        parameters=payload.parameters,
    )
    db.add(step)
    await db.commit()
    await db.refresh(step)
    return step


# ---- Emergency Events ---------------------------------------------------------


async def get_event_or_404(db: AsyncSession, event_id: int) -> EmergencyEvent:
    event = await db.get(EmergencyEvent, event_id)
    if event is None:
        raise NotFoundError(f"Emergency event {event_id} not found")
    return event


async def create_event(db: AsyncSession, payload: EmergencyEventCreate, *, initiated_by: int) -> EmergencyEvent:
    if payload.playbook_id is not None:
        await get_playbook_or_404(db, payload.playbook_id)

    event = EmergencyEvent(
        incident_id=payload.incident_id,
        plant_id=payload.plant_id,
        zone_id=payload.zone_id,
        playbook_id=payload.playbook_id,
        event_type=payload.event_type,
        status="initiated",
        initiated_by_user_id=initiated_by,
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)
    return event


async def resolve_event(db: AsyncSession, event_id: int) -> EmergencyEvent:
    event = await get_event_or_404(db, event_id)
    if event.status == "resolved":
        raise InvalidStateError(f"Emergency event {event_id} is already resolved")
    event.status = "resolved"
    event.resolved_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(event)
    return event


async def create_event_step(db: AsyncSession, event_id: int, payload: EmergencyEventStepCreate) -> EmergencyEventStep:
    await get_event_or_404(db, event_id)
    if payload.playbook_step_id is not None:
        step = await db.get(PlaybookStep, payload.playbook_step_id)
        if step is None:
            raise NotFoundError(f"Playbook step {payload.playbook_step_id} not found")

    event_step = EmergencyEventStep(
        emergency_event_id=event_id,
        playbook_step_id=payload.playbook_step_id,
        status="pending",
    )
    db.add(event_step)
    await db.commit()
    await db.refresh(event_step)
    return event_step


async def get_event_step_or_404(db: AsyncSession, step_id: int) -> EmergencyEventStep:
    step = await db.get(EmergencyEventStep, step_id)
    if step is None:
        raise NotFoundError(f"Emergency event step {step_id} not found")
    return step


async def approve_event_step(db: AsyncSession, step_id: int, *, approved_by: int) -> EmergencyEventStep:
    step = await get_event_step_or_404(db, step_id)
    if step.status != "pending":
        raise InvalidStateError(f"Emergency event step {step_id} must be 'pending' to approve (currently '{step.status}')")
    step.status = "approved"
    step.approved_by = approved_by
    step.approved_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(step)
    return step


async def reject_event_step(db: AsyncSession, step_id: int, *, rejected_by: int) -> EmergencyEventStep:
    step = await get_event_step_or_404(db, step_id)
    if step.status != "pending":
        raise InvalidStateError(f"Emergency event step {step_id} must be 'pending' to reject (currently '{step.status}')")
    step.status = "rejected"
    step.approved_by = rejected_by
    step.approved_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(step)
    return step


async def complete_event_step(db: AsyncSession, step_id: int, payload: EmergencyEventStepCompleteRequest) -> EmergencyEventStep:
    step = await get_event_step_or_404(db, step_id)
    if step.status != "approved":
        raise InvalidStateError(f"Emergency event step {step_id} must be 'approved' to complete (currently '{step.status}')")
    step.status = "completed" if payload.success else "failed"
    step.executed_at = datetime.now(timezone.utc)
    step.result = payload.result
    await db.commit()
    await db.refresh(step)
    return step
