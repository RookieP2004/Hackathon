"""
Core authentication business logic. Kept separate from app/api/auth.py so the
HTTP layer stays a thin translation of these calls into request/response
shapes — the same separation-of-concerns principle ARCHITECTURE.md §8.2
applies to every service's domain/ vs api/ layers.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aegis_db.models import AuditLog, PasswordResetToken, RefreshToken, User
from app.config import get_settings
from app.core.security import (
    create_access_token,
    generate_opaque_token,
    hash_opaque_token,
    hash_password,
    verify_password,
)

settings = get_settings()


async def _write_audit_entry(
    db: AsyncSession, *, actor_user_id: int | None, action: str, resource_id: int | None, ip_address: str | None
) -> None:
    """
    Explicit application-level audit entries for events that don't correspond
    to a row UPDATE the users-table trigger (audit_row_change(), migration
    0006) would already capture -- e.g. a failed login attempt changes no row
    at all, but is exactly the kind of security-relevant event ARCHITECTURE.md
    §21.5 says must never go unlogged.
    """
    db.add(
        AuditLog(
            actor_user_id=actor_user_id,
            action=action,
            resource_type="users",
            resource_id=resource_id,
            ip_address=ip_address,
        )
    )


async def login(db: AsyncSession, *, email: str, password: str, ip_address: str | None) -> tuple[str, str, int]:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if user is None or user.password_hash is None or not verify_password(password, user.password_hash):
        # Deliberately identical error whether the email doesn't exist or the
        # password is wrong -- distinguishing the two lets an attacker enumerate
        # valid emails, a well-known login-endpoint anti-pattern.
        await _write_audit_entry(
            db, actor_user_id=user.id if user else None, action="LOGIN_FAILED",
            resource_id=user.id if user else None, ip_address=ip_address,
        )
        await db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    if user.status != "active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is not active")

    access_token = create_access_token(user_id=user.id, role_id=user.default_role_id)
    raw_refresh, refresh_hash = generate_opaque_token()
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=refresh_hash,
            expires_at=datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days),
        )
    )
    user.last_login_at = datetime.now(timezone.utc)  # triggers trg_users_audit via migration 0006
    await _write_audit_entry(db, actor_user_id=user.id, action="LOGIN_SUCCESS", resource_id=user.id, ip_address=ip_address)
    await db.commit()

    return access_token, raw_refresh, settings.jwt_access_token_expire_minutes * 60


async def refresh(db: AsyncSession, *, raw_refresh_token: str) -> tuple[str, str, int]:
    """
    Rotation-on-use (aegis_db.models.auth.RefreshToken's documented mitigation):
    the presented token is revoked and a new one issued every time, chained via
    replaced_by_token_id. Presenting an already-revoked token is treated as a
    signal of possible theft -- the entire chain from that token forward is
    revoked, not just rejected.
    """
    token_hash = hash_opaque_token(raw_refresh_token)
    result = await db.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    token_row = result.scalar_one_or_none()

    unauthorized = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")

    if token_row is None:
        raise unauthorized

    if token_row.revoked_at is not None:
        # Reused a token already rotated away -- revoke the whole subsequent
        # chain as a theft-containment measure.
        await _revoke_chain_from(db, token_row.id)
        await db.commit()
        raise unauthorized

    if token_row.expires_at < datetime.now(timezone.utc):
        raise unauthorized

    user = await db.get(User, token_row.user_id)
    if user is None or user.status != "active":
        raise unauthorized

    new_access_token = create_access_token(user_id=user.id, role_id=user.default_role_id)
    new_raw_refresh, new_refresh_hash = generate_opaque_token()
    new_token_row = RefreshToken(
        user_id=user.id,
        token_hash=new_refresh_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days),
    )
    db.add(new_token_row)
    await db.flush()

    token_row.revoked_at = datetime.now(timezone.utc)
    token_row.replaced_by_token_id = new_token_row.id
    await db.commit()

    return new_access_token, new_raw_refresh, settings.jwt_access_token_expire_minutes * 60


async def _revoke_chain_from(db: AsyncSession, token_id: int) -> None:
    result = await db.execute(select(RefreshToken).where(RefreshToken.id == token_id))
    token_row = result.scalar_one_or_none()
    now = datetime.now(timezone.utc)
    visited = set()
    while token_row is not None and token_row.id not in visited:
        visited.add(token_row.id)
        if token_row.revoked_at is None:
            token_row.revoked_at = now
        if token_row.replaced_by_token_id is None:
            break
        result = await db.execute(select(RefreshToken).where(RefreshToken.id == token_row.replaced_by_token_id))
        token_row = result.scalar_one_or_none()


async def logout(db: AsyncSession, *, raw_refresh_token: str) -> None:
    token_hash = hash_opaque_token(raw_refresh_token)
    result = await db.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    token_row = result.scalar_one_or_none()
    if token_row is not None and token_row.revoked_at is None:
        token_row.revoked_at = datetime.now(timezone.utc)
        await _write_audit_entry(db, actor_user_id=token_row.user_id, action="LOGOUT", resource_id=token_row.user_id, ip_address=None)
        await db.commit()


async def request_password_reset(db: AsyncSession, *, email: str, ip_address: str | None) -> None:
    """
    Always returns successfully regardless of whether the email exists --
    otherwise this endpoint becomes the same account-enumeration vector the
    login endpoint's identical-error-message design already avoids. The actual
    reset token is only generated (and, in a later pass, emailed) when a
    matching active user is found.
    """
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None or user.status != "active":
        return

    raw_token, token_hash = generate_opaque_token()
    db.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=settings.password_reset_token_expire_minutes),
            requested_ip=ip_address,
        )
    )
    await _write_audit_entry(db, actor_user_id=user.id, action="PASSWORD_RESET_REQUESTED", resource_id=user.id, ip_address=ip_address)
    await db.commit()

    # Sending the actual email (with a link embedding raw_token) is an explicit
    # follow-up integration point (Notification Service, ARCHITECTURE.md
    # §11.3) -- not implemented here since it depends on that service's email
    # channel adapter, which is itself a placeholder in the current scaffold.
    # raw_token is deliberately never logged or returned from this function.


async def reset_password(db: AsyncSession, *, raw_token: str, new_password: str) -> None:
    token_hash = hash_opaque_token(raw_token)
    result = await db.execute(select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash))
    token_row = result.scalar_one_or_none()

    invalid = HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset token")

    if token_row is None or token_row.used_at is not None:
        raise invalid
    if token_row.expires_at < datetime.now(timezone.utc):
        raise invalid

    user = await db.get(User, token_row.user_id)
    if user is None:
        raise invalid

    user.password_hash = hash_password(new_password)  # triggers trg_users_audit
    token_row.used_at = datetime.now(timezone.utc)

    # Reset password = assume the account may have been compromised; revoke
    # every existing refresh token so any other active session is logged out.
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
    )
    now = datetime.now(timezone.utc)
    for rt in result.scalars().all():
        rt.revoked_at = now

    await _write_audit_entry(db, actor_user_id=user.id, action="PASSWORD_RESET_COMPLETED", resource_id=user.id, ip_address=None)
    await db.commit()
