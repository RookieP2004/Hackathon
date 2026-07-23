"""
Sync — KNOWLEDGE_GRAPH.md §7: "this graph is not an independent system of
record ... a materialized view over the same event backbone every other
store consumes." No Kafka producer/consumer exists anywhere in this repo yet
(confirmed empirically while building computer-vision's downstream
integration -- every cross-service call in this codebase is direct REST, not
event-driven), so a real `equipment.*`/`incident.*` Kafka consumer would have
nothing upstream actually publishing to it. Until that exists, this module is
the practical equivalent of §7's replay-from-event-log guarantee: a pull-based
full sync directly from the real Postgres tables that are each node type's
`Postgres Counterpart` (§2.1's table), safe to re-run at any time because
every write below is `MERGE`-idempotent (writes.py). When the real event
stream exists, this function's bodies become that consumer's per-topic
handlers essentially unchanged -- the Cypher doesn't need to change, only
what triggers it.
"""

from __future__ import annotations

import asyncpg
import structlog

from app.graph.writes import GraphWriter

logger = structlog.get_logger(__name__)

# equipment_types.name -> the multi-label subtype this graph uses (§1.1). Anything
# not listed here (Reactor, Tank, Heat Exchanger) stays plain :Equipment -- the spec's
# own §2.2 only names Machine/Valve/Pipeline as subtypes, it does not require every
# equipment_type to have one.
EQUIPMENT_TYPE_SUBTYPE: dict[str, str] = {
    "Pipe": "Pipeline",
    "Valve": "Valve",
    "Relief Valve": "Valve",
}

# knowledge_documents.document_class -> (node label, 'Document' vs 'Regulation')
REGULATION_CLASSES = {"factory_act", "dgms", "oisd"}
DOCUMENT_SUBTYPE_LABEL: dict[str, str] = {
    "safety_sop": "Procedure",
    "equipment_manual": "Manual",
    "maintenance_manual": "Manual",
    "inspection_report": "InspectionReport",
    "incident_report": "InspectionReport",
    "near_miss": "InspectionReport",
    "audit_report": "InspectionReport",
}


async def run_full_sync(writer: GraphWriter, postgres_dsn: str) -> dict:
    conn = await asyncpg.connect(postgres_dsn)
    counts: dict[str, int] = {}
    try:
        counts["plants"] = await _sync_plants(writer, conn)
        counts["buildings"] = await _sync_buildings(writer, conn)
        counts["zones"] = await _sync_zones(writer, conn)
        counts["equipment"] = await _sync_equipment(writer, conn)
        counts["equipment_flow_links"] = await _sync_equipment_flow(writer, conn)
        counts["sensors"] = await _sync_sensors(writer, conn)
        counts["workers"] = await _sync_workers(writer, conn)
        counts["shift_assignments"] = await _sync_shift_assignments(writer, conn)
        counts["permits"] = await _sync_permits(writer, conn)
        counts["maintenance_records"] = await _sync_maintenance(writer, conn)
        counts["incidents"] = await _sync_incidents(writer, conn)
        counts["knowledge_documents"] = await _sync_knowledge_documents(writer, conn)
        counts["risk_scores"] = await _sync_risk_scores(writer, conn)
    finally:
        await conn.close()
    logger.info("graph_sync_complete", **counts)
    return counts


async def _sync_plants(writer: GraphWriter, conn: asyncpg.Connection) -> int:
    rows = await conn.fetch("SELECT id, code, name, timezone FROM plants")
    for r in rows:
        await writer.upsert_plant(id=r["id"], code=r["code"], name=r["name"], timezone=r["timezone"])
    return len(rows)


async def _sync_buildings(writer: GraphWriter, conn: asyncpg.Connection) -> int:
    rows = await conn.fetch("SELECT id, plant_id, code, name, floor_count FROM buildings")
    for r in rows:
        await writer.upsert_building(
            id=r["id"], plant_id=r["plant_id"], code=r["code"], name=r["name"], floor_count=r["floor_count"]
        )
    return len(rows)


async def _sync_zones(writer: GraphWriter, conn: asyncpg.Connection) -> int:
    rows = await conn.fetch(
        "SELECT id, building_id, code, name, zone_type, hazard_class, safe_occupancy_limit, floor_level FROM zones"
    )
    for r in rows:
        await writer.upsert_zone(
            id=r["id"], building_id=r["building_id"], code=r["code"], name=r["name"], zone_type=r["zone_type"],
            hazard_class=r["hazard_class"], safe_occupancy_limit=r["safe_occupancy_limit"], floor_level=r["floor_level"],
        )
    return len(rows)


async def _sync_equipment(writer: GraphWriter, conn: asyncpg.Connection) -> int:
    rows = await conn.fetch(
        """
        SELECT e.id, e.zone_id, e.tag, e.name, e.criticality, e.status::text AS status,
               et.name AS equipment_type_name,
               m.machine_class, m.rated_power_kw, m.rated_rpm, m.control_system, m.plc_tag
        FROM equipment e
        JOIN equipment_types et ON et.id = e.equipment_type_id
        LEFT JOIN machines m ON m.equipment_id = e.id
        """
    )
    for r in rows:
        if r["machine_class"] is not None:
            subtype_label = "Machine"
            subtype_properties = {
                "machineClass": r["machine_class"],
                "ratedPowerKw": float(r["rated_power_kw"]) if r["rated_power_kw"] is not None else None,
                "ratedRpm": r["rated_rpm"],
                "controlSystem": r["control_system"],
                "plcTag": r["plc_tag"],
            }
        else:
            subtype_label = EQUIPMENT_TYPE_SUBTYPE.get(r["equipment_type_name"])
            subtype_properties = {}
        await writer.upsert_equipment(
            id=r["id"], zone_id=r["zone_id"], tag=r["tag"], name=r["name"], criticality=r["criticality"],
            status=r["status"], subtype_label=subtype_label, subtype_properties=subtype_properties,
        )
    return len(rows)


async def _sync_equipment_flow(writer: GraphWriter, conn: asyncpg.Connection) -> int:
    rows = await conn.fetch("SELECT id, upstream_equipment_id FROM equipment WHERE upstream_equipment_id IS NOT NULL")
    for r in rows:
        await writer.link_equipment_flow(upstream_id=r["upstream_equipment_id"], downstream_id=r["id"])
    return len(rows)


async def _sync_sensors(writer: GraphWriter, conn: asyncpg.Connection) -> int:
    rows = await conn.fetch(
        """
        SELECT s.id, s.tag, s.unit, s.status, s.equipment_id, s.zone_id, st.name AS sensor_type_name
        FROM sensors s JOIN sensor_types st ON st.id = s.sensor_type_id
        """
    )
    for r in rows:
        await writer.upsert_sensor(
            id=r["id"], tag=r["tag"], sensor_type=r["sensor_type_name"], unit=r["unit"], status=r["status"],
            equipment_id=r["equipment_id"], zone_id=r["zone_id"],
        )
    return len(rows)


async def _sync_workers(writer: GraphWriter, conn: asyncpg.Connection) -> int:
    rows = await conn.fetch("SELECT id, badge_id, full_name, worker_type, active FROM workers")
    for r in rows:
        await writer.upsert_worker(
            id=r["id"], badge_id=r["badge_id"], full_name=r["full_name"], worker_type=r["worker_type"], active=r["active"]
        )
    return len(rows)


async def _sync_shift_assignments(writer: GraphWriter, conn: asyncpg.Connection) -> int:
    rows = await conn.fetch(
        "SELECT worker_id, zone_id, assigned_date FROM shift_assignments WHERE zone_id IS NOT NULL"
    )
    for r in rows:
        await writer.link_worker_assigned_to_zone(
            worker_id=r["worker_id"], zone_id=r["zone_id"], since=str(r["assigned_date"])
        )
    return len(rows)


async def _sync_permits(writer: GraphWriter, conn: asyncpg.Connection) -> int:
    rows = await conn.fetch(
        """
        SELECT p.id, p.permit_number, pt.name AS permit_type_name, p.status, p.valid_from, p.valid_to,
               p.worker_id, p.zone_id, p.equipment_id
        FROM permits p JOIN permit_types pt ON pt.id = p.permit_type_id
        """
    )
    for r in rows:
        await writer.upsert_permit(
            id=r["id"], permit_number=r["permit_number"], permit_type=r["permit_type_name"], status=r["status"],
            valid_from=r["valid_from"].isoformat(), valid_to=r["valid_to"].isoformat(),
            worker_id=r["worker_id"], zone_id=r["zone_id"], equipment_id=r["equipment_id"],
        )
    return len(rows)


async def _sync_maintenance(writer: GraphWriter, conn: asyncpg.Connection) -> int:
    rows = await conn.fetch(
        """
        SELECT mr.id, mt.name AS maintenance_type_name, mr.status, mr.scheduled_date, mr.completed_at,
               mr.findings, mr.equipment_id, mr.performed_by
        FROM maintenance_records mr JOIN maintenance_types mt ON mt.id = mr.maintenance_type_id
        """
    )
    for r in rows:
        await writer.upsert_maintenance(
            id=r["id"], maintenance_type=r["maintenance_type_name"], status=r["status"],
            scheduled_date=str(r["scheduled_date"]) if r["scheduled_date"] else None,
            completed_at=r["completed_at"].isoformat() if r["completed_at"] else None,
            findings=r["findings"], equipment_id=r["equipment_id"], performed_by=r["performed_by"],
        )
    return len(rows)


async def _sync_incidents(writer: GraphWriter, conn: asyncpg.Connection) -> int:
    rows = await conn.fetch(
        "SELECT id, incident_number, severity, status, opened_at, zone_id, equipment_id, root_cause FROM incidents"
    )
    for r in rows:
        await writer.create_incident(
            id=r["id"], incident_number=r["incident_number"], severity=r["severity"], status=r["status"],
            opened_at=r["opened_at"].isoformat(), zone_id=r["zone_id"], equipment_id=r["equipment_id"],
            root_cause=r["root_cause"],
        )
    return len(rows)


async def _sync_knowledge_documents(writer: GraphWriter, conn: asyncpg.Connection) -> int:
    rows = await conn.fetch(
        "SELECT id, title, document_class, version, equipment_type_scope, hazard_class_scope FROM knowledge_documents"
    )
    for r in rows:
        if r["document_class"] in REGULATION_CLASSES:
            await writer.upsert_regulation(
                id=r["id"], code=r["document_class"].upper(), title=r["title"], jurisdiction="India",
                clause_ref=None, effective_date=None,
            )
        else:
            label = DOCUMENT_SUBTYPE_LABEL.get(r["document_class"], "Manual")
            await writer.upsert_document(
                id=r["id"], title=r["title"], document_class_label=label, version=r["version"],
                equipment_type_scope=r["equipment_type_scope"], hazard_class_scope=r["hazard_class_scope"],
            )
    return len(rows)


async def _sync_risk_scores(writer: GraphWriter, conn: asyncpg.Connection) -> int:
    """§2.5: only significant assessments are meant to become :Risk nodes, not
    every routine tick -- in this environment every row already in risk_scores
    is one computer-vision (or, later, Risk Fusion Engine) chose to persist,
    so all of them qualify rather than needing a further threshold filter here."""
    rows = await conn.fetch(
        "SELECT id, equipment_id, zone_id, score, confidence, contributing_factors, model_version, computed_at "
        "FROM risk_scores"
    )
    for r in rows:
        hazard_class = "unclassified"
        factors = r["contributing_factors"]
        if factors:
            import json

            parsed = json.loads(factors) if isinstance(factors, str) else factors
            if parsed and isinstance(parsed, list) and "detection_class" in parsed[0]:
                hazard_class = parsed[0]["detection_class"]
        await writer.create_risk(
            id=f"risk-{r['id']}", postgres_prediction_id=r["id"], hazard_class=hazard_class,
            score=float(r["score"]), confidence=float(r["confidence"]), epistemic_flag=False,
            assessed_at=r["computed_at"].isoformat(), gate_structure_version=r["model_version"],
            equipment_id=r["equipment_id"], zone_id=r["zone_id"],
        )
    return len(rows)
