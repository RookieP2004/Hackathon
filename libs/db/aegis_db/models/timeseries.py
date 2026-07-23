"""
High-frequency time-series tables — DATABASE_SCHEMA.md §20-21, plus
WorkerLocationHistory (new — see class docstring). All three are TimescaleDB
hypertables converted via raw SQL in their Alembic migrations.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Enum as PgEnum, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from aegis_db.base import Base
from aegis_db.enums import ReadingQuality


class SensorReading(Base):
    """
    Owned by: ingestion-gateway. The highest-volume table in the schema
    (DATABASE_SCHEMA.md §20) — 2D-partitioned (time + sensor_id) at the Alembic
    migration level, not representable as a plain SQLAlchemy Table option.

    Primary key includes sensor_id (not just id + recorded_at): TimescaleDB
    requires every unique index on a hypertable, including its primary key, to
    include all of that hypertable's partitioning dimensions — confirmed
    empirically when add_dimension('sensor_readings', 'sensor_id', ...) rejected
    a 2-column PK with "cannot create a unique index without the column
    sensor_id (used in partitioning)". DATABASE_SCHEMA.md §20's original
    (id, recorded_at) PK was insufficient for a 2D hypertable; corrected here.
    """

    __tablename__ = "sensor_readings"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    sensor_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("sensors.id", ondelete="CASCADE"), primary_key=True, nullable=False
    )
    value: Mapped[float] = mapped_column(nullable=False)
    quality: Mapped[ReadingQuality] = mapped_column(
        PgEnum(ReadingQuality, name="reading_quality", create_type=False, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        server_default=ReadingQuality.GOOD.value,
    )
    recorded_at: Mapped[datetime] = mapped_column(primary_key=True, nullable=False)

    __table_args__ = (Index("idx_sensor_readings_sensor_id", "sensor_id", "recorded_at"),)


class MachineStateHistory(Base):
    """Owned by: predictive-risk-engine. Time-only hypertable (no space dimension)."""

    __tablename__ = "machine_state_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    machine_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("machines.equipment_id", ondelete="CASCADE"), nullable=False
    )
    operating_state: Mapped[str] = mapped_column(String, nullable=False)
    rpm: Mapped[float | None] = mapped_column(Numeric(8, 2))
    temperature_c: Mapped[float | None] = mapped_column(Numeric(6, 2))
    vibration_rms_mm_s: Mapped[float | None] = mapped_column(Numeric(8, 4))
    cycle_count: Mapped[int | None] = mapped_column(BigInteger)
    cumulative_operating_hours: Mapped[float | None] = mapped_column(Numeric(12, 2))
    fault_code: Mapped[str | None] = mapped_column(String)
    recorded_at: Mapped[datetime] = mapped_column(primary_key=True, nullable=False)


    __table_args__ = (Index("idx_machine_state_machine_id", "machine_id", "recorded_at"),)


class WorkerLocationHistory(Base):
    """
    Owned by: predictive-risk-engine (Worker Agent, AGENT_ARCHITECTURE.md §3).

    NOT part of the original DATABASE_SCHEMA.md/KNOWLEDGE_GRAPH.md design — those
    documents deliberately kept only a short-TTL *current* position in a fast
    cache (Redis / Digital Twin state layer) and explicitly did not persist
    historical movement trails by default, per the privacy-by-design stance in
    UI_UX_SPECIFICATION.md §6 ("no historical movement trails... in its default
    view" — an operator who feels surveilled hides problems instead of
    reporting them).

    This table exists because it was explicitly requested as "Worker Location
    History." To stay consistent with that earlier, deliberate privacy stance
    rather than silently overriding it, this table is implemented with real
    constraints reflecting the same intent:
      - it is a genuine append-only history table (for legitimate safety
        investigation / compliance use, e.g. reconstructing who was near a
        confirmed hazard at a given time), and
      - retention is short and finite (90 days, applied via
        add_retention_policy in the Alembic migration), not indefinite, and
      - application-layer access to this table (built in a later pass) should
        be restricted to the safety_officer / government_auditor / system_admin
        roles with the access itself audit-logged, exactly like any other
        access-controlled compliance surface in this system.

    The default Worker Tracking UI screen continues to query only *current*
    position (still cached separately, not from this table) — this history
    table is for investigation, not routine display.
    """

    __tablename__ = "worker_location_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    worker_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("workers.id", ondelete="CASCADE"), nullable=False)
    zone_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("zones.id", ondelete="SET NULL"))
    source: Mapped[str] = mapped_column(String, nullable=False, server_default="badge")
    location_confidence: Mapped[float | None] = mapped_column(Numeric(4, 3))
    identity_confidence: Mapped[float | None] = mapped_column(Numeric(4, 3))
    recorded_at: Mapped[datetime] = mapped_column(primary_key=True, nullable=False)


    __table_args__ = (Index("idx_worker_location_worker_id", "worker_id", "recorded_at"),)
