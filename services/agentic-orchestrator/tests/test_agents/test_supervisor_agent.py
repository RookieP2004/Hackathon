import asyncio

from aegis_agents.envelope import AgentMessage, MessageType
from app.agents.supervisor_agent import SupervisorAgent
from app.agents import topics

POSTGRES_DSN = "postgresql://aegis:changeme_local_only@localhost:5432/aegis"


async def test_supervisor_tracks_fleet_health(bus):
    agent = SupervisorAgent(bus, POSTGRES_DSN)
    agent.agent_id = "zztest-supervisor-agent"
    agent.memory.agent_id = "zztest-supervisor-agent"
    subscriber_task = asyncio.create_task(agent.run_subscriber_loop())
    await asyncio.sleep(0.2)

    await bus.publish(topics.HEALTH, AgentMessage(agent_id="zztest-some-agent", agent_version="v1", message_type=MessageType.HEALTH, payload={"healthy": True, "ticks": 5}))
    await asyncio.sleep(0.3)
    subscriber_task.cancel()

    assert agent.fleet_health.get("zztest-some-agent") == {"healthy": True, "ticks": 5}


async def test_supervisor_never_downgrades_critical_on_disagreement(bus):
    agent = SupervisorAgent(bus, POSTGRES_DSN)
    agent.agent_id = "zztest-supervisor-agent-2"
    agent.memory.agent_id = "zztest-supervisor-agent-2"
    subscriber_task = asyncio.create_task(agent.run_subscriber_loop())
    await asyncio.sleep(0.2)

    escalations = []

    async def _listen():
        async for message in bus.subscribe(topics.ESCALATION):
            if message.payload.get("equipment_id") == 999001:
                escalations.append(message)
                break

    listener = asyncio.create_task(_listen())
    await asyncio.sleep(0.1)

    await bus.publish(topics.ASSERTION, AgentMessage(
        agent_id="zztest-agent-a", agent_version="v1", message_type=MessageType.ASSERTION,
        confidence=0.4, payload={"equipment_id": 999001, "severity": "low"},
    ))
    await asyncio.sleep(0.1)
    await bus.publish(topics.ASSERTION, AgentMessage(
        agent_id="zztest-agent-b", agent_version="v1", message_type=MessageType.ASSERTION,
        confidence=0.95, payload={"equipment_id": 999001, "severity": "critical"},
    ))

    await asyncio.wait_for(listener, timeout=5.0)
    subscriber_task.cancel()

    assert len(escalations) == 1
    assert escalations[0].payload["precedence_severity"] == "critical"
    assert escalations[0].payload["disagreement"] == {"zztest-agent-a": "low", "zztest-agent-b": "critical"}


async def test_supervisor_does_not_arbitrate_when_agents_agree(bus):
    agent = SupervisorAgent(bus, POSTGRES_DSN)
    agent.agent_id = "zztest-supervisor-agent-3"
    agent.memory.agent_id = "zztest-supervisor-agent-3"
    subscriber_task = asyncio.create_task(agent.run_subscriber_loop())
    await asyncio.sleep(0.2)

    escalations = []

    async def _listen():
        async for message in bus.subscribe(topics.ESCALATION):
            if message.payload.get("equipment_id") == 999002:
                escalations.append(message)
            break

    listener = asyncio.create_task(_listen())
    await asyncio.sleep(0.1)

    for agent_id in ("zztest-agent-c", "zztest-agent-d"):
        await bus.publish(topics.ASSERTION, AgentMessage(
            agent_id=agent_id, agent_version="v1", message_type=MessageType.ASSERTION,
            confidence=0.9, payload={"equipment_id": 999002, "severity": "high"},
        ))
    await asyncio.sleep(0.5)
    listener.cancel()
    subscriber_task.cancel()

    assert escalations == []
