"""
Seeds every lookup table (DATABASE_SCHEMA.md §3) — the reference data every
other seed script and every service assumes already exists. Idempotent: safe
to re-run against an already-seeded database.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from aegis_db.models import EquipmentType, Employer, MaintenanceType, PermitType, Role, SensorType

# The eight authoritative roles — see aegis_db/models/lookups.py's Role docstring
# for the mapping from the earlier ARCHITECTURE.md §21.2 draft.
ROLES = [
    ("system_admin", "Global superuser — all plants, all RBAC/user management"),
    ("plant_admin", "Full administrative authority scoped to one or more plants"),
    ("safety_officer", "Compliance, procedures, playbooks, incident investigation"),
    ("maintenance_engineer", "Equipment/maintenance work-order authority"),
    ("operator", "Control-room, zone-scoped live monitoring & acknowledgment"),
    ("emergency_team", "Incident command, playbook approval authority"),
    ("government_auditor", "External, read-only, compliance/audit-trail access"),
    ("viewer", "Generic least-privilege read-only access"),
]

EQUIPMENT_TYPES = [
    ("Valve", "Static", "Flow-control device"),
    ("Pump", "Rotating", "Centrifugal or reciprocating pump"),
    ("Pipe", "Static", "Process piping segment"),
    ("Reactor", "Static", "Process vessel"),
    ("Tank", "Static", "Storage vessel"),
    ("Compressor", "Rotating", "Gas compression equipment"),
    ("Relief Valve", "Static", "Over-pressure protection device"),
    ("Heat Exchanger", "Static", "Thermal transfer equipment"),
]

SENSOR_TYPES = [
    ("Pressure", "psi"),
    ("Temperature", "celsius"),
    ("Vibration", "mm/s"),
    ("Gas Concentration", "ppm"),
    ("Flow Rate", "m3/h"),
    ("Level", "%"),
    ("Acoustic", "dB"),
]

PERMIT_TYPES = [
    ("Hot Work", True),
    ("Confined Space", True),
    ("Lockout-Tagout", True),
    ("Working at Height", False),
    ("Electrical Isolation", True),
]

MAINTENANCE_TYPES = ["Preventive", "Corrective", "Predictive", "Inspection"]

EMPLOYERS = [
    ("Aegis Industrial Operations", True, "ops@aegis-demo.example", "+1-555-0100"),
    ("Meridian Contracting Services", False, "dispatch@meridian-demo.example", "+1-555-0177"),
]


def seed_lookups(session: Session) -> None:
    if session.scalar(select(Role).limit(1)) is None:
        session.add_all([Role(name=n, description=d) for n, d in ROLES])

    if session.scalar(select(EquipmentType).limit(1)) is None:
        session.add_all(
            [EquipmentType(name=n, category=c, description=d) for n, c, d in EQUIPMENT_TYPES]
        )

    if session.scalar(select(SensorType).limit(1)) is None:
        session.add_all([SensorType(name=n, default_unit=u) for n, u in SENSOR_TYPES])

    if session.scalar(select(PermitType).limit(1)) is None:
        session.add_all(
            [PermitType(name=n, requires_dual_signoff=d) for n, d in PERMIT_TYPES]
        )

    if session.scalar(select(MaintenanceType).limit(1)) is None:
        session.add_all([MaintenanceType(name=n) for n in MAINTENANCE_TYPES])

    if session.scalar(select(Employer).limit(1)) is None:
        session.add_all(
            [
                Employer(name=n, is_internal=i, contact_email=e, contact_phone=p)
                for n, i, e, p in EMPLOYERS
            ]
        )

    session.commit()
