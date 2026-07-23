"""
Prediction Agent — AGENT_ARCHITECTURE.md §8. The agent-level shell around
the same real Risk Fusion Engine's Stage 5 output (score, severity,
confidence band, time-to-event) -- distinct from Risk Fusion Agent (§7),
which narrates *that a correlation happened*; this agent narrates *the
final scored forecast*, publishing on every materially-scored risk (not
only multi-factor ones), matching §8's framing as the direct input to the
Incident Service/Dashboard's Risk Timeline.
"""

from __future__ import annotations

import json

import asyncpg

from aegis_agents import BaseAgent
from aegis_agents.db import acquire

CRITICAL_SCORE_THRESHOLD = 80.0


class PredictionAgent(BaseAgent):
    agent_id = "prediction-agent"
    failure_mode = "fail_open"  # correlated patterns remain visible unscored, never a silent absence of signal (§8)
    tick_interval_seconds = 10.0

    def __init__(self, bus, postgres_dsn: str, pg_pool: asyncpg.Pool | None = None) -> None:
        super().__init__(bus, postgres_dsn, pg_pool)
        self._last_seen_id: int | None = None  # lazily initialized to "now" on the first tick

    async def tick(self) -> None:
        async with acquire(self.postgres_dsn, self.pg_pool) as conn:
            if self._last_seen_id is None:
                # Start watching from "now", not from the beginning of history --
                # a restarted agent shouldn't spend a potentially long time replaying
                # an accumulated backlog of stale risk scores before it can react to
                # what's actually happening right now (_last_seen_id is in-memory only,
                # so every process restart would otherwise reset it to a full replay).
                self._last_seen_id = await conn.fetchval("SELECT COALESCE(max(id), 0) FROM risk_scores")
            rows = await conn.fetch(
                "SELECT id, equipment_id, zone_id, score, confidence, contributing_factors, model_version, computed_at "
                "FROM risk_scores WHERE id > $1 AND model_version LIKE 'risk-fusion:%' ORDER BY id ASC LIMIT 50",
                self._last_seen_id,
            )

        for row in rows:
            self._last_seen_id = max(self._last_seen_id, row["id"])
            hazard_class = row["model_version"].split(":")[1] if ":" in row["model_version"] else "unknown"
            severity = "critical" if row["score"] >= CRITICAL_SCORE_THRESHOLD else "high" if row["score"] >= 60 else "medium" if row["score"] >= 35 else "low"

            message = await self.assert_finding(
                decision="risk_scored",
                reasoning=(
                    f"Equipment {row['equipment_id']} scored {row['score']:.1f}/100 ({severity}) for {hazard_class} "
                    f"at confidence {row['confidence']:.2f}; computed by the versioned survival/Bayesian scoring model, "
                    f"not this agent's own judgment (§8: this agent computes and publishes, nothing else)."
                ),
                confidence=float(row["confidence"]),
                evidence_refs=[f"risk_score:{row['id']}"],
                payload={"equipment_id": row["equipment_id"], "zone_id": row["zone_id"], "hazard_class": hazard_class, "score": float(row["score"]), "severity": severity},
            )

            if severity == "critical":
                # §8's escalation policy: publishing IS the escalation -- actual human notification and
                # playbook triggering are Emergency Agent's job, kept out of this agent's responsibility surface.
                await self.memory.log_decision(
                    decision="critical_threshold_crossed", reasoning=f"Score {row['score']:.1f} crossed the {CRITICAL_SCORE_THRESHOLD} critical threshold -- routed to Emergency Agent via the standard assertion.",
                    confidence=float(row["confidence"]), evidence_refs=[f"risk_score:{row['id']}"], correlation_id=message.correlation_id,
                )
