"""
A live value generator for the real, already-seeded `sensors` rows (the same
100 sensors KNOWLEDGE_GRAPH.md's sync materialized into Neo4j) -- the Risk
Fusion Engine's Stage 3 temporal reasoning (rate of change, persistence,
lead-lag correlation, precursor-sequence similarity) fundamentally needs a
real accumulating history to compute those features from, and
`sensor_readings` (owned by the never-built ingestion-gateway service) starts
empty. Rather than trying to correlate iot-simulator's separate, unrelated
synthetic world (confirmed in the Vision AI pass to have zero correspondence
to this real seeded topology) with these real sensor ids, this generates
plausible values *directly for the real sensors* and persists them into the
real `sensor_readings` hypertable -- the same mean-reverting random-walk
technique iot-simulator itself uses, just anchored to real sensor rows
instead of a parallel fictional world.

Supports scenario injection (`inject_precursor_pattern`) so the fusion
pipeline's output can be demonstrated end-to-end against a deliberately
engineered escalation, the same way iot-simulator's `/control/scenario`
lets the rest of the demo be driven on purpose rather than only observed
passively.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime, timezone

import asyncpg
import structlog

from app.fusion.db import acquire

logger = structlog.get_logger(__name__)

# Per sensor-type baseline (mean, std, theta [mean-reversion rate], min, max) --
# realistic industrial ranges, not fitted to any real plant data.
BASELINES: dict[str, dict] = {
    "Gas Concentration": {"mean": 200.0, "std": 40.0, "theta": 0.15, "min": 0.0, "max": 50000.0},  # ppm
    "Pressure": {"mean": 6.0, "std": 0.4, "theta": 0.12, "min": 0.0, "max": 60.0},  # psi (gauge, process-side)
    "Temperature": {"mean": 45.0, "std": 3.0, "theta": 0.10, "min": -20.0, "max": 400.0},  # celsius
    "Vibration": {"mean": 1.5, "std": 0.3, "theta": 0.15, "min": 0.0, "max": 30.0},  # mm/s
    "Acoustic": {"mean": 65.0, "std": 4.0, "theta": 0.12, "min": 0.0, "max": 140.0},  # dB
    "Level": {"mean": 55.0, "std": 5.0, "theta": 0.08, "min": 0.0, "max": 100.0},  # %
    "Flow Rate": {"mean": 40.0, "std": 5.0, "theta": 0.10, "min": 0.0, "max": 500.0},  # m3/h
}


@dataclass
class SensorRuntimeState:
    sensor_id: int
    sensor_type: str
    value: float
    target_override: float | None = None  # set by an active scenario injection
    override_rate: float = 0.0  # how fast `value` is pulled toward target_override each tick


@dataclass
class SensorSimulator:
    states: dict[int, SensorRuntimeState] = field(default_factory=dict)
    rng: random.Random = field(default_factory=lambda: random.Random(20260722))

    async def load_sensors(self, dsn: str) -> int:
        conn = await asyncpg.connect(dsn)
        try:
            rows = await conn.fetch(
                "SELECT s.id, st.name AS sensor_type FROM sensors s JOIN sensor_types st ON st.id = s.sensor_type_id"
            )
        finally:
            await conn.close()

        for row in rows:
            baseline = BASELINES.get(row["sensor_type"])
            if baseline is None:
                continue
            self.states[row["id"]] = SensorRuntimeState(
                sensor_id=row["id"], sensor_type=row["sensor_type"], value=baseline["mean"]
            )
        return len(self.states)

    def inject_precursor_pattern(self, sensor_id: int, *, target: float, rate: float = 0.15) -> None:
        """Pulls a specific sensor's value toward `target` at `rate` per tick
        (in addition to its normal random walk), instead of instantly setting
        it -- a gradual escalation the temporal-reasoning stage's rate-of-
        change and persistence features can genuinely observe developing,
        matching how the worked example's trace unfolds over several ticks
        rather than jumping straight to its endpoint."""
        if sensor_id in self.states:
            self.states[sensor_id].target_override = target
            self.states[sensor_id].override_rate = rate

    def clear_injection(self, sensor_id: int) -> None:
        if sensor_id in self.states:
            self.states[sensor_id].target_override = None
            self.states[sensor_id].override_rate = 0.0

    def clear_all_injections(self) -> None:
        for state in self.states.values():
            state.target_override = None
            state.override_rate = 0.0

    def tick(self) -> dict[int, float]:
        updated: dict[int, float] = {}
        for sensor_id, state in self.states.items():
            baseline = BASELINES[state.sensor_type]
            if state.target_override is not None:
                state.value += (state.target_override - state.value) * state.override_rate
                state.value += self.rng.gauss(0, baseline["std"] * 0.1)
            else:
                state.value += (baseline["mean"] - state.value) * baseline["theta"]
                state.value += self.rng.gauss(0, baseline["std"] * 0.3)
            state.value = max(baseline["min"], min(baseline["max"], state.value))
            updated[sensor_id] = state.value
        return updated

    async def tick_and_persist(self, dsn: str, pool: asyncpg.Pool | None = None) -> int:
        values = self.tick()
        if not values:
            return 0
        now = datetime.now(timezone.utc)
        async with acquire(dsn, pool) as conn:
            await conn.executemany(
                "INSERT INTO sensor_readings (sensor_id, value, quality, recorded_at) VALUES ($1, $2, 'good', $3)",
                [(sensor_id, value, now) for sensor_id, value in values.items()],
            )
        return len(values)
