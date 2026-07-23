import asyncio
from datetime import datetime, timedelta, timezone

import asyncpg

from app.agents.sensor_agent import SensorAgent

POSTGRES_DSN = "postgresql://aegis:changeme_local_only@localhost:5432/aegis"
TEST_SENSOR_ID = 1  # GS-14


async def _seed_readings(values: list[float]) -> None:
    conn = await asyncpg.connect(POSTGRES_DSN)
    try:
        await conn.execute("DELETE FROM sensor_readings WHERE sensor_id = $1", TEST_SENSOR_ID)
        base = datetime.now(timezone.utc) - timedelta(seconds=len(values) * 10)
        await conn.executemany(
            "INSERT INTO sensor_readings (sensor_id, value, quality, recorded_at) VALUES ($1, $2, 'good', $3)",
            [(TEST_SENSOR_ID, v, base + timedelta(seconds=i * 10)) for i, v in enumerate(values)],
        )
    finally:
        await conn.close()


async def test_flat_readings_produce_no_assertion_for_that_sensor(bus):
    # Other real sensors in SensorAgent's watched cluster are independently, continuously
    # ticked by predictive-risk-engine's own live background loop -- this only asserts
    # that OUR flat, seeded sensor specifically stays quiet, not that the whole watch
    # list is silent (that would be flaky against genuinely concurrent live activity).
    await _seed_readings([200.0 + (i % 3) for i in range(20)])
    agent = SensorAgent(bus, POSTGRES_DSN)
    agent.agent_id = "zztest-sensor-agent"
    agent.memory.agent_id = "zztest-sensor-agent"

    assertions = []

    async def _listen():
        async for message in bus.subscribe("agent.assertion"):
            if message.agent_id == "zztest-sensor-agent":
                assertions.append(message)
                if len(assertions) >= 1:
                    break

    listener = asyncio.create_task(_listen())
    await asyncio.sleep(0.1)
    await agent.tick()
    await asyncio.sleep(0.3)
    listener.cancel()

    assert all(a.payload["sensor_id"] != TEST_SENSOR_ID for a in assertions)


async def test_escalating_readings_produce_an_assertion(bus):
    normal = [200.0 + (i % 3) for i in range(15)]
    spike = [200.0 + i * 400 for i in range(1, 8)]  # a real, sharp escalation
    await _seed_readings(normal + spike)

    agent = SensorAgent(bus, POSTGRES_DSN)
    agent.agent_id = "zztest-sensor-agent-2"
    agent.memory.agent_id = "zztest-sensor-agent-2"

    assertions = []

    async def _listen():
        async for message in bus.subscribe("agent.assertion"):
            if message.agent_id == "zztest-sensor-agent-2":
                assertions.append(message)
                break

    listener = asyncio.create_task(_listen())
    await asyncio.sleep(0.1)
    await agent.tick()
    await asyncio.wait_for(listener, timeout=3.0)

    assert len(assertions) >= 1
    match = next(a for a in assertions if a.payload["sensor_id"] == TEST_SENSOR_ID)
    assert match.confidence > 0
    assert "anomaly" in match.reasoning.lower() or "z-score" in match.reasoning.lower()
