"""Organizational hierarchy — DATABASE_SCHEMA.md §4. Owned by: digital-twin."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    ForeignKey,
    Numeric,
    SmallInteger,
    String,
    Text,
    CheckConstraint,
    UniqueConstraint,
    Index,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from aegis_db.base import Base, TimestampMixin


class Plant(Base, TimestampMixin):
    __tablename__ = "plants"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    timezone: Mapped[str] = mapped_column(String, nullable=False)
    latitude: Mapped[float | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[float | None] = mapped_column(Numeric(9, 6))
    address: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String, nullable=False, server_default="active")

    __table_args__ = (
        CheckConstraint("status IN ('active','inactive','decommissioned')", name="status_valid"),
    )

    buildings: Mapped[list["Building"]] = relationship(back_populates="plant", cascade="all, delete-orphan")


class Building(Base, TimestampMixin):
    __tablename__ = "buildings"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    plant_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("plants.id", ondelete="CASCADE"), nullable=False)
    code: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    floor_count: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="1")

    __table_args__ = (
        UniqueConstraint("plant_id", "code", name="uq_buildings_plant_code"),
        Index("idx_buildings_plant_id", "plant_id"),
    )

    plant: Mapped[Plant] = relationship(back_populates="buildings")
    zones: Mapped[list["Zone"]] = relationship(back_populates="building", cascade="all, delete-orphan")


class Zone(Base, TimestampMixin):
    __tablename__ = "zones"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    building_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("buildings.id", ondelete="CASCADE"), nullable=False)
    code: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    zone_type: Mapped[str] = mapped_column(String, nullable=False)
    hazard_class: Mapped[str | None] = mapped_column(String)
    safe_occupancy_limit: Mapped[int | None] = mapped_column(SmallInteger)
    floor_level: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="1")

    __table_args__ = (
        UniqueConstraint("building_id", "code", name="uq_zones_building_code"),
        Index("idx_zones_building_id", "building_id"),
        Index("idx_zones_hazard_class", "hazard_class", postgresql_where=text("hazard_class IS NOT NULL")),
    )

    building: Mapped[Building] = relationship(back_populates="zones")
