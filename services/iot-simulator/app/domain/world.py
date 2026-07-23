"""
The demo factory — a small, fixed topology of zones, equipment, and workers
that the simulation engine drives every tick. Deliberately reuses "Valve V-12"
as a tag (DIGITAL_TWIN_EXPERIENCE.md §5.1's canonical predicted-leak walkthrough)
so this simulator's output lines up with the documented demo narrative.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.sensor_types import SensorKind

# machine_class -> which SensorKinds that class of equipment actually reports,
# plus the baseline value relative_spec() derives that machine's bands from.
# Not every machine has every sensor: a storage tank has no RPM, a conveyor
# motor has no oil level. This mirrors real nameplate/instrumentation reality.
MACHINE_PROFILES: dict[str, dict] = {
    "compressor": {
        "sensors": {
            SensorKind.TEMPERATURE: 65.0,
            SensorKind.VIBRATION: None,  # universal spec, no baseline needed
            SensorKind.CURRENT: 120.0,
            SensorKind.VOLTAGE: 415.0,
            SensorKind.RPM: 2950.0,
            SensorKind.OIL_LEVEL: None,
            SensorKind.NOISE: None,
            SensorKind.PRESSURE: 8.5,
        },
    },
    "boiler": {
        "sensors": {
            SensorKind.TEMPERATURE: 180.0,
            SensorKind.PRESSURE: 12.0,
            SensorKind.SMOKE: None,
            SensorKind.GAS: None,
            SensorKind.NOISE: None,
            SensorKind.WATER_FLOW: 40.0,
        },
    },
    "storage_tank": {
        "sensors": {
            SensorKind.PRESSURE: 4.0,
            SensorKind.TEMPERATURE: 30.0,
            SensorKind.GAS: None,
            SensorKind.VALVE_POSITION: 50.0,
        },
    },
    "valve": {
        "sensors": {
            SensorKind.PRESSURE: 6.0,
            SensorKind.VALVE_POSITION: 50.0,
            SensorKind.TEMPERATURE: 28.0,
        },
    },
    "conveyor_motor": {
        "sensors": {
            SensorKind.CURRENT: 45.0,
            SensorKind.VOLTAGE: 415.0,
            SensorKind.RPM: 1450.0,
            SensorKind.VIBRATION: None,
            SensorKind.TEMPERATURE: 55.0,
            SensorKind.NOISE: None,
        },
    },
    "pump": {
        "sensors": {
            SensorKind.CURRENT: 60.0,
            SensorKind.VOLTAGE: 415.0,
            SensorKind.RPM: 1780.0,
            SensorKind.VIBRATION: None,
            SensorKind.TEMPERATURE: 50.0,
            SensorKind.WATER_FLOW: 25.0,
            SensorKind.OIL_LEVEL: None,
            SensorKind.NOISE: None,
        },
    },
}

# Oil level and noise and vibration and smoke/gas don't scale off a baseline
# the way current/rpm/pressure do -- these use the universal spec directly
# (a bearing that needs 80% oil is the same whether it's a 5kW or 500kW motor).
UNIVERSAL_ONLY_KINDS = {
    SensorKind.VIBRATION,
    SensorKind.OIL_LEVEL,
    SensorKind.VALVE_POSITION,
    SensorKind.NOISE,
    SensorKind.SMOKE,
    SensorKind.GAS,
}

# Per-kind unit/bias used when building a baseline-relative spec (see engine.py's
# sensor construction) for the kinds that DO scale with a specific machine's
# nameplate rating.
RELATIVE_KIND_DEFAULTS: dict[SensorKind, dict] = {
    SensorKind.TEMPERATURE: {"unit": "C", "bias": "high"},
    SensorKind.CURRENT: {"unit": "A", "bias": "high"},
    SensorKind.VOLTAGE: {"unit": "V", "bias": "low"},
    SensorKind.RPM: {"unit": "rpm", "bias": "high"},
    SensorKind.PRESSURE: {"unit": "bar", "bias": "high"},
    SensorKind.WATER_FLOW: {"unit": "m3/h", "bias": "low"},
}


@dataclass
class Equipment:
    equipment_id: str
    tag: str
    name: str
    machine_class: str
    status: str = "operational"


@dataclass
class Zone:
    zone_id: str
    name: str
    building_id: str
    equipment: list[Equipment] = field(default_factory=list)
    camera_id: str = ""


@dataclass
class Building:
    building_id: str
    name: str


@dataclass
class Worker:
    worker_id: str
    name: str
    zone_id: str
    badge_id: str


@dataclass
class Vehicle:
    vehicle_id: str
    name: str
    vehicle_type: str  # "forklift" | "tanker_truck"
    zone_id: str


@dataclass
class EmergencyExit:
    exit_id: str
    name: str
    zone_id: str


@dataclass
class FireSystem:
    fire_system_id: str
    name: str
    zone_id: str
    system_type: str  # "sprinkler" | "deluge" | "foam"


@dataclass
class Pipeline:
    pipeline_id: str
    name: str
    kind: str  # "process" | "utility" | "feed"
    from_equipment_id: str
    to_equipment_id: str


@dataclass
class Robot:
    robot_id: str
    name: str
    robot_type: str  # "arm" (stationary, tied to one piece of equipment) | "amr" (roams its zone)
    zone_id: str
    equipment_id: str | None = None  # arms are bolted to a specific machine; AMRs have none


@dataclass
class EmergencyResponder:
    responder_id: str
    name: str
    home_zone_id: str  # muster point — where they stand by when nothing is happening


@dataclass
class World:
    buildings: list[Building]
    zones: list[Zone]
    workers: list[Worker]
    vehicles: list[Vehicle]
    emergency_exits: list[EmergencyExit]
    fire_systems: list[FireSystem]
    pipelines: list[Pipeline]
    robots: list[Robot]
    emergency_responders: list[EmergencyResponder]
    zone_adjacency: dict[str, list[str]]
    plant_lat: float = 19.0760
    plant_lon: float = 72.8777

    def zone_by_id(self, zone_id: str) -> Zone:
        for z in self.zones:
            if z.zone_id == zone_id:
                return z
        raise KeyError(f"Unknown zone_id: {zone_id}")

    def equipment_by_id(self, equipment_id: str) -> tuple[Zone, Equipment]:
        for z in self.zones:
            for eq in z.equipment:
                if eq.equipment_id == equipment_id:
                    return z, eq
        raise KeyError(f"Unknown equipment_id: {equipment_id}")

    def worker_by_id(self, worker_id: str) -> Worker:
        for w in self.workers:
            if w.worker_id == worker_id:
                return w
        raise KeyError(f"Unknown worker_id: {worker_id}")

    def vehicle_by_id(self, vehicle_id: str) -> Vehicle:
        for v in self.vehicles:
            if v.vehicle_id == vehicle_id:
                return v
        raise KeyError(f"Unknown vehicle_id: {vehicle_id}")

    def robot_by_id(self, robot_id: str) -> Robot:
        for r in self.robots:
            if r.robot_id == robot_id:
                return r
        raise KeyError(f"Unknown robot_id: {robot_id}")

    def responder_by_id(self, responder_id: str) -> EmergencyResponder:
        for r in self.emergency_responders:
            if r.responder_id == responder_id:
                return r
        raise KeyError(f"Unknown responder_id: {responder_id}")


def build_demo_world() -> World:
    buildings = [
        Building("utilities-building", "Utilities Building"),
        Building("tank-farm-building", "Tank Farm"),
        Building("production-building", "Production Building"),
        Building("warehouse-building", "Warehouse Building"),
    ]

    zones = [
        Zone(
            zone_id="compressor-house",
            name="Compressor House",
            building_id="utilities-building",
            camera_id="CAM-01",
            equipment=[
                Equipment("eq-c101", "C-101", "Air Compressor 101", "compressor"),
                Equipment("eq-c102", "C-102", "Air Compressor 102", "compressor"),
            ],
        ),
        Zone(
            zone_id="boiler-room",
            name="Boiler Room",
            building_id="utilities-building",
            camera_id="CAM-02",
            equipment=[Equipment("eq-b201", "B-201", "Boiler 201", "boiler")],
        ),
        Zone(
            zone_id="tank-farm",
            name="Storage Tank Farm",
            building_id="tank-farm-building",
            camera_id="CAM-03",
            equipment=[
                Equipment("eq-t301", "T-301", "Storage Tank 301", "storage_tank"),
                Equipment("eq-v12", "V-12", "Outlet Valve 12", "valve"),
            ],
        ),
        Zone(
            zone_id="assembly-line",
            name="Assembly Line",
            building_id="production-building",
            camera_id="CAM-04",
            equipment=[
                Equipment("eq-m401", "M-401", "Conveyor Motor 401", "conveyor_motor"),
                Equipment("eq-p402", "P-402", "Transfer Pump 402", "pump"),
            ],
        ),
        Zone(zone_id="warehouse", name="Warehouse", building_id="warehouse-building", camera_id="CAM-05", equipment=[]),
    ]

    workers = [
        Worker("w-1", "Ramesh Kumar", "compressor-house", "BADGE-1001"),
        Worker("w-2", "Suresh Patil", "boiler-room", "BADGE-1002"),
        Worker("w-3", "Anita Sharma", "tank-farm", "BADGE-1003"),
        Worker("w-4", "Vikram Singh", "assembly-line", "BADGE-1004"),
    ]

    vehicles = [
        Vehicle("veh-1", "Forklift 1", "forklift", "warehouse"),
        Vehicle("veh-2", "Forklift 2", "forklift", "assembly-line"),
        Vehicle("veh-3", "Tanker Truck 1", "tanker_truck", "tank-farm"),
    ]

    emergency_exits = [
        EmergencyExit("exit-1", "Compressor House Exit A", "compressor-house"),
        EmergencyExit("exit-2", "Boiler Room Exit A", "boiler-room"),
        EmergencyExit("exit-3", "Tank Farm Exit A", "tank-farm"),
        EmergencyExit("exit-4", "Tank Farm Exit B", "tank-farm"),
        EmergencyExit("exit-5", "Assembly Line Exit A", "assembly-line"),
        EmergencyExit("exit-6", "Warehouse Exit A", "warehouse"),
        EmergencyExit("exit-7", "Warehouse Exit B", "warehouse"),
    ]

    fire_systems = [
        FireSystem("fs-1", "Compressor House Sprinklers", "compressor-house", "sprinkler"),
        FireSystem("fs-2", "Boiler Room Deluge", "boiler-room", "deluge"),
        FireSystem("fs-3", "Tank Farm Foam System", "tank-farm", "foam"),
        FireSystem("fs-4", "Assembly Line Sprinklers", "assembly-line", "sprinkler"),
        FireSystem("fs-5", "Warehouse Sprinklers", "warehouse", "sprinkler"),
    ]

    pipelines = [
        Pipeline("pipe-1", "Tank 301 to Valve 12", "process", "eq-t301", "eq-v12"),
        Pipeline("pipe-2", "Valve 12 to Boiler Feed", "feed", "eq-v12", "eq-b201"),
        Pipeline("pipe-3", "Compressor Discharge Header", "process", "eq-c101", "eq-c102"),
        Pipeline("pipe-4", "Boiler Steam to Assembly", "utility", "eq-b201", "eq-m401"),
        Pipeline("pipe-5", "Transfer Pump to Warehouse", "utility", "eq-p402", "eq-t301"),
    ]

    robots = [
        Robot("robot-1", "Assembly Arm 1", "arm", "assembly-line", equipment_id="eq-m401"),
        Robot("robot-2", "Compressor Inspection Arm", "arm", "compressor-house", equipment_id="eq-c101"),
        Robot("robot-3", "Warehouse AMR 1", "amr", "warehouse"),
    ]

    emergency_responders = [
        EmergencyResponder("resp-1", "Fire Team Alpha", "warehouse"),
        EmergencyResponder("resp-2", "Fire Team Bravo", "warehouse"),
    ]

    # A simple linear adjacency chain — realistic enough for fire-spread logic
    # without needing a real facility floor plan.
    zone_adjacency = {
        "compressor-house": ["boiler-room"],
        "boiler-room": ["compressor-house", "tank-farm"],
        "tank-farm": ["boiler-room", "assembly-line"],
        "assembly-line": ["tank-farm", "warehouse"],
        "warehouse": ["assembly-line"],
    }

    return World(
        buildings=buildings,
        zones=zones,
        workers=workers,
        vehicles=vehicles,
        emergency_exits=emergency_exits,
        fire_systems=fire_systems,
        pipelines=pipelines,
        robots=robots,
        emergency_responders=emergency_responders,
        zone_adjacency=zone_adjacency,
    )
