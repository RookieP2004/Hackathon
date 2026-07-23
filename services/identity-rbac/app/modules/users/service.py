from __future__ import annotations

from aegis_api_common import ConflictError, NotFoundError
from aegis_db.models import User
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.modules.users.schemas import UserCreate, UserUpdate


async def get_user_or_404(db: AsyncSession, user_id: int) -> User:
    user = await db.get(User, user_id)
    if user is None:
        raise NotFoundError(f"User {user_id} not found")
    return user


async def create_user(db: AsyncSession, payload: UserCreate) -> User:
    existing = await db.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none() is not None:
        raise ConflictError(f"A user with email {payload.email} already exists")

    user = User(
        email=payload.email,
        full_name=payload.full_name,
        default_role_id=payload.default_role_id,
        password_hash=hash_password(payload.password) if payload.password else None,
        status="active",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def update_user(db: AsyncSession, user_id: int, payload: UserUpdate) -> User:
    user = await get_user_or_404(db, user_id)
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(user, field, value)
    await db.commit()
    await db.refresh(user)
    return user


async def deactivate_user(db: AsyncSession, user_id: int) -> User:
    """
    Soft delete only -- a user row is never actually removed, both because
    other tables (incidents.opened_by_user_id, audit_logs.actor_user_id, ...)
    reference it with ON DELETE SET NULL/RESTRICT precisely so historical
    records survive, and because DATABASE_SCHEMA.md §21.5 treats user
    lifecycle changes themselves as compliance-relevant, auditable events --
    an actually-deleted row can't be audited after the fact.
    """
    user = await get_user_or_404(db, user_id)
    user.status = "deactivated"
    await db.commit()
    await db.refresh(user)
    return user
