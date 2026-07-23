from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.auth import auth
from app.agents.fleet import AgentFleet

router = APIRouter(prefix="/agents", tags=["agents"])

_READ_ROLES = ("system_admin", "plant_admin", "safety_officer", "maintenance_engineer", "operator", "emergency_team", "government_auditor", "viewer")


@router.get("/status", summary="Fleet health -- every agent's running/healthy/degraded state")
async def get_fleet_status(request: Request, _principal=Depends(auth.require_roles(*_READ_ROLES))):
    fleet: AgentFleet = request.app.state.fleet
    supervisor = next((a for a in fleet.agents if a.agent_id == "supervisor-agent"), None)
    return {"agents": fleet.status(), "fleet_health_snapshot": getattr(supervisor, "fleet_health", {})}


@router.get("/{agent_id}/decisions", summary="An agent's recent decisions, each with its own logged reasoning")
async def get_agent_decisions(agent_id: str, request: Request, limit: int = Query(20, ge=1, le=200), _principal=Depends(auth.require_roles(*_READ_ROLES))):
    fleet: AgentFleet = request.app.state.fleet
    agent = next((a for a in fleet.agents if a.agent_id == agent_id), None)
    if agent is None:
        raise HTTPException(status_code=404, detail=f"No agent with id '{agent_id}'")
    decisions = await agent.memory.recent_decisions(limit=limit)
    return {
        "agent_id": agent_id,
        "decisions": [
            {
                "id": d.id, "decision": d.decision, "reasoning": d.reasoning, "confidence": d.confidence,
                "evidence_refs": d.evidence_refs, "correlation_id": d.correlation_id, "created_at": d.created_at.isoformat(),
            }
            for d in decisions
        ],
    }


@router.get("/{agent_id}/decisions/{decision_id}/explain", summary="The \"Why?\" affordance -- one decision's own recorded reasoning, verbatim")
async def explain_decision(agent_id: str, decision_id: int, request: Request, _principal=Depends(auth.require_roles(*_READ_ROLES))):
    fleet: AgentFleet = request.app.state.fleet
    agent = next((a for a in fleet.agents if a.agent_id == agent_id), None)
    if agent is None:
        raise HTTPException(status_code=404, detail=f"No agent with id '{agent_id}'")
    reasoning = await agent.memory.explain(decision_id)
    if reasoning is None:
        raise HTTPException(status_code=404, detail=f"No decision {decision_id} found for agent '{agent_id}'")
    return {"agent_id": agent_id, "decision_id": decision_id, "reasoning": reasoning}
