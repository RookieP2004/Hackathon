"""
Capture Sensor Data + Store Evidence — the Emergency Response Orchestrator's
two evidentiary steps. Both write real, retrievable artifacts to disk
(JSON, human- and machine-readable) rather than only logging a summary line,
since "store evidence" and "capture sensor data" are explicit, separate
requirements from what's merely narrated in the incident timeline.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import asyncpg

EVIDENCE_DIR = Path(__file__).resolve().parent.parent.parent / "generated_reports" / "evidence"
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)


async def capture_sensor_data(postgres_dsn: str, equipment_id: int | None, *, window: int = 20) -> dict:
    """A real, verbatim snapshot of the specific sensors physically monitoring
    the triggering equipment, at the moment of the incident -- not a
    re-derivation, the actual raw readings that were used."""
    if equipment_id is None:
        return {"equipment_id": None, "sensors": []}

    conn = await asyncpg.connect(postgres_dsn)
    try:
        sensors = await conn.fetch(
            "SELECT s.id, s.tag, st.name AS sensor_type, s.unit FROM sensors s "
            "JOIN sensor_types st ON st.id = s.sensor_type_id WHERE s.equipment_id = $1",
            equipment_id,
        )
        snapshot = []
        for sensor in sensors:
            readings = await conn.fetch(
                "SELECT value, quality, recorded_at FROM sensor_readings WHERE sensor_id = $1 "
                "ORDER BY recorded_at DESC LIMIT $2",
                sensor["id"], window,
            )
            snapshot.append({
                "sensor_id": sensor["id"], "tag": sensor["tag"], "sensor_type": sensor["sensor_type"], "unit": sensor["unit"],
                "readings": [{"value": float(r["value"]), "quality": r["quality"], "recorded_at": r["recorded_at"].isoformat()} for r in readings],
            })
    finally:
        await conn.close()

    return {"equipment_id": equipment_id, "captured_at": datetime.now(timezone.utc).isoformat(), "sensors": snapshot}


def store_evidence_bundle(incident_id: int, evidence_bundle: dict, sensor_snapshot: dict) -> str:
    """Persists the full Evidence Bundle (Risk Fusion Engine's Stage 6 output
    -- contributing factors, counterfactuals, recommendations) plus the raw
    sensor snapshot into one retrievable file per incident. Returns the real
    file path, not a placeholder URL."""
    record = {
        "incident_id": incident_id,
        "stored_at": datetime.now(timezone.utc).isoformat(),
        "evidence_bundle": evidence_bundle,
        "sensor_snapshot": sensor_snapshot,
    }
    file_path = EVIDENCE_DIR / f"incident-{incident_id}-evidence.json"
    file_path.write_text(json.dumps(record, indent=2, default=str), encoding="utf-8")
    return str(file_path)
