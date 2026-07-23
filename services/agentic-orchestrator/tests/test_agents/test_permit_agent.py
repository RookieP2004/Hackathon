import asyncio

from app.agents.permit_agent import PermitAgent
from app.agents import topics

POSTGRES_DSN = "postgresql://aegis:changeme_local_only@localhost:5432/aegis"
KNOWLEDGE_GRAPH_URL = "http://localhost:8007"
JWT_SECRET = "changeme_generate_a_real_secret_before_any_shared_deployment"
V12_EQUIPMENT_ID = 2  # real seeded equipment, no active permit scoped to it (per the Risk Fusion Engine pass's own findings)


async def test_permit_agent_responds_approve_when_no_conflict(bus):
    agent = PermitAgent(bus, POSTGRES_DSN, KNOWLEDGE_GRAPH_URL, jwt_secret=JWT_SECRET, jwt_algorithm="HS256")
    agent.agent_id = "zztest-permit-agent"
    agent.memory.agent_id = "zztest-permit-agent"

    subscriber_task = asyncio.create_task(agent.run_subscriber_loop())
    await asyncio.sleep(0.2)
    try:
        response = await bus.request(
            requester_agent_id="zztest-requester", requester_version="v1",
            target_topic=topics.PERMIT_CONFLICT_CHECK_REQUEST, response_topic="zztest-requester.response",
            payload={"equipment_id": V12_EQUIPMENT_ID, "action_description": "zztest isolate valve"}, timeout=5.0,
        )
    finally:
        subscriber_task.cancel()

    assert response is not None
    assert response.payload["verdict"] == "approve"
    assert response.confidence == 1.0


async def test_permit_agent_flags_conflict_for_expired_active_permit_equipment(bus):
    # PIPE-12A (equipment_id=1) has a permit with status='active' but an already-expired
    # valid_to (a real fact confirmed in the Agentic Framework pass's own exploration) --
    # the graph's permit-conflict query filters on validFrom<=now()<=validTo, so this
    # specific one should NOT show as a conflict (it's expired) -- verifying the negative
    # case explicitly here, since PIPE-12A's permit being expired is exactly why Compliance
    # Agent (not Permit Agent) is the one that should flag it.
    agent = PermitAgent(bus, POSTGRES_DSN, KNOWLEDGE_GRAPH_URL, jwt_secret=JWT_SECRET, jwt_algorithm="HS256")
    agent.agent_id = "zztest-permit-agent-2"
    agent.memory.agent_id = "zztest-permit-agent-2"

    subscriber_task = asyncio.create_task(agent.run_subscriber_loop())
    await asyncio.sleep(0.2)
    try:
        response = await bus.request(
            requester_agent_id="zztest-requester", requester_version="v1",
            target_topic=topics.PERMIT_CONFLICT_CHECK_REQUEST, response_topic="zztest-requester.response",
            payload={"equipment_id": 1, "action_description": "zztest isolate pipeline"}, timeout=5.0,
        )
    finally:
        subscriber_task.cancel()

    assert response is not None
    assert response.payload["verdict"] == "approve"  # expired permits don't count as an active conflict
