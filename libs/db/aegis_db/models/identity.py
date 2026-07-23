"""
Users, workers, RBAC scoping, shifts — DATABASE_SCHEMA.md §6. Owned by: identity-rbac.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    String,
    Time,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import CITEXT, JSONB, TSRANGE
from sqlalchemy.orm import Mapped, mapped_column, relationship

from aegis_db.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(CITEXT, unique=True, nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String)
    full_name: Mapped[str] = mapped_column(String, nullable=False)
    default_role_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("roles.id", ondelete="RESTRICT"), nullable=False)
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    status: Mapped[str] = mapped_column(String, nullable=False, server_default="active")
    last_login_at: Mapped[datetime | None] = mapped_column()

    __table_args__ = (
        CheckConstraint("status IN ('active','suspended','deactivated')", name="status_valid"),
        Index("idx_users_default_role_id", "default_role_id"),
    )

    worker: Mapped["Worker | None"] = relationship(back_populates="user", uselist=False)


class Worker(Base, TimestampMixin):
    __tablename__ = "workers"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL"), unique=True
    )
    employer_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("employers.id", ondelete="RESTRICT"), nullable=False)
    badge_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String, nullable=False)
    worker_type: Mapped[str] = mapped_column(String, nullable=False, server_default="employee")
    certifications: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    __table_args__ = (
        Index("idx_workers_employer_id", "employer_id"),
        Index("idx_workers_user_id", "user_id"),
    )

    user: Mapped[User | None] = relationship(back_populates="worker")


class UserRoleScope(Base):
    """The (Role, Resource Scope) RBAC model — ARCHITECTURE.md §21.1."""

    __tablename__ = "user_role_scopes"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("roles.id", ondelete="RESTRICT"), nullable=False)
    plant_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("plants.id", ondelete="CASCADE"))
    zone_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("zones.id", ondelete="CASCADE"))
    granted_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"))
    granted_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint("zone_id IS NULL OR plant_id IS NOT NULL", name="chk_zone_implies_plant"),
        UniqueConstraint("user_id", "role_id", "plant_id", "zone_id", name="uq_user_role_scope"),
        Index("idx_user_role_scopes_user_id", "user_id"),
        Index("idx_user_role_scopes_plant_id", "plant_id"),
        Index("idx_user_role_scopes_zone_id", "zone_id"),
    )


class Shift(Base, TimestampMixin):
    __tablename__ = "shifts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    plant_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("plants.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    start_time: Mapped[str] = mapped_column(Time, nullable=False)
    end_time: Mapped[str] = mapped_column(Time, nullable=False)

    __table_args__ = (
        UniqueConstraint("plant_id", "name", name="uq_shifts_plant_name"),
        Index("idx_shifts_plant_id", "plant_id"),
    )


class ShiftAssignment(Base):
    __tablename__ = "shift_assignments"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    shift_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("shifts.id", ondelete="CASCADE"), nullable=False)
    worker_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("workers.id", ondelete="CASCADE"), nullable=False)
    zone_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("zones.id", ondelete="SET NULL"))
    assigned_date: Mapped[date] = mapped_column(Date, nullable=False)
    period: Mapped[str] = mapped_column(TSRANGE, nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("idx_shift_assignments_shift_id", "shift_id"),
        Index("idx_shift_assignments_worker_id", "worker_id"),
        Index("idx_shift_assignments_date", "assigned_date"),
        # The EXCLUDE USING gist constraint (no double-booking a worker into
        # overlapping shifts) cannot be expressed as a SQLAlchemy Table arg
        # directly — it is added via raw DDL in
        # alembic/versions/0006_identity.py, immediately after this table is
        # created, exactly as DATABASE_SCHEMA.md §6.4 specifies.
    )
