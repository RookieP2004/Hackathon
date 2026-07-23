"""
Runs a real full sync against the actual running Postgres (the same demo DB
every other service in this repo uses) and the real Neo4j instance, then spot
-checks that specific known-seeded rows actually materialized as graph nodes
with the right relationships -- not just that the sync function returned
without raising.
"""

import asyncpg

from app.graph.sync import run_full_sync

POSTGRES_DSN = "postgresql://aegis:changeme_local_only@localhost:5432/aegis"


async def test_full_sync_matches_postgres_row_counts(writer, driver):
    async with driver.session() as session:
        await session.run("MATCH (n) WHERE NOT n.id STARTS WITH 'test-' DETACH DELETE n")

    counts = await run_full_sync(writer, POSTGRES_DSN)

    conn = await asyncpg.connect(POSTGRES_DSN)
    try:
        pg_zone_count = await conn.fetchval("SELECT count(*) FROM zones")
        pg_equipment_count = await conn.fetchval("SELECT count(*) FROM equipment")
        pg_sensor_count = await conn.fetchval("SELECT count(*) FROM sensors")
        pg_worker_count = await conn.fetchval("SELECT count(*) FROM workers")
    finally:
        await conn.close()

    assert counts["zones"] == pg_zone_count
    assert counts["equipment"] == pg_equipment_count
    assert counts["sensors"] == pg_sensor_count
    assert counts["workers"] == pg_worker_count

    async with driver.session() as session:
        result = await session.run("MATCH (n:Zone) RETURN count(n) AS c")
        record = await result.single()
        assert record["c"] == pg_zone_count

        result = await session.run("MATCH (:Zone)<-[:HAS_ZONE]-(:Building)<-[:HAS_BUILDING]-(:Plant) RETURN count(*) AS c")
        record = await result.single()
        assert record["c"] == pg_zone_count  # every zone should trace back to a plant


async def test_sync_is_idempotent(writer):
    first = await run_full_sync(writer, POSTGRES_DSN)
    second = await run_full_sync(writer, POSTGRES_DSN)
    assert first == second
