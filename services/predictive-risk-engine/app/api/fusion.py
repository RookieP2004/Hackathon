from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.auth import auth
from app.fusion.networks import DEFAULT_PRIOR_ODDS
from app.fusion.pipeline import assess_equipment

router = APIRouter(prefix="/fusion", tags=["risk-fusion"])

_READ_ROLES = ("system_admin", "plant_admin", "safety_officer", "maintenance_engineer", "operator", "emergency_team", "government_auditor", "viewer")
_WRITE_ROLES = ("system_admin", "plant_admin", "safety_officer")


@router.get("/hazards", summary="The five hazard classes this engine reasons over, and their gate structure")
async def get_hazards(_principal=Depends(auth.require_roles(*_READ_ROLES))):
    return {
        "hazard_classes": [
            {"name": "fire", "gate_structure": "noisy-or", "default_prior_odds": DEFAULT_PRIOR_ODDS["fire"]},
            {"name": "explosion", "gate_structure": "noisy-and (fuel-in-range, ignition-source, confinement)", "default_prior_odds": DEFAULT_PRIOR_ODDS["explosion"]},
            {"name": "gas_leak", "gate_structure": "noisy-or", "default_prior_odds": DEFAULT_PRIOR_ODDS["gas_leak"]},
            {"name": "worker_injury", "gate_structure": "multiplicative exposure model", "default_prior_odds": None},
            {"name": "machine_failure", "gate_structure": "noisy-or, temporal-reasoning-dominant", "default_prior_odds": DEFAULT_PRIOR_ODDS["machine_failure"]},
        ],
        "assessment_order": ["gas_leak", "machine_failure", "fire", "explosion", "worker_injury"],
    }


@router.post("/assess/{equipment_id}", summary="Run all five hazard networks for one piece of real equipment")
async def post_assess(equipment_id: int, request: Request, _principal=Depends(auth.require_roles(*_READ_ROLES))):
    settings = request.app.state.settings
    try:
        bundles = await assess_equipment(
            equipment_id=equipment_id, postgres_dsn=_pg_dsn(settings),
            knowledge_graph_url=settings.knowledge_graph_url, computer_vision_url=settings.computer_vision_url,
            token_minter=request.app.state.token_minter, pg_pool=request.app.state.pg_pool,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"equipment_id": equipment_id, "assessments": bundles}


@router.get("/simulator/status", summary="Sensor simulator + fusion loop status")
async def get_simulator_status(request: Request, _principal=Depends(auth.require_roles(*_READ_ROLES))):
    loop = request.app.state.fusion_loop
    simulator = request.app.state.sensor_simulator
    return {"sensors_loaded": len(simulator.states), "ticks_processed": loop.ticks, "last_error": loop.last_error}


class ScenarioInjectionRequest(BaseModel):
    sensor_id: int
    target_value: float
    rate: float = Field(default=0.15, gt=0, le=1)


@router.post("/simulator/scenario", summary="Inject a gradual precursor pattern into a real sensor (demo/testing)")
async def post_inject_scenario(payload: ScenarioInjectionRequest, request: Request, _principal=Depends(auth.require_roles(*_WRITE_ROLES))):
    simulator = request.app.state.sensor_simulator
    if payload.sensor_id not in simulator.states:
        raise HTTPException(status_code=404, detail=f"Sensor {payload.sensor_id} is not loaded in the simulator")
    simulator.inject_precursor_pattern(payload.sensor_id, target=payload.target_value, rate=payload.rate)
    return {"injected": True, "sensor_id": payload.sensor_id, "target_value": payload.target_value}


@router.post("/simulator/reset", summary="Clear all active scenario injections")
async def post_reset_scenario(request: Request, _principal=Depends(auth.require_roles(*_WRITE_ROLES))):
    request.app.state.sensor_simulator.clear_all_injections()
    return {"reset": True}


def _pg_dsn(settings) -> str:
    return settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
