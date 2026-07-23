"""
The one Neo4j driver instance this service holds, created at lifespan
startup and closed at shutdown — mirrors every other service's asyncpg
engine/session lifecycle (app/db.py elsewhere in this repo), just for the
graph database instead of the relational one.
"""

from __future__ import annotations

from neo4j import AsyncDriver, AsyncGraphDatabase

from app.config import Settings


def create_driver(settings: Settings) -> AsyncDriver:
    return AsyncGraphDatabase.driver(settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password))
