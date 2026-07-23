"""
Audit Logs — DATABASE_SCHEMA.md §16. Owned by: audit-log.

Immutability (no UPDATE/DELETE, ever) is enforced by the prevent_mutation()
Postgres trigger, not by anything in this ORM layer — a role/bug in application
code must not be the only thing standing between this table and a silent
compliance-record alteration.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from aegis_db.base import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    actor_user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String, nullable=False)
    resource_type: Mapped[str] = mapped_column(String, nullable=False)
    resource_id: Mapped[int | None] = mapped_column(BigInteger)
    old_value: Mapped[dict | None] = mapped_column(JSONB)
    new_value: Mapped[dict | None] = mapped_column(JSONB)
    ip_address: Mapped[str | None] = mapped_column(INET)
    occurred_at: Mapped[datetime] = mapped_column(primary_key=True, nullable=False, server_default=func.now())

    __table_args__ = (
        Index("idx_audit_logs_actor", "actor_user_id", "occurred_at"),
        Index("idx_audit_logs_resource", "resource_type", "resource_id", "occurred_at"),
    )
