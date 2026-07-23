from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from aegis_api_common import NotFoundError
from app.auth import auth
from app.control.schemas import ModeRequest, ResetRequest, ScenarioRequest
from app.core.logging import get_logger
from app.domain.engine import SimulationEngine
from app.domain.scenarios import SCENARIO_TYPES
from app.domain.sensor_types import Severity

router = APIRouter(tags=["control"])
logger = get_logger("iot-simulator.control")

_READ_ROLES = ("system_admin", "plant_admin", "safety_officer", "maintenance_engineer", "operator", "emergency_team", "government_auditor", "viewer")
_WRITE_ROLES = ("system_admin", "plant_admin", "safety_officer", "operator")


def _engine(request: Request) -> SimulationEngine:
    return request.app.state.engine


@router.get("/world", summary="Static factory topology (buildings, zones, equipment, workers, vehicles, exits, fire systems, pipelines)")
async def get_world(request: Request, _principal=Depends(auth.require_roles(*_READ_ROLES))) -> dict:
    engine = _engine(request)
    return {
        "buildings": [
            {"building_id": b.building_id, "name": b.name} for b in engine.world.buildings
        ],
        "zones": [
            {
                "zone_id": z.zone_id,
                "name": z.name,
                "building_id": z.building_id,
                "camera_id": z.camera_id,
                "equipment": [
                    {"equipment_id": e.equipment_id, "tag": e.tag, "name": e.name, "machine_class": e.machine_class}
                    for e in z.equipment
                ],
            }
            for z in engine.world.zones
        ],
        "workers": [
            {"worker_id": w.worker_id, "name": w.name, "badge_id": w.badge_id, "zone_id": w.zone_id}
            for w in engine.world.workers
        ],
        "vehicles": [
            {"vehicle_id": v.vehicle_id, "name": v.name, "vehicle_type": v.vehicle_type, "zone_id": v.zone_id}
            for v in engine.world.vehicles
        ],
        "emergency_exits": [
            {"exit_id": ex.exit_id, "name": ex.name, "zone_id": ex.zone_id} for ex in engine.world.emergency_exits
        ],
        "fire_systems": [
            {"fire_system_id": fs.fire_system_id, "name": fs.name, "zone_id": fs.zone_id, "system_type": fs.system_type}
            for fs in engine.world.fire_systems
        ],
        "pipelines": [
            {
                "pipeline_id": p.pipeline_id,
                "name": p.name,
                "kind": p.kind,
                "from_equipment_id": p.from_equipment_id,
                "to_equipment_id": p.to_equipment_id,
            }
            for p in engine.world.pipelines
        ],
        "robots": [
            {
                "robot_id": r.robot_id,
                "name": r.name,
                "robot_type": r.robot_type,
                "zone_id": r.zone_id,
                "equipment_id": r.equipment_id,
            }
            for r in engine.world.robots
        ],
        "emergency_responders": [
            {"responder_id": r.responder_id, "name": r.name, "home_zone_id": r.home_zone_id}
            for r in engine.world.emergency_responders
        ],
        "zone_adjacency": engine.world.zone_adjacency,
        "scenario_types": list(SCENARIO_TYPES),
    }


@router.get("/status", summary="Current mode, active scenarios, and connected client count")
async def get_status(request: Request, _principal=Depends(auth.require_roles(*_READ_ROLES))) -> dict:
    engine = _engine(request)
    snapshot = engine.snapshot()
    return {
        "tick": snapshot["tick"],
        "global_mode": snapshot["global_mode"],
        "zone_modes": {zid: sev.value for zid, sev in engine.zone_modes.items()},
        "active_scenarios": snapshot["active_scenarios"],
        "connected_clients": request.app.state.manager.connection_count,
    }


@router.post("/control/mode", summary="Set Normal/Warning/Critical mode, globally or for one zone")
async def set_mode(payload: ModeRequest, request: Request, _principal=Depends(auth.require_roles(*_WRITE_ROLES))) -> dict:
    engine = _engine(request)
    if payload.zone_id is not None:
        _require_zone(engine, payload.zone_id)
    engine.set_mode(Severity(payload.mode), payload.zone_id)
    logger.info("mode_set", mode=payload.mode, zone_id=payload.zone_id)
    return {"global_mode": engine.global_mode.value, "zone_modes": {k: v.value for k, v in engine.zone_modes.items()}}


@router.post("/control/scenario", summary="Trigger an emergency scenario")
async def trigger_scenario(payload: ScenarioRequest, request: Request, _principal=Depends(auth.require_roles(*_WRITE_ROLES))) -> dict:
    engine = _engine(request)

    zone_id = payload.zone_id
    if payload.equipment_id is not None:
        zone, _ = _require_equipment(engine, payload.equipment_id)
        zone_id = zone_id or zone.zone_id
    if payload.worker_id is not None:
        worker = _require_worker(engine, payload.worker_id)
        zone_id = zone_id or worker.zone_id
    _require_zone(engine, zone_id)

    sc = engine.trigger_scenario(
        payload.scenario, zone_id=zone_id, equipment_id=payload.equipment_id, worker_id=payload.worker_id
    )
    logger.info(
        "scenario_triggered", scenario=payload.scenario, zone_id=zone_id,
        equipment_id=payload.equipment_id, worker_id=payload.worker_id,
    )
    return {"scenario_type": sc.scenario_type, "zone_id": sc.zone_id, "phase": sc.phase}


@router.post("/control/reset", summary="Clear active scenarios and return to Normal mode")
async def reset(payload: ResetRequest, request: Request, _principal=Depends(auth.require_roles(*_WRITE_ROLES))) -> dict:
    engine = _engine(request)
    if payload.zone_id is not None:
        _require_zone(engine, payload.zone_id)
    engine.reset(payload.zone_id)
    logger.info("simulation_reset", zone_id=payload.zone_id)
    return {"reset": True, "zone_id": payload.zone_id}


def _require_zone(engine: SimulationEngine, zone_id: str) -> None:
    try:
        engine.world.zone_by_id(zone_id)
    except KeyError as exc:
        raise NotFoundError(f"Zone '{zone_id}' not found") from exc


def _require_equipment(engine: SimulationEngine, equipment_id: str):
    try:
        return engine.world.equipment_by_id(equipment_id)
    except KeyError as exc:
        raise NotFoundError(f"Equipment '{equipment_id}' not found") from exc


def _require_worker(engine: SimulationEngine, worker_id: str):
    try:
        return engine.world.worker_by_id(worker_id)
    except KeyError as exc:
        raise NotFoundError(f"Worker '{worker_id}' not found") from exc
