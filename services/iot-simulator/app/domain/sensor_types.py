"""
Sensor type catalog — realistic units and Normal/Warning/Critical bands.

Bands for zone-ambient and worker-vital sensors are universal physical or
physiological constants (ISO 10816 vibration zones, human heart-rate ranges,
etc.) and are defined once here as `UNIVERSAL_SPECS`. Equipment electrical/
mechanical sensors (current, voltage, rpm, pressure, water flow) are
inherently machine-specific — their bands are derived per-instance from each
machine's rated values via `relative_spec()`, not hardcoded here.

Worker GPS and Camera Events are structured/discrete, not continuous scalars,
so they are handled separately in `world.py`/`engine.py` rather than modeled
as a SensorSpec.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class SensorKind(str, Enum):
    TEMPERATURE = "temperature_c"
    HUMIDITY = "humidity_pct"
    PRESSURE = "pressure_bar"
    GAS = "gas_pct_lel"
    SMOKE = "smoke_pct_obscuration"
    VIBRATION = "vibration_mm_s"
    CURRENT = "current_a"
    VOLTAGE = "voltage_v"
    RPM = "rpm"
    OIL_LEVEL = "oil_level_pct"
    VALVE_POSITION = "valve_position_pct"
    WATER_FLOW = "water_flow_m3h"
    NOISE = "noise_db"
    HEART_RATE = "heart_rate_bpm"
    STRESS = "stress_index"
    BODY_TEMPERATURE = "body_temperature_c"


class Severity(str, Enum):
    NORMAL = "normal"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass(frozen=True)
class Band:
    lo: float
    hi: float

    def contains(self, value: float) -> bool:
        return self.lo <= value <= self.hi

    def midpoint(self) -> float:
        return (self.lo + self.hi) / 2


@dataclass(frozen=True)
class SensorSpec:
    """
    `bias` is which direction "gets worse" for this sensor — most factory
    signals get worse going up (temperature, pressure, vibration...), but a
    few genuinely fail low in the real world (oil level draining, water flow
    blocked, voltage sagging under load). Mode-based (non-scripted) Warning/
    Critical escalation pushes the sensor's random-walk target in this
    direction; scripted scenarios (scenarios.py) ignore this and drive the
    value explicitly instead.
    """

    unit: str
    normal: Band
    warning: Band
    critical_push: float
    volatility: float
    theta: float = 0.15
    bias: str = "high"  # "high" or "low"

    def classify(self, value: float) -> Severity:
        if self.normal.contains(value):
            return Severity.NORMAL
        if self.warning.contains(value):
            return Severity.WARNING
        return Severity.CRITICAL

    def target_for(self, severity: Severity) -> float:
        if severity is Severity.NORMAL:
            return self.normal.midpoint()
        if severity is Severity.WARNING:
            if self.bias == "high":
                return self.normal.hi + 0.6 * (self.warning.hi - self.normal.hi)
            return self.normal.lo - 0.6 * (self.normal.lo - self.warning.lo)
        # CRITICAL
        if self.bias == "high":
            return self.warning.hi + self.critical_push
        return self.warning.lo - self.critical_push


def relative_spec(
    unit: str,
    baseline: float,
    *,
    normal_pct: float = 0.10,
    warning_pct: float = 0.25,
    critical_push_pct: float = 0.30,
    volatility_pct: float = 0.015,
    theta: float = 0.20,
    bias: str = "high",
) -> SensorSpec:
    """Builds a SensorSpec whose bands are percentages of a per-instance baseline
    (rated current, rated RPM, design pressure, ...) rather than fixed absolutes —
    used for equipment sensors where "normal" depends on which machine it is."""
    normal = Band(baseline * (1 - normal_pct), baseline * (1 + normal_pct))
    warning = Band(baseline * (1 - warning_pct), baseline * (1 + warning_pct))
    return SensorSpec(
        unit=unit,
        normal=normal,
        warning=warning,
        critical_push=baseline * critical_push_pct,
        volatility=baseline * volatility_pct,
        theta=theta,
        bias=bias,
    )


# Universal bands — the same for every instance of these sensor kinds.
UNIVERSAL_SPECS: dict[SensorKind, SensorSpec] = {
    SensorKind.HUMIDITY: SensorSpec(
        unit="%", normal=Band(30, 60), warning=Band(20, 75), critical_push=10, volatility=1.2, theta=0.08,
    ),
    SensorKind.NOISE: SensorSpec(
        unit="dB", normal=Band(55, 85), warning=Band(55, 100), critical_push=15, volatility=1.5, theta=0.15,
    ),
    SensorKind.GAS: SensorSpec(
        unit="%LEL", normal=Band(0, 5), warning=Band(0, 20), critical_push=20, volatility=0.4, theta=0.12,
    ),
    SensorKind.SMOKE: SensorSpec(
        unit="%obscuration", normal=Band(0, 3), warning=Band(0, 15), critical_push=20, volatility=0.3, theta=0.15,
    ),
    SensorKind.VIBRATION: SensorSpec(
        unit="mm/s", normal=Band(0, 2.8), warning=Band(0, 7.1), critical_push=4.0, volatility=0.2, theta=0.12,
    ),
    SensorKind.HEART_RATE: SensorSpec(
        unit="bpm", normal=Band(60, 100), warning=Band(45, 140), critical_push=20, volatility=1.5, theta=0.15,
    ),
    SensorKind.STRESS: SensorSpec(
        unit="index", normal=Band(0, 40), warning=Band(0, 70), critical_push=15, volatility=2.0, theta=0.10,
    ),
    SensorKind.BODY_TEMPERATURE: SensorSpec(
        unit="C", normal=Band(36.1, 37.5), warning=Band(35.5, 38.5), critical_push=1.0, volatility=0.05, theta=0.06,
    ),
    SensorKind.OIL_LEVEL: SensorSpec(
        unit="%", normal=Band(60, 100), warning=Band(30, 100), critical_push=15, volatility=0.3, theta=0.03, bias="low",
    ),
    SensorKind.VALVE_POSITION: SensorSpec(
        unit="%", normal=Band(20, 80), warning=Band(5, 95), critical_push=5, volatility=1.5, theta=0.05,
    ),
}

# Ambient zone-level temperature is universal too, but named separately from
# equipment surface temperature (which uses relative_spec per machine).
AMBIENT_TEMPERATURE_SPEC = SensorSpec(
    unit="C", normal=Band(20, 35), warning=Band(10, 45), critical_push=10, volatility=0.3, theta=0.05,
)
