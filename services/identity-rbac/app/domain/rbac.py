"""
FastAPI dependencies implementing ARCHITECTURE.md §21's (Role, Resource Scope)
model at the service layer — the second of the three enforcement layers in
§21.3 (API Gateway does coarse-grained checks; this is the fine-grained,
per-resource layer; row-level security at the data layer is the third).
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from aegis_db.models import Role, User, UserRoleScope
from app.core.security import decode_access_token
from app.db import get_db

# tokenUrl is documented, not actually hit by this dependency (we decode the JWT
# directly) -- it's what makes FastAPI's auto-generated OpenAPI docs show the
# correct "Authorize" flow for interactive testing.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


async def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if token is None:
        raise unauthorized

    payload = decode_access_token(token)
    if payload is None:
        raise unauthorized

    user_id = int(payload["sub"])
    result = await db.execute(
        select(User).where(User.id == user_id).options(selectinload(User.worker))
    )
    user = result.scalar_one_or_none()
    if user is None or user.status != "active":
        raise unauthorized
    return user


async def get_user_scoped_roles(db: AsyncSession, user_id: int) -> list[UserRoleScope]:
    result = await db.execute(
        select(UserRoleScope).where(UserRoleScope.user_id == user_id)
    )
    return list(result.scalars().all())


def require_roles(*allowed_role_names: str):
    """
    Dependency factory: `Depends(require_roles("system_admin", "plant_admin"))`.
    Grants access if the user's default role OR any scoped-role grant matches
    one of the allowed names — scope (plant_id/zone_id) narrowing is left to
    the calling route, which knows which specific resource is being accessed;
    this dependency answers "does this user hold this role at all," the
    coarser of the two checks ARCHITECTURE.md §21.3 describes happening at
    this layer.
    """

    async def _check(
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        default_role = await db.get(Role, user.default_role_id)
        if default_role and default_role.name in allowed_role_names:
            return user

        scoped = await get_user_scoped_roles(db, user.id)
        if scoped:
            role_ids = {s.role_id for s in scoped}
            result = await db.execute(select(Role).where(Role.id.in_(role_ids)))
            if any(r.name in allowed_role_names for r in result.scalars().all()):
                return user

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Requires one of roles: {', '.join(allowed_role_names)}",
        )

    return _check
