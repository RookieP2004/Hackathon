"""
Stage 3 — Temporal Reasoning Layer (RISK_FUSION_ENGINE.md §3.3). Raw
instantaneous values are weak evidence; *how a signal is moving* is almost
always more diagnostic. Four features per graph-admitted Evidence Node:
rate of change, persistence/dwell time, lead-lag cross-correlation between
pairs of connected nodes, and precursor-sequence similarity (dynamic time
warping against a small library of reference hazard trajectories).
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from datetime import datetime


@dataclass
class TemporalFeatures:
    rate_of_change: float  # units per second
    persistence_ticks: int  # consecutive most-recent readings beyond 1 std of the window's own mean
    is_sustained: bool  # persistence_ticks >= SUSTAINED_THRESHOLD


SUSTAINED_THRESHOLD = 3


def compute_rate_of_change(history: list[tuple[float, datetime, str]]) -> float:
    if len(history) < 2:
        return 0.0
    (v0, t0, _), (v1, t1, _) = history[0], history[-1]
    elapsed = (t1 - t0).total_seconds()
    if elapsed <= 0:
        return 0.0
    return (v1 - v0) / elapsed


def compute_persistence(history: list[tuple[float, datetime, str]]) -> int:
    """§3.3: "a two-second spike and a ten-minute sustained deviation are not
    equally weighted" -- counts how many of the most recent readings, in a
    row, sit more than 1 standard deviation from a *baseline* on the same
    side of it (matching the direction of the latest deviation).

    The baseline is deliberately computed from only the window's leading
    points (not the whole window): if a currently-developing anomaly occupies
    a large fraction of the window -- exactly the case this feature exists to
    detect -- including those same points in their own reference baseline
    inflates the baseline's mean/std and can mask the very deviation being
    measured (confirmed empirically: a naive whole-window mean/std let a
    genuine multi-tick escalation register as *not* persistent, since the
    escalation's own later ticks dragged the baseline toward them)."""
    if len(history) < 4:
        return 0
    values = [v for v, _, _ in history]
    baseline_size = min(3, len(values) - 1)
    baseline = values[:baseline_size]
    mean = statistics.mean(baseline)
    std = statistics.pstdev(baseline) or 1e-6
    direction = 1 if values[-1] > mean else -1

    count = 0
    for value in reversed(values):
        z = (value - mean) / std
        if direction * z > 1.0:
            count += 1
        else:
            break
    return count


def compute_temporal_features(history: list[tuple[float, datetime, str]]) -> TemporalFeatures:
    persistence = compute_persistence(history)
    return TemporalFeatures(
        rate_of_change=compute_rate_of_change(history),
        persistence_ticks=persistence,
        is_sustained=persistence >= SUSTAINED_THRESHOLD,
    )


def lead_lag_cross_correlation(series_a: list[float], series_b: list[float], max_lag: int = 5) -> tuple[int, float]:
    """§3.3: "does one signal's movement reliably precede another's by a
    consistent time offset." Tries each lag in [-max_lag, max_lag] and
    returns the (lag, correlation) pair with the strongest |correlation| --
    a positive lag means series_a leads series_b by that many ticks."""
    n = min(len(series_a), len(series_b))
    if n < 4:
        return 0, 0.0

    best_lag, best_corr = 0, 0.0
    for lag in range(-max_lag, max_lag + 1):
        if lag >= 0:
            a, b = series_a[: n - lag], series_b[lag:n]
        else:
            a, b = series_a[-lag:n], series_b[: n + lag]
        if len(a) < 3 or len(b) < 3:
            continue
        corr = _pearson(a, b)
        if abs(corr) > abs(best_corr):
            best_lag, best_corr = lag, corr
    return best_lag, best_corr


def _pearson(a: list[float], b: list[float]) -> float:
    n = len(a)
    mean_a, mean_b = statistics.mean(a), statistics.mean(b)
    cov = sum((x - mean_a) * (y - mean_b) for x, y in zip(a, b))
    std_a = (sum((x - mean_a) ** 2 for x in a)) ** 0.5
    std_b = (sum((y - mean_b) ** 2 for y in b)) ** 0.5
    if std_a == 0 or std_b == 0:
        return 0.0
    return cov / (std_a * std_b)


def dtw_distance(series_a: list[float], series_b: list[float]) -> float:
    """Classic dynamic time warping distance -- a compact, dependency-free
    implementation (O(n*m) DP table), since the reference-trajectory
    library (§3.3's "labeled historical pre-incident windows") this compares
    against is intentionally small in this environment (a handful of
    hand-specified canonical precursor shapes, not a mined incident
    warehouse -- see networks.py's PRECURSOR_LIBRARY docstring for why)."""
    n, m = len(series_a), len(series_b)
    if n == 0 or m == 0:
        return float("inf")
    dtw = [[float("inf")] * (m + 1) for _ in range(n + 1)]
    dtw[0][0] = 0.0
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            cost = abs(series_a[i - 1] - series_b[j - 1])
            dtw[i][j] = cost + min(dtw[i - 1][j], dtw[i][j - 1], dtw[i - 1][j - 1])
    return dtw[n][m]


def normalize_series(values: list[float]) -> list[float]:
    """Min-max to [0,1] so DTW compares *shape*, not absolute scale --
    essential since different sensors (ppm vs psi vs mm/s) are being
    compared against reference trajectories expressed as generic 0-1 curves."""
    if not values:
        return values
    lo, hi = min(values), max(values)
    if hi - lo < 1e-9:
        return [0.5] * len(values)
    return [(v - lo) / (hi - lo) for v in values]


def precursor_similarity(current_series: list[float], reference_series: list[float]) -> float:
    """Returns a similarity score in [0,1] (1 == identical shape) derived
    from normalized DTW distance -- the `graph_relationship_novelty` input
    (§6): a high score against a known hazard-precursor shape means "this
    looks like it did last time", a low score against every reference in the
    library means a genuinely novel pattern."""
    a, b = normalize_series(current_series), normalize_series(reference_series)
    if not a or not b:
        return 0.0
    distance = dtw_distance(a, b)
    max_possible = max(len(a), len(b)) * 1.0  # each step can differ by at most 1.0 after normalization
    return max(0.0, 1.0 - distance / max_possible)
