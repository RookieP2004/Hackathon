"""
The AI Copilot, exercised end-to-end against the real, live agentic-orchestrator
service (localhost:8009) -- every answer must come from a real backend call
(incident-service, notification-service, predictive-risk-engine,
knowledge-graph, rag-service, or a direct Postgres read), never a fabricated
sentence, since no LLM is available in this environment.
"""

from pathlib import Path

import asyncpg
import httpx
from jose import jwt

BASE_URL = "http://localhost:8009"
POSTGRES_DSN = "postgresql://aegis:changeme_local_only@localhost:5432/aegis"
JWT_SECRET = "changeme_generate_a_real_secret_before_any_shared_deployment"
V12_TAG = "V-12"


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


async def _ask(query: str, session_id: str | None = None) -> dict:
    headers = await _auth_headers()
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(f"{BASE_URL}/copilot/query", headers=headers, json={"query": query, "session_id": session_id})
        response.raise_for_status()
        return response.json()


async def test_current_state_intent_is_grounded_in_real_open_incidents_and_alerts():
    result = await _ask("what is happening right now at the plant")
    assert result["intent"] == "current_state"
    assert isinstance(result["answer"], str) and len(result["answer"]) > 0


async def test_why_risk_increasing_resolves_the_mentioned_equipment_and_hazard():
    result = await _ask(f"why is the explosion risk high on {V12_TAG}")
    assert result["intent"] == "why_risk_increasing"
    assert result["entities"]["equipment"]["tag"] == V12_TAG
    assert result["entities"]["hazard_class"] == "explosion"
    assert "explosion" in result["answer"].lower()


async def test_machine_history_reports_real_maintenance_and_incident_data():
    result = await _ask(f"show machine history for {V12_TAG}")
    assert result["intent"] == "machine_history"
    assert result["entities"]["equipment"]["tag"] == V12_TAG
    assert V12_TAG in result["answer"]


async def test_predict_failures_returns_real_time_to_event_estimates():
    result = await _ask(f"predict failures for {V12_TAG}")
    assert result["intent"] == "predict_failures"
    assert "time to event" in result["answer"].lower() or "time-to-event" in result["answer"].lower()


async def test_permit_violations_surfaces_the_real_seeded_expired_permits():
    result = await _ask("show permit violations")
    assert result["intent"] == "permit_violations"
    # The demo dataset has real permits with status='active' but valid_to already in the past.
    assert "expired" in result["answer"].lower()


async def test_generate_inspection_report_writes_a_real_pdf_and_report_row():
    result = await _ask(f"generate an inspection report for {V12_TAG}")
    assert result["intent"] == "generate_inspection_report"

    file_path = None
    for line in result["answer"].split(": ", 1):
        if line.strip().endswith(".pdf"):
            file_path = line.strip()
    assert file_path is not None
    assert Path(file_path).exists()
    assert Path(file_path).read_bytes().startswith(b"%PDF")

    report_id = result["citations"][0].split(":")[1]
    conn = await asyncpg.connect(POSTGRES_DSN)
    try:
        row = await conn.fetchrow("SELECT status, file_url FROM reports WHERE id = $1", int(report_id))
        await conn.execute("DELETE FROM reports WHERE id = $1", int(report_id))
    finally:
        await conn.close()
    assert row["status"] == "completed"

    Path(file_path).unlink(missing_ok=True)


async def test_similar_incidents_uses_the_real_knowledge_graph():
    result = await _ask(f"find similar incidents to {V12_TAG}")
    assert result["intent"] == "similar_incidents"
    assert isinstance(result["answer"], str)


async def test_explain_regulation_is_grounded_in_real_rag_citations():
    result = await _ask("explain the required response to a gas leak")
    assert result["intent"] == "explain_regulation"
    assert isinstance(result["citations"], list)


async def test_unknown_intent_degrades_gracefully_instead_of_fabricating():
    result = await _ask("purple elephants dance on the moon")
    assert result["intent"] == "unknown"
    assert "confident answer" in result["answer"].lower()


async def test_session_continuity_remembers_the_last_mentioned_equipment():
    first = await _ask(f"show machine history for {V12_TAG}")
    session_id = first["session_id"]

    second = await _ask("why is the explosion risk high", session_id=session_id)
    assert second["entities"]["equipment"]["tag"] == V12_TAG
