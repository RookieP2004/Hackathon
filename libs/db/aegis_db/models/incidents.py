"""
Incidents — DATABASE_SCHEMA.md §9. Owned by: incident-service.

`incidents` is natively range-partitioned by created_at (monthly), which is why
its primary key is composite (id, created_at) — Postgres requires the
partitioning column to be part of every unique constraint. The actual
`PARTITION BY RANGE` clause and the first partitions are created via raw DDL in
the corresponding Alembic migration, since SQLAlchemy's Table construct doesn't
model partitioned tables directly.

Composite primary keys are declared with `primary_key=True` on BOTH columns —
`__mapper_args__ = {"primary_key": [...]}` alone does NOT create an actual
database PRIMARY KEY constraint, it only affects the ORM's identity mapping.
This was a real bug caught by inspecting the first autogenerate pass, fixed here.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from aegis_db.base import Base, TimestampMixin


class Incident(Base, TimestampMixin):
    __tablename__ = "incidents"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(primary_key=True, nullable=False, server_default=func.now())
    # Postgres requires every unique constraint on a partitioned table to include the
    # partition key -- see the composite UniqueConstraint below and
    # alembic/versions/0004_native_partitioning.py's comment on the same point.
    # Text, not String: the 0004 raw-SQL migration created these as TEXT (matching
    # DATABASE_SCHEMA.md's native-partitioning DDL, which uses TEXT throughout) —
    # matched here to avoid Alembic reporting a false type-drift on every future
    # autogenerate run. Postgres treats TEXT and unbounded VARCHAR identically in
    # storage/performance; this is a naming-consistency fix, not a behavior change.
    incident_number: Mapped[str] = mapped_column(Text, nullable=False)
    plant_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("plants.id", ondelete="RESTRICT"), nullable=False)
    zone_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("zones.id", ondelete="SET NULL"))
    equipment_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("equipment.id", ondelete="SET NULL"))
    severity: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="open")
    ai_generated_summary: Mapped[str | None] = mapped_column(Text)
    root_cause: Mapped[str | None] = mapped_column(Text)
    opened_by_user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"))
    acknowledged_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"))
    closed_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"))
    opened_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    acknowledged_at: Mapped[datetime | None] = mapped_column()
    escalated_at: Mapped[datetime | None] = mapped_column()
    closed_at: Mapped[datetime | None] = mapped_column()

    __table_args__ = (
        UniqueConstraint("incident_number", "created_at", name="uq_incidents_incident_number_created_at"),
        Index("idx_incidents_plant_id", "plant_id", "created_at"),
        Index("idx_incidents_zone_id", "zone_id", "created_at"),
        Index("idx_incidents_equipment_id", "equipment_id", "created_at"),
    )


class IncidentTimelineEvent(Base):
    """Append-only; mutation is blocked by the prevent_mutation() trigger, not by SQLAlchemy."""

    __tablename__ = "incident_timeline_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    incident_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    actor_type: Mapped[str] = mapped_column(String, nullable=False)
    actor_user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"))
    event_data: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    occurred_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())

    __table_args__ = (
        Index("idx_timeline_events_incident_id", "incident_id", "occurred_at"),
    )
