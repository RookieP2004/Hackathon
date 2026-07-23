"""
Every test here runs against the real, already-running Neo4j instance
(bolt://localhost:7687) rather than a mock -- per this project's standing
practice of empirically verifying against a live server/database, not just
reviewing written code. Test data uses `test-` prefixed ids exclusively and
is deleted before and after each test, so runs never collide with or
pollute the real data a `POST /graph/sync` run has materialized from Postgres.
"""

from __future__ import annotations

import pytest
from neo4j import AsyncGraphDatabase

from app.graph.reads import GraphReader
from app.graph.writes import GraphWriter

NEO4J_URI = "bolt://localhost:7687"
NEO4J_AUTH = ("neo4j", "changeme_local_only")


@pytest.fixture(autouse=True)
async def _clean_test_nodes():
    """Runs for every test in this package regardless of which fixtures it
    requests -- test_graph_api.py's TestClient-based tests write `test-`
    prefixed nodes through the live app, not through the `driver` fixture
    below, so cleanup can't depend on that fixture being requested."""
    drv = AsyncGraphDatabase.driver(NEO4J_URI, auth=NEO4J_AUTH)
    async with drv.session() as session:
        await session.run("MATCH (n) WHERE n.id STARTS WITH 'test-' DETACH DELETE n")
    await drv.close()
    yield
    drv = AsyncGraphDatabase.driver(NEO4J_URI, auth=NEO4J_AUTH)
    async with drv.session() as session:
        await session.run("MATCH (n) WHERE n.id STARTS WITH 'test-' DETACH DELETE n")
    await drv.close()


@pytest.fixture
async def driver():
    drv = AsyncGraphDatabase.driver(NEO4J_URI, auth=NEO4J_AUTH)
    yield drv
    await drv.close()


@pytest.fixture
def writer(driver):
    return GraphWriter(driver)


@pytest.fixture
def reader(driver):
    return GraphReader(driver)
