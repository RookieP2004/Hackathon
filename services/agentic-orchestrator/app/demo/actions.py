"""
Concrete actions for each Demo Mode story beat. Every action is a real
operation against a real running service (or a direct Postgres write where
no endpoint exists, e.g. shift assignments) -- Demo Mode's job is to
sequence real stimuli and then observe the already-built autonomous system
(the twelve-agent fleet, the Risk Fusion Engine, the Emergency Response
Orchestrator) react for real, not to fake any of the reaction.

Real seeded ids this script depends on (aegis dev DB, plant 1):
  - equipment 2 = V-12 (Reactor Feed Isolation Valve, Zone 3), sensor 1 = GS-14 (gas)
  - equipment 3 = RV-9, sensor 5 = VI-202 (vibration)
  - worker 1 = Priya Sharma (operator), worker 4 = Tasha Reyes (maintenance_engineer)
  - permit_type 1 = Hot Work, maintenance_type 2 = Corrective, shift 1 = Demo Day Shift
  - iot-simulator's separate fictional world happens to reuse the tag "V-12"
    (equipment_id "eq-v12") for its own Tank Farm zone -- coincidence from a
    shared original demo narrative, not a real cross-reference to Postgres.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import asyncpg
import httpx

from app.agents import topics
from app.copilot.entities import resolve_equipment
from app.copilot.handlers import handle_why_risk_increasing
from app.demo.context import DemoContext

V12_EQUIPMENT_ID = 2
V12_GAS_SENSOR_ID = 1
V12_TEMPERATURE_SENSOR_ID = 4
RV9_EQUIPMENT_ID = 3
RV9_VIBRATION_SENSOR_ID = 5
ZONE3_ID = 3
WORKER_PRIYA = 1
WORKER_TASHA = 4
HOT_WORK_PERMIT_TYPE = 1
CORRECTIVE_MAINTENANCE_TYPE = 2
SHIFT_ID = 1


async def setup_baseline(ctx: DemoContext) -> dict:
    now = datetime.now(timezone.utc)
    async with httpx.AsyncClient(timeout=10.0) as client:
        headers = await ctx.clients.auth_headers()
        create_resp = await client.post(
            f"{ctx.clients.incident_service_url}/permits", headers=headers,
            json={
                "permit_number": f"DEMO-HW-{int(now.timestamp())}", "permit_type_id": HOT_WORK_PERMIT_TYPE,
                "worker_id": WORKER_TASHA, "zone_id": ZONE3_ID, "equipment_id": V12_EQUIPMENT_ID,
                "valid_from": now.isoformat(), "valid_to": (now + timedelta(hours=2)).isoformat(),
                "conditions": "Demo Mode baseline permit.",
            },
        )
        create_resp.raise_for_status()
        permit_row = create_resp.json()

        activate_resp = await client.patch(
            f"{ctx.clients.incident_service_url}/permits/{permit_row['id']}", headers=headers, json={"status": "active"},
        )
        activate_resp.raise_for_status()

    ctx.state["permit_id"] = permit_row["id"]
    ctx.state["permit_number"] = permit_row["permit_number"]
    ctx.state["demo_started_at"] = now.isoformat()

    try:
        assessments = await ctx.clients.assess_equipment(V12_EQUIPMENT_ID)
        baseline_score = max((a["score"] for a in assessments), default=0.0)
    except Exception:
        baseline_score = None

    return {"permit_number": permit_row["permit_number"], "baseline_risk_score": baseline_score}


async def inject_gas_rise(ctx: DemoContext) -> dict:
    async with httpx.AsyncClient(timeout=10.0) as client:
        headers = await ctx.clients.auth_headers()
        gas_resp = await client.post(
            f"{ctx.clients.predictive_risk_engine_url}/fusion/simulator/scenario", headers=headers,
            json={"sensor_id": V12_GAS_SENSOR_ID, "target_value": 4500.0, "rate": 0.45},
        )
        gas_resp.raise_for_status()
        # A real gas escalation on its own doesn't satisfy explosion's noisy-AND
        # gate (fuel-in-range AND ignition-source AND confinement) -- a
        # temperature climb alongside the gas reading is a standard real
        # accompanying precursor, so inject it too rather than relying on luck
        # for the ignition-source condition to also be met. Values pushed well
        # past the danger threshold (not just "elevated") since this hazard's
        # posterior also depends on corroborating vision confidence, which is
        # genuinely noisy tick to tick -- a stronger sensor signal keeps the
        # noisy-OR combination reliably over the critical threshold regardless.
        temp_resp = await client.post(
            f"{ctx.clients.predictive_risk_engine_url}/fusion/simulator/scenario", headers=headers,
            json={"sensor_id": V12_TEMPERATURE_SENSOR_ID, "target_value": 420.0, "rate": 0.45},
        )
        temp_resp.raise_for_status()
    return {"sensors": ["GS-14", "TE-201"], "target_values": [4500.0, 420.0]}


async def inject_vibration_rise(ctx: DemoContext) -> dict:
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            f"{ctx.clients.predictive_risk_engine_url}/fusion/simulator/scenario", headers=await ctx.clients.auth_headers(),
            json={"sensor_id": RV9_VIBRATION_SENSOR_ID, "target_value": 22.0, "rate": 0.4},
        )
        response.raise_for_status()
    return {"sensor": "VI-202", "target_value": 22.0}


async def begin_maintenance(ctx: DemoContext) -> dict:
    async with httpx.AsyncClient(timeout=10.0) as client:
        headers = await ctx.clients.auth_headers()
        create_resp = await client.post(
            f"{ctx.clients.predictive_risk_engine_url}/maintenance", headers=headers,
            json={
                "equipment_id": V12_EQUIPMENT_ID, "maintenance_type_id": CORRECTIVE_MAINTENANCE_TYPE,
                "performed_by": WORKER_TASHA, "description": "Demo Mode: investigating elevated GS-14 gas reading on V-12.",
            },
        )
        create_resp.raise_for_status()
        record = create_resp.json()

        patch_resp = await client.patch(
            f"{ctx.clients.predictive_risk_engine_url}/maintenance/{record['id']}", headers=headers, json={"status": "in_progress"},
        )
        patch_resp.raise_for_status()
    ctx.state["maintenance_id"] = record["id"]
    return {"maintenance_id": record["id"], "status": "in_progress"}


async def worker_enters_zone(ctx: DemoContext) -> dict:
    now = datetime.now(timezone.utc)
    conn = await asyncpg.connect(ctx.postgres_dsn)
    # shift_assignments.period is a plain tsrange (timestamp without time zone) --
    # asyncpg rejects tz-aware datetimes against it, so pass naive UTC values.
    naive_now = now.replace(tzinfo=None)
    try:
        # A replay/previous run may have left this worker's shift assignment for
        # today still overlapping "now" -- the exclusion constraint on
        # (worker_id, period) would otherwise reject a second one for the same
        # worker. Clear this action's own prior demo assignment before inserting.
        await conn.execute(
            "DELETE FROM shift_assignments WHERE worker_id = $1 AND zone_id = $2 AND assigned_date = $3",
            WORKER_PRIYA, ZONE3_ID, now.date(),
        )
        await conn.execute(
            "INSERT INTO shift_assignments (shift_id, worker_id, zone_id, assigned_date, period) "
            "VALUES ($1, $2, $3, $4, tsrange($5, $6))",
            SHIFT_ID, WORKER_PRIYA, ZONE3_ID, now.date(), naive_now, naive_now + timedelta(hours=2),
        )
    finally:
        await conn.close()
    return {"worker": "Priya Sharma", "zone": "Reactor Feed Line (Zone 3)"}


async def expire_permit(ctx: DemoContext) -> dict:
    permit_id = ctx.state.get("permit_id")
    if permit_id is None:
        return {"expired": False, "reason": "no baseline permit was created this run"}

    now = datetime.now(timezone.utc)
    async with httpx.AsyncClient(timeout=10.0) as client:
        headers = await ctx.clients.auth_headers()
        response = await client.patch(
            f"{ctx.clients.incident_service_url}/permits/{permit_id}", headers=headers, json={"valid_to": now.isoformat()},
        )
        response.raise_for_status()

    # The Permit Agent's fail-closed conflict check reads the *graph*, not
    # Postgres directly -- sync just this one permit so the expiry is
    # immediately visible, instead of waiting on (or triggering) a full
    # /graph/sync pull across every node type.
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            await client.post(f"{ctx.clients.knowledge_graph_url}/graph/permits/{permit_id}/sync", headers=await ctx.clients.auth_headers())
    except Exception:
        pass

    return {"permit_number": ctx.state.get("permit_number"), "expired_at": now.isoformat()}


async def camera_detects_fire(ctx: DemoContext) -> dict:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{ctx.iot_simulator_url}/control/scenario", json={"scenario": "fire", "equipment_id": "eq-v12"},
                headers=await ctx.clients.auth_headers(),
            )
            response.raise_for_status()
            return response.json()
    except Exception as exc:
        return {"triggered": False, "error": str(exc)}


async def observe_current_risk(ctx: DemoContext) -> dict:
    try:
        assessments = await ctx.clients.assess_equipment(V12_EQUIPMENT_ID)
    except Exception:
        return {"observed": False}
    top = max(assessments, key=lambda a: a["score"]) if assessments else None
    if top is None:
        return {"observed": False}
    # Whichever hazard is actually highest right now (gas_leak from the direct
    # sensor injection, fire from the camera detection, or explosion if both
    # its noisy-AND conditions happen to align) -- ask_ai_why explains this
    # same hazard next, not a hardcoded guess.
    ctx.state["top_hazard_class"] = top["hazard_class"]
    return {"hazard_class": top["hazard_class"], "score": top["score"], "severity": top["severity"]}


async def ask_ai_why(ctx: DemoContext) -> dict:
    equipment = await resolve_equipment(ctx.postgres_dsn, "V-12")
    hazard_class = ctx.state.get("top_hazard_class", "gas_leak")
    result = await handle_why_risk_increasing(ctx.clients, equipment, hazard_class)
    return {"answer": result["answer"], "citations": result["citations"]}


async def wait_for_emergency_response(ctx: DemoContext) -> dict:
    async def _listen() -> dict | None:
        async for message in ctx.bus.subscribe(topics.ESCALATION):
            if message.agent_id == "emergency-agent" and message.payload.get("equipment_id") == V12_EQUIPMENT_ID:
                return message.payload
        return None

    try:
        payload = await asyncio.wait_for(_listen(), timeout=240.0)
    except asyncio.TimeoutError:
        return {"observed": False, "note": "No automatic emergency response was observed within the wait window -- risk may not have crossed the critical threshold yet this run."}

    if payload is None:
        return {"observed": False}
    ctx.state["incident_id"] = payload.get("incident_id")
    return {
        "observed": True, "incident_number": payload.get("incident_number"), "incident_id": payload.get("incident_id"),
        "timeline": payload.get("timeline"), "incident_report_path": payload.get("incident_report_path"),
        "regulatory_report_path": payload.get("regulatory_report_path"),
    }


async def summarize_reports(ctx: DemoContext) -> dict:
    incident_id = ctx.state.get("incident_id")
    if incident_id is None:
        return {"reports": []}
    conn = await asyncpg.connect(ctx.postgres_dsn)
    try:
        rows = await conn.fetch("SELECT report_type, file_url FROM reports WHERE parameters->>'incident_id' = $1", str(incident_id))
    finally:
        await conn.close()
    return {"reports": [dict(r) for r in rows]}
