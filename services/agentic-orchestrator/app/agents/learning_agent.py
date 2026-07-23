"""
Learning Agent — AGENT_ARCHITECTURE.md §11. A scheduled, low-priority batch
job evaluating the fleet's own collective track record (the real
`agent_decision_log`/`agent_episodic_memory` tables every other agent in
this fleet has been writing to) -- never auto-promotes anything, always
reports for human review, exactly per §11's non-negotiable human-gating
commitment.
"""

from __future__ import annotations

import asyncpg

from aegis_agents import BaseAgent
from aegis_agents.db import acquire

DRIFT_CONFIDENCE_DROP_THRESHOLD = 0.15


class LearningAgent(BaseAgent):
    agent_id = "learning-agent"
    failure_mode = "fail_open"  # the safest failure profile in the fleet (§11): the fleet simply doesn't improve during downtime
    tick_interval_seconds = 120.0

    async def tick(self) -> None:
        async with acquire(self.postgres_dsn, self.pg_pool) as conn:
            rows = await conn.fetch(
                """
                SELECT agent_id,
                       count(*) AS decision_count,
                       avg(confidence) FILTER (WHERE created_at > now() - interval '1 hour') AS recent_avg_confidence,
                       avg(confidence) FILTER (WHERE created_at <= now() - interval '1 hour' AND created_at > now() - interval '2 hours') AS prior_avg_confidence
                FROM agent_decision_log
                WHERE agent_id NOT LIKE 'zztest-%'
                GROUP BY agent_id
                """
            )

        for row in rows:
            recent, prior = row["recent_avg_confidence"], row["prior_avg_confidence"]
            if recent is None or prior is None:
                continue
            drift = prior - recent
            if drift > DRIFT_CONFIDENCE_DROP_THRESHOLD:
                await self.assert_finding(
                    decision="performance_drift_detected",
                    reasoning=(
                        f"Agent '{row['agent_id']}''s average assertion confidence dropped from {prior:.2f} to {recent:.2f} "
                        f"(delta {drift:.2f}) over the trailing evaluation window -- a meta-confidence about a "
                        f"performance-drift detection, not a claim about the underlying hazard itself (§11). "
                        f"No retraining or auto-promotion follows from this alone; flagged for Safety Officer review."
                    ),
                    confidence=min(1.0, drift * 2),  # a meta-level confidence about the drift measurement itself
                    evidence_refs=[f"agent:{row['agent_id']}"],
                    payload={"agent_id": row["agent_id"], "recent_avg_confidence": float(recent), "prior_avg_confidence": float(prior), "decision_count": row["decision_count"]},
                )
