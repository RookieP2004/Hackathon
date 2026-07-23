import asyncio

import asyncpg
import pytest

from aegis_agents.base_agent import BaseAgent
from aegis_agents.bus import MessageBus
from aegis_agents.envelope import MessageType
from aegis_agents.memory import ensure_agent_memory_tables

POSTGRES_DSN = "postgresql://aegis:changeme_local_only@localhost:5432/aegis"
REDIS_URL = "redis://localhost:6379/0"


class _TickingAgent(BaseAgent):
    agent_id = "zztest-ticking-agent"
    tick_interval_seconds = 0.1

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tick_count = 0

    async def tick(self) -> None:
        self.tick_count += 1


class _AlwaysFailsFailOpenAgent(BaseAgent):
    agent_id = "zztest-fail-open-agent"
    failure_mode = "fail_open"
    tick_interval_seconds = 0.05
    max_consecutive_failures_before_degraded = 2

    async def tick(self) -> None:
        raise RuntimeError("simulated Core failure")


class _AlwaysFailsFailClosedAgent(BaseAgent):
    agent_id = "zztest-fail-closed-agent"
    failure_mode = "fail_closed"
    tick_interval_seconds = 0.05
    max_consecutive_failures_before_degraded = 2

    async def tick(self) -> None:
        raise RuntimeError("simulated Core failure")


@pytest.fixture(autouse=True)
async def _clean_test_agent_rows():
    await ensure_agent_memory_tables(POSTGRES_DSN)
    conn = await asyncpg.connect(POSTGRES_DSN)
    try:
        await conn.execute("DELETE FROM agent_decision_log WHERE agent_id LIKE 'zztest-%'")
        await conn.execute("DELETE FROM agent_episodic_memory WHERE agent_id LIKE 'zztest-%'")
    finally:
        await conn.close()
    yield


@pytest.fixture
async def bus():
    b = MessageBus(REDIS_URL)
    await b.connect()
    yield b
    await b.close()


async def test_agent_ticks_independently_once_started(bus):
    agent = _TickingAgent(bus, POSTGRES_DSN)
    agent.start()
    await asyncio.sleep(0.35)
    await agent.stop()
    assert agent.tick_count >= 2
    assert agent.is_healthy is True


async def test_agent_publishes_heartbeats(bus):
    heartbeats = []

    async def _listen():
        async for message in bus.subscribe("agent.health"):
            if message.agent_id == "zztest-ticking-agent":
                heartbeats.append(message)
                break

    listener = asyncio.create_task(_listen())
    await asyncio.sleep(0.2)

    agent = _TickingAgent(bus, POSTGRES_DSN)
    agent.start()
    await asyncio.wait_for(listener, timeout=3.0)
    await agent.stop()

    assert len(heartbeats) == 1
    assert heartbeats[0].message_type == MessageType.HEALTH
    assert heartbeats[0].payload["healthy"] is True


async def test_assert_finding_publishes_logs_and_remembers(bus):
    agent = _TickingAgent(bus, POSTGRES_DSN)

    assertions = []

    async def _listen():
        # Real, unrelated agents (the live agentic-orchestrator service, if running)
        # publish on this same shared "agent.assertion" topic continuously -- must
        # filter to this test's own agent_id, not just take the first message seen.
        async for message in bus.subscribe("agent.assertion"):
            if message.agent_id == agent.agent_id:
                assertions.append(message)
                break

    listener = asyncio.create_task(_listen())
    await asyncio.sleep(0.2)

    await agent.assert_finding(
        decision="anomaly_detected", reasoning="gas reading 4 std above baseline",
        confidence=0.92, evidence_refs=["sensor:1"], payload={"sensor_tag": "GS-14"},
    )
    await asyncio.wait_for(listener, timeout=3.0)

    assert len(assertions) == 1
    assert assertions[0].confidence == 0.92
    assert assertions[0].payload["sensor_tag"] == "GS-14"

    decisions = await agent.memory.recent_decisions(limit=5)
    assert any(d.decision == "anomaly_detected" for d in decisions)


async def test_fail_open_agent_does_not_escalate_when_degraded(bus):
    escalations = []

    async def _listen():
        async for message in bus.subscribe("agent.escalation"):
            if message.agent_id == "zztest-fail-open-agent":
                escalations.append(message)
            break

    listener = asyncio.create_task(_listen())
    await asyncio.sleep(0.1)

    agent = _AlwaysFailsFailOpenAgent(bus, POSTGRES_DSN)
    agent.start()
    await asyncio.sleep(0.4)
    await agent.stop()

    assert agent.is_healthy is False
    assert agent.degraded_reason is not None
    listener.cancel()
    assert escalations == []


async def test_fail_closed_agent_escalates_when_degraded(bus):
    escalations = []

    async def _listen():
        async for message in bus.subscribe("agent.escalation"):
            if message.agent_id == "zztest-fail-closed-agent":
                escalations.append(message)
                break

    listener = asyncio.create_task(_listen())
    await asyncio.sleep(0.2)

    agent = _AlwaysFailsFailClosedAgent(bus, POSTGRES_DSN)
    agent.start()
    await asyncio.wait_for(listener, timeout=3.0)
    await agent.stop()

    assert len(escalations) == 1
    assert "fails closed" in escalations[0].payload["reason"]
