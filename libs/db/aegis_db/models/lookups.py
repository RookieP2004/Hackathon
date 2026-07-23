"""
Lookup / reference tables — DATABASE_SCHEMA.md §3.

roles is the authoritative RBAC role set. It supersedes the earlier 6-role draft
in ARCHITECTURE.md §21.2: Plant Manager -> Plant Admin, Supervisor -> Emergency
Team, Admin -> System Admin, plus two new roles (Government Auditor, Viewer).
Seeded in seed/seed_lookups.py.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, String, Text, Boolean, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from aegis_db.base import Base


class Role(Base):
    """
    Owned by: identity-rbac.
    The eight roles this system recognizes:
      system_admin        — global superuser, all plants, all RBAC/user management
      plant_admin         — full administrative authority scoped to one or more plants
      safety_officer       — compliance, procedures, playbooks, incident investigation
      maintenance_engineer — equipment/maintenance work-order authority
      operator             — control-room, zone-scoped live monitoring & acknowledgment
      emergency_team        — incident command, playbook approval authority
      government_auditor    — external, read-only, compliance/audit-trail access
      viewer                — generic least-privilege read-only access
    """

    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class EquipmentType(Base):
    """Owned by: digital-twin."""

    __tablename__ = "equipment_types"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class SensorType(Base):
    """Owned by: ingestion-gateway."""

    __tablename__ = "sensor_types"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    default_unit: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PermitType(Base):
    """Owned by: incident-service."""

    __tablename__ = "permit_types"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    requires_dual_signoff: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class MaintenanceType(Base):
    """Owned by: predictive-risk-engine (maintenance work-order scheduling)."""

    __tablename__ = "maintenance_types"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Employer(Base):
    """Owned by: identity-rbac."""

    __tablename__ = "employers"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    contact_phone: Mapped[str | None] = mapped_column(String)
    contact_email: Mapped[str | None] = mapped_column(String)
    is_internal: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
