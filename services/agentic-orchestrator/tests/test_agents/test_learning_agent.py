import asyncio
from datetime import datetime, timedelta, timezone

import asyncpg

from app.agents.learning_agent import LearningAgent

POSTGRES_DSN = "postgresql://aegis:changeme_local_only@localhost:5432/aegis"
DRIFTING_AGENT_ID = "test-only-drifting-agent"


async def _seed_decisions(agent_id: str, *, prior_confidences: list[float], recent_confidences: list[float]) -> None:
    conn = await asyncpg.connect(POSTGRES_DSN)
    try:
        now = datetime.now(timezone.utc)
        for i, conf in enumerate(prior_confidences):
            await conn.execute(
                "INSERT INTO agent_decision_log (agent_id, agent_version, decision, reasoning, confidence, created_at) "
                "VALUES ($1, 'v1', 'd', 'r', $2, $3)",
                agent_id, conf, now - timedelta(minutes=90) + timedelta(seconds=i),
            )
        for i, conf in enumerate(recent_confidences):
            await conn.execute(
                "INSERT INTO agent_decision_log (agent_id, agent_version, decision, reasoning, confidence, created_at) "
                "VALUES ($1, 'v1', 'd', 'r', $2, $3)",
                agent_id, conf, now - timedelta(minutes=30) + timedelta(seconds=i),
            )
    finally:
        await conn.close()


async def test_detects_real_confidence_drift(bus):
    await _seed_decisions(DRIFTING_AGENT_ID, prior_confidences=[0.9, 0.92, 0.88], recent_confidences=[0.4, 0.45, 0.42])

    agent = LearningAgent(bus, POSTGRES_DSN)
    agent.agent_id = "zztest-learning-agent"
    agent.memory.agent_id = "zztest-learning-agent"

    assertions = []

    async def _listen():
        async for message in bus.subscribe("agent.assertion"):
            if message.agent_id == "zztest-learning-agent" and message.payload.get("agent_id") == DRIFTING_AGENT_ID:
                assertions.append(message)
                break

    listener = asyncio.create_task(_listen())
    await asyncio.sleep(0.1)
    await agent.tick()
    await asyncio.wait_for(listener, timeout=5.0)

    assert len(assertions) == 1
    assert "drift" in assertions[0].reasoning.lower()
    assert "no retraining" in assertions[0].reasoning.lower() or "no" in assertions[0].reasoning.lower()

    conn = await asyncpg.connect(POSTGRES_DSN)
    try:
        await conn.execute("DELETE FROM agent_decision_log WHERE agent_id = $1", DRIFTING_AGENT_ID)
    finally:
        await conn.close()
