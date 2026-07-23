import asyncio

import asyncpg

from app.agents.worker_agent import WorkerAgent

POSTGRES_DSN = "postgresql://aegis:changeme_local_only@localhost:5432/aegis"
COMPUTER_VISION_URL = "http://localhost:8004"
TEST_ZONE_ID = 1  # Tank Farm A, safe_occupancy_limit = 4


async def _seed_overcapacity_shift(count: int) -> tuple[list[int], list[int], int | None]:
    """Dedicated `zztest-` workers, not the fixed real roster -- avoids
    colliding with the real worker-in-zone-3 fact seeded in the Risk Fusion
    Engine pass (an overlapping-period double-booking would be silently
    skipped by the exclusion constraint, making the test's exact count
    non-deterministic)."""
    conn = await asyncpg.connect(POSTGRES_DSN)
    try:
        employer_id = await conn.fetchval(
            "INSERT INTO employers (name, is_internal) VALUES ('zztest-employer', true) RETURNING id"
        )
        shift_id = await conn.fetchval("SELECT id FROM shifts WHERE plant_id = 1 LIMIT 1")
        worker_ids = []
        for i in range(count):
            wid = await conn.fetchval(
                "INSERT INTO workers (employer_id, badge_id, full_name, worker_type) VALUES ($1, $2, $3, 'employee') RETURNING id",
                employer_id, f"ZZTEST-BADGE-{i}", f"ZZTest Worker {i}",
            )
            worker_ids.append(wid)
        assignment_ids = []
        for worker_id in worker_ids:
            # assigned_date uses Postgres's own now()::date, matching exactly what
            # worker_agent.py's query filters on -- using the test process's local
            # date.today() here caused a real, reproducible failure near a UTC day
            # boundary (the app server's local timezone is ahead of Postgres's UTC
            # clock, so a Python-computed "today" landed one day past what the
            # query's own now()::date considered "today").
            aid = await conn.fetchval(
                "INSERT INTO shift_assignments (shift_id, worker_id, zone_id, assigned_date, period) "
                "VALUES ($1, $2, $3, now()::date, tsrange((now() - interval '1 hour')::timestamp, (now() + interval '1 hour')::timestamp)) "
                "RETURNING id",
                shift_id, worker_id, TEST_ZONE_ID,
            )
            assignment_ids.append(aid)
        return assignment_ids, worker_ids, employer_id
    finally:
        await conn.close()


async def _cleanup(assignment_ids: list[int], worker_ids: list[int], employer_id: int | None) -> None:
    conn = await asyncpg.connect(POSTGRES_DSN)
    try:
        if assignment_ids:
            await conn.execute("DELETE FROM shift_assignments WHERE id = ANY($1::bigint[])", assignment_ids)
        if worker_ids:
            await conn.execute("DELETE FROM workers WHERE id = ANY($1::bigint[])", worker_ids)
        if employer_id:
            await conn.execute("DELETE FROM employers WHERE id = $1", employer_id)
    finally:
        await conn.close()


async def test_occupancy_threshold_exceeded_flagged(bus):
    assignment_ids, worker_ids, employer_id = await _seed_overcapacity_shift(5)  # 5 > zone 1's limit of 4
    try:
        agent = WorkerAgent(bus, POSTGRES_DSN, COMPUTER_VISION_URL, jwt_secret="changeme_generate_a_real_secret_before_any_shared_deployment", jwt_algorithm="HS256")
        agent.agent_id = "zztest-worker-agent"
        agent.memory.agent_id = "zztest-worker-agent"

        assertions = []

        async def _listen():
            async for message in bus.subscribe("agent.assertion"):
                if message.agent_id == "zztest-worker-agent" and message.payload.get("zone_id") == TEST_ZONE_ID:
                    assertions.append(message)
                    break

        listener = asyncio.create_task(_listen())
        await asyncio.sleep(0.1)
        await agent.tick()
        await asyncio.wait_for(listener, timeout=5.0)

        assert len(assertions) == 1
        match = assertions[0]
        assert match.payload["current_count"] > match.payload["safe_occupancy_limit"]
        assert match.confidence == 1.0
    finally:
        await _cleanup(assignment_ids, worker_ids, employer_id)
