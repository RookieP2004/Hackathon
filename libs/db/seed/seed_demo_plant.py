"""
Seeds one demo plant end to end (DEVELOPMENT_ROADMAP.md M43): 1 plant, 3
buildings, 10 zones, 40 equipment, 100 sensors, 5 workers + users, 2 permits.

Equipment/sensor tags deliberately reuse the names from RISK_FUSION_ENGINE.md
§5's worked example (V-12, RV-9, GS-14, PT-22 on the Reactor Feed Line in
Zone 3) — this is the same demo topology every document in the series has been
narrating against, now actually instantiated as real rows.

Idempotent: checks for the plant's code before inserting anything.
"""

from __future__ import annotations

import secrets
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from aegis_db.models import (
    Building,
    Employer,
    Equipment,
    EquipmentType,
    Machine,
    Permit,
    PermitType,
    Plant,
    Role,
    Sensor,
    SensorType,
    User,
    Worker,
    Zone,
)

PLANT_CODE = "AEGIS-DEMO-01"


def _get(session: Session, model, **filters):
    return session.execute(select(model).filter_by(**filters)).scalar_one()


def seed_demo_plant(session: Session) -> None:
    if session.execute(select(Plant).filter_by(code=PLANT_CODE)).scalar_one_or_none() is not None:
        return  # already seeded

    plant = Plant(
        code=PLANT_CODE,
        name="Aegis Demo Refinery",
        timezone="America/Chicago",
        latitude=29.7604,
        longitude=-95.3698,
        address="1 Refinery Row, Demo, TX",
        status="active",
    )
    session.add(plant)
    session.flush()

    buildings = {
        "PU1": Building(plant_id=plant.id, code="PU1", name="Process Unit 1", floor_count=1),
        "CTL": Building(plant_id=plant.id, code="CTL", name="Control Building", floor_count=2),
        "UTL": Building(plant_id=plant.id, code="UTL", name="Utility Building", floor_count=1),
    }
    session.add_all(buildings.values())
    session.flush()

    zone_defs = [
        # (code, name, building, zone_type, hazard_class, safe_occupancy_limit)
        ("Z1", "Tank Farm A", "PU1", "storage", "flammable_liquid", 4),
        ("Z2", "Tank Farm B", "PU1", "storage", "flammable_liquid", 4),
        ("Z3", "Reactor Feed Line", "PU1", "process_unit", "flammable_gas", 6),
        ("Z4", "Reactor Bay", "PU1", "process_unit", "high_temperature", 6),
        ("Z5", "Separation Unit", "PU1", "process_unit", "flammable_gas", 6),
        ("Z6", "Compression Train", "PU1", "process_unit", "high_pressure", 4),
        ("Z7", "Loading Dock", "PU1", "loading_dock", None, 10),
        ("Z8", "Main Control Room", "CTL", "control_room", None, 12),
        ("Z9", "Server Room", "CTL", "utility", None, 2),
        ("Z10", "Boiler House", "UTL", "utility", "high_temperature", 3),
    ]
    zones: dict[str, Zone] = {}
    for code, name, bldg, ztype, hazard, occ in zone_defs:
        z = Zone(
            building_id=buildings[bldg].id,
            code=code,
            name=name,
            zone_type=ztype,
            hazard_class=hazard,
            safe_occupancy_limit=occ,
        )
        zones[code] = z
        session.add(z)
    session.flush()

    et = {row.name: row for row in session.execute(select(EquipmentType)).scalars()}

    # Zone 3 (Reactor Feed Line) — the exact equipment RISK_FUSION_ENGINE.md §5
    # narrates. Wired as a small linear chain via upstream_equipment_id, matching
    # DATABASE_SCHEMA.md §5.1's narrow denormalized convenience column (the full
    # branching topology lives in Neo4j per KNOWLEDGE_GRAPH.md, not here).
    equipment: dict[str, Equipment] = {}

    pipe_feed = Equipment(
        zone_id=zones["Z3"].id, equipment_type_id=et["Pipe"].id, tag="PIPE-12A",
        name="Reactor Feed Line Segment A", criticality=4, status="operational",
        manufacturer="Demo Fabrication Co", install_date=date(2019, 3, 1),
    )
    session.add(pipe_feed)
    session.flush()
    equipment["PIPE-12A"] = pipe_feed

    v12 = Equipment(
        zone_id=zones["Z3"].id, equipment_type_id=et["Valve"].id, tag="V-12",
        name="Reactor Feed Isolation Valve", criticality=5, status="operational",
        manufacturer="Demo Valve Works", install_date=date(2019, 3, 1),
        upstream_equipment_id=pipe_feed.id,
    )
    session.add(v12)
    session.flush()
    equipment["V-12"] = v12

    rv9 = Equipment(
        zone_id=zones["Z3"].id, equipment_type_id=et["Relief Valve"].id, tag="RV-9",
        name="Feed Line Relief Valve", criticality=5, status="operational",
        manufacturer="Demo Safety Systems", install_date=date(2018, 11, 15),
        upstream_equipment_id=v12.id,
    )
    session.add(rv9)
    session.flush()
    equipment["RV-9"] = rv9

    r3 = Equipment(
        zone_id=zones["Z4"].id, equipment_type_id=et["Reactor"].id, tag="R-3",
        name="Reactor 3", criticality=5, status="operational",
        manufacturer="Demo Process Systems", install_date=date(2017, 6, 1),
        upstream_equipment_id=v12.id,
    )
    session.add(r3)
    session.flush()
    equipment["R-3"] = r3

    # Remaining ~36 equipment rows across every zone, generated for realistic
    # volume (matching the 40-equipment target) without hand-naming each one.
    generic_specs = [
        ("Z1", "Tank", "TK", 4),
        ("Z1", "Valve", "V", 3),
        ("Z2", "Tank", "TK", 4),
        ("Z2", "Valve", "V", 3),
        ("Z4", "Pump", "P", 4),
        ("Z4", "Heat Exchanger", "HX", 3),
        ("Z5", "Reactor", "R", 4),
        ("Z5", "Pipe", "PIPE", 2),
        ("Z6", "Compressor", "C", 5),
        ("Z6", "Valve", "V", 3),
        ("Z7", "Pump", "P", 2),
        ("Z10", "Pump", "P", 3),
    ]
    counters: dict[str, int] = {}
    n = 0
    while n < 36:
        zone_code, type_name, prefix, criticality = generic_specs[n % len(generic_specs)]
        counters[prefix] = counters.get(prefix, 0) + 1
        tag = f"{prefix}-{100 + counters[prefix]}"
        eq = Equipment(
            zone_id=zones[zone_code].id,
            equipment_type_id=et[type_name].id,
            tag=tag,
            name=f"{type_name} {tag}",
            criticality=criticality,
            status="operational",
        )
        session.add(eq)
        equipment[tag] = eq
        n += 1
    session.flush()

    # Machine subtype rows for the rotating equipment (Pump/Compressor), per
    # DATABASE_SCHEMA.md §5.2's class-table-inheritance pattern.
    for tag, eq in equipment.items():
        if eq.equipment_type_id in (et["Pump"].id, et["Compressor"].id):
            session.add(
                Machine(
                    equipment_id=eq.id,
                    machine_class="centrifugal_pump" if eq.equipment_type_id == et["Pump"].id else "reciprocating_compressor",
                    rated_power_kw=75.0,
                    rated_rpm=1780,
                    control_system="DCS",
                    plc_tag=f"PLC-{tag}",
                )
            )
    session.flush()

    # Sensors — GS-14 and PT-22 explicitly monitor V-12, exactly as
    # RISK_FUSION_ENGINE.md §5's worked example narrates. ~98 more generated
    # across every zone/equipment to reach the 100-sensor target.
    st = {row.name: row for row in session.execute(select(SensorType)).scalars()}

    sensors = [
        Sensor(
            sensor_type_id=st["Gas Concentration"].id, equipment_id=v12.id, tag="GS-14",
            unit="ppm", protocol="mqtt", min_range=0, max_range=100, sample_rate_hz=1,
            calibration_date=date(2025, 1, 15), status="active",
        ),
        Sensor(
            sensor_type_id=st["Pressure"].id, equipment_id=v12.id, tag="PT-22",
            unit="psi", protocol="mqtt", min_range=0, max_range=500, sample_rate_hz=10,
            calibration_date=date(2025, 1, 15), status="active",
        ),
    ]
    session.add_all(sensors)

    equipment_list = list(equipment.values())
    sensor_type_cycle = list(st.values())
    for i in range(98):
        eq = equipment_list[i % len(equipment_list)]
        s_type = sensor_type_cycle[i % len(sensor_type_cycle)]
        session.add(
            Sensor(
                sensor_type_id=s_type.id,
                equipment_id=eq.id,
                tag=f"{s_type.name[:2].upper()}-{200 + i}",
                unit=s_type.default_unit,
                protocol="mqtt",
                sample_rate_hz=1,
                status="active",
            )
        )
    session.flush()

    # Users + Workers — one per role, covering the eight-role RBAC set.
    roles = {r.name: r for r in session.execute(select(Role)).scalars()}
    employer = session.execute(select(Employer).filter_by(is_internal=True)).scalars().first()

    demo_people = [
        ("priya.operator@aegis-demo.example", "Priya Sharma", "operator", "BADGE-0001"),
        ("marcus.emergency@aegis-demo.example", "Marcus Alvarez", "emergency_team", "BADGE-0002"),
        ("elena.safety@aegis-demo.example", "Dr. Elena Kwan", "safety_officer", "BADGE-0003"),
        ("tasha.maintenance@aegis-demo.example", "Tasha Reyes", "maintenance_engineer", "BADGE-0004"),
        ("james.admin@aegis-demo.example", "James Whitfield", "plant_admin", "BADGE-0005"),
    ]
    for email, name, role_name, badge in demo_people:
        user = User(
            email=email,
            full_name=name,
            default_role_id=roles[role_name].id,
            status="active",
            # No password_hash set here -- seed data is not meant to be
            # directly loggable-in-as; the auth system's user-creation path
            # (identity-rbac service) is what sets real password hashes.
        )
        session.add(user)
        session.flush()
        session.add(
            Worker(
                user_id=user.id,
                employer_id=employer.id,
                badge_id=badge,
                full_name=name,
                worker_type="employee",
                active=True,
            )
        )
    session.flush()

    # Two permits: one active Hot Work permit (deliberately NOT on V-12/Zone 3,
    # so the Permit Agent conflict-check demo scenario has a clean "no conflict"
    # baseline), one active Confined Space permit.
    permit_types = {p.name: p for p in session.execute(select(PermitType)).scalars()}
    tasha = session.execute(select(Worker).filter_by(badge_id="BADGE-0004")).scalar_one()
    james = session.execute(select(User).filter_by(email="james.admin@aegis-demo.example")).scalar_one()
    now = datetime.now(timezone.utc)

    session.add_all(
        [
            Permit(
                permit_number="HW-2026-0001",
                permit_type_id=permit_types["Hot Work"].id,
                worker_id=tasha.id,
                zone_id=zones["Z10"].id,
                issued_by=james.id,
                status="active",
                valid_from=now,
                valid_to=now + timedelta(hours=8),
                conditions="Fire watch required for duration of work.",
            ),
            Permit(
                permit_number="CS-2026-0001",
                permit_type_id=permit_types["Confined Space"].id,
                worker_id=tasha.id,
                zone_id=zones["Z1"].id,
                equipment_id=equipment_list[0].id,
                issued_by=james.id,
                status="active",
                valid_from=now,
                valid_to=now + timedelta(hours=4),
                conditions="Continuous gas monitoring required.",
            ),
        ]
    )

    session.commit()
