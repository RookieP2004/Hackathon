from __future__ import annotations

from datetime import datetime, timezone

from aegis_api_common import InvalidStateError, NotFoundError
from aegis_db.models import MaintenanceRecord
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.maintenance.schemas import (
    MaintenanceCompleteRequest,
    MaintenanceRecordCreate,
    MaintenanceRecordUpdate,
)

_TERMINAL_STATUSES = {"completed", "cancelled"}


async def get_record_or_404(db: AsyncSession, record_id: int) -> MaintenanceRecord:
    record = await db.get(MaintenanceRecord, record_id)
    if record is None:
        raise NotFoundError(f"Maintenance record {record_id} not found")
    return record


async def create_record(db: AsyncSession, payload: MaintenanceRecordCreate, *, requested_by: int) -> MaintenanceRecord:
    record = MaintenanceRecord(
        equipment_id=payload.equipment_id,
        maintenance_type_id=payload.maintenance_type_id,
        requested_by=requested_by,
        performed_by=payload.performed_by,
        related_prediction_id=payload.related_prediction_id,
        status="scheduled",
        scheduled_date=payload.scheduled_date,
        description=payload.description,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


async def update_record(db: AsyncSession, record_id: int, payload: MaintenanceRecordUpdate) -> MaintenanceRecord:
    record = await get_record_or_404(db, record_id)
    if record.status in _TERMINAL_STATUSES:
        raise InvalidStateError(f"Maintenance record {record_id} is already '{record.status}' and cannot be modified")

    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(record, field, value)

    await db.commit()
    await db.refresh(record)
    return record


async def complete_record(db: AsyncSession, record_id: int, payload: MaintenanceCompleteRequest) -> MaintenanceRecord:
    record = await get_record_or_404(db, record_id)
    if record.status in _TERMINAL_STATUSES:
        raise InvalidStateError(f"Maintenance record {record_id} is already '{record.status}'")

    record.status = "completed"
    record.findings = payload.findings
    record.parts_used = payload.parts_used
    record.cost = payload.cost
    record.completed_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(record)
    return record


async def cancel_record(db: AsyncSession, record_id: int) -> MaintenanceRecord:
    record = await get_record_or_404(db, record_id)
    if record.status in _TERMINAL_STATUSES:
        raise InvalidStateError(f"Maintenance record {record_id} is already '{record.status}'")
    record.status = "cancelled"
    await db.commit()
    await db.refresh(record)
    return record
