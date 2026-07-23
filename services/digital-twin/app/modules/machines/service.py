from __future__ import annotations

from aegis_api_common import ConflictError, NotFoundError
from aegis_db.models import Equipment, Machine
from fastapi import HTTPException, status
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.machines.schemas import MachineCreate, MachineFilter, MachineUpdate

# Machine spans two tables sharing a primary key (DATABASE_SCHEMA.md §5.2) —
# the generic aegis_api_common.apply_filters/apply_sorting helpers assume a
# single model, so filtering/sorting here is applied directly against the
# joined query instead of going through them. This is a deliberate, narrow
# exception to the shared-helper pattern used everywhere else in this API,
# not an oversight.


def base_query() -> Select:
    return select(Equipment).join(Machine, Machine.equipment_id == Equipment.id).options(selectinload(Equipment.machine))


def apply_machine_filters(query: Select, filters: MachineFilter) -> Select:
    if filters.zone_id is not None:
        query = query.where(Equipment.zone_id == filters.zone_id)
    if filters.status is not None:
        query = query.where(Equipment.status == filters.status)
    if filters.criticality_gte is not None:
        query = query.where(Equipment.criticality >= filters.criticality_gte)
    if filters.tag_ilike is not None:
        query = query.where(Equipment.tag.ilike(f"%{filters.tag_ilike}%"))
    if filters.machine_class is not None:
        query = query.where(Machine.machine_class == filters.machine_class)
    return query


def apply_machine_sort(query: Select, sort_fields: list[tuple[str, bool]]) -> Select:
    allowed = {"id": Equipment.id, "tag": Equipment.tag, "name": Equipment.name, "criticality": Equipment.criticality, "created_at": Equipment.created_at}
    if not sort_fields:
        return query.order_by(Equipment.id.asc())
    for field, descending in sort_fields:
        if field not in allowed:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Cannot sort by '{field}'. Allowed: {', '.join(allowed)}")
        column = allowed[field]
        query = query.order_by(column.desc() if descending else column.asc())
    return query


def to_read_dict(equipment: Equipment) -> dict:
    machine = equipment.machine
    return {
        "id": equipment.id,
        "tag": equipment.tag,
        "name": equipment.name,
        "zone_id": equipment.zone_id,
        "equipment_type_id": equipment.equipment_type_id,
        "manufacturer": equipment.manufacturer,
        "model_number": equipment.model_number,
        "serial_number": equipment.serial_number,
        "install_date": equipment.install_date,
        "criticality": equipment.criticality,
        "status": equipment.status,
        "machine_class": machine.machine_class,
        "rated_power_kw": float(machine.rated_power_kw) if machine.rated_power_kw is not None else None,
        "rated_rpm": machine.rated_rpm,
        "control_system": machine.control_system,
        "plc_tag": machine.plc_tag,
        "created_at": equipment.created_at,
        "updated_at": equipment.updated_at,
    }


async def get_machine_or_404(db: AsyncSession, machine_id: int) -> Equipment:
    result = await db.execute(base_query().where(Equipment.id == machine_id))
    equipment = result.scalar_one_or_none()
    if equipment is None:
        raise NotFoundError(f"Machine {machine_id} not found")
    return equipment


async def create_machine(db: AsyncSession, payload: MachineCreate) -> Equipment:
    existing = await db.execute(select(Equipment).where(Equipment.zone_id == payload.zone_id, Equipment.tag == payload.tag))
    if existing.scalar_one_or_none() is not None:
        raise ConflictError(f"Equipment with tag '{payload.tag}' already exists in zone {payload.zone_id}")

    equipment = Equipment(
        zone_id=payload.zone_id,
        equipment_type_id=payload.equipment_type_id,
        tag=payload.tag,
        name=payload.name,
        manufacturer=payload.manufacturer,
        model_number=payload.model_number,
        serial_number=payload.serial_number,
        install_date=payload.install_date,
        criticality=payload.criticality,
        status="operational",
    )
    db.add(equipment)
    await db.flush()  # assigns equipment.id, needed for the Machine FK below, within the same transaction

    machine = Machine(
        equipment_id=equipment.id,
        machine_class=payload.machine_class,
        rated_power_kw=payload.rated_power_kw,
        rated_rpm=payload.rated_rpm,
        control_system=payload.control_system,
        plc_tag=payload.plc_tag,
    )
    db.add(machine)
    await db.commit()

    return await get_machine_or_404(db, equipment.id)


async def update_machine(db: AsyncSession, machine_id: int, payload: MachineUpdate) -> Equipment:
    equipment = await get_machine_or_404(db, machine_id)
    data = payload.model_dump(exclude_unset=True)

    equipment_fields = {"name", "criticality", "status"}
    machine_fields = {"rated_power_kw", "rated_rpm", "control_system", "plc_tag"}

    for field in equipment_fields & data.keys():
        setattr(equipment, field, data[field])
    for field in machine_fields & data.keys():
        setattr(equipment.machine, field, data[field])

    await db.commit()
    return await get_machine_or_404(db, machine_id)


async def decommission_machine(db: AsyncSession, machine_id: int) -> Equipment:
    equipment = await get_machine_or_404(db, machine_id)
    equipment.status = "decommissioned"
    await db.commit()
    return await get_machine_or_404(db, machine_id)
