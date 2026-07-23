"""
Temporal-persistence gate — AGENT_ARCHITECTURE.md §2 / ARCHITECTURE.md §18.2:
"require N consecutive frames before raising an alert, to suppress
single-frame false positives." This is explicitly described as a hard,
non-negotiable rule, not a tunable nicety, so it lives as its own small,
independently-tested module rather than being folded into the pipeline loop.

Confidence reported to callers is the detector's own per-frame confidence
multiplied by a persistence factor that ramps from 0 to 1 over the required
run — matching §2's "Confidence Score" definition exactly.
"""

from __future__ import annotations

from dataclasses import dataclass

DEFAULT_REQUIRED_CONSECUTIVE = 3


@dataclass
class PersistenceResult:
    is_confirmed: bool  # has persisted >= required consecutive ticks
    just_crossed_threshold: bool  # this is the exact tick it became confirmed -- the one moment to fire a new alert
    persistence_factor: float  # 0-1, ramping with consecutive count
    consecutive_ticks: int


class PersistenceGate:
    def __init__(self, required_consecutive: int = DEFAULT_REQUIRED_CONSECUTIVE) -> None:
        self.required = required_consecutive
        self._counters: dict[tuple[str, str], int] = {}

    def observe(self, key: tuple[str, str], detected: bool) -> PersistenceResult:
        previous = self._counters.get(key, 0)
        current = previous + 1 if detected else 0
        self._counters[key] = current

        is_confirmed = current >= self.required
        just_crossed = current == self.required and previous < self.required
        factor = min(1.0, current / self.required)
        return PersistenceResult(
            is_confirmed=is_confirmed,
            just_crossed_threshold=just_crossed,
            persistence_factor=factor,
            consecutive_ticks=current,
        )

    def reset(self, key: tuple[str, str] | None = None) -> None:
        if key is None:
            self._counters.clear()
        else:
            self._counters.pop(key, None)
