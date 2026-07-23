from __future__ import annotations

import ipaddress

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from aegis_db.models import Role, User, UserRoleScope
from app.db import get_db
from app.domain import auth_service
from app.domain.rbac import get_current_user, get_user_scoped_roles
from app.domain.schemas import (
    CurrentUserOut,
    ForgotPasswordRequest,
    GenericMessage,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    ResetPasswordRequest,
    RoleOut,
    TokenPair,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _client_ip(request: Request) -> str | None:
    """
    Returns a validated IP string or None -- never a raw, unvalidated value.
    audit_logs.ip_address is a strict Postgres INET column (DATABASE_SCHEMA.md
    §16), and a malformed value there must not be allowed to fail the audit
    INSERT, since that INSERT shares a transaction with the auth action itself
    (login/reset) -- a bad IP string would otherwise take down login entirely,
    not just the audit trail. Confirmed empirically: Starlette's TestClient
    reports request.client.host as the literal string "testclient", which is
    exactly this failure mode, not just a hypothetical one.
    """
    if request.client is None:
        return None
    host = request.client.host
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return None
    return host


@router.post("/login", response_model=TokenPair)
async def login(payload: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)) -> TokenPair:
    access_token, refresh_token, expires_in = await auth_service.login(
        db, email=payload.email, password=payload.password, ip_address=_client_ip(request)
    )
    return TokenPair(access_token=access_token, refresh_token=refresh_token, expires_in=expires_in)


@router.post("/refresh", response_model=TokenPair)
async def refresh(payload: RefreshRequest, db: AsyncSession = Depends(get_db)) -> TokenPair:
    access_token, refresh_token, expires_in = await auth_service.refresh(db, raw_refresh_token=payload.refresh_token)
    return TokenPair(access_token=access_token, refresh_token=refresh_token, expires_in=expires_in)


@router.post("/logout", response_model=GenericMessage)
async def logout(payload: LogoutRequest, db: AsyncSession = Depends(get_db)) -> GenericMessage:
    await auth_service.logout(db, raw_refresh_token=payload.refresh_token)
    return GenericMessage(message="Logged out")


@router.post("/forgot-password", response_model=GenericMessage)
async def forgot_password(
    payload: ForgotPasswordRequest, request: Request, db: AsyncSession = Depends(get_db)
) -> GenericMessage:
    await auth_service.request_password_reset(db, email=payload.email, ip_address=_client_ip(request))
    # Same response regardless of whether the email matched an account --
    # see auth_service.request_password_reset's docstring.
    return GenericMessage(message="If that email exists, a password reset link has been sent.")


@router.post("/reset-password", response_model=GenericMessage)
async def reset_password(payload: ResetPasswordRequest, db: AsyncSession = Depends(get_db)) -> GenericMessage:
    await auth_service.reset_password(db, raw_token=payload.token, new_password=payload.new_password)
    return GenericMessage(message="Password has been reset. Please log in again.")


@router.get("/me", response_model=CurrentUserOut)
async def me(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> CurrentUserOut:
    default_role = await db.get(Role, user.default_role_id)
    scoped = await get_user_scoped_roles(db, user.id)

    scoped_out: list[dict] = []
    if scoped:
        role_ids = {s.role_id for s in scoped}
        roles_by_id = {
            r.id: r for r in (await db.execute(select(Role).where(Role.id.in_(role_ids)))).scalars()
        }
        scoped_out = [
            {
                "role": roles_by_id[s.role_id].name,
                "plant_id": s.plant_id,
                "zone_id": s.zone_id,
            }
            for s in scoped
        ]

    return CurrentUserOut(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        mfa_enabled=user.mfa_enabled,
        status=user.status,
        last_login_at=user.last_login_at,
        default_role=RoleOut.model_validate(default_role),
        scoped_roles=scoped_out,
    )
