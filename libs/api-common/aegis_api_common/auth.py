"""
Shared JWT verification + RBAC dependencies. Every service verifies the
access token independently (never by calling identity-rbac over the network
per-request) — standard microservice practice, and specifically what
ARCHITECTURE.md §21.3 means by "enforced at the service layer": each service
is its own enforcement point, not a client of one central one.

All services must be configured with the SAME jwt_secret (the shared signing
secret — see root .env.example's JWT_SECRET) since a token issued by
identity-rbac's login endpoint has to verify successfully everywhere else.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aegis_db.models import Role, User, UserRoleScope


@dataclass(frozen=True)
class AuthenticatedPrincipal:
    """
    What every protected endpoint actually needs to know about the caller —
    deliberately not the full ORM User object, so a permission check doesn't
    accidentally depend on lazy-loading a relationship outside its session.
    """

    user_id: int
    default_role_id: int


def decode_access_token(token: str, *, jwt_secret: str, jwt_algorithm: str) -> dict | None:
    try:
        # `require` defensively enforces that exp/sub are actually present,
        # not just verified-if-present -- every real token this codebase
        # mints always sets both, so this changes nothing for a genuine
        # token, only closes off a token missing them by construction.
        payload = jwt.decode(token, jwt_secret, algorithms=[jwt_algorithm], options={"require": ["exp", "sub"]})
    except JWTError:
        return None
    if payload.get("type") != "access":
        return None
    return payload


class AuthDependencies:
    """
    Bound to one service's settings (jwt_secret/jwt_algorithm) and its
    get_db dependency at service-startup time, then used as ordinary FastAPI
    `Depends(...)` throughout that service's routers:

        auth = AuthDependencies(jwt_secret=settings.jwt_secret,
                                 jwt_algorithm=settings.jwt_algorithm,
                                 get_db=get_db)

        @router.get("/", dependencies=[Depends(auth.require_roles("system_admin"))])
    """

    def __init__(self, *, jwt_secret: str, jwt_algorithm: str, get_db) -> None:
        self._jwt_secret = jwt_secret
        self._jwt_algorithm = jwt_algorithm
        self._get_db = get_db
        self._oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)

    def get_current_principal_dependency(self):
        oauth2_scheme = self._oauth2_scheme

        async def _dependency(token: str | None = Depends(oauth2_scheme)) -> AuthenticatedPrincipal:
            unauthorized = HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated",
                headers={"WWW-Authenticate": "Bearer"},
            )
            if token is None:
                raise unauthorized
            payload = decode_access_token(token, jwt_secret=self._jwt_secret, jwt_algorithm=self._jwt_algorithm)
            if payload is None:
                raise unauthorized
            return AuthenticatedPrincipal(user_id=int(payload["sub"]), default_role_id=payload["role_id"])

        return _dependency

    def require_roles(self, *allowed_role_names: str):
        get_principal = self.get_current_principal_dependency()
        get_db = self._get_db

        async def _check(
            principal: AuthenticatedPrincipal = Depends(get_principal),
            db: AsyncSession = Depends(get_db),
        ) -> AuthenticatedPrincipal:
            default_role = await db.get(Role, principal.default_role_id)
            if default_role and default_role.name in allowed_role_names:
                return principal

            result = await db.execute(
                select(UserRoleScope).where(UserRoleScope.user_id == principal.user_id)
            )
            scoped = list(result.scalars().all())
            if scoped:
                role_ids = {s.role_id for s in scoped}
                roles_result = await db.execute(select(Role).where(Role.id.in_(role_ids)))
                if any(r.name in allowed_role_names for r in roles_result.scalars().all()):
                    return principal

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of roles: {', '.join(allowed_role_names)}",
            )

        return _check

    def any_authenticated_user(self):
        """For endpoints that only require a valid session, no specific role."""
        return self.get_current_principal_dependency()
