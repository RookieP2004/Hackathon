"""
Schema setup — KNOWLEDGE_GRAPH.md §4. Constraints/indexes are declared once,
idempotently (every statement is `IF NOT EXISTS`), mirroring the uniqueness
guarantees already established relationally rather than inventing separate
identity rules for the graph (§1.2: a node's `id` always equals its
corresponding Postgres row's primary key).
"""

from __future__ import annotations

from neo4j import AsyncDriver

CONSTRAINTS: list[str] = [
    "CREATE CONSTRAINT plant_id IF NOT EXISTS FOR (n:Plant) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT building_id IF NOT EXISTS FOR (n:Building) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT zone_id IF NOT EXISTS FOR (n:Zone) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT equipment_id IF NOT EXISTS FOR (n:Equipment) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT sensor_id IF NOT EXISTS FOR (n:Sensor) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT worker_id IF NOT EXISTS FOR (n:Worker) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT permit_id IF NOT EXISTS FOR (n:Permit) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT incident_id IF NOT EXISTS FOR (n:Incident) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT maintenance_id IF NOT EXISTS FOR (n:Maintenance) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT document_id IF NOT EXISTS FOR (n:Document) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT regulation_id IF NOT EXISTS FOR (n:Regulation) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT weather_episode_id IF NOT EXISTS FOR (n:WeatherEpisode) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT risk_id IF NOT EXISTS FOR (n:Risk) REQUIRE n.id IS UNIQUE",
]

INDEXES: list[str] = [
    "CREATE INDEX equipment_tag IF NOT EXISTS FOR (n:Equipment) ON (n.tag)",
    "CREATE INDEX sensor_tag IF NOT EXISTS FOR (n:Sensor) ON (n.tag)",
    "CREATE INDEX incident_severity IF NOT EXISTS FOR (n:Incident) ON (n.severity)",
    "CREATE INDEX risk_hazard_class IF NOT EXISTS FOR (n:Risk) ON (n.hazardClass, n.assessedAt)",
    "CREATE FULLTEXT INDEX document_title_search IF NOT EXISTS FOR (n:Document|Regulation) ON EACH [n.title]",
]


async def apply_schema(driver: AsyncDriver) -> dict:
    applied = []
    async with driver.session() as session:
        for statement in CONSTRAINTS + INDEXES:
            await session.run(statement)
            applied.append(statement)
    return {"applied": len(applied), "statements": applied}
