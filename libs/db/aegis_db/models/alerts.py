"""Alerts — DATABASE_SCHEMA.md §11. Owned by: notification-service."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, ForeignKey, Index, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from aegis_db.base import Base


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(primary_key=True, nullable=False, server_default=func.now())
    # Text, not String — matches the 0004 raw-SQL migration's DDL, per the same
    # reasoning documented in aegis_db/models/incidents.py.
    alert_type: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="open")
    equipment_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("equipment.id", ondelete="SET NULL"))
    zone_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("zones.id", ondelete="SET NULL"))
    sensor_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("sensors.id", ondelete="SET NULL"))
    related_incident_id: Mapped[int | None] = mapped_column(BigInteger)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    triggered_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    acknowledged_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"))
    acknowledged_at: Mapped[datetime | None] = mapped_column()
    resolved_at: Mapped[datetime | None] = mapped_column()

    __table_args__ = (
        Index("idx_alerts_equipment_id", "equipment_id", "created_at"),
        Index("idx_alerts_zone_id", "zone_id", "created_at"),
        Index("idx_alerts_sensor_id", "sensor_id", "created_at"),
        Index("idx_alerts_incident_id", "related_incident_id"),
    )
