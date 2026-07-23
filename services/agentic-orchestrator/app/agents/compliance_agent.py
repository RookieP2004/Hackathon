"""
Compliance Agent — AGENT_ARCHITECTURE.md §10. Deterministic rule-based
policy evaluation against the real `permits`/`audit_logs` tables -- no
probabilistic judgment anywhere in the Core, matching §10's own description.
Deliberately non-adaptive (§10's Memory section: episodic history is used
for trend reporting only, never for self-tuning).
"""

from __future__ import annotations

import asyncpg

from aegis_agents import BaseAgent
from aegis_agents.db import acquire


class ComplianceAgent(BaseAgent):
    agent_id = "compliance-agent"
    failure_mode = "fail_open"  # this agent's downtime delays *detection*, never affects audit_logs' own integrity (§10)
    tick_interval_seconds = 60.0

    async def tick(self) -> None:
        async with acquire(self.postgres_dsn, self.pg_pool) as conn:
            await self._check_expired_active_permits(conn)
            await self._check_audit_log_liveness(conn)

    async def _check_expired_active_permits(self, conn: asyncpg.Connection) -> None:
        expired = await conn.fetch(
            "SELECT id, permit_number, valid_to FROM permits WHERE status = 'active' AND valid_to < now()"
        )
        for row in expired:
            marker = f"[compliance:expired_permit:{row['id']}]"
            already_flagged = await conn.fetchval(
                "SELECT id FROM agent_decision_log WHERE reasoning LIKE $1 AND agent_id = $2", f"%{marker}%", self.agent_id
            )
            if already_flagged:
                continue
            await self.assert_finding(
                decision="expired_permit_still_active",
                reasoning=(
                    f"Permit {row['permit_number']} (id {row['id']}) has status 'active' but expired at {row['valid_to'].isoformat()} "
                    f"-- a factual database evaluation, not a probabilistic claim. {marker}"
                ),
                confidence=1.0,
                evidence_refs=[f"permit:{row['id']}"],
                payload={"permit_id": row["id"], "permit_number": row["permit_number"], "expired_at": row["valid_to"].isoformat()},
            )

    async def _check_audit_log_liveness(self, conn: asyncpg.Connection) -> None:
        most_recent = await conn.fetchval("SELECT max(occurred_at) FROM audit_logs")
        if most_recent is None:
            return
        stale_hours = (await conn.fetchval("SELECT extract(epoch FROM now() - $1) / 3600", most_recent)) or 0
        if stale_hours > 24:
            await self.assert_finding(
                decision="audit_log_stale",
                reasoning=f"No new audit_logs entries in {stale_hours:.1f} hours -- flagged as a monitoring-of-the-monitor concern (§10).",
                confidence=1.0, evidence_refs=["audit_logs:liveness"], payload={"stale_hours": round(stale_hours, 1)},
            )
