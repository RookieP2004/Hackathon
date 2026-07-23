"""
Physical asset core — DATABASE_SCHEMA.md §5. Owned by: digital-twin (equipment,
machines) and ingestion-gateway (sensors).

Machine is a class-table-inheritance subtype of Equipment (shared primary key),
mirroring the Neo4j multi-label pattern KNOWLEDGE_GRAPH.md §1.1 uses for the
same real-world distinction.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    Enum as PgEnum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from aegis_db.base import Base, TimestampMixin
from aegis_db.enums import EquipmentStatus


class Equipment(Base, TimestampMixin):
    __tablename__ = "equipment"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    zone_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("zones.id", ondelete="RESTRICT"), nullable=False)
    equipment_type_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("equipment_types.id", ondelete="RESTRICT"), nullable=False
    )
    tag: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    manufacturer: Mapped[str | None] = mapped_column(String)
    model_number: Mapped[str | None] = mapped_column(String)
    serial_number: Mapped[str | None] = mapped_column(String)
    install_date: Mapped[date | None] = mapped_column(Date)
    criticality: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="3")
    status: Mapped[EquipmentStatus] = mapped_column(
        PgEnum(EquipmentStatus, name="equipment_status", create_type=False, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        server_default=EquipmentStatus.OPERATIONAL.value,
    )
    upstream_equipment_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("equipment.id", ondelete="SET NULL")
    )

    __table_args__ = (
        UniqueConstraint("zone_id", "tag", name="uq_equipment_zone_tag"),
        CheckConstraint("criticality BETWEEN 1 AND 5", name="criticality_range"),
        Index("idx_equipment_zone_id", "zone_id"),
        Index("idx_equipment_type_id", "equipment_type_id"),
        Index("idx_equipment_upstream", "upstream_equipment_id"),
    )

    machine: Mapped["Machine | None"] = relationship(back_populates="equipment", uselist=False)
    sensors: Mapped[list["Sensor"]] = relationship(back_populates="equipment")


class Machine(Base, TimestampMixin):
    __tablename__ = "machines"

    equipment_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("equipment.id", ondelete="CASCADE"), primary_key=True
    )
    machine_class: Mapped[str] = mapped_column(String, nullable=False)
    rated_power_kw: Mapped[float | None] = mapped_column(Numeric(10, 2))
    rated_rpm: Mapped[int | None] = mapped_column(Integer)
    control_system: Mapped[str | None] = mapped_column(String)
    plc_tag: Mapped[str | None] = mapped_column(String)

    equipment: Mapped[Equipment] = relationship(back_populates="machine")


class Sensor(Base, TimestampMixin):
    __tablename__ = "sensors"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    sensor_type_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("sensor_types.id", ondelete="RESTRICT"), nullable=False
    )
    equipment_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("equipment.id", ondelete="SET NULL"))
    zone_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("zones.id", ondelete="SET NULL"))
    tag: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    unit: Mapped[str] = mapped_column(String, nullable=False)
    protocol: Mapped[str] = mapped_column(String, nullable=False)
    min_range: Mapped[float | None] = mapped_column(Numeric(14, 4))
    max_range: Mapped[float | None] = mapped_column(Numeric(14, 4))
    sample_rate_hz: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False, server_default="1.0")
    calibration_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String, nullable=False, server_default="active")

    __table_args__ = (
        CheckConstraint(
            "protocol IN ('mqtt','opc_ua','modbus_tcp','simulated')", name="protocol_valid"
        ),
        CheckConstraint("status IN ('active','faulted','decommissioned')", name="status_valid"),
        CheckConstraint(
            "equipment_id IS NOT NULL OR zone_id IS NOT NULL", name="chk_sensor_monitors_something"
        ),
        Index("idx_sensors_equipment_id", "equipment_id"),
        Index("idx_sensors_zone_id", "zone_id"),
        Index("idx_sensors_type_id", "sensor_type_id"),
    )

    equipment: Mapped[Equipment | None] = relationship(back_populates="sensors")
