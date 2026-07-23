from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aegis_api_common import Page, PaginationParams, apply_filters, apply_sorting, get_logger, paginate, parse_sort
from aegis_db.models import MaintenanceRecord
from app.auth import auth
from app.db import get_db
from app.modules.maintenance import service
from app.modules.maintenance.schemas import (
    MaintenanceCompleteRequest,
    MaintenanceRecordCreate,
    MaintenanceRecordFilter,
    MaintenanceRecordRead,
    MaintenanceRecordUpdate,
)

router = APIRouter(prefix="/maintenance", tags=["maintenance"])
logger = get_logger("predictive-risk-engine.maintenance")

_READ_ROLES = ("system_admin", "plant_admin", "safety_officer", "maintenance_engineer", "operator")
_WRITE_ROLES = ("system_admin", "plant_admin", "maintenance_engineer", "safety_officer")

_SORTABLE_FIELDS = {"id", "status", "scheduled_date", "created_at"}


@router.get("", response_model=Page[MaintenanceRecordRead], summary="List maintenance records")
async def list_records(
    pagination: PaginationParams = Depends(),
    sort_fields: list[tuple[str, bool]] = Depends(parse_sort),
    filters: MaintenanceRecordFilter = Depends(),
    db: AsyncSession = Depends(get_db),
    _principal=Depends(auth.require_roles(*_READ_ROLES)),
) -> Page[MaintenanceRecordRead]:
    query = apply_filters(select(MaintenanceRecord), MaintenanceRecord, filters)
    query = apply_sorting(query, MaintenanceRecord, sort_fields, _SORTABLE_FIELDS, default_field="id")
    return await paginate(db, query, pagination, MaintenanceRecordRead)


@router.get(
    "/{record_id}",
    response_model=MaintenanceRecordRead,
    summary="Get a maintenance record by ID",
    responses={404: {"description": "Maintenance record not found"}},
)
async def get_record(
    record_id: int,
    db: AsyncSession = Depends(get_db),
    _principal=Depends(auth.require_roles(*_READ_ROLES)),
) -> MaintenanceRecordRead:
    record = await service.get_record_or_404(db, record_id)
    return MaintenanceRecordRead.model_validate(record)


@router.post(
    "",
    response_model=MaintenanceRecordRead,
    status_code=201,
    summary="Schedule a maintenance record",
)
async def create_record(
    payload: MaintenanceRecordCreate,
    db: AsyncSession = Depends(get_db),
    principal=Depends(auth.require_roles(*_WRITE_ROLES)),
) -> MaintenanceRecordRead:
    record = await service.create_record(db, payload, requested_by=principal.user_id)
    logger.info("maintenance_record_created", record_id=record.id, equipment_id=record.equipment_id)
    return MaintenanceRecordRead.model_validate(record)


@router.patch(
    "/{record_id}",
    response_model=MaintenanceRecordRead,
    summary="Update a maintenance record",
    responses={404: {"description": "Not found"}, 422: {"description": "Record is in a terminal state"}},
)
async def update_record(
    record_id: int,
    payload: MaintenanceRecordUpdate,
    db: AsyncSession = Depends(get_db),
    _principal=Depends(auth.require_roles(*_WRITE_ROLES)),
) -> MaintenanceRecordRead:
    record = await service.update_record(db, record_id, payload)
    logger.info("maintenance_record_updated", record_id=record.id)
    return MaintenanceRecordRead.model_validate(record)


@router.post(
    "/{record_id}/complete",
    response_model=MaintenanceRecordRead,
    summary="Complete a maintenance record",
    responses={404: {"description": "Not found"}, 422: {"description": "Record is already in a terminal state"}},
)
async def complete_record(
    record_id: int,
    payload: MaintenanceCompleteRequest,
    db: AsyncSession = Depends(get_db),
    _principal=Depends(auth.require_roles(*_WRITE_ROLES)),
) -> MaintenanceRecordRead:
    record = await service.complete_record(db, record_id, payload)
    logger.info("maintenance_record_completed", record_id=record.id)
    return MaintenanceRecordRead.model_validate(record)


@router.post(
    "/{record_id}/cancel",
    response_model=MaintenanceRecordRead,
    summary="Cancel a maintenance record",
    responses={404: {"description": "Not found"}, 422: {"description": "Record is already in a terminal state"}},
)
async def cancel_record(
    record_id: int,
    db: AsyncSession = Depends(get_db),
    _principal=Depends(auth.require_roles(*_WRITE_ROLES)),
) -> MaintenanceRecordRead:
    record = await service.cancel_record(db, record_id)
    logger.info("maintenance_record_cancelled", record_id=record.id)
    return MaintenanceRecordRead.model_validate(record)
