"""
Authentication support tables — refresh-token rotation and password-reset flow.

Not part of the original DATABASE_SCHEMA.md table list; added to support the
JWT + refresh-token + forgot/reset-password authentication system. Owned by:
identity-rbac. Both tables store only a SHA-256 hash of the actual token value
— the raw token is never persisted anywhere, only returned to the client once
at issuance, matching standard practice for bearer-token secrets.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, text, func
from sqlalchemy.orm import Mapped, mapped_column

from aegis_db.base import Base


class RefreshToken(Base):
    """
    One row per issued refresh token. Rotation-on-use: refreshing a token
    revokes the old one and issues a new one, recording the chain via
    replaced_by_token_id — this lets a reuse of an already-rotated (and
    therefore potentially stolen) token be detected and the whole chain
    revoked, a standard refresh-token-theft mitigation.
    """

    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    replaced_by_token_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("refresh_tokens.id", ondelete="SET NULL")
    )
    user_agent: Mapped[str | None] = mapped_column(String)
    ip_address: Mapped[str | None] = mapped_column(String)

    __table_args__ = (
        Index("idx_refresh_tokens_user_id", "user_id"),
        Index("idx_refresh_tokens_active", "user_id", postgresql_where=text("revoked_at IS NULL")),
    )


class PasswordResetToken(Base):
    """
    One row per issued password-reset request. Single-use (enforced at the
    application layer by checking used_at IS NULL before honoring a reset),
    short-lived (expires_at typically 15-30 minutes from issuance).
    """

    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    requested_ip: Mapped[str | None] = mapped_column(String)

    __table_args__ = (Index("idx_password_reset_tokens_user_id", "user_id"),)
