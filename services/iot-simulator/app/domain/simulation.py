"""
Baseline signal physics — an Ornstein-Uhlenbeck-style mean-reverting random
walk per sensor. Values drift smoothly toward a "target" (set by the current
Normal/Warning/Critical mode) with gaussian noise, instead of jumping —
real sensors don't teleport, and neither should this simulator.

Scripted scenarios (scenarios.py) bypass this and drive affected sensors
directly; `SensorState.step()` is only called for sensors NOT currently under
scenario control that tick.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from app.domain.sensor_types import Severity, SensorSpec


@dataclass
class SensorState:
    key: str  # e.g. "eq-c101:temperature_c" or "compressor-house:humidity_pct"
    spec: SensorSpec
    value: float
    mode: Severity = Severity.NORMAL

    def step(self, rng: random.Random) -> float:
        target = self.spec.target_for(self.mode)
        noise = rng.gauss(0, self.spec.volatility)
        self.value = self.value + self.spec.theta * (target - self.value) + noise
        return self.value

    def severity(self) -> Severity:
        return self.spec.classify(self.value)

    def nudge_toward(self, target: float, rate: float, rng: random.Random, extra_noise: float = 0.0) -> float:
        """Used by scripted scenarios to drive a sensor toward an explicit
        target at a given closing rate (0-1 per tick), independent of `mode`."""
        noise = rng.gauss(0, self.spec.volatility * (1 + extra_noise))
        self.value = self.value + rate * (target - self.value) + noise
        return self.value

    def set(self, value: float) -> float:
        self.value = value
        return self.value
