"""Maintenance — DATABASE_SCHEMA.md §8. Owned by: predictive-risk-engine."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import BigInteger, Date, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from aegis_db.base import Base, TimestampMixin


class MaintenanceRecord(Base, TimestampMixin):
    __tablename__ = "maintenance_records"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    equipment_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("equipment.id", ondelete="CASCADE"), nullable=False)
    maintenance_type_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("maintenance_types.id", ondelete="RESTRICT"), nullable=False
    )
    requested_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"))
    performed_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("workers.id", ondelete="SET NULL"))
    # FK to predictions is added in a later migration once that table exists —
    # see DATABASE_SCHEMA.md §8's own note on this same forward reference.
    related_prediction_id: Mapped[int | None] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String, nullable=False, server_default="scheduled")
    scheduled_date: Mapped[date | None] = mapped_column(Date)
    completed_at: Mapped[datetime | None] = mapped_column()
    description: Mapped[str] = mapped_column(Text, nullable=False)
    findings: Mapped[str | None] = mapped_column(Text)
    parts_used: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    cost: Mapped[float | None] = mapped_column(Numeric(12, 2))

    __table_args__ = (
        Index("idx_maintenance_equipment_id", "equipment_id"),
        Index("idx_maintenance_performed_by", "performed_by"),
        Index("idx_maintenance_prediction_id", "related_prediction_id"),
    )
