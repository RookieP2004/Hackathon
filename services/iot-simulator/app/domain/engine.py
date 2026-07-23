"""
SimulationEngine — owns every sensor's live value, the active scenario list,
worker GPS/collapse state, and per-zone camera state. `tick()` is called once
a second by app/loop.py; it advances scripted scenarios first (they claim
specific sensors for that tick), then runs the baseline random walk for every
sensor NOT claimed this tick, then returns a JSON-serializable snapshot for
WebSocket broadcast.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field

from app.domain.scenarios import SCENARIO_HANDLERS, ActiveScenario
from app.domain.sensor_types import (
    AMBIENT_TEMPERATURE_SPEC,
    UNIVERSAL_SPECS,
    Severity,
    SensorKind,
    relative_spec,
)
from app.domain.simulation import SensorState
from app.domain.world import (
    MACHINE_PROFILES,
    RELATIVE_KIND_DEFAULTS,
    UNIVERSAL_ONLY_KINDS,
    World,
    build_demo_world,
)

FIRE_SCENARIO_TYPES_FOR_ZONE = ("fire",)
EXPLOSION_BLAST_PHASES = ("blast", "aftermath")

AMBIENT_KINDS = (
    SensorKind.HUMIDITY,
    SensorKind.GAS,
    SensorKind.SMOKE,
    SensorKind.NOISE,
)

WORKER_KINDS = (SensorKind.HEART_RATE, SensorKind.STRESS, SensorKind.BODY_TEMPERATURE)

CAMERA_EVENT_TYPES_NORMAL = ("normal", "normal", "normal", "normal", "ppe_violation")

ZONE_GRID_STEP_DEG = 0.0006  # roughly ~65m at this latitude — plausible indoor-plant spacing
WORKER_JITTER_DEG = 0.00004  # a few meters of GPS jitter per tick
VEHICLE_JITTER_DEG = 0.00012  # vehicles cover more ground per tick than a walking worker
RESPONDER_LERP_RATE = 0.18  # fraction of remaining distance closed per tick when responding/returning
RESPONDER_ARRIVAL_EPSILON_DEG = 0.00003  # "close enough to call it arrived"


@dataclass
class CameraEvent:
    camera_id: str
    event_type: str
    confidence: float
    person_count: int


@dataclass
class WorkerRuntimeState:
    lat: float
    lon: float
    collapsed: bool = False
    shocked_until: float = 0.0


@dataclass
class VehicleRuntimeState:
    lat: float
    lon: float
    status: str = "idle"  # "moving" | "idle" | "parked"


@dataclass
class FireSystemRuntimeState:
    status: str = "armed"  # "armed" | "discharged" | "fault"
    discharge_count: int = 0


@dataclass
class RobotRuntimeState:
    lat: float
    lon: float
    status: str = "idle"  # arm: "idle" | "running" | "fault"; amr: "idle" | "moving"
    cycle_phase: float = 0.0  # 0-1, drives the arm's repeating animation


@dataclass
class ResponderRuntimeState:
    lat: float
    lon: float
    status: str = "standby"  # "standby" | "responding" | "on_scene"


class SimulationEngine:
    def __init__(self, world: World | None = None, seed: int | None = None) -> None:
        self.world = world or build_demo_world()
        self.rng = random.Random(seed)
        self.tick_count = 0
        self.clock = 0.0
        self.global_mode: Severity = Severity.NORMAL
        self.zone_modes: dict[str, Severity] = {}
        self.active_scenarios: list[ActiveScenario] = []
        self.camera_state: dict[str, CameraEvent] = {}
        self.worker_state: dict[str, WorkerRuntimeState] = {}
        self.vehicle_state: dict[str, VehicleRuntimeState] = {}
        self.fire_system_state: dict[str, FireSystemRuntimeState] = {
            fs.fire_system_id: FireSystemRuntimeState() for fs in self.world.fire_systems
        }
        self.robot_state: dict[str, RobotRuntimeState] = {}
        self.responder_state: dict[str, ResponderRuntimeState] = {}
        self.sensors: dict[str, SensorState] = {}
        self._build_sensors()
        self._build_mobile_asset_state()

    # ---- construction ----------------------------------------------------

    def _build_sensors(self) -> None:
        for zone_index, zone in enumerate(self.world.zones):
            for kind in (SensorKind.TEMPERATURE,) + AMBIENT_KINDS:
                spec = AMBIENT_TEMPERATURE_SPEC if kind is SensorKind.TEMPERATURE else UNIVERSAL_SPECS[kind]
                key = f"{zone.zone_id}:ambient:{kind.value}"
                self.sensors[key] = SensorState(key=key, spec=spec, value=spec.normal.midpoint())
            self.camera_state[zone.zone_id] = CameraEvent(zone.camera_id, "normal", 0.98, person_count=0)

            for eq in zone.equipment:
                profile = MACHINE_PROFILES[eq.machine_class]
                for kind, baseline in profile["sensors"].items():
                    key = f"{eq.equipment_id}:{kind.value}"
                    if baseline is None or kind in UNIVERSAL_ONLY_KINDS:
                        spec = UNIVERSAL_SPECS[kind]
                        start = spec.normal.midpoint()
                    else:
                        defaults = RELATIVE_KIND_DEFAULTS[kind]
                        spec = relative_spec(defaults["unit"], baseline, bias=defaults["bias"])
                        start = baseline
                    self.sensors[key] = SensorState(key=key, spec=spec, value=start)

        for worker in self.world.workers:
            for kind in WORKER_KINDS:
                spec = UNIVERSAL_SPECS[kind]
                key = f"{worker.worker_id}:{kind.value}"
                self.sensors[key] = SensorState(key=key, spec=spec, value=spec.normal.midpoint())

    def _zone_anchors(self) -> dict[str, tuple[float, float]]:
        return {
            zone.zone_id: (
                self.world.plant_lat + i * ZONE_GRID_STEP_DEG,
                self.world.plant_lon + (i % 2) * ZONE_GRID_STEP_DEG,
            )
            for i, zone in enumerate(self.world.zones)
        }

    def _build_mobile_asset_state(self) -> None:
        zone_anchor = self._zone_anchors()
        for worker in self.world.workers:
            lat, lon = zone_anchor[worker.zone_id]
            self.worker_state[worker.worker_id] = WorkerRuntimeState(lat=lat, lon=lon)
        for vehicle in self.world.vehicles:
            lat, lon = zone_anchor[vehicle.zone_id]
            self.vehicle_state[vehicle.vehicle_id] = VehicleRuntimeState(lat=lat, lon=lon)
        for robot in self.world.robots:
            lat, lon = zone_anchor[robot.zone_id]
            self.robot_state[robot.robot_id] = RobotRuntimeState(lat=lat, lon=lon)
        for responder in self.world.emergency_responders:
            lat, lon = zone_anchor[responder.home_zone_id]
            self.responder_state[responder.responder_id] = ResponderRuntimeState(lat=lat, lon=lon)

    # ---- scenario/world control used by scenarios.py ----------------------

    def set_camera_override(self, zone_id: str, event_type: str, confidence: float, person_count: int | None) -> None:
        current = self.camera_state[zone_id]
        pc = current.person_count if person_count is None else person_count
        self.camera_state[zone_id] = CameraEvent(current.camera_id, event_type, confidence, pc)

    def shock_worker(self, worker_id: str) -> None:
        state = self.worker_state[worker_id]
        state.shocked_until = self.clock + 15.0
        for kind in (SensorKind.HEART_RATE, SensorKind.STRESS):
            sensor = self.sensors.get(f"{worker_id}:{kind.value}")
            if sensor is not None:
                sensor.nudge_toward(sensor.spec.warning.hi, 0.6, self.rng)

    def collapse_worker(self, worker_id: str) -> None:
        self.worker_state[worker_id].collapsed = True

    def zone_has_active_fire(self, zone_id: str) -> bool:
        return any(sc.scenario_type == "fire" and not sc.finished and sc.zone_id == zone_id for sc in self.active_scenarios)

    # ---- public control API (used by REST layer) ---------------------------

    def set_mode(self, mode: Severity, zone_id: str | None = None) -> None:
        if zone_id is None:
            self.global_mode = mode
            self.zone_modes.clear()
        else:
            self.zone_modes[zone_id] = mode

    def trigger_scenario(
        self, scenario_type: str, *, zone_id: str, equipment_id: str | None = None, worker_id: str | None = None
    ) -> ActiveScenario:
        sc = ActiveScenario(
            scenario_type=scenario_type,
            zone_id=zone_id,
            equipment_id=equipment_id,
            worker_id=worker_id,
            started_at=self.clock,
        )
        self.active_scenarios.append(sc)
        return sc

    def reset(self, zone_id: str | None = None) -> None:
        if zone_id is None:
            self.active_scenarios.clear()
            self.zone_modes.clear()
            self.global_mode = Severity.NORMAL
            for eq_zone in self.world.zones:
                for eq in eq_zone.equipment:
                    eq.status = "operational"
            for worker in self.world.workers:
                self.worker_state[worker.worker_id].collapsed = False
                self.worker_state[worker.worker_id].shocked_until = 0.0
            for zone in self.world.zones:
                self.camera_state[zone.zone_id] = CameraEvent(zone.camera_id, "normal", 0.98, person_count=0)
            for fs in self.world.fire_systems:
                self.fire_system_state[fs.fire_system_id].status = "armed"
        else:
            self.active_scenarios = [sc for sc in self.active_scenarios if sc.zone_id != zone_id]
            self.zone_modes.pop(zone_id, None)
            zone = self.world.zone_by_id(zone_id)
            for eq in zone.equipment:
                eq.status = "operational"
            self.camera_state[zone_id] = CameraEvent(zone.camera_id, "normal", 0.98, person_count=0)
            for worker in self.world.workers:
                if worker.zone_id == zone_id:
                    self.worker_state[worker.worker_id].collapsed = False
            for fs in self.world.fire_systems:
                if fs.zone_id == zone_id:
                    self.fire_system_state[fs.fire_system_id].status = "armed"

    # ---- the per-second tick ------------------------------------------------

    def tick(self) -> dict:
        self.tick_count += 1
        self.clock += 1.0

        claimed_keys: set[str] = set()
        still_active: list[ActiveScenario] = []
        newly_spawned: list[ActiveScenario] = []

        for sc in self.active_scenarios:
            if sc.finished:
                continue
            handler = SCENARIO_HANDLERS[sc.scenario_type]
            elapsed = self.clock - sc.started_at
            spawned = handler(self, sc, elapsed, self.rng)
            newly_spawned.extend(spawned)
            claimed_keys.update(self._keys_for_scenario(sc))
            if not sc.finished:
                still_active.append(sc)
        self.active_scenarios = still_active + newly_spawned

        for key, sensor in self.sensors.items():
            if key in claimed_keys:
                continue
            zone_id = self._zone_id_for_key(key)
            sensor.mode = self.zone_modes.get(zone_id, self.global_mode) if zone_id else self.global_mode
            sensor.step(self.rng)

        self._step_worker_gps()
        self._step_vehicle_gps()
        self._step_robots()
        self._step_responders()
        self._step_fire_systems()
        self._step_camera_baseline(claimed_keys)

        return self.snapshot()

    def _keys_for_scenario(self, sc: ActiveScenario) -> set[str]:
        # Claim exactly the sensors each scenario handler actually writes to
        # this tick — anything else in the same zone (e.g. an unrelated
        # machine during a gas_leak, or the zone's ambient air during a
        # worker_collapse) must keep drifting under the baseline random walk
        # rather than freezing just because *something* is happening nearby.
        keys: set[str] = set()
        zone = self.world.zone_by_id(sc.zone_id)

        if sc.scenario_type in ("gas_leak", "explosion", "fire"):
            for kind in (SensorKind.TEMPERATURE,) + AMBIENT_KINDS:
                keys.add(f"{zone.zone_id}:ambient:{kind.value}")

        if sc.scenario_type == "gas_leak" and sc.equipment_id:
            keys.add(f"{sc.equipment_id}:pressure_bar")

        if sc.scenario_type == "explosion":
            for eq in zone.equipment:
                for kind in MACHINE_PROFILES[eq.machine_class]["sensors"]:
                    keys.add(f"{eq.equipment_id}:{kind.value}")
            for worker in self.world.workers:
                if worker.zone_id == sc.zone_id:
                    for kind in (SensorKind.HEART_RATE, SensorKind.STRESS):
                        keys.add(f"{worker.worker_id}:{kind.value}")

        if sc.scenario_type == "machine_failure" and sc.equipment_id:
            _, eq = self.world.equipment_by_id(sc.equipment_id)
            for kind in MACHINE_PROFILES[eq.machine_class]["sensors"]:
                keys.add(f"{sc.equipment_id}:{kind.value}")

        if sc.scenario_type == "worker_collapse" and sc.worker_id:
            for kind in WORKER_KINDS:
                keys.add(f"{sc.worker_id}:{kind.value}")

        return keys

    def _zone_id_for_key(self, key: str) -> str | None:
        if ":ambient:" in key:
            return key.split(":ambient:")[0]
        owner_id = key.split(":")[0]
        for zone in self.world.zones:
            for eq in zone.equipment:
                if eq.equipment_id == owner_id:
                    return zone.zone_id
        for worker in self.world.workers:
            if worker.worker_id == owner_id:
                return worker.zone_id
        return None

    def _step_worker_gps(self) -> None:
        for worker in self.world.workers:
            state = self.worker_state[worker.worker_id]
            if state.collapsed:
                continue  # a collapsed worker's position stops updating
            state.lat += self.rng.gauss(0, WORKER_JITTER_DEG)
            state.lon += self.rng.gauss(0, WORKER_JITTER_DEG)

    def _step_vehicle_gps(self) -> None:
        for vehicle in self.world.vehicles:
            state = self.vehicle_state[vehicle.vehicle_id]
            # Vehicles alternate moving/idle rather than jittering continuously
            # like worker GPS -- a forklift sits still between runs, it doesn't
            # perpetually drift the way ambient GPS noise would suggest.
            if self.rng.random() < 0.15:
                state.status = "idle" if state.status == "moving" else "moving"
            if state.status == "moving":
                state.lat += self.rng.gauss(0, VEHICLE_JITTER_DEG)
                state.lon += self.rng.gauss(0, VEHICLE_JITTER_DEG)

    def _step_robots(self) -> None:
        for robot in self.world.robots:
            state = self.robot_state[robot.robot_id]
            if robot.robot_type == "arm":
                assert robot.equipment_id is not None
                _, eq = self.world.equipment_by_id(robot.equipment_id)
                if eq.status != "operational":
                    state.status = "fault"
                    continue  # a faulted arm stops mid-cycle, it doesn't keep waving around
                state.status = "running"
                state.cycle_phase = (state.cycle_phase + 0.12) % 1.0
            else:  # "amr" -- roams its zone like a vehicle
                if self.rng.random() < 0.15:
                    state.status = "idle" if state.status == "moving" else "moving"
                if state.status == "moving":
                    state.lat += self.rng.gauss(0, VEHICLE_JITTER_DEG)
                    state.lon += self.rng.gauss(0, VEHICLE_JITTER_DEG)

    def _current_emergency_zone_id(self) -> str | None:
        for sc in self.active_scenarios:
            if not sc.finished:
                return sc.zone_id
        return None

    def _step_responders(self) -> None:
        zone_anchor = self._zone_anchors()
        emergency_zone_id = self._current_emergency_zone_id()

        for responder in self.world.emergency_responders:
            state = self.responder_state[responder.responder_id]
            target_zone_id = emergency_zone_id or responder.home_zone_id
            target_lat, target_lon = zone_anchor[target_zone_id]

            # Ease toward the target rather than teleporting -- a fixed fraction
            # of the remaining distance per tick, so it visibly travels across
            # the plant over several seconds instead of snapping there.
            state.lat += (target_lat - state.lat) * RESPONDER_LERP_RATE
            state.lon += (target_lon - state.lon) * RESPONDER_LERP_RATE

            close_enough = abs(state.lat - target_lat) < RESPONDER_ARRIVAL_EPSILON_DEG and abs(state.lon - target_lon) < RESPONDER_ARRIVAL_EPSILON_DEG
            if emergency_zone_id is None:
                state.status = "standby" if close_enough else "responding"
            else:
                state.status = "on_scene" if close_enough else "responding"

    def _zone_has_fire_or_blast(self, zone_id: str) -> bool:
        for sc in self.active_scenarios:
            if sc.finished or sc.zone_id != zone_id:
                continue
            if sc.scenario_type == "fire":
                return True
            if sc.scenario_type == "explosion" and sc.phase in EXPLOSION_BLAST_PHASES:
                return True
        return False

    def _step_fire_systems(self) -> None:
        for fs in self.world.fire_systems:
            state = self.fire_system_state[fs.fire_system_id]
            if state.status == "fault":
                continue  # a faulted system stays faulted until manually reset
            active = self._zone_has_fire_or_blast(fs.zone_id)
            if active and state.status == "armed":
                state.status = "discharged"
                state.discharge_count += 1
            # Deliberately does NOT auto-revert to "armed" once the fire clears
            # -- a real suppression system needs manual recharge/reset before
            # it's armed again, matching this simulator's existing rule that
            # emergency scenarios never self-resolve without operator action.

    def _step_camera_baseline(self, claimed_keys: set[str]) -> None:
        for zone in self.world.zones:
            if any(sc.zone_id == zone.zone_id and not sc.finished for sc in self.active_scenarios):
                continue  # scenario already owns this zone's camera feed this tick
            current = self.camera_state[zone.zone_id]
            person_count = sum(1 for w in self.world.workers if w.zone_id == zone.zone_id)
            if self.rng.random() < 0.01:
                event_type = self.rng.choice(CAMERA_EVENT_TYPES_NORMAL)
                confidence = round(self.rng.uniform(0.75, 0.99), 2)
            else:
                event_type, confidence = "normal", round(self.rng.uniform(0.9, 0.99), 2)
            self.camera_state[zone.zone_id] = CameraEvent(current.camera_id, event_type, confidence, person_count)

    # ---- serialization -----------------------------------------------------

    @staticmethod
    def _worst_of(severities: list[Severity]) -> Severity:
        if Severity.CRITICAL in severities:
            return Severity.CRITICAL
        if Severity.WARNING in severities:
            return Severity.WARNING
        return Severity.NORMAL

    def snapshot(self) -> dict:
        zones_payload = []
        for zone in self.world.zones:
            ambient_kinds = (SensorKind.TEMPERATURE,) + AMBIENT_KINDS
            ambient = {
                kind.value: round(self.sensors[f"{zone.zone_id}:ambient:{kind.value}"].value, 2)
                for kind in ambient_kinds
            }
            ambient_severity = self._worst_of(
                [self.sensors[f"{zone.zone_id}:ambient:{kind.value}"].severity() for kind in ambient_kinds]
            )

            equipment_payload = []
            equipment_severities = [ambient_severity]
            for eq in zone.equipment:
                kinds = MACHINE_PROFILES[eq.machine_class]["sensors"]
                readings = {kind.value: round(self.sensors[f"{eq.equipment_id}:{kind.value}"].value, 2) for kind in kinds}
                worst = self._worst_of([self.sensors[f"{eq.equipment_id}:{kind.value}"].severity() for kind in kinds])
                equipment_severities.append(worst)
                equipment_payload.append(
                    {
                        "equipment_id": eq.equipment_id,
                        "tag": eq.tag,
                        "name": eq.name,
                        "machine_class": eq.machine_class,
                        "status": eq.status,
                        "severity": worst.value,
                        "readings": readings,
                    }
                )
            camera = self.camera_state[zone.zone_id]
            zones_payload.append(
                {
                    "zone_id": zone.zone_id,
                    "name": zone.name,
                    "building_id": zone.building_id,
                    "mode": self.zone_modes.get(zone.zone_id, self.global_mode).value,
                    "severity": self._worst_of(equipment_severities).value,
                    "ambient": ambient,
                    "ambient_severity": ambient_severity.value,
                    "equipment": equipment_payload,
                    "camera": {
                        "camera_id": camera.camera_id,
                        "event_type": camera.event_type,
                        "confidence": camera.confidence,
                        "person_count": camera.person_count,
                    },
                }
            )

        zone_severity_by_id = {z["zone_id"]: Severity(z["severity"]) for z in zones_payload}

        buildings_payload = []
        for building in self.world.buildings:
            zone_ids = [z.zone_id for z in self.world.zones if z.building_id == building.building_id]
            buildings_payload.append(
                {
                    "building_id": building.building_id,
                    "name": building.name,
                    "zone_ids": zone_ids,
                    "severity": self._worst_of([zone_severity_by_id[zid] for zid in zone_ids]).value,
                }
            )

        workers_payload = []
        for worker in self.world.workers:
            state = self.worker_state[worker.worker_id]
            vitals = {
                kind.value: round(self.sensors[f"{worker.worker_id}:{kind.value}"].value, 1) for kind in WORKER_KINDS
            }
            vitals_severity = self._worst_of(
                [self.sensors[f"{worker.worker_id}:{kind.value}"].severity() for kind in WORKER_KINDS]
            )
            workers_payload.append(
                {
                    "worker_id": worker.worker_id,
                    "name": worker.name,
                    "badge_id": worker.badge_id,
                    "zone_id": worker.zone_id,
                    "status": "collapsed" if state.collapsed else "active",
                    "severity": vitals_severity.value,
                    "gps": {"lat": round(state.lat, 6), "lon": round(state.lon, 6)},
                    "vitals": vitals,
                }
            )

        vehicles_payload = []
        for vehicle in self.world.vehicles:
            state = self.vehicle_state[vehicle.vehicle_id]
            vehicles_payload.append(
                {
                    "vehicle_id": vehicle.vehicle_id,
                    "name": vehicle.name,
                    "vehicle_type": vehicle.vehicle_type,
                    "zone_id": vehicle.zone_id,
                    "status": state.status,
                    "gps": {"lat": round(state.lat, 6), "lon": round(state.lon, 6)},
                }
            )

        emergency_exits_payload = [
            {
                "exit_id": ex.exit_id,
                "name": ex.name,
                "zone_id": ex.zone_id,
                "status": "blocked" if self._zone_has_fire_or_blast(ex.zone_id) else "clear",
            }
            for ex in self.world.emergency_exits
        ]

        fire_systems_payload = [
            {
                "fire_system_id": fs.fire_system_id,
                "name": fs.name,
                "zone_id": fs.zone_id,
                "system_type": fs.system_type,
                "status": self.fire_system_state[fs.fire_system_id].status,
                "discharge_count": self.fire_system_state[fs.fire_system_id].discharge_count,
            }
            for fs in self.world.fire_systems
        ]

        equipment_index = {
            eq.equipment_id: (zone, eq) for zone in self.world.zones for eq in zone.equipment
        }
        equipment_severity_by_id = {
            eq["equipment_id"]: eq["severity"] for zone in zones_payload for eq in zone["equipment"]
        }
        pipelines_payload = []
        for pipe in self.world.pipelines:
            from_zone, from_eq = equipment_index[pipe.from_equipment_id]
            to_zone, to_eq = equipment_index[pipe.to_equipment_id]
            flowing = from_eq.status == "operational" and to_eq.status == "operational"
            from_severity = Severity(equipment_severity_by_id[pipe.from_equipment_id])
            to_severity = Severity(equipment_severity_by_id[pipe.to_equipment_id])
            pipelines_payload.append(
                {
                    "pipeline_id": pipe.pipeline_id,
                    "name": pipe.name,
                    "kind": pipe.kind,
                    "from_equipment_id": pipe.from_equipment_id,
                    "to_equipment_id": pipe.to_equipment_id,
                    "from_zone_id": from_zone.zone_id,
                    "to_zone_id": to_zone.zone_id,
                    "status": "flowing" if flowing else "stopped",
                    "severity": self._worst_of([from_severity, to_severity]).value,
                }
            )

        robots_payload = []
        for robot in self.world.robots:
            state = self.robot_state[robot.robot_id]
            robots_payload.append(
                {
                    "robot_id": robot.robot_id,
                    "name": robot.name,
                    "robot_type": robot.robot_type,
                    "zone_id": robot.zone_id,
                    "equipment_id": robot.equipment_id,
                    "status": state.status,
                    "cycle_phase": round(state.cycle_phase, 3),
                    "gps": {"lat": round(state.lat, 6), "lon": round(state.lon, 6)},
                }
            )

        emergency_responders_payload = [
            {
                "responder_id": responder.responder_id,
                "name": responder.name,
                "home_zone_id": responder.home_zone_id,
                "status": self.responder_state[responder.responder_id].status,
                "gps": {
                    "lat": round(self.responder_state[responder.responder_id].lat, 6),
                    "lon": round(self.responder_state[responder.responder_id].lon, 6),
                },
            }
            for responder in self.world.emergency_responders
        ]

        return {
            "type": "telemetry",
            "tick": self.tick_count,
            "timestamp": time.time(),
            "global_mode": self.global_mode.value,
            "active_scenarios": [
                {
                    "scenario_type": sc.scenario_type,
                    "zone_id": sc.zone_id,
                    "equipment_id": sc.equipment_id,
                    "worker_id": sc.worker_id,
                    "phase": sc.phase,
                    "elapsed_seconds": round(self.clock - sc.started_at, 1),
                }
                for sc in self.active_scenarios
            ],
            "buildings": buildings_payload,
            "zones": zones_payload,
            "vehicles": vehicles_payload,
            "emergency_exits": emergency_exits_payload,
            "fire_systems": fire_systems_payload,
            "pipelines": pipelines_payload,
            "robots": robots_payload,
            "emergency_responders": emergency_responders_payload,
            "workers": workers_payload,
        }
