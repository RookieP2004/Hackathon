"""Emergency Events & Playbooks — DATABASE_SCHEMA.md §13. Owned by: agentic-orchestrator."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Enum as PgEnum,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from aegis_db.base import Base, TimestampMixin
from aegis_db.enums import AutonomyTier


class Playbook(Base, TimestampMixin):
    __tablename__ = "playbooks"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    hazard_class: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(String)
    version: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="1")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"))

    __table_args__ = (
        UniqueConstraint("name", "version", name="uq_playbooks_name_version"),
        Index("idx_playbooks_hazard_class", "hazard_class"),
    )


class PlaybookStep(Base):
    __tablename__ = "playbook_steps"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    playbook_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("playbooks.id", ondelete="CASCADE"), nullable=False)
    step_order: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    autonomy_tier: Mapped[AutonomyTier] = mapped_column(
        PgEnum(AutonomyTier, name="autonomy_tier", create_type=False, values_callable=lambda x: [e.value for e in x]), nullable=False
    )
    tool_name: Mapped[str] = mapped_column(String, nullable=False)
    parameters: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")

    __table_args__ = (
        UniqueConstraint("playbook_id", "step_order", name="uq_playbook_steps_order"),
        Index("idx_playbook_steps_playbook_id", "playbook_id"),
    )


class EmergencyEvent(Base, TimestampMixin):
    __tablename__ = "emergency_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    incident_id: Mapped[int | None] = mapped_column(BigInteger)
    plant_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("plants.id", ondelete="RESTRICT"), nullable=False)
    zone_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("zones.id", ondelete="SET NULL"))
    playbook_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("playbooks.id", ondelete="SET NULL"))
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, server_default="initiated")
    initiated_by_user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"))
    initiated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column()

    __table_args__ = (
        Index("idx_emergency_events_incident_id", "incident_id"),
        Index("idx_emergency_events_plant_id", "plant_id"),
    )


class EmergencyEventStep(Base):
    __tablename__ = "emergency_event_steps"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    emergency_event_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("emergency_events.id", ondelete="CASCADE"), nullable=False
    )
    playbook_step_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("playbook_steps.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(String, nullable=False, server_default="pending")
    approved_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"))
    approved_at: Mapped[datetime | None] = mapped_column()
    executed_at: Mapped[datetime | None] = mapped_column()
    result: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','approved','rejected','executing','completed','failed')",
            name="status_valid",
        ),
        UniqueConstraint("emergency_event_id", "playbook_step_id", name="uq_event_steps"),
        Index("idx_event_steps_event_id", "emergency_event_id"),
    )
