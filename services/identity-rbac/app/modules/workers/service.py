from __future__ import annotations

from aegis_api_common import ConflictError, NotFoundError
from aegis_db.models import Worker
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.workers.schemas import WorkerCreate, WorkerUpdate


async def get_worker_or_404(db: AsyncSession, worker_id: int) -> Worker:
    worker = await db.get(Worker, worker_id)
    if worker is None:
        raise NotFoundError(f"Worker {worker_id} not found")
    return worker


async def create_worker(db: AsyncSession, payload: WorkerCreate) -> Worker:
    existing = await db.execute(select(Worker).where(Worker.badge_id == payload.badge_id))
    if existing.scalar_one_or_none() is not None:
        raise ConflictError(f"A worker with badge ID {payload.badge_id} already exists")

    worker = Worker(
        employer_id=payload.employer_id,
        badge_id=payload.badge_id,
        full_name=payload.full_name,
        worker_type=payload.worker_type,
        user_id=payload.user_id,
        certifications=payload.certifications,
        active=True,
    )
    db.add(worker)
    await db.commit()
    await db.refresh(worker)
    return worker


async def update_worker(db: AsyncSession, worker_id: int, payload: WorkerUpdate) -> Worker:
    worker = await get_worker_or_404(db, worker_id)
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(worker, field, value)
    await db.commit()
    await db.refresh(worker)
    return worker


async def deactivate_worker(db: AsyncSession, worker_id: int) -> Worker:
    worker = await get_worker_or_404(db, worker_id)
    worker.active = False
    await db.commit()
    await db.refresh(worker)
    return worker
