"""
Stage 1 — Evidence Normalization & Feature Extraction (RISK_FUSION_ENGINE.md
§3.1). Every raw input becomes a common EvidenceNode shape before anything
else happens: `{source_type, source_id, raw_value, normalized_value, unit,
timestamp, quality_flag}`, with `normalized_value` on a comparable [0,1]
deviation-from-expected-baseline scale computed against *that specific
sensor's own historical distribution* -- never a single global constant.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timezone

import asyncpg

from app.fusion.db import acquire

# A sensor repeating the exact same bit-identical reading this many times in
# a row has zero variance, so normalize_against_baseline's z-score is
# mathematically zero -- a frozen gas sensor would silently read as "right
# at its own historical baseline" forever, never independently triggering
# anything. Excluding it as "missing" evidence (not a fabricated "safe"
# reading) is the fail-safe direction: absence of evidence, not evidence of
# absence.
STUCK_READING_REPEAT_THRESHOLD = 5

# A sensor that stops transmitting still has a "latest" row (its last real
# reading) with no explicit signal that time has passed since -- nothing
# compared `recorded_at` against "now" anywhere in this pipeline. Twelve
# missed ticks at this simulator's 5s cadence (RISK_FUSION_ENGINE.md's
# worked-example loop) is a generous allowance before a reading is
# considered stale, not a hair-trigger.
STALE_READING_SECONDS = 60


@dataclass
class EvidenceNode:
    source_type: str
    source_id: str
    raw_value: float | None
    normalized_value: float  # [0,1]; 0.5 == at this source's own historical baseline
    unit: str | None
    timestamp: datetime | None
    quality_flag: str  # 'good' | 'uncertain' | 'bad' | 'missing'
    metadata: dict = field(default_factory=dict)


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def normalize_against_baseline(raw_value: float, history: list[float]) -> float:
    """z-score against the sensor's own recent history, squashed to [0,1]
    via sigmoid so a deviation of ~+3 std reads near 1.0 and ~-3 std reads
    near 0.0, with 0.5 meaning "right at its own historical mean".

    Only a *leading* slice of `history` is used as the reference baseline,
    not the whole thing -- mirroring temporal.py's compute_persistence fix
    and for the identical reason: if `history` itself already contains a
    developing escalation (exactly the case this function most needs to
    detect), including those later points in their own reference baseline
    inflates the baseline's mean/std enough that the escalation stops
    looking anomalous relative to it (confirmed empirically: a 200ppm ->
    5000ppm ramp normalized to only ~0.63 instead of near 1.0, because the
    ramp's own intermediate values dominated the "baseline" it was being
    compared against)."""
    if len(history) < 3:
        return 0.5  # insufficient history to say anything about deviation yet
    baseline_size = min(5, max(3, len(history) // 3))
    baseline = history[:baseline_size]
    mean = statistics.mean(baseline)
    std = statistics.pstdev(baseline) or 1e-6
    z = (raw_value - mean) / std
    return _sigmoid(z / 2)  # /2 softens the curve so +/-3 std maps to roughly 0.08/0.92, not saturated


async def fetch_sensor_history(
    dsn: str, sensor_id: int, *, window: int = 30, pool: asyncpg.Pool | None = None
) -> list[tuple[float, datetime, str]]:
    """Most recent `window` readings, oldest first -- the raw material for
    every Stage 1/3 computation. Returns (value, recorded_at, quality)."""
    async with acquire(dsn, pool) as conn:
        rows = await conn.fetch(
            "SELECT value, recorded_at, quality FROM sensor_readings WHERE sensor_id = $1 "
            "ORDER BY recorded_at DESC LIMIT $2",
            sensor_id, window,
        )
    return [(float(r["value"]), r["recorded_at"], r["quality"]) for r in reversed(rows)]


def _is_stuck(values: list[float]) -> bool:
    if len(values) < STUCK_READING_REPEAT_THRESHOLD:
        return False
    tail = values[-STUCK_READING_REPEAT_THRESHOLD:]
    return len(set(tail)) == 1


def _is_stale(latest_time: datetime) -> bool:
    reference = latest_time if latest_time.tzinfo is not None else latest_time.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - reference).total_seconds() > STALE_READING_SECONDS


def build_sensor_evidence_node(sensor_id: int, sensor_tag: str, unit: str, history: list[tuple[float, datetime, str]]) -> EvidenceNode:
    if not history:
        return EvidenceNode(
            source_type="sensor", source_id=sensor_tag, raw_value=None, normalized_value=0.5,
            unit=unit, timestamp=None, quality_flag="missing",
        )
    values = [v for v, _, _ in history]
    latest_value, latest_time, latest_quality = history[-1]

    if _is_stuck(values):
        return EvidenceNode(
            source_type="sensor", source_id=sensor_tag, raw_value=latest_value, normalized_value=0.5,
            unit=unit, timestamp=latest_time, quality_flag="missing",
            metadata={"sensor_id": sensor_id, "history_length": len(history), "fault": "stuck_reading"},
        )
    if _is_stale(latest_time):
        return EvidenceNode(
            source_type="sensor", source_id=sensor_tag, raw_value=latest_value, normalized_value=0.5,
            unit=unit, timestamp=latest_time, quality_flag="missing",
            metadata={"sensor_id": sensor_id, "history_length": len(history), "fault": "stale_reading"},
        )

    normalized = normalize_against_baseline(latest_value, values[:-1] or values)
    return EvidenceNode(
        source_type="sensor", source_id=sensor_tag, raw_value=latest_value, normalized_value=normalized,
        unit=unit, timestamp=latest_time, quality_flag=latest_quality,
        metadata={"sensor_id": sensor_id, "history_length": len(history)},
    )


def build_equipment_health_evidence_node(equipment_tag: str, status: str, criticality: int) -> EvidenceNode:
    """SCADA/PLC-style discrepancy proxy (§3.1's special handling): this
    environment has no real PLC commanded-vs-observed integration, so
    `equipment.status` (a coarse operational/degraded/fault-class signal
    already tracked relationally) stands in for it, honestly documented as a
    simplified proxy rather than a genuine control/actual mismatch feature."""
    status_severity = {
        "operational": 0.1, "under_maintenance": 0.4, "degraded": 0.75, "offline": 0.9, "decommissioned": 0.5,
    }.get(status, 0.5)
    criticality_weight = criticality / 5.0
    normalized = min(1.0, status_severity * (0.6 + 0.4 * criticality_weight))
    return EvidenceNode(
        source_type="equipment_health", source_id=equipment_tag, raw_value=None, normalized_value=normalized,
        unit=None, timestamp=None, quality_flag="good", metadata={"status": status, "criticality": criticality},
    )
