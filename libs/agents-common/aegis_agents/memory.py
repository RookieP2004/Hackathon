"""
Episodic memory and decision logging — AGENT_ARCHITECTURE.md §0.4's Memory
Architecture standard, the persisted tier every agent writes to. Working
memory (§0.4's ephemeral tier) is deliberately NOT here -- it's scoped to a
single reasoning episode and lives in each concrete agent's own process
state, discarded once the episode ends, per the spec's own definition.

Self-managed tables (created directly by this library, not through any
service's Alembic chain) -- the same pattern rag-service's `rag_feedback`
table and computer-vision's downstream integration already established for
narrow, cross-cutting concerns that don't belong to any one service's owned
schema.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime

import asyncpg

DECISION_LOG_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS agent_decision_log (
    id BIGSERIAL PRIMARY KEY,
    agent_id TEXT NOT NULL,
    agent_version TEXT NOT NULL,
    decision TEXT NOT NULL,
    reasoning TEXT NOT NULL,
    confidence REAL,
    evidence_refs JSONB NOT NULL DEFAULT '[]',
    correlation_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
)
"""

EPISODIC_MEMORY_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS agent_episodic_memory (
    id BIGSERIAL PRIMARY KEY,
    agent_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}',
    outcome TEXT,
    outcome_recorded_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
)
"""

_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_agent_decision_log_agent_id ON agent_decision_log (agent_id, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_agent_episodic_memory_agent_id ON agent_episodic_memory (agent_id, created_at)",
]


async def ensure_agent_memory_tables(dsn: str) -> None:
    conn = await asyncpg.connect(dsn)
    try:
        await conn.execute(DECISION_LOG_TABLE_DDL)
        await conn.execute(EPISODIC_MEMORY_TABLE_DDL)
        for stmt in _INDEXES:
            await conn.execute(stmt)
    finally:
        await conn.close()


@dataclass
class DecisionLogEntry:
    id: int
    agent_id: str
    agent_version: str
    decision: str
    reasoning: str
    confidence: float | None
    evidence_refs: list[str]
    correlation_id: str | None
    created_at: datetime


class AgentMemory:
    """Bound to one agent_id; every concrete agent owns exactly one of these."""

    def __init__(self, dsn: str, agent_id: str, agent_version: str) -> None:
        self._dsn = dsn
        self.agent_id = agent_id
        self.agent_version = agent_version

    async def log_decision(
        self, *, decision: str, reasoning: str, confidence: float | None = None,
        evidence_refs: list[str] | None = None, correlation_id: str | None = None,
    ) -> int:
        """§0's "log decisions" + "explain reasoning" requirements, in one
        durable row -- `reasoning` is never optional in practice (every
        caller supplies real text), only typed loosely to keep the table
        usable for agents whose Core is fully deterministic and whose
        "reasoning" is just a plain statement of the rule that fired."""
        conn = await asyncpg.connect(self._dsn)
        try:
            row_id = await conn.fetchval(
                "INSERT INTO agent_decision_log (agent_id, agent_version, decision, reasoning, confidence, evidence_refs, correlation_id) "
                "VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7) RETURNING id",
                self.agent_id, self.agent_version, decision, reasoning, confidence,
                json.dumps(evidence_refs or []), correlation_id,
            )
        finally:
            await conn.close()
        return row_id

    async def remember_episode(self, *, kind: str, payload: dict, outcome: str | None = None) -> int:
        """Episodic memory (§0.4): this agent's own history of past
        assertions/decisions, the raw material the Learning Agent consumes."""
        conn = await asyncpg.connect(self._dsn)
        try:
            row_id = await conn.fetchval(
                "INSERT INTO agent_episodic_memory (agent_id, kind, payload, outcome) VALUES ($1, $2, $3::jsonb, $4) RETURNING id",
                self.agent_id, kind, json.dumps(payload), outcome,
            )
        finally:
            await conn.close()
        return row_id

    async def record_outcome(self, episode_id: int, outcome: str) -> None:
        conn = await asyncpg.connect(self._dsn)
        try:
            await conn.execute(
                "UPDATE agent_episodic_memory SET outcome = $1, outcome_recorded_at = now() WHERE id = $2",
                outcome, episode_id,
            )
        finally:
            await conn.close()

    async def recent_decisions(self, limit: int = 20) -> list[DecisionLogEntry]:
        conn = await asyncpg.connect(self._dsn)
        try:
            rows = await conn.fetch(
                "SELECT * FROM agent_decision_log WHERE agent_id = $1 ORDER BY created_at DESC LIMIT $2",
                self.agent_id, limit,
            )
        finally:
            await conn.close()
        return [
            DecisionLogEntry(
                id=r["id"], agent_id=r["agent_id"], agent_version=r["agent_version"], decision=r["decision"],
                reasoning=r["reasoning"], confidence=r["confidence"],
                evidence_refs=json.loads(r["evidence_refs"]) if isinstance(r["evidence_refs"], str) else r["evidence_refs"],
                correlation_id=r["correlation_id"], created_at=r["created_at"],
            )
            for r in rows
        ]

    async def explain(self, decision_id: int) -> str | None:
        """The "Why?" affordance (UI_UX_SPECIFICATION.md §0.2), at the agent
        level: fetch a past decision's own recorded reasoning verbatim,
        never regenerate an explanation after the fact."""
        conn = await asyncpg.connect(self._dsn)
        try:
            row = await conn.fetchrow(
                "SELECT reasoning FROM agent_decision_log WHERE id = $1 AND agent_id = $2", decision_id, self.agent_id
            )
        finally:
            await conn.close()
        return row["reasoning"] if row else None
