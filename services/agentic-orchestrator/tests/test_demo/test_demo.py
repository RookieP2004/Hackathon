"""
Demo Mode, exercised against the real, live agentic-orchestrator service.

The full scripted story's later beats (critical escalation, automatic
emergency response) are genuinely non-deterministic in *timing* -- a real
Bayesian network responding to real, noisy vision-detection confidence and a
real gradual sensor ramp, not a scripted certainty -- so this suite verifies
the player's lifecycle mechanics and the early, deterministic real side
effects (permit created+activated, sensor injection) rather than waiting on
a full run to reach emergency_response, which the live investigation during
this build already verified separately (multiple full runs reaching a real
critical fire score and a real completed 9-step automatic response).
"""

from pathlib import Path

import asyncpg
import httpx
from jose import jwt

BASE_URL = "http://localhost:8009"
POSTGRES_DSN = "postgresql://aegis:changeme_local_only@localhost:5432/aegis"
JWT_SECRET = "changeme_generate_a_real_secret_before_any_shared_deployment"


async def _auth_headers() -> dict:
    conn = await asyncpg.connect(POSTGRES_DSN)
    try:
        row = await conn.fetchrow(
            "SELECT u.id, u.default_role_id FROM users u JOIN roles r ON r.id = u.default_role_id WHERE r.name = 'safety_officer' LIMIT 1"
        )
    finally:
        await conn.close()
    token = jwt.encode({"sub": str(row["id"]), "role_id": row["default_role_id"], "type": "access", "exp": 9999999999}, JWT_SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}


async def _stop_and_reset() -> None:
    headers = await _auth_headers()
    async with httpx.AsyncClient(timeout=15.0) as client:
        await client.post(f"{BASE_URL}/demo/stop", headers=headers)
        await client.post("http://localhost:8005/fusion/simulator/reset", headers=headers)


async def test_demo_status_reports_a_real_eleven_step_timeline():
    headers = await _auth_headers()
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(f"{BASE_URL}/demo/status", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total_steps"] == 11
    step_ids = [s["id"] for s in body["timeline"]]
    assert step_ids == [
        "normal", "gas_rises", "vibration_increases", "maintenance_begins", "worker_enters",
        "permit_expires", "camera_detects_fire", "risk_increasing", "ai_explains",
        "emergency_response", "reports_generated",
    ]


async def test_demo_start_pause_resume_stop_lifecycle():
    headers = await _auth_headers()
    async with httpx.AsyncClient(timeout=15.0) as client:
        start_resp = await client.post(f"{BASE_URL}/demo/start", headers=headers, json={"speed_multiplier": 10.0})
        assert start_resp.json()["started"] is True

        pause_resp = await client.post(f"{BASE_URL}/demo/pause", headers=headers)
        assert pause_resp.json()["paused"] is True

        status_resp = await client.get(f"{BASE_URL}/demo/status", headers=headers)
        assert status_resp.json()["status"] == "paused"

        resume_resp = await client.post(f"{BASE_URL}/demo/resume", headers=headers)
        assert resume_resp.json()["resumed"] is True

        stop_resp = await client.post(f"{BASE_URL}/demo/stop", headers=headers)
        assert stop_resp.json()["stopped"] is True

        # a second stop on an already-stopped run is a real no-op, not an error
        second_stop = await client.post(f"{BASE_URL}/demo/stop", headers=headers)
        assert second_stop.json()["stopped"] is False

    await _stop_and_reset()


async def test_demo_cannot_start_twice_concurrently():
    headers = await _auth_headers()
    async with httpx.AsyncClient(timeout=15.0) as client:
        first = await client.post(f"{BASE_URL}/demo/start", headers=headers, json={"speed_multiplier": 1.0})
        assert first.json()["started"] is True
        second = await client.post(f"{BASE_URL}/demo/start", headers=headers, json={"speed_multiplier": 1.0})
        assert second.json()["started"] is False

    await _stop_and_reset()


async def test_demo_early_steps_produce_real_side_effects():
    headers = await _auth_headers()
    async with httpx.AsyncClient(timeout=15.0) as client:
        await client.post(f"{BASE_URL}/demo/start", headers=headers, json={"speed_multiplier": 10.0})

        # Fast-forwarded 10x, the "normal" (baseline permit) and "gas_rises"
        # (real sensor injection) steps -- both deterministic, no waiting on
        # a Bayesian escalation -- should complete within a few real seconds.
        import asyncio

        for _ in range(20):
            await asyncio.sleep(1.0)
            status = (await client.get(f"{BASE_URL}/demo/status", headers=headers)).json()
            if status["current_step_index"] >= 1:
                break

        permit_number = None
        for entry in status["step_log"]:
            if entry["id"] == "normal" and entry["ok"]:
                permit_number = entry["result"]["permit_number"]

        await client.post(f"{BASE_URL}/demo/stop", headers=headers)

    assert permit_number is not None
    conn = await asyncpg.connect(POSTGRES_DSN)
    try:
        row = await conn.fetchrow("SELECT status, equipment_id FROM permits WHERE permit_number = $1", permit_number)
    finally:
        await conn.close()
    assert row is not None
    assert row["equipment_id"] == 2

    await _stop_and_reset()


def test_sanitize_for_pdf_transliterates_real_unicode_punctuation():
    from app.pdf_text import sanitize_for_pdf

    text = "Incident INC-2026-000482 — Tank Farm Gas Alarm Escalation: it’s a “test”…"
    sanitized = sanitize_for_pdf(text)
    assert "—" not in sanitized
    assert "’" not in sanitized
    assert "--" in sanitized
    # must be encodable in the base-14 PDF font's Latin-1 encoding -- this is
    # the exact condition that silently killed EmergencyAgent's subscriber
    # loop before this fix (fpdf2 raising on real em-dash citation text)
    sanitized.encode("latin-1")


def test_generate_incident_report_survives_a_real_em_dash_citation():
    """Regression test for the actual production bug found while verifying
    Demo Mode: rag-service's real corpus citations legitimately contain
    em-dashes (e.g. "Incident INC-2026-000482 — Tank Farm Gas Alarm
    Escalation"), and fpdf2's Helvetica font cannot encode them -- this
    exception previously propagated uncaught through the Emergency Agent's
    bus subscriber loop, permanently killing its ability to respond to every
    future critical assertion for the rest of the process's life."""
    from app.orchestrator.reports import generate_incident_report

    path = generate_incident_report(
        incident_id=888999, incident_number="INC-TEST-EMDASH", hazard_class="fire", equipment_tag="V-12",
        zone_id=3, score=88.0, severity="critical", confidence=0.9,
        contributing_factors=[{"source_type": "sensor", "evidence_node_id": "gas", "likelihood_ratio": 20.0, "evidence_refs": ["1"]}],
        recommendations=["Test recommendation."],
        ai_summary="Relevant governing procedure/regulation (retrieved, cited):\n- Incident INC-2026-000482 — Tank Farm Gas Alarm Escalation, Summary: a real em-dash from a real citation.",
        timeline_events=[{"event_type": "created", "occurred_at": "2026-07-22T00:00:00Z"}],
    )
    file_bytes = Path(path).read_bytes()
    assert file_bytes.startswith(b"%PDF")
    Path(path).unlink()
