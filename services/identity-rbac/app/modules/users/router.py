from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aegis_api_common import Page, PaginationParams, apply_filters, apply_sorting, get_logger, paginate, parse_sort
from aegis_db.models import User
from app.db import get_db
from app.domain.rbac import get_current_user, require_roles
from app.modules.users.schemas import UserCreate, UserFilter, UserRead, UserUpdate
from app.modules.users import service

router = APIRouter(prefix="/users", tags=["users"])
logger = get_logger("identity-rbac.users")

_SORTABLE_FIELDS = {"id", "email", "full_name", "status", "created_at", "last_login_at"}


@router.get(
    "",
    response_model=Page[UserRead],
    summary="List users",
    description="Paginated, filterable, sortable list of user accounts. Requires system_admin or plant_admin.",
)
async def list_users(
    pagination: PaginationParams = Depends(),
    sort_fields: list[tuple[str, bool]] = Depends(parse_sort),
    filters: UserFilter = Depends(),
    db: AsyncSession = Depends(get_db),
    _principal=Depends(require_roles("system_admin", "plant_admin")),
) -> Page[UserRead]:
    query = select(User)
    query = apply_filters(query, User, filters)
    query = apply_sorting(query, User, sort_fields, _SORTABLE_FIELDS, default_field="id")
    return await paginate(db, query, pagination, UserRead)


@router.get(
    "/{user_id}",
    response_model=UserRead,
    summary="Get a user by ID",
    responses={404: {"description": "User not found"}},
)
async def get_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _principal=Depends(require_roles("system_admin", "plant_admin")),
) -> UserRead:
    user = await service.get_user_or_404(db, user_id)
    return UserRead.model_validate(user)


@router.post(
    "",
    response_model=UserRead,
    status_code=201,
    summary="Create a user",
    responses={409: {"description": "Email already in use"}},
)
async def create_user(
    payload: UserCreate,
    db: AsyncSession = Depends(get_db),
    _principal=Depends(require_roles("system_admin", "plant_admin")),
) -> UserRead:
    user = await service.create_user(db, payload)
    logger.info("user_created", user_id=user.id, email=user.email)
    return UserRead.model_validate(user)


@router.patch(
    "/{user_id}",
    response_model=UserRead,
    summary="Update a user",
    responses={404: {"description": "User not found"}},
)
async def update_user(
    user_id: int,
    payload: UserUpdate,
    db: AsyncSession = Depends(get_db),
    _principal=Depends(require_roles("system_admin", "plant_admin")),
) -> UserRead:
    user = await service.update_user(db, user_id, payload)
    logger.info("user_updated", user_id=user.id, fields=list(payload.model_dump(exclude_unset=True).keys()))
    return UserRead.model_validate(user)


@router.delete(
    "/{user_id}",
    response_model=UserRead,
    summary="Deactivate a user (soft delete)",
    description="Never physically deletes the row — see service.deactivate_user's docstring.",
    responses={404: {"description": "User not found"}},
)
async def deactivate_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _principal=Depends(require_roles("system_admin")),
) -> UserRead:
    user = await service.deactivate_user(db, user_id)
    logger.info("user_deactivated", user_id=user.id)
    return UserRead.model_validate(user)
