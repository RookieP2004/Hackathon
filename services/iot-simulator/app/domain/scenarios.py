"""
Scripted emergency scenarios. Each one drives a small set of sensors through a
phased time-series (onset -> escalation -> event -> aftermath) instead of
jumping straight to an alarming number, because that's how real industrial
incidents actually read on a trend chart. A scenario holds control of its
sensors until `SimulationEngine.reset()` is called for its zone — a seized
motor doesn't un-seize itself, and neither does a fire put itself out.

Some scenarios chain into others (`explosion` ignites a `fire`; an unchecked
`gas_leak` ignites into an `explosion`; an unchecked `fire` spreads to an
adjacent zone) — this is what makes the simulator feel like a real facility
rather than a set of independent random-number generators.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

SCENARIO_TYPES = ("gas_leak", "explosion", "machine_failure", "worker_collapse", "fire")


@dataclass
class ActiveScenario:
    scenario_type: str
    zone_id: str
    equipment_id: str | None = None
    worker_id: str | None = None
    started_at: float = 0.0
    phase: str = "onset"
    data: dict = field(default_factory=dict)
    finished: bool = False


def _zone_key(zone_id: str, kind: str) -> str:
    return f"{zone_id}:ambient:{kind}"


def _eq_key(equipment_id: str, kind: str) -> str:
    return f"{equipment_id}:{kind}"


def _worker_key(worker_id: str, kind: str) -> str:
    return f"{worker_id}:{kind}"


def tick_gas_leak(engine, sc: ActiveScenario, elapsed: float, rng: random.Random) -> list[ActiveScenario]:
    gas_key = _zone_key(sc.zone_id, "gas_pct_lel")
    gas = engine.sensors.get(gas_key)
    if gas is None:
        sc.finished = True
        return []

    if elapsed < 10:
        sc.phase = "onset"
        gas.nudge_toward(15.0, 0.08, rng)
    elif elapsed < 60:
        sc.phase = "escalation"
        gas.nudge_toward(55.0, 0.05, rng)
        # the leaking vessel loses pressure as it empties out
        if sc.equipment_id:
            pressure = engine.sensors.get(_eq_key(sc.equipment_id, "pressure_bar"))
            if pressure is not None:
                pressure.nudge_toward(pressure.spec.normal.lo * 0.5, 0.03, rng)
    else:
        sc.phase = "peak"
        gas.nudge_toward(75.0, 0.06, rng)

    if gas.value > gas.spec.warning.hi:
        engine.set_camera_override(
            sc.zone_id, "gas_leak_detected", min(0.4 + elapsed * 0.01, 0.97), person_count=None
        )
        sc.data["critical_seconds"] = sc.data.get("critical_seconds", 0.0) + 1.0
    else:
        sc.data["critical_seconds"] = 0.0

    # Left unchecked long enough, a sustained high gas concentration ignites.
    if sc.data["critical_seconds"] > 30 and not sc.data.get("ignited"):
        sc.data["ignited"] = True
        sc.finished = True
        return [ActiveScenario(scenario_type="explosion", zone_id=sc.zone_id, started_at=engine.clock)]
    return []


def tick_explosion(engine, sc: ActiveScenario, elapsed: float, rng: random.Random) -> list[ActiveScenario]:
    zone = engine.world.zone_by_id(sc.zone_id)
    chained: list[ActiveScenario] = []

    if elapsed < 2:
        sc.phase = "onset"
    elif not sc.data.get("blast_done"):
        sc.phase = "blast"
        sc.data["blast_done"] = True
        for eq in zone.equipment:
            for kind, multiplier in (("temperature_c", 3.0), ("pressure_bar", 4.0)):
                sensor = engine.sensors.get(_eq_key(eq.equipment_id, kind))
                if sensor is not None:
                    sensor.set(sensor.spec.normal.hi * multiplier)
            vib = engine.sensors.get(_eq_key(eq.equipment_id, "vibration_mm_s"))
            if vib is not None:
                vib.set(vib.spec.warning.hi * 3)
            eq.status = "fault"
        for kind, value in (("noise_db", 135.0), ("smoke_pct_obscuration", 95.0), ("gas_pct_lel", 10.0)):
            sensor = engine.sensors.get(_zone_key(sc.zone_id, kind))
            if sensor is not None:
                sensor.set(value)
        for worker in engine.world.workers:
            if worker.zone_id == sc.zone_id:
                engine.shock_worker(worker.worker_id)
        engine.set_camera_override(sc.zone_id, "explosion_detected", 0.99, person_count=None)
        for adjacent in engine.world.zone_adjacency.get(sc.zone_id, []):
            noise = engine.sensors.get(_zone_key(adjacent, "noise_db"))
            if noise is not None:
                noise.nudge_toward(noise.spec.warning.hi, 0.5, rng)
    else:
        sc.phase = "aftermath"
        for kind, decay_target in (("temperature_c", 90.0), ("smoke_pct_obscuration", 60.0)):
            for eq in zone.equipment:
                sensor = engine.sensors.get(_eq_key(eq.equipment_id, "temperature_c"))
                if kind == "temperature_c" and sensor is not None:
                    sensor.nudge_toward(decay_target, 0.03, rng)
            zone_sensor = engine.sensors.get(_zone_key(sc.zone_id, kind))
            if zone_sensor is not None:
                zone_sensor.nudge_toward(decay_target, 0.03, rng)

        if elapsed > 4 and not sc.data.get("ignited_fire"):
            sc.data["ignited_fire"] = True
            chained.append(ActiveScenario(scenario_type="fire", zone_id=sc.zone_id, started_at=engine.clock))

        if elapsed > 8:
            sc.finished = True

    return chained


def tick_machine_failure(engine, sc: ActiveScenario, elapsed: float, rng: random.Random) -> list[ActiveScenario]:
    if sc.equipment_id is None:
        sc.finished = True
        return []
    zone, eq = engine.world.equipment_by_id(sc.equipment_id)

    vib = engine.sensors.get(_eq_key(sc.equipment_id, "vibration_mm_s"))
    temp = engine.sensors.get(_eq_key(sc.equipment_id, "temperature_c"))
    oil = engine.sensors.get(_eq_key(sc.equipment_id, "oil_level_pct"))
    current = engine.sensors.get(_eq_key(sc.equipment_id, "current_a"))
    rpm = engine.sensors.get(_eq_key(sc.equipment_id, "rpm"))
    noise = engine.sensors.get(_eq_key(sc.equipment_id, "noise_db"))

    if sc.data.get("terminal"):
        sc.phase = "terminal"
        if temp is not None:
            temp.nudge_toward(temp.spec.normal.hi, 0.01, rng)  # slow post-failure cooldown
        return []

    if elapsed < 20:
        sc.phase = "onset"
        if vib is not None:
            vib.nudge_toward(vib.spec.warning.lo + 0.7 * (vib.spec.warning.hi - vib.spec.warning.lo), 0.04, rng)
        if temp is not None:
            temp.nudge_toward(temp.spec.warning.hi, 0.03, rng)
        if oil is not None:
            oil.nudge_toward(oil.spec.warning.lo, 0.02, rng)
    elif elapsed < 60:
        sc.phase = "escalation"
        if vib is not None:
            vib.nudge_toward(vib.spec.warning.hi * 1.3, 0.05, rng)
        if temp is not None:
            temp.nudge_toward(temp.spec.warning.hi * 1.2, 0.04, rng)
        if current is not None:
            current.nudge_toward(current.spec.warning.hi, 0.04, rng)
        if rpm is not None:
            rpm.nudge_toward(rpm.spec.normal.midpoint(), 0.05, rng, extra_noise=2.0)  # unstable oscillation
    else:
        sc.phase = "terminal"
        sc.data["terminal"] = True
        if rpm is not None:
            rpm.set(0.0)
        if current is not None:
            current.set(current.spec.warning.hi * 2.5)  # inrush spike
        if noise is not None:
            noise.set(noise.spec.warning.hi + 20)
        if vib is not None:
            vib.set(vib.spec.critical_push + vib.spec.warning.hi)
        eq.status = "fault"

    return []


def tick_worker_collapse(engine, sc: ActiveScenario, elapsed: float, rng: random.Random) -> list[ActiveScenario]:
    if sc.worker_id is None:
        sc.finished = True
        return []

    hr = engine.sensors.get(_worker_key(sc.worker_id, "heart_rate_bpm"))
    stress = engine.sensors.get(_worker_key(sc.worker_id, "stress_index"))
    body_temp = engine.sensors.get(_worker_key(sc.worker_id, "body_temperature_c"))

    if sc.data.get("collapsed"):
        sc.phase = "collapsed"
        engine.set_camera_override(
            engine.world.worker_by_id(sc.worker_id).zone_id,
            "person_down",
            min(0.5 + (elapsed - sc.data["collapse_elapsed"]) * 0.05, 0.98),
            person_count=None,
        )
        return []

    if elapsed < 30:
        sc.phase = "onset"
        if hr is not None:
            hr.nudge_toward(hr.spec.warning.hi, 0.05, rng)
        if stress is not None:
            stress.nudge_toward(stress.spec.warning.hi, 0.05, rng)
        if body_temp is not None:
            body_temp.nudge_toward(body_temp.spec.warning.hi, 0.03, rng)
    elif elapsed < 40:
        sc.phase = "peak"
        if hr is not None:
            hr.nudge_toward(185.0, 0.15, rng)
        if body_temp is not None:
            body_temp.nudge_toward(body_temp.spec.critical_push + body_temp.spec.warning.hi, 0.05, rng)
    else:
        sc.phase = "collapse"
        sc.data["collapsed"] = True
        sc.data["collapse_elapsed"] = elapsed
        engine.collapse_worker(sc.worker_id)
        if hr is not None:
            hr.set(38.0)  # bradycardia after collapse

    return []


def tick_fire(engine, sc: ActiveScenario, elapsed: float, rng: random.Random) -> list[ActiveScenario]:
    chained: list[ActiveScenario] = []
    temp = engine.sensors.get(_zone_key(sc.zone_id, "temperature_c"))
    smoke = engine.sensors.get(_zone_key(sc.zone_id, "smoke_pct_obscuration"))
    gas = engine.sensors.get(_zone_key(sc.zone_id, "gas_pct_lel"))
    noise = engine.sensors.get(_zone_key(sc.zone_id, "noise_db"))

    if elapsed < 15:
        sc.phase = "onset"
        rate = 0.08
    elif elapsed < 45:
        sc.phase = "escalation"
        rate = 0.06
    else:
        sc.phase = "sustained"
        rate = 0.04

    if temp is not None:
        temp.nudge_toward(temp.spec.warning.hi + temp.spec.critical_push, rate, rng)
    if smoke is not None:
        smoke.nudge_toward(90.0, rate, rng)
    if gas is not None:
        gas.nudge_toward(12.0, rate * 0.5, rng)
    if noise is not None:
        noise.nudge_toward(noise.spec.warning.hi, rate, rng)

    confidence = min(0.3 + elapsed * 0.015, 0.99)
    engine.set_camera_override(sc.zone_id, "fire_detected", confidence, person_count=None)

    if elapsed > 90 and not sc.data.get("spread_done"):
        sc.data["spread_done"] = True
        for adjacent in engine.world.zone_adjacency.get(sc.zone_id, []):
            if not engine.zone_has_active_fire(adjacent):
                chained.append(ActiveScenario(scenario_type="fire", zone_id=adjacent, started_at=engine.clock))
                break

    return chained


SCENARIO_HANDLERS = {
    "gas_leak": tick_gas_leak,
    "explosion": tick_explosion,
    "machine_failure": tick_machine_failure,
    "worker_collapse": tick_worker_collapse,
    "fire": tick_fire,
}
