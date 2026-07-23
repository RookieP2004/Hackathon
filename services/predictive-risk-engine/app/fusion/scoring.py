"""
Stage 5 — Probabilistic Scoring & Confidence Estimation (RISK_FUSION_ENGINE.md
§3.5). Converts a hazard network's posterior into the user-facing Risk
Score, Severity, and a structured confidence object that keeps aleatoric and
epistemic uncertainty separate (§3.5's explicit reason: they call for
different downstream responses, which one scalar cannot express).

Time-to-event proper belongs to a downstream survival model (§3.5: "the Risk
Fusion Engine's output is this stage's *input*, not a duplicate
computation") -- this module produces an honest, simple linear trend
projection in log-odds space over this process's own recent assessment
history as a stand-in, clearly distinguished from that fuller model rather
than presented as equivalent to it.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime

CRITICAL_PROBABILITY_THRESHOLD = 0.9
MIN_HISTORY_FOR_TREND = 3
MAX_HISTORY_PER_KEY = 20

# In-memory only -- a short rolling window of this process's own recent
# assessments per (equipment_id, hazard_class), used solely for the trend
# projection below. Resets on restart, matching every other derived/rebuildable
# state in this codebase (the chunk index, the Neo4j graph) rather than
# persisting a table for what is an honestly-labeled proxy feature.
_posterior_history: dict[tuple[int, str], list[tuple[datetime, float]]] = {}


def severity_for_score(score: float) -> str:
    if score >= 80:
        return "critical"
    if score >= 60:
        return "high"
    if score >= 35:
        return "medium"
    return "low"


@dataclass
class ConfidenceEstimate:
    confidence_band: tuple[float, float]  # aleatoric
    epistemic_flag: str  # 'low' | 'elevated' | 'high'
    corroborating_modalities: int
    graph_relationship_novelty: str  # 'known' | 'uncertain' | 'novel'
    data_completeness: float


def estimate_confidence(
    *, posterior: float, num_contributions: int, num_admitted_sources: int, num_good_quality: int,
    precursor_similarity: float | None,
) -> ConfidenceEstimate:
    data_completeness = (num_good_quality / num_admitted_sources) if num_admitted_sources > 0 else 0.0

    # Aleatoric: irreducible process noise -- modeled as a band that narrows
    # as more independent modalities corroborate the same conclusion (§5's
    # "four independent modalities corroborating ... low epistemic
    # uncertainty; moderate aleatoric uncertainty ... reflected in a +/-4
    # point band" is the calibration reference point this scales from).
    base_band_width = 12.0 / max(1, num_contributions) ** 0.5
    lower = max(0.0, posterior - base_band_width / 100)
    upper = min(1.0, posterior + base_band_width / 100)

    if data_completeness >= 0.9 and (precursor_similarity is None or precursor_similarity >= 0.5):
        epistemic_flag = "low"
    elif data_completeness >= 0.6:
        epistemic_flag = "elevated"
    else:
        epistemic_flag = "high"

    if precursor_similarity is None:
        novelty = "uncertain"
    elif precursor_similarity >= 0.6:
        novelty = "known"
    elif precursor_similarity >= 0.3:
        novelty = "uncertain"
    else:
        novelty = "novel"
        epistemic_flag = "elevated" if epistemic_flag == "low" else epistemic_flag

    return ConfidenceEstimate(
        confidence_band=(round(lower, 4), round(upper, 4)),
        epistemic_flag=epistemic_flag,
        corroborating_modalities=num_contributions,
        graph_relationship_novelty=novelty,
        data_completeness=round(data_completeness, 3),
    )


_EPISTEMIC_PENALTY = {"low": 0.0, "elevated": 0.15, "high": 0.35}


def scalar_confidence(estimate: ConfidenceEstimate) -> float:
    """Collapses the structured estimate to the single `risk_scores.confidence`
    column (ge=0, le=1) the existing schema requires -- the full structured
    object (both uncertainty kinds kept separate, per §3.5's own reasoning)
    still travels in full inside the Evidence Bundle; this is only for the
    one relational column that predates this engine and expects one float."""
    band_width = estimate.confidence_band[1] - estimate.confidence_band[0]
    aleatoric_confidence = 1.0 - band_width
    penalty = _EPISTEMIC_PENALTY.get(estimate.epistemic_flag, 0.2)
    return round(max(0.0, min(1.0, aleatoric_confidence - penalty)), 4)


def record_and_estimate_time_to_event(
    equipment_id: int, hazard_class: str, timestamp: datetime, posterior: float,
) -> float | None:
    """Returns estimated seconds until this (equipment, hazard) pair's
    posterior would cross CRITICAL_PROBABILITY_THRESHOLD if its recent trend
    continues linearly in log-odds space -- None if there isn't enough
    history yet, or the trend isn't moving toward the threshold."""
    key = (equipment_id, hazard_class)
    history = _posterior_history.setdefault(key, [])
    history.append((timestamp, posterior))
    if len(history) > MAX_HISTORY_PER_KEY:
        del history[: len(history) - MAX_HISTORY_PER_KEY]

    if len(history) < MIN_HISTORY_FOR_TREND:
        return None

    t0 = history[0][0]
    xs = [(t - t0).total_seconds() for t, _ in history]
    ys = [math.log(max(p, 1e-6) / max(1 - p, 1e-6)) for _, p in history]

    n = len(xs)
    mean_x, mean_y = sum(xs) / n, sum(ys) / n
    cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    var_x = sum((x - mean_x) ** 2 for x in xs)
    if var_x < 1e-9:
        return None
    slope = cov / var_x
    if slope <= 1e-9:
        return None  # not trending upward -- no time-to-event to report

    current_log_odds = ys[-1]
    critical_log_odds = math.log(CRITICAL_PROBABILITY_THRESHOLD / (1 - CRITICAL_PROBABILITY_THRESHOLD))
    if current_log_odds >= critical_log_odds:
        return 0.0

    return (critical_log_odds - current_log_odds) / slope


def reset_history() -> None:
    """Test-only hook -- keeps the module-level trend state from leaking
    between independent test cases."""
    _posterior_history.clear()
