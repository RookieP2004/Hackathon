"""
Sensor Agent — AGENT_ARCHITECTURE.md §1. Perception band, leaf position in
the fleet graph (§0.2): watches sensors, asserts anomalies, never correlates
across signals and never decides an incident is warranted.

The Core is a small ensemble of interpretable statistical methods (EWMA
z-score + a simple isolation-style rank check) voting together -- no prompt,
no LLM anywhere in the detection path, matching §1's own description of
this being "the agent where that statement is most literally true in the
entire fleet." Reads the same real `sensor_readings` rows the Risk Fusion
Engine's SensorSimulator has been writing continuously since that pass --
genuinely live, already-running data, not a fixture.
"""

from __future__ import annotations

import statistics

import asyncpg

from aegis_agents import BaseAgent
from app.agents import topics

EWMA_ALPHA = 0.3
Z_SCORE_THRESHOLD = 2.5
WATCHED_SENSOR_IDS = [1, 2, 3, 4, 5, 6, 43, 44, 45, 46, 83, 84, 85, 86]  # the V-12/RV-9/R-3/PIPE-12A cluster
STUCK_READING_REPEAT_THRESHOLD = 5  # matches predictive-risk-engine/app/fusion/evidence.py's own threshold


def _ewma_z_score(values: list[float]) -> float:
    if len(values) < 4:
        return 0.0
    baseline = values[: max(3, len(values) // 3)]
    mean = statistics.mean(baseline)
    std = statistics.pstdev(baseline) or 1e-6
    ewma = baseline[0]
    for v in values[len(baseline):]:
        ewma = EWMA_ALPHA * v + (1 - EWMA_ALPHA) * ewma
    return (ewma - mean) / std


def _isolation_rank_score(values: list[float]) -> float:
    """A simple, dependency-free stand-in for isolation-forest voting: how
    extreme is the latest value's rank within its own recent window,
    expressed on the same [0, inf) scale as a z-score so the two methods
    can vote on a common footing."""
    if len(values) < 4:
        return 0.0
    sorted_vals = sorted(values)
    latest = values[-1]
    rank = sorted_vals.index(latest) if latest in sorted_vals else len(sorted_vals) // 2
    percentile = rank / (len(sorted_vals) - 1)
    return abs(percentile - 0.5) * 2 * Z_SCORE_THRESHOLD  # scaled onto the same threshold footing


class SensorAgent(BaseAgent):
    agent_id = "sensor-agent"
    failure_mode = "fail_open"
    tick_interval_seconds = 8.0

    def __init__(self, bus, postgres_dsn: str) -> None:
        super().__init__(bus, postgres_dsn)
        self._consecutive_read_failures: dict[int, int] = {}

    async def tick(self) -> None:
        conn = await asyncpg.connect(self.postgres_dsn)
        try:
            for sensor_id in WATCHED_SENSOR_IDS:
                await self._check_sensor(conn, sensor_id)
        finally:
            await conn.close()

    async def _check_sensor(self, conn: asyncpg.Connection, sensor_id: int) -> None:
        row = await conn.fetchrow("SELECT tag FROM sensors WHERE id = $1", sensor_id)
        if row is None:
            return
        tag = row["tag"]

        rows = await conn.fetch(
            "SELECT value FROM sensor_readings WHERE sensor_id = $1 ORDER BY recorded_at DESC LIMIT 30", sensor_id
        )
        values = [float(r["value"]) for r in reversed(rows)]
        if len(values) < 4:
            return  # Retry Logic (§1): insufficient window yet, not a failure -- just wait for more ticks

        if len(values) >= STUCK_READING_REPEAT_THRESHOLD and len(set(values[-STUCK_READING_REPEAT_THRESHOLD:])) == 1:
            # A frozen sensor has zero variance, so the z-score/rank-deviation
            # checks below would silently see "no anomaly" forever -- the
            # fault itself must be its own loud finding, not something the
            # statistical checks happen to notice as a side effect.
            await self.assert_finding(
                decision="sensor_fault_detected",
                reasoning=f"Sensor {tag} (id {sensor_id}) has repeated the identical reading {values[-1]} for its last {STUCK_READING_REPEAT_THRESHOLD} samples -- likely frozen/stuck, not a genuinely stable process value.",
                confidence=0.9, evidence_refs=[f"sensor:{sensor_id}"],
                payload={"sensor_id": sensor_id, "sensor_tag": tag, "fault": "stuck_reading", "repeated_value": values[-1]},
            )
            return

        ewma_z = _ewma_z_score(values)
        rank_z = _isolation_rank_score(values)
        votes = [abs(ewma_z) > Z_SCORE_THRESHOLD, rank_z > Z_SCORE_THRESHOLD]
        agreement = sum(votes) / len(votes)

        if agreement == 0:
            return

        confidence = min(1.0, agreement * (0.5 + min(abs(ewma_z), 6.0) / 12.0))
        await self.assert_finding(
            decision="anomaly_detected",
            reasoning=(
                f"Sensor {tag} (id {sensor_id}): EWMA z-score {ewma_z:.2f}, rank-deviation score {rank_z:.2f} "
                f"against its own recent baseline; {int(agreement * len(votes))}/{len(votes)} ensemble members agree."
            ),
            confidence=confidence,
            evidence_refs=[f"sensor:{sensor_id}"],
            payload={"sensor_id": sensor_id, "sensor_tag": tag, "ewma_z_score": round(ewma_z, 3), "rank_deviation_score": round(rank_z, 3)},
        )
