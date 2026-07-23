"""
Risk Fusion Agent — AGENT_ARCHITECTURE.md §7. The agent-level shell around
the real six-stage Bayesian Risk Fusion Engine (predictive-risk-engine's
`app/fusion/` package, built in the Risk Fusion Engine pass) -- that
service's own background loop is already continuously assessing the real
V-12/RV-9/R-3 cluster and writing real, graph-admitted, multi-factor
`risk_scores` rows. This agent's job is exactly what §7 describes: watch for
signals that were *jointly* correlated (>=2 independent contributing
factors, meaning the Bayesian network's gates actually combined more than
one evidence source) and publish that as a distinct `agent.assertion`,
never inventing or reweighting a correlation the Core didn't already decide.
"""

from __future__ import annotations

import json

import asyncpg

from aegis_agents import BaseAgent
from aegis_agents.db import acquire

MIN_CORROBORATING_FACTORS = 2


class RiskFusionAgent(BaseAgent):
    agent_id = "risk-fusion-agent"
    failure_mode = "fail_open"  # per-signal alerting from Sensor/Vision/Worker Agent remains a real safety net (§7)
    tick_interval_seconds = 10.0

    def __init__(self, bus, postgres_dsn: str, pg_pool: asyncpg.Pool | None = None) -> None:
        super().__init__(bus, postgres_dsn, pg_pool)
        self._last_seen_id = 0

    async def tick(self) -> None:
        async with acquire(self.postgres_dsn, self.pg_pool) as conn:
            rows = await conn.fetch(
                "SELECT id, equipment_id, zone_id, score, confidence, contributing_factors, model_version, computed_at "
                "FROM risk_scores WHERE id > $1 AND model_version LIKE 'risk-fusion:%' ORDER BY id ASC LIMIT 50",
                self._last_seen_id,
            )

        for row in rows:
            self._last_seen_id = max(self._last_seen_id, row["id"])
            factors = json.loads(row["contributing_factors"]) if isinstance(row["contributing_factors"], str) else row["contributing_factors"]
            if len(factors) < MIN_CORROBORATING_FACTORS:
                continue  # a single-signal pattern isn't a correlation -- nothing for this agent to report

            hazard_class = row["model_version"].split(":")[1] if ":" in row["model_version"] else "unknown"
            factor_summary = ", ".join(f"{f['source_type']}:{f['evidence_node_id']} (LR {f['likelihood_ratio']:.1f})" for f in factors[:4])

            await self.assert_finding(
                decision="correlated_risk_pattern",
                reasoning=(
                    f"{len(factors)} independent, graph-admitted evidence sources jointly correlated for "
                    f"{hazard_class} on equipment {row['equipment_id']}: {factor_summary}. Correlation itself was "
                    f"decided entirely by the graph-constrained Bayesian Core -- this assertion only narrates it."
                ),
                confidence=float(row["confidence"]),
                evidence_refs=[f"risk_score:{row['id']}"] + [f"{f['source_type']}:{f['evidence_node_id']}" for f in factors],
                payload={"equipment_id": row["equipment_id"], "zone_id": row["zone_id"], "hazard_class": hazard_class, "score": float(row["score"]), "contributing_factor_count": len(factors)},
            )
