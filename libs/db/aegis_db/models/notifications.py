"""Notifications — DATABASE_SCHEMA.md §17. Owned by: notification-service."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Enum as PgEnum, ForeignKey, Index, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from aegis_db.base import Base
from aegis_db.enums import NotificationChannel


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(primary_key=True, nullable=False, server_default=func.now())
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    channel: Mapped[NotificationChannel] = mapped_column(
        PgEnum(NotificationChannel, name="notification_channel", create_type=False, values_callable=lambda x: [e.value for e in x]), nullable=False
    )
    # Text, not String — matches the 0004 raw-SQL migration's DDL, per the same
    # reasoning documented in aegis_db/models/incidents.py.
    severity: Mapped[str] = mapped_column(Text, nullable=False)
    related_incident_id: Mapped[int | None] = mapped_column(BigInteger)
    related_alert_id: Mapped[int | None] = mapped_column(BigInteger)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="pending")
    sent_at: Mapped[datetime | None] = mapped_column()
    delivered_at: Mapped[datetime | None] = mapped_column()
    acknowledged_at: Mapped[datetime | None] = mapped_column()

    __table_args__ = (
        Index("idx_notifications_user_id", "user_id", "created_at"),
        Index("idx_notifications_incident_id", "related_incident_id"),
    )
