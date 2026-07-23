"""
Demo Mode control surface -- start/pause/resume/stop/replay the scripted
story (app/demo/script.py), fast-forward via speed_multiplier, and poll
status for a live timeline UI.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.auth import auth
from app.demo.player import DemoPlayer

router = APIRouter(prefix="/demo", tags=["demo"])

_READ_ROLES = ("system_admin", "plant_admin", "safety_officer", "maintenance_engineer", "operator", "emergency_team", "government_auditor", "viewer")
_WRITE_ROLES = ("system_admin", "plant_admin", "safety_officer")


class StartRequest(BaseModel):
    speed_multiplier: float = Field(default=1.0, ge=0.1, le=20.0)


class SpeedRequest(BaseModel):
    speed_multiplier: float = Field(ge=0.1, le=20.0)


def _player(request: Request) -> DemoPlayer:
    return request.app.state.demo_player


@router.post("/start", summary="Start the scripted demo story from the beginning")
async def post_start(payload: StartRequest, request: Request, _principal=Depends(auth.require_roles(*_WRITE_ROLES))):
    return _player(request).start(speed_multiplier=payload.speed_multiplier)


@router.post("/pause", summary="Pause between steps (does not interrupt a step already in progress)")
async def post_pause(request: Request, _principal=Depends(auth.require_roles(*_WRITE_ROLES))):
    return _player(request).pause()


@router.post("/resume", summary="Resume a paused demo")
async def post_resume(request: Request, _principal=Depends(auth.require_roles(*_WRITE_ROLES))):
    return _player(request).resume()


@router.post("/stop", summary="Stop the demo run")
async def post_stop(request: Request, _principal=Depends(auth.require_roles(*_WRITE_ROLES))):
    return _player(request).stop()


@router.post("/replay", summary="Stop (if running) and start a fresh run from the beginning")
async def post_replay(request: Request, _principal=Depends(auth.require_roles(*_WRITE_ROLES))):
    return _player(request).replay()


@router.post("/speed", summary="Change the fast-forward speed multiplier of the current or next run")
async def post_speed(payload: SpeedRequest, request: Request, _principal=Depends(auth.require_roles(*_WRITE_ROLES))):
    return _player(request).set_speed(payload.speed_multiplier)


@router.get("/status", summary="Current step, full timeline, and step-by-step results so far")
async def get_status(request: Request, _principal=Depends(auth.require_roles(*_READ_ROLES))):
    return _player(request).status()
