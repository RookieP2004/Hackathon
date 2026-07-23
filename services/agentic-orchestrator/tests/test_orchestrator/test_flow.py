"""
Full end-to-end: the real Emergency Response Orchestrator flow against the
actual running incident-service, notification-service, and rag-service --
every step genuinely executed, not mocked.
"""

from pathlib import Path

import asyncpg
import httpx

from app.orchestrator.clients import ServiceClients
from app.orchestrator.flow import run_automatic_emergency_response

POSTGRES_DSN = "postgresql://aegis:changeme_local_only@localhost:5432/aegis"
V12_EQUIPMENT_ID = 2
ZONE_ID = 3
PLANT_ID = 1


def _clients() -> ServiceClients:
    return ServiceClients(
        postgres_dsn=POSTGRES_DSN, incident_service_url="http://localhost:8010",
        notification_service_url="http://localhost:8011", rag_service_url="http://localhost:8008",
        jwt_secret="changeme_generate_a_real_secret_before_any_shared_deployment", jwt_algorithm="HS256",
    )


async def test_full_automatic_emergency_response_flow():
    clients = _clients()
    result = await run_automatic_emergency_response(
        clients, POSTGRES_DSN, hazard_class="explosion", equipment_id=V12_EQUIPMENT_ID, equipment_tag="V-12",
        zone_id=ZONE_ID, plant_id=PLANT_ID, score=88.0, severity="critical", confidence=0.9,
        contributing_factors=[
            {"source_type": "sensor", "evidence_node_id": "gas", "likelihood_ratio": 40.0, "evidence_refs": ["1"]},
            {"source_type": "sensor", "evidence_node_id": "pressure", "likelihood_ratio": 15.0, "evidence_refs": ["2"]},
        ],
        recommendations=["Investigate the gas sensor reading immediately.", "Prioritize relief-valve inspection."],
        counterfactuals=[{"removed_node_id": "gas", "resulting_probability": 0.15, "delta": -0.73}],
    )

    # All ten required steps happened, in order.
    assert result.timeline == [
        "incident_generated", "users_notified", "emergency_team_notified", "evacuation_activated",
        "sensor_data_captured", "evidence_stored", "ai_summary_generated", "report_generated", "regulatory_report_generated",
    ]

    # Real incident row, real severity, real AI-generated summary field populated.
    conn = await asyncpg.connect(POSTGRES_DSN)
    try:
        incident_row = await conn.fetchrow("SELECT severity, status, ai_generated_summary FROM incidents WHERE id = $1", result.incident_id)
        timeline_rows = await conn.fetch(
            "SELECT event_type FROM incident_timeline_events WHERE incident_id = $1 ORDER BY occurred_at ASC", result.incident_id
        )
        report_rows = await conn.fetch("SELECT report_type, status, file_url FROM reports WHERE parameters->>'incident_id' = $1", str(result.incident_id))
    finally:
        await conn.close()

    assert incident_row["severity"] == "critical"
    assert incident_row["ai_generated_summary"] is not None and "explosion" in incident_row["ai_generated_summary"].lower()

    real_event_types = [r["event_type"] for r in timeline_rows]
    assert "auto_response_started" in real_event_types
    assert "evacuation_activated" in real_event_types
    assert "report_generated" in real_event_types
    assert "regulatory_report_generated" in real_event_types

    assert len(report_rows) == 2
    for report in report_rows:
        assert report["status"] == "completed"
        assert Path(report["file_url"]).exists()
        assert Path(report["file_url"]).read_bytes().startswith(b"%PDF")

    # Real evidence file on disk.
    assert Path(result.evidence_path).exists()

    # Real alerts landed in notification-service's own database.
    conn = await asyncpg.connect(POSTGRES_DSN)
    try:
        alert_count = await conn.fetchval("SELECT count(*) FROM alerts WHERE related_incident_id = $1", result.incident_id)
    finally:
        await conn.close()
    assert alert_count == 2  # users_notified + emergency_team_notified

    # Cleanup the real files this test wrote.
    for report in report_rows:
        Path(report["file_url"]).unlink(missing_ok=True)
    Path(result.evidence_path).unlink(missing_ok=True)

    # Close the incident this test created -- EmergencyAgent's dedup check
    # suppresses a duplicate automatic response while any open incident
    # exists for the same equipment; leaving this open would silently break
    # every subsequent test/demo run against V-12.
    conn = await asyncpg.connect(POSTGRES_DSN)
    try:
        await conn.execute("UPDATE incidents SET status='closed', closed_at=now() WHERE id = $1", result.incident_id)
    finally:
        await conn.close()
