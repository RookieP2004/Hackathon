from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aegis_api_common import Page, PaginationParams, apply_filters, apply_sorting, get_logger, paginate, parse_sort
from aegis_db.models import Worker
from app.db import get_db
from app.domain.rbac import require_roles
from app.modules.workers.schemas import WorkerCreate, WorkerFilter, WorkerRead, WorkerUpdate
from app.modules.workers import service

router = APIRouter(prefix="/workers", tags=["workers"])
logger = get_logger("identity-rbac.workers")

_SORTABLE_FIELDS = {"id", "badge_id", "full_name", "worker_type", "created_at"}
_READ_ROLES = ("system_admin", "plant_admin", "safety_officer", "maintenance_engineer", "emergency_team")
_WRITE_ROLES = ("system_admin", "plant_admin")


@router.get("", response_model=Page[WorkerRead], summary="List workers")
async def list_workers(
    pagination: PaginationParams = Depends(),
    sort_fields: list[tuple[str, bool]] = Depends(parse_sort),
    filters: WorkerFilter = Depends(),
    db: AsyncSession = Depends(get_db),
    _principal=Depends(require_roles(*_READ_ROLES)),
) -> Page[WorkerRead]:
    query = select(Worker)
    query = apply_filters(query, Worker, filters)
    query = apply_sorting(query, Worker, sort_fields, _SORTABLE_FIELDS, default_field="id")
    return await paginate(db, query, pagination, WorkerRead)


@router.get(
    "/{worker_id}",
    response_model=WorkerRead,
    summary="Get a worker by ID",
    responses={404: {"description": "Worker not found"}},
)
async def get_worker(
    worker_id: int,
    db: AsyncSession = Depends(get_db),
    _principal=Depends(require_roles(*_READ_ROLES)),
) -> WorkerRead:
    worker = await service.get_worker_or_404(db, worker_id)
    return WorkerRead.model_validate(worker)


@router.post(
    "",
    response_model=WorkerRead,
    status_code=201,
    summary="Create a worker",
    responses={409: {"description": "Badge ID already in use"}},
)
async def create_worker(
    payload: WorkerCreate,
    db: AsyncSession = Depends(get_db),
    _principal=Depends(require_roles(*_WRITE_ROLES)),
) -> WorkerRead:
    worker = await service.create_worker(db, payload)
    logger.info("worker_created", worker_id=worker.id, badge_id=worker.badge_id)
    return WorkerRead.model_validate(worker)


@router.patch(
    "/{worker_id}",
    response_model=WorkerRead,
    summary="Update a worker",
    responses={404: {"description": "Worker not found"}},
)
async def update_worker(
    worker_id: int,
    payload: WorkerUpdate,
    db: AsyncSession = Depends(get_db),
    _principal=Depends(require_roles(*_WRITE_ROLES)),
) -> WorkerRead:
    worker = await service.update_worker(db, worker_id, payload)
    logger.info("worker_updated", worker_id=worker.id)
    return WorkerRead.model_validate(worker)


@router.delete(
    "/{worker_id}",
    response_model=WorkerRead,
    summary="Deactivate a worker (soft delete)",
    responses={404: {"description": "Worker not found"}},
)
async def deactivate_worker(
    worker_id: int,
    db: AsyncSession = Depends(get_db),
    _principal=Depends(require_roles(*_WRITE_ROLES)),
) -> WorkerRead:
    worker = await service.deactivate_worker(db, worker_id)
    logger.info("worker_deactivated", worker_id=worker.id)
    return WorkerRead.model_validate(worker)
