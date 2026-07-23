"""
Orchestrates all six stages into one callable: given a real equipment id,
assess all five hazard classes, in RISK_FUSION_ENGINE.md §4.6's causal order,
and return each one's full Evidence Bundle. Writes each result to the real
`risk_scores` table (already owned by this service) and anchors it into the
Neo4j graph via the `/graph/risk` endpoint built specifically for this in
the knowledge-graph pass.
"""

from __future__ import annotations

from datetime import datetime, timezone

import asyncpg
import httpx
import structlog

from aegis_api_common import ServiceActorTokenMinter

from app.fusion.db import acquire
from app.fusion.evidence import EvidenceNode, build_equipment_health_evidence_node, build_sensor_evidence_node, fetch_sensor_history
from app.fusion.explainability import assemble_evidence_bundle, evidence_bundle_to_dict
from app.fusion.graph_client import fetch_risk_context, post_risk_to_graph
from app.fusion.networks import HazardAssessmentInput, run_all_networks
from app.fusion.scoring import estimate_confidence, record_and_estimate_time_to_event, scalar_confidence, severity_for_score
from app.fusion.temporal import compute_temporal_features

logger = structlog.get_logger(__name__)

HOT_WORK_PERMIT_TYPE = "Hot Work"
CONFINED_SPACE_PERMIT_TYPE = "Confined Space"
FIRE_SMOKE_GAS_CLASSES = {"fire", "smoke", "gas_leak"}


async def _fetch_equipment(dsn: str, equipment_id: int, pool: asyncpg.Pool | None = None) -> dict | None:
    async with acquire(dsn, pool) as conn:
        row = await conn.fetchrow(
            "SELECT id, tag, zone_id, criticality, status::text AS status FROM equipment WHERE id = $1", equipment_id
        )
    return dict(row) if row else None


async def _fetch_direct_sensor_ids(dsn: str, equipment_id: int, pool: asyncpg.Pool | None = None) -> list[int]:
    async with acquire(dsn, pool) as conn:
        rows = await conn.fetch("SELECT id FROM sensors WHERE equipment_id = $1", equipment_id)
    return [r["id"] for r in rows]


async def _check_maintenance_overdue(dsn: str, equipment_ids: list[int], pool: asyncpg.Pool | None = None) -> bool:
    if not equipment_ids:
        return False
    async with acquire(dsn, pool) as conn:
        row = await conn.fetchrow(
            "SELECT count(*) AS c FROM maintenance_records WHERE equipment_id = ANY($1::bigint[]) "
            "AND status = 'scheduled' AND scheduled_date < now()::date",
            equipment_ids,
        )
    return row["c"] > 0


async def _check_active_permits(dsn: str, equipment_id: int, zone_id: int, pool: asyncpg.Pool | None = None) -> tuple[bool, bool]:
    async with acquire(dsn, pool) as conn:
        rows = await conn.fetch(
            """
            SELECT pt.name FROM permits p JOIN permit_types pt ON pt.id = p.permit_type_id
            WHERE (p.equipment_id = $1 OR p.zone_id = $2) AND p.status = 'active'
            AND p.valid_from <= now() AND p.valid_to >= now()
            """,
            equipment_id, zone_id,
        )
    names = {r["name"] for r in rows}
    return HOT_WORK_PERMIT_TYPE in names, CONFINED_SPACE_PERMIT_TYPE in names


async def _check_worker_present(dsn: str, zone_id: int, pool: asyncpg.Pool | None = None) -> bool:
    async with acquire(dsn, pool) as conn:
        row = await conn.fetchrow(
            "SELECT count(*) AS c FROM shift_assignments WHERE zone_id = $1 AND assigned_date = now()::date "
            "AND period @> now()::timestamp",
            zone_id,
        )
    return row["c"] > 0


async def _fetch_vision_signal(computer_vision_url: str, token_minter: ServiceActorTokenMinter) -> tuple[float, bool]:
    """A genuinely live call to the Vision AI service's confirmed detections
    -- but honestly scoped: computer-vision's live pipeline observes
    iot-simulator's separate synthetic world, which (confirmed empirically
    in that pass) has no spatial correspondence to this real seeded
    equipment topology. Rather than fabricate a false equipment-specific
    match, this takes the plant-wide maximum fire/smoke/gas-leak detection
    confidence as a coarse corroborating signal, and PPE-violation presence
    separately -- real, live data, honestly not claiming spatial precision
    it doesn't have."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{computer_vision_url}/vision/live", headers=await token_minter.auth_headers())
            response.raise_for_status()
            detections = response.json()["detections"]
    except httpx.HTTPError as exc:
        logger.warning("vision_signal_fetch_failed", error=str(exc))
        return 0.0, False

    max_confidence = 0.0
    ppe_violation = False
    for d in detections:
        cls = d["detection_class"]
        conf = d["confidence"] * d.get("persistence_factor", 1.0)
        if cls in ("fire", "smoke", "gas_leak"):
            max_confidence = max(max_confidence, conf)
        if cls in ("helmet", "vest", "gloves", "mask"):
            ppe_violation = True
    return max_confidence, ppe_violation


async def assess_equipment(
    *, equipment_id: int, postgres_dsn: str, knowledge_graph_url: str, computer_vision_url: str,
    token_minter: ServiceActorTokenMinter, anchor_to_graph: bool = True, pg_pool: asyncpg.Pool | None = None,
) -> list[dict]:
    equipment = await _fetch_equipment(postgres_dsn, equipment_id, pg_pool)
    if equipment is None:
        raise ValueError(f"No equipment with id {equipment_id}")

    risk_context = await fetch_risk_context(knowledge_graph_url, equipment_id, token_minter)
    admitted_sensor_nodes = risk_context.get("admitted_sensors", [])
    all_equipment_ids = [equipment_id] + [n["id"] for n in risk_context.get("graph_neighborhood", []) if "id" in n]

    # Multiple admitted sensors can share the same sensorType (the assessed
    # equipment's own gas sensor AND a graph-neighbor's gas sensor, e.g.) --
    # sensor_nodes is keyed by type, so without an explicit tie-break the
    # iteration order silently decides which one a hazard network actually
    # sees (confirmed empirically: a neighbor's untouched reading displaced
    # the assessed equipment's own escalating one). The assessed equipment's
    # *own* direct sensor always wins ties, never a neighbor's.
    direct_sensor_ids = set(await _fetch_direct_sensor_ids(postgres_dsn, equipment_id, pg_pool))

    sensor_nodes: dict[str, EvidenceNode] = {}
    sensor_temporal = {}
    good_quality_count = 0
    for sensor in admitted_sensor_nodes:
        sensor_type = sensor.get("sensorType")
        if sensor_type is None:
            continue
        is_direct = sensor["id"] in direct_sensor_ids
        if sensor_type in sensor_nodes and not is_direct:
            continue  # a slot is already filled and this sensor isn't the assessed equipment's own -- skip it
        history = await fetch_sensor_history(postgres_dsn, sensor["id"], window=30, pool=pg_pool)
        node = build_sensor_evidence_node(sensor["id"], sensor.get("tag", str(sensor["id"])), sensor.get("unit", ""), history)
        sensor_nodes[sensor_type] = node
        sensor_temporal[sensor_type] = compute_temporal_features(history)
        if node.quality_flag == "good":
            good_quality_count += 1

    equipment_health_node = build_equipment_health_evidence_node(equipment["tag"], equipment["status"], equipment["criticality"])

    maintenance_overdue = await _check_maintenance_overdue(postgres_dsn, all_equipment_ids, pg_pool)
    hot_work_active, confined_space_active = await _check_active_permits(postgres_dsn, equipment_id, equipment["zone_id"], pg_pool)
    worker_present = await _check_worker_present(postgres_dsn, equipment["zone_id"], pg_pool)
    vision_confidence, ppe_violation = await _fetch_vision_signal(computer_vision_url, token_minter)

    vision_node = None
    if vision_confidence > 0:
        vision_node = EvidenceNode(
            source_type="vision", source_id="plant_wide_camera_feed", raw_value=vision_confidence,
            normalized_value=vision_confidence, unit=None, timestamp=datetime.now(timezone.utc), quality_flag="good",
            metadata={"scope": "plant_wide", "caveat": "no spatial correspondence to this equipment confirmed"},
        )

    inp = HazardAssessmentInput(
        equipment_tag=equipment["tag"], sensor_nodes=sensor_nodes, sensor_temporal=sensor_temporal,
        equipment_health=equipment_health_node, vision_detection=vision_node,
        permit_active_hot_work=hot_work_active, permit_active_confined_space=confined_space_active,
        maintenance_overdue=maintenance_overdue, worker_present=worker_present, ppe_violation_detected=ppe_violation,
    )

    results = run_all_networks(inp)
    now = datetime.now(timezone.utc)
    bundles = []

    for hazard_class, result in results.items():
        score = round(result.posterior_probability * 100, 1)
        confidence = estimate_confidence(
            posterior=result.posterior_probability, num_contributions=len(result.contributions),
            num_admitted_sources=max(1, len(admitted_sensor_nodes)), num_good_quality=good_quality_count,
            precursor_similarity=None,
        )
        time_to_event = record_and_estimate_time_to_event(equipment_id, hazard_class, now, result.posterior_probability)
        confidence_scalar = scalar_confidence(confidence)

        bundle = assemble_evidence_bundle(
            result=result, equipment_id=equipment_id, equipment_tag=equipment["tag"], zone_id=equipment["zone_id"],
            score=score, confidence=confidence, time_to_event_seconds=time_to_event,
            graph_neighborhood_snapshot_id=f"eq-{equipment_id}-{now.isoformat()}",
        )
        bundle_dict = evidence_bundle_to_dict(bundle)
        bundle_dict["confidence_scalar"] = confidence_scalar
        bundles.append(bundle_dict)

        await _persist_risk_score(postgres_dsn, bundle_dict, pg_pool)
        if anchor_to_graph:
            await _anchor_to_graph(knowledge_graph_url, bundle_dict, token_minter)

    return bundles


async def _persist_risk_score(dsn: str, bundle: dict, pool: asyncpg.Pool | None = None) -> None:
    async with acquire(dsn, pool) as conn:
        await conn.execute(
            """
            INSERT INTO risk_scores (equipment_id, zone_id, score, confidence, contributing_factors, model_version)
            VALUES ($1, $2, $3, $4, $5::jsonb, $6)
            """,
            bundle["equipment_id"], bundle["zone_id"], bundle["score"], bundle["confidence_scalar"],
            _to_json(bundle["contributing_factors"]), f"risk-fusion:{bundle['hazard_class']}:{bundle['gate_structure_version']}",
        )


def _to_json(value) -> str:
    import json

    return json.dumps(value)


async def _anchor_to_graph(knowledge_graph_url: str, bundle: dict, token_minter: ServiceActorTokenMinter) -> None:
    risk_id = f"risk-fusion-{bundle['equipment_id']}-{bundle['hazard_class']}-{bundle['assessed_at']}"
    payload = {
        "id": risk_id,
        "hazard_class": bundle["hazard_class"],
        "score": bundle["score"],
        "confidence": bundle["posterior_probability"],
        "epistemic_flag": bundle["confidence"]["epistemic_flag"] != "low",
        "assessed_at": bundle["assessed_at"],
        "gate_structure_version": bundle["gate_structure_version"],
        "equipment_id": bundle["equipment_id"],
        "zone_id": bundle["zone_id"],
        "evidence_sensor_ids": [
            int(ref) for f in bundle["contributing_factors"] for ref in f["evidence_refs"] if ref.isdigit()
        ],
    }
    await post_risk_to_graph(knowledge_graph_url, payload, token_minter)
