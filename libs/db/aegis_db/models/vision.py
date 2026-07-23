"""Cameras, Camera Events, PPE Violations — DATABASE_SCHEMA.md §14-15. Owned by: computer-vision."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, Enum as PgEnum, ForeignKey, Index, Numeric, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from aegis_db.base import Base, TimestampMixin
from aegis_db.enums import CameraKind


class Camera(Base, TimestampMixin):
    __tablename__ = "cameras"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    zone_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("zones.id", ondelete="RESTRICT"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    camera_kind: Mapped[CameraKind] = mapped_column(
        PgEnum(CameraKind, name="camera_kind", create_type=False, values_callable=lambda x: [e.value for e in x]), nullable=False
    )
    install_location: Mapped[str | None] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, nullable=False, server_default="active")

    __table_args__ = (Index("idx_cameras_zone_id", "zone_id"),)


class CameraEvent(Base):
    __tablename__ = "camera_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    camera_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("cameras.id", ondelete="CASCADE"), nullable=False)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    confidence: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False)
    bounding_box: Mapped[dict | None] = mapped_column(JSONB)
    frame_url: Mapped[str | None] = mapped_column(String)
    detected_at: Mapped[datetime] = mapped_column(primary_key=True, nullable=False, server_default=func.now())

    __table_args__ = (
        CheckConstraint("confidence BETWEEN 0 AND 1", name="confidence_range"),
        Index("idx_camera_events_camera_id", "camera_id", "detected_at"),
        Index("idx_camera_events_type", "event_type", "detected_at"),
    )


class PPEViolation(Base):
    __tablename__ = "ppe_violations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    # No formal ForeignKey here: camera_events has a composite PK (id, detected_at)
    # because it's a hypertable, and Postgres requires a unique constraint on a
    # partitioned table's referenced columns to include the partition key —
    # a plain FK to camera_events.id alone is not valid. Same pattern used for
    # every other hypertable-referencing column in this schema (e.g.
    # Alert.related_incident_id, Notification.related_alert_id).
    camera_event_id: Mapped[int | None] = mapped_column(BigInteger)
    worker_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("workers.id", ondelete="SET NULL"))
    zone_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("zones.id", ondelete="RESTRICT"), nullable=False)
    violation_type: Mapped[str] = mapped_column(String, nullable=False)
    confidence: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False)
    detected_at: Mapped[datetime] = mapped_column(primary_key=True, nullable=False, server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column()

    __table_args__ = (
        CheckConstraint("confidence BETWEEN 0 AND 1", name="confidence_range"),
        Index("idx_ppe_violations_worker_id", "worker_id", "detected_at"),
        Index("idx_ppe_violations_zone_id", "zone_id", "detected_at"),
    )
