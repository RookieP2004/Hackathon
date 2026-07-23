from __future__ import annotations

from datetime import datetime, timezone

from aegis_api_common import ConflictError, InvalidStateError, NotFoundError
from aegis_db.models import Incident, IncidentTimelineEvent
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.incidents.schemas import IncidentCreate, IncidentTimelineEventCreate, IncidentUpdate


async def get_incident_or_404(db: AsyncSession, incident_id: int) -> Incident:
    # Incident's primary key is composite (id, created_at) because the table is
    # native-partitioned by created_at (see aegis_db.models.incidents' module
    # docstring) — `id` alone is still globally unique (one shared sequence), so
    # filtering by it and expecting a single row is safe.
    result = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = result.scalar_one_or_none()
    if incident is None:
        raise NotFoundError(f"Incident {incident_id} not found")
    return incident


async def _log_event(db: AsyncSession, incident_id: int, event_type: str, actor_user_id: int) -> None:
    db.add(
        IncidentTimelineEvent(
            incident_id=incident_id,
            event_type=event_type,
            actor_type="user",
            actor_user_id=actor_user_id,
            event_data={},
        )
    )


async def create_incident(db: AsyncSession, payload: IncidentCreate, *, opened_by: int) -> Incident:
    existing = await db.execute(select(Incident).where(Incident.incident_number == payload.incident_number))
    if existing.scalar_one_or_none() is not None:
        raise ConflictError(f"Incident number '{payload.incident_number}' already exists")

    incident = Incident(
        incident_number=payload.incident_number,
        plant_id=payload.plant_id,
        zone_id=payload.zone_id,
        equipment_id=payload.equipment_id,
        severity=payload.severity,
        status="open",
        ai_generated_summary=payload.ai_generated_summary,
        opened_by_user_id=opened_by,
    )
    db.add(incident)
    await db.flush()
    await _log_event(db, incident.id, "created", opened_by)
    await db.commit()
    return await get_incident_or_404(db, incident.id)


async def update_incident(db: AsyncSession, incident_id: int, payload: IncidentUpdate) -> Incident:
    incident = await get_incident_or_404(db, incident_id)
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(incident, field, value)
    await db.commit()
    return await get_incident_or_404(db, incident_id)


async def acknowledge_incident(db: AsyncSession, incident_id: int, *, actor_user_id: int) -> Incident:
    incident = await get_incident_or_404(db, incident_id)
    if incident.status != "open":
        raise InvalidStateError(f"Incident {incident_id} must be 'open' to acknowledge (currently '{incident.status}')")
    incident.status = "acknowledged"
    incident.acknowledged_by = actor_user_id
    incident.acknowledged_at = datetime.now(timezone.utc)
    await _log_event(db, incident_id, "acknowledged", actor_user_id)
    await db.commit()
    return await get_incident_or_404(db, incident_id)


async def escalate_incident(db: AsyncSession, incident_id: int, *, actor_user_id: int) -> Incident:
    incident = await get_incident_or_404(db, incident_id)
    if incident.status not in ("open", "acknowledged"):
        raise InvalidStateError(f"Incident {incident_id} cannot be escalated from status '{incident.status}'")
    incident.status = "escalated"
    incident.escalated_at = datetime.now(timezone.utc)
    await _log_event(db, incident_id, "escalated", actor_user_id)
    await db.commit()
    return await get_incident_or_404(db, incident_id)


async def add_timeline_event(
    db: AsyncSession, incident_id: int, payload: IncidentTimelineEventCreate, *, actor_user_id: int | None
) -> IncidentTimelineEvent:
    await get_incident_or_404(db, incident_id)
    event = IncidentTimelineEvent(
        incident_id=incident_id,
        event_type=payload.event_type,
        actor_type=payload.actor_type,
        actor_user_id=actor_user_id,
        event_data=payload.event_data,
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)
    return event


async def close_incident(db: AsyncSession, incident_id: int, root_cause: str, *, actor_user_id: int) -> Incident:
    incident = await get_incident_or_404(db, incident_id)
    if incident.status == "closed":
        raise InvalidStateError(f"Incident {incident_id} is already closed")
    incident.status = "closed"
    incident.root_cause = root_cause
    incident.closed_by = actor_user_id
    incident.closed_at = datetime.now(timezone.utc)
    await _log_event(db, incident_id, "closed", actor_user_id)
    await db.commit()
    return await get_incident_or_404(db, incident_id)
