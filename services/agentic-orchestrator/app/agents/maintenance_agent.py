"""
Maintenance Agent — AGENT_ARCHITECTURE.md §5. Turns Prediction Agent's
(here: the real Risk Fusion Engine's) high-severity forecasts into real,
scheduled `maintenance_records` work orders. Idempotent, keyed by the
triggering `risk_scores.id` (§5's own explicit idempotency requirement,
"to prevent a retried creation call from generating a duplicate work
order for the same forecast").
"""

from __future__ import annotations

import asyncpg

from aegis_agents import BaseAgent

HIGH_SEVERITY_SCORE_THRESHOLD = 60.0
PREDICTIVE_MAINTENANCE_TYPE_ID = 3


class MaintenanceAgent(BaseAgent):
    agent_id = "maintenance-agent"
    failure_mode = "fail_open"  # unactioned predictions simply accumulate, visibly, rather than vanish (§5)
    tick_interval_seconds = 15.0

    async def tick(self) -> None:
        conn = await asyncpg.connect(self.postgres_dsn)
        try:
            candidates = await conn.fetch(
                """
                SELECT id, equipment_id, score, confidence, model_version, computed_at
                FROM risk_scores
                WHERE equipment_id IS NOT NULL AND score >= $1
                  AND computed_at > now() - interval '2 hours'
                ORDER BY computed_at DESC
                LIMIT 20
                """,
                HIGH_SEVERITY_SCORE_THRESHOLD,
            )
            for row in candidates:
                await self._maybe_create_work_order(conn, row)
        finally:
            await conn.close()

    async def _maybe_create_work_order(self, conn: asyncpg.Connection, row) -> None:
        marker = f"[auto:risk_score:{row['id']}]"
        existing = await conn.fetchval("SELECT id FROM maintenance_records WHERE description LIKE $1", f"%{marker}%")
        if existing is not None:
            return  # idempotent -- already actioned this exact forecast

        equipment = await conn.fetchrow("SELECT tag, name FROM equipment WHERE id = $1", row["equipment_id"])
        if equipment is None:
            return

        description = (
            f"Predictive maintenance work order {marker}: equipment {equipment['tag']} ({equipment['name']}) "
            f"flagged at risk score {row['score']:.1f}/100 (confidence {row['confidence']:.2f}) by {row['model_version']}."
        )
        work_order_id = await conn.fetchval(
            "INSERT INTO maintenance_records (equipment_id, maintenance_type_id, status, scheduled_date, description) "
            "VALUES ($1, $2, 'scheduled', now()::date, $3) RETURNING id",
            row["equipment_id"], PREDICTIVE_MAINTENANCE_TYPE_ID, description,
        )

        await self.assert_finding(
            decision="work_order_created",
            reasoning=(
                f"Risk score {row['score']:.1f} for equipment {equipment['tag']} crossed the "
                f"{HIGH_SEVERITY_SCORE_THRESHOLD} work-order threshold; created maintenance record {work_order_id}, "
                f"inheriting the triggering assessment's confidence directly rather than assigning its own."
            ),
            confidence=float(row["confidence"]),
            evidence_refs=[f"risk_score:{row['id']}", f"equipment:{row['equipment_id']}"],
            payload={"maintenance_record_id": work_order_id, "equipment_id": row["equipment_id"], "triggering_risk_score_id": row["id"]},
        )
