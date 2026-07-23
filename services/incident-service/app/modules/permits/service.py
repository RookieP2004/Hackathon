from __future__ import annotations

from aegis_api_common import ConflictError, InvalidStateError, NotFoundError
from aegis_db.models import Permit
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.permits.schemas import PermitCreate, PermitUpdate

_TERMINAL_STATUSES = {"closed", "revoked"}


async def get_permit_or_404(db: AsyncSession, permit_id: int) -> Permit:
    permit = await db.get(Permit, permit_id)
    if permit is None:
        raise NotFoundError(f"Permit {permit_id} not found")
    return permit


async def create_permit(db: AsyncSession, payload: PermitCreate, *, issued_by: int) -> Permit:
    existing = await db.execute(select(Permit).where(Permit.permit_number == payload.permit_number))
    if existing.scalar_one_or_none() is not None:
        raise ConflictError(f"Permit number '{payload.permit_number}' already exists")

    permit = Permit(
        permit_number=payload.permit_number,
        permit_type_id=payload.permit_type_id,
        worker_id=payload.worker_id,
        zone_id=payload.zone_id,
        equipment_id=payload.equipment_id,
        issued_by=issued_by,
        cosigned_by=payload.cosigned_by,
        status="draft",
        valid_from=payload.valid_from,
        valid_to=payload.valid_to,
        conditions=payload.conditions,
    )
    db.add(permit)
    await db.commit()
    await db.refresh(permit)
    return permit


async def update_permit(db: AsyncSession, permit_id: int, payload: PermitUpdate) -> Permit:
    permit = await get_permit_or_404(db, permit_id)

    if permit.status in _TERMINAL_STATUSES:
        raise InvalidStateError(f"Permit {permit_id} is already '{permit.status}' and cannot be modified")

    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(permit, field, value)

    await db.commit()
    await db.refresh(permit)
    return permit


async def revoke_permit(db: AsyncSession, permit_id: int) -> Permit:
    permit = await get_permit_or_404(db, permit_id)
    if permit.status in _TERMINAL_STATUSES:
        raise InvalidStateError(f"Permit {permit_id} is already '{permit.status}'")
    permit.status = "revoked"
    await db.commit()
    await db.refresh(permit)
    return permit
