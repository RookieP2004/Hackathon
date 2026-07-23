import asyncpg
import pytest

from aegis_agents import MessageBus, ensure_agent_memory_tables

POSTGRES_DSN = "postgresql://aegis:changeme_local_only@localhost:5432/aegis"
REDIS_URL = "redis://localhost:6379/0"


@pytest.fixture(autouse=True)
async def _clean_test_agent_rows():
    await ensure_agent_memory_tables(POSTGRES_DSN)
    conn = await asyncpg.connect(POSTGRES_DSN)
    try:
        await conn.execute("DELETE FROM agent_decision_log WHERE agent_id LIKE 'zztest-%' OR reasoning LIKE '%zztest%'")
        await conn.execute("DELETE FROM agent_episodic_memory WHERE agent_id LIKE 'zztest-%'")
        await conn.execute("DELETE FROM maintenance_records WHERE description LIKE '%zztest%'")
        await conn.execute("DELETE FROM emergency_events WHERE event_type LIKE 'zztest%'")
        await conn.execute("DELETE FROM risk_scores WHERE model_version LIKE 'risk-fusion:zztest%'")
    finally:
        await conn.close()
    yield


@pytest.fixture
async def bus():
    b = MessageBus(REDIS_URL)
    await b.connect()
    yield b
    await b.close()
