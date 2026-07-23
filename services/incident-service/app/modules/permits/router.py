from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aegis_api_common import Page, PaginationParams, apply_filters, apply_sorting, get_logger, paginate, parse_sort
from aegis_db.models import Permit
from app.auth import auth
from app.db import get_db
from app.modules.permits import service
from app.modules.permits.schemas import PermitCreate, PermitFilter, PermitRead, PermitUpdate

router = APIRouter(prefix="/permits", tags=["permits"])
logger = get_logger("incident-service.permits")

_READ_ROLES = ("system_admin", "plant_admin", "safety_officer", "maintenance_engineer", "operator", "emergency_team")
_WRITE_ROLES = ("system_admin", "plant_admin", "safety_officer")

_SORTABLE_FIELDS = {"id", "permit_number", "status", "valid_from", "valid_to", "created_at"}


@router.get("", response_model=Page[PermitRead], summary="List permits")
async def list_permits(
    pagination: PaginationParams = Depends(),
    sort_fields: list[tuple[str, bool]] = Depends(parse_sort),
    filters: PermitFilter = Depends(),
    db: AsyncSession = Depends(get_db),
    _principal=Depends(auth.require_roles(*_READ_ROLES)),
) -> Page[PermitRead]:
    query = apply_filters(select(Permit), Permit, filters)
    query = apply_sorting(query, Permit, sort_fields, _SORTABLE_FIELDS, default_field="id")
    return await paginate(db, query, pagination, PermitRead)


@router.get(
    "/{permit_id}",
    response_model=PermitRead,
    summary="Get a permit by ID",
    responses={404: {"description": "Permit not found"}},
)
async def get_permit(
    permit_id: int,
    db: AsyncSession = Depends(get_db),
    _principal=Depends(auth.require_roles(*_READ_ROLES)),
) -> PermitRead:
    permit = await service.get_permit_or_404(db, permit_id)
    return PermitRead.model_validate(permit)


@router.post(
    "",
    response_model=PermitRead,
    status_code=201,
    summary="Issue a permit",
    description="Creates a permit in 'draft' status, per ARCHITECTURE.md §19's permit-to-work lifecycle.",
    responses={409: {"description": "Permit number already exists"}},
)
async def create_permit(
    payload: PermitCreate,
    db: AsyncSession = Depends(get_db),
    principal=Depends(auth.require_roles(*_WRITE_ROLES)),
) -> PermitRead:
    permit = await service.create_permit(db, payload, issued_by=principal.user_id)
    logger.info("permit_created", permit_id=permit.id, permit_number=permit.permit_number)
    return PermitRead.model_validate(permit)


@router.patch(
    "/{permit_id}",
    response_model=PermitRead,
    summary="Update a permit",
    responses={404: {"description": "Permit not found"}, 422: {"description": "Permit is in a terminal state"}},
)
async def update_permit(
    permit_id: int,
    payload: PermitUpdate,
    db: AsyncSession = Depends(get_db),
    _principal=Depends(auth.require_roles(*_WRITE_ROLES)),
) -> PermitRead:
    permit = await service.update_permit(db, permit_id, payload)
    logger.info("permit_updated", permit_id=permit.id)
    return PermitRead.model_validate(permit)


@router.delete(
    "/{permit_id}",
    response_model=PermitRead,
    summary="Revoke a permit",
    description="Sets status to 'revoked' — never physically deletes the row (compliance history).",
    responses={404: {"description": "Permit not found"}, 422: {"description": "Permit is already in a terminal state"}},
)
async def revoke_permit(
    permit_id: int,
    db: AsyncSession = Depends(get_db),
    _principal=Depends(auth.require_roles(*_WRITE_ROLES)),
) -> PermitRead:
    permit = await service.revoke_permit(db, permit_id)
    logger.info("permit_revoked", permit_id=permit.id)
    return PermitRead.model_validate(permit)
