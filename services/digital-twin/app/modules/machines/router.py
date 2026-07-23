from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from aegis_api_common import Page, PaginationParams, get_logger, paginate, parse_sort
from app.auth import auth
from app.db import get_db
from app.modules.machines.schemas import MachineCreate, MachineFilter, MachineRead, MachineUpdate
from app.modules.machines import service

router = APIRouter(prefix="/machines", tags=["machines"])
logger = get_logger("digital-twin.machines")

_READ_ROLES = ("system_admin", "plant_admin", "safety_officer", "maintenance_engineer", "operator", "emergency_team")
_WRITE_ROLES = ("system_admin", "plant_admin", "maintenance_engineer")


@router.get("", response_model=Page[MachineRead], summary="List machines")
async def list_machines(
    pagination: PaginationParams = Depends(),
    sort_fields: list[tuple[str, bool]] = Depends(parse_sort),
    filters: MachineFilter = Depends(),
    db: AsyncSession = Depends(get_db),
    _principal=Depends(auth.require_roles(*_READ_ROLES)),
) -> Page[MachineRead]:
    query = service.apply_machine_filters(service.base_query(), filters)
    query = service.apply_machine_sort(query, sort_fields)
    return await paginate(db, query, pagination, MachineRead, transform=service.to_read_dict)


@router.get(
    "/{machine_id}",
    response_model=MachineRead,
    summary="Get a machine by ID",
    responses={404: {"description": "Machine not found"}},
)
async def get_machine(
    machine_id: int,
    db: AsyncSession = Depends(get_db),
    _principal=Depends(auth.require_roles(*_READ_ROLES)),
) -> MachineRead:
    equipment = await service.get_machine_or_404(db, machine_id)
    return MachineRead.model_validate(service.to_read_dict(equipment))


@router.post(
    "",
    response_model=MachineRead,
    status_code=201,
    summary="Register a machine",
    description="Creates the underlying Equipment row and its Machine extension row together, in one transaction.",
    responses={409: {"description": "A machine with this tag already exists in the zone"}},
)
async def create_machine(
    payload: MachineCreate,
    db: AsyncSession = Depends(get_db),
    _principal=Depends(auth.require_roles(*_WRITE_ROLES)),
) -> MachineRead:
    equipment = await service.create_machine(db, payload)
    logger.info("machine_created", machine_id=equipment.id, tag=equipment.tag)
    return MachineRead.model_validate(service.to_read_dict(equipment))


@router.patch(
    "/{machine_id}",
    response_model=MachineRead,
    summary="Update a machine",
    responses={404: {"description": "Machine not found"}},
)
async def update_machine(
    machine_id: int,
    payload: MachineUpdate,
    db: AsyncSession = Depends(get_db),
    _principal=Depends(auth.require_roles(*_WRITE_ROLES)),
) -> MachineRead:
    equipment = await service.update_machine(db, machine_id, payload)
    logger.info("machine_updated", machine_id=equipment.id)
    return MachineRead.model_validate(service.to_read_dict(equipment))


@router.delete(
    "/{machine_id}",
    response_model=MachineRead,
    summary="Decommission a machine",
    description="Sets status to 'decommissioned' — never physically deletes the row (maintenance/sensor/incident history references it).",
    responses={404: {"description": "Machine not found"}},
)
async def decommission_machine(
    machine_id: int,
    db: AsyncSession = Depends(get_db),
    _principal=Depends(auth.require_roles("system_admin", "plant_admin")),
) -> MachineRead:
    equipment = await service.decommission_machine(db, machine_id)
    logger.info("machine_decommissioned", machine_id=equipment.id)
    return MachineRead.model_validate(service.to_read_dict(equipment))
