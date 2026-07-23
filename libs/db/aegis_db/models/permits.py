"""Permits — DATABASE_SCHEMA.md §7. Owned by: incident-service."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from aegis_db.base import Base, TimestampMixin


class Permit(Base, TimestampMixin):
    __tablename__ = "permits"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    permit_number: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    permit_type_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("permit_types.id", ondelete="RESTRICT"), nullable=False
    )
    worker_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("workers.id", ondelete="RESTRICT"), nullable=False)
    zone_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("zones.id", ondelete="RESTRICT"), nullable=False)
    equipment_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("equipment.id", ondelete="SET NULL"))
    issued_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    cosigned_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String, nullable=False, server_default="draft")
    valid_from: Mapped[datetime] = mapped_column(nullable=False)
    valid_to: Mapped[datetime] = mapped_column(nullable=False)
    conditions: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint("valid_to > valid_from", name="chk_permit_validity_window"),
        Index("idx_permits_worker_id", "worker_id"),
        Index("idx_permits_zone_id", "zone_id"),
        Index("idx_permits_equipment_id", "equipment_id"),
    )
