import asyncio

import asyncpg

from app.agents.maintenance_agent import MaintenanceAgent

POSTGRES_DSN = "postgresql://aegis:changeme_local_only@localhost:5432/aegis"


async def _seed_high_score(equipment_id: int) -> int:
    conn = await asyncpg.connect(POSTGRES_DSN)
    try:
        return await conn.fetchval(
            "INSERT INTO risk_scores (equipment_id, score, confidence, contributing_factors, model_version) "
            "VALUES ($1, 75.0, 0.8, '[]'::jsonb, 'risk-fusion:zztest_hazard:v1') RETURNING id",
            equipment_id,
        )
    finally:
        await conn.close()


async def test_creates_a_real_work_order_for_a_high_score(bus):
    equipment_id = 2  # V-12
    risk_score_id = await _seed_high_score(equipment_id)

    agent = MaintenanceAgent(bus, POSTGRES_DSN)
    agent.agent_id = "zztest-maintenance-agent"
    agent.memory.agent_id = "zztest-maintenance-agent"

    await agent.tick()

    conn = await asyncpg.connect(POSTGRES_DSN)
    try:
        row = await conn.fetchrow(
            "SELECT id FROM maintenance_records WHERE description LIKE $1", f"%[auto:risk_score:{risk_score_id}]%"
        )
    finally:
        await conn.close()

    assert row is not None


async def test_is_idempotent_on_repeated_ticks(bus):
    equipment_id = 3  # RV-9
    risk_score_id = await _seed_high_score(equipment_id)

    agent = MaintenanceAgent(bus, POSTGRES_DSN)
    agent.agent_id = "zztest-maintenance-agent-2"
    agent.memory.agent_id = "zztest-maintenance-agent-2"

    await agent.tick()
    await agent.tick()
    await agent.tick()

    conn = await asyncpg.connect(POSTGRES_DSN)
    try:
        count = await conn.fetchval(
            "SELECT count(*) FROM maintenance_records WHERE description LIKE $1", f"%[auto:risk_score:{risk_score_id}]%"
        )
    finally:
        await conn.close()

    assert count == 1
