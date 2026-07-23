import asyncio

import asyncpg

from aegis_agents.envelope import AgentMessage, MessageType
from app.agents.emergency_agent import EmergencyAgent
from app.agents.permit_agent import PermitAgent
from app.agents import topics

POSTGRES_DSN = "postgresql://aegis:changeme_local_only@localhost:5432/aegis"
KNOWLEDGE_GRAPH_URL = "http://localhost:8007"
V12_EQUIPMENT_ID = 2
ZONE_ID = 3
JWT_SECRET = "changeme_generate_a_real_secret_before_any_shared_deployment"


def _emergency_agent(bus) -> EmergencyAgent:
    return EmergencyAgent(
        bus, POSTGRES_DSN, predictive_risk_engine_url="http://localhost:8005",
        incident_service_url="http://localhost:8010", notification_service_url="http://localhost:8011",
        rag_service_url="http://localhost:8008", jwt_secret=JWT_SECRET, jwt_algorithm="HS256",
    )


async def test_emergency_agent_runs_the_full_automatic_response_on_critical_risk_with_clean_permit(bus):
    # PermitAgent listens on a fixed topic name (topics.PERMIT_CONFLICT_CHECK_REQUEST),
    # not one derived from its own agent_id -- only the memory-log identity needs isolating.
    permit_agent = PermitAgent(bus, POSTGRES_DSN, KNOWLEDGE_GRAPH_URL, jwt_secret=JWT_SECRET, jwt_algorithm="HS256")
    permit_agent.agent_id = "zztest-permit-agent-live"
    permit_agent.memory.agent_id = "zztest-permit-agent-live"
    permit_task = asyncio.create_task(permit_agent.run_subscriber_loop())

    emergency_agent = _emergency_agent(bus)
    emergency_agent.agent_id = "zztest-emergency-agent"
    emergency_agent.memory.agent_id = "zztest-emergency-agent"
    emergency_task = asyncio.create_task(emergency_agent.run_subscriber_loop())

    await asyncio.sleep(0.2)

    escalations = []

    async def _listen():
        async for message in bus.subscribe(topics.ESCALATION):
            if message.agent_id == "zztest-emergency-agent":
                escalations.append(message)
                break

    listener = asyncio.create_task(_listen())
    await asyncio.sleep(0.1)

    # "explosion" is a real hazard class the live Risk Fusion Engine tracks for
    # V-12 -- _fetch_current_assessment matches on hazard_class name, not on
    # this fabricated message's score/severity, so the agent fetches its own
    # fresh, genuinely-computed assessment rather than trusting this payload.
    critical_assertion = AgentMessage(
        agent_id="zztest-prediction-agent", agent_version="v1", message_type=MessageType.ASSERTION,
        confidence=0.9, evidence_refs=["risk_score:1"],
        payload={"equipment_id": V12_EQUIPMENT_ID, "zone_id": ZONE_ID, "hazard_class": "explosion", "score": 88.0, "severity": "critical"},
    )
    await bus.publish(topics.ASSERTION, critical_assertion)

    try:
        await asyncio.wait_for(listener, timeout=20.0)
    finally:
        permit_task.cancel()
        emergency_task.cancel()

    assert len(escalations) == 1
    payload = escalations[0].payload
    assert "automated emergency response completed" in payload["reason"].lower()
    assert payload["hazard_class"] == "explosion"
    incident_id = payload["incident_id"]
    assert len(payload["timeline"]) == 9  # the full 10-step flow minus the initial incident-creation step itself

    conn = await asyncpg.connect(POSTGRES_DSN)
    try:
        incident_row = await conn.fetchrow("SELECT severity, ai_generated_summary FROM incidents WHERE id = $1", incident_id)
        report_rows = await conn.fetch("SELECT file_url FROM reports WHERE parameters->>'incident_id' = $1", str(incident_id))
        alert_count = await conn.fetchval("SELECT count(*) FROM alerts WHERE related_incident_id = $1", incident_id)
    finally:
        await conn.close()

    assert incident_row is not None
    assert incident_row["ai_generated_summary"] is not None
    assert alert_count == 2

    from pathlib import Path

    for report in report_rows:
        Path(report["file_url"]).unlink(missing_ok=True)
    Path(payload["incident_report_path"]).unlink(missing_ok=True)
    Path(payload["regulatory_report_path"]).unlink(missing_ok=True)

    # Close the incident this test created -- EmergencyAgent now suppresses a
    # duplicate automatic response while any open incident exists for the
    # same equipment, so leaving this one open would silently break every
    # subsequent test/demo run against V-12.
    conn = await asyncpg.connect(POSTGRES_DSN)
    try:
        await conn.execute("UPDATE incidents SET status='closed', closed_at=now() WHERE id = $1", incident_id)
    finally:
        await conn.close()
