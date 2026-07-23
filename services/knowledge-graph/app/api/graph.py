from __future__ import annotations

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from app.auth import auth
from app.graph.schema import apply_schema
from app.graph.sync import run_full_sync
from app.graph.writes import GraphWriter

router = APIRouter(prefix="/graph", tags=["graph"])

_READ_ROLES = ("system_admin", "plant_admin", "safety_officer", "maintenance_engineer", "operator", "emergency_team", "government_auditor", "viewer")
_WRITE_ROLES = ("system_admin", "plant_admin", "safety_officer")

# The Copilot's read-only Cypher escape hatch (reads.py's run_read_only_cypher)
# must never be allowed to write -- these are the write clauses/procedure
# calls Cypher supports. A bare "CALL" (not just "CALL {") is blocked too:
# Neo4j Community Edition doesn't enforce read-only at the session/driver
# level (that's an Enterprise routing feature), and this container loads
# APOC, so "CALL apoc.merge.node(...)"/"CALL apoc.periodic.iterate(...)"
# contain none of a narrower blocklist's keywords but can still write --
# confirmed as a real, not theoretical, bypass during this audit.
_WRITE_KEYWORDS = ("CREATE", "MERGE", "DELETE", "SET", "REMOVE", "DROP", "CALL", "APOC.", "DB.", "DBMS.")


@router.post("/schema/apply", summary="Idempotently (re)create every constraint/index (KNOWLEDGE_GRAPH.md §4)")
async def post_apply_schema(request: Request, _principal=Depends(auth.require_roles(*_WRITE_ROLES))):
    return await apply_schema(request.app.state.neo4j_driver)


@router.post("/sync", summary="Full pull-based sync from the real Postgres tables (see sync.py's docstring)")
async def post_sync(request: Request, _principal=Depends(auth.require_roles(*_WRITE_ROLES))):
    settings = request.app.state.settings
    writer = GraphWriter(request.app.state.neo4j_driver)
    dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    return await run_full_sync(writer, dsn)


@router.get("/equipment/{tag}/downstream", summary="§6.1 — variable-depth downstream impact traversal")
async def get_downstream_impact(tag: str, request: Request, max_hops: int = Query(6, ge=1, le=15), _principal=Depends(auth.require_roles(*_READ_ROLES))):
    reader = request.app.state.graph_reader
    return {"tag": tag, "downstream": await reader.downstream_impact(tag, max_hops=max_hops)}


@router.get("/equipment/{equipment_id}/risk-context", summary="§6.2 — graph-constrained candidate generation")
async def get_risk_context(equipment_id: int, request: Request, _principal=Depends(auth.require_roles(*_READ_ROLES))):
    reader = request.app.state.graph_reader
    result = await reader.risk_context(equipment_id)
    if result["equipment"] is None:
        raise HTTPException(status_code=404, detail=f"No Equipment node with id {equipment_id}")
    return result


@router.get("/equipment/{equipment_id}/similar-incidents", summary="§6.3 — incident similarity by topological role")
async def get_similar_incidents(equipment_id: int, request: Request, limit: int = Query(10, ge=1, le=50), _principal=Depends(auth.require_roles(*_READ_ROLES))):
    reader = request.app.state.graph_reader
    return {"incidents": await reader.similar_incidents_by_topology(equipment_id, limit=limit)}


@router.get("/equipment/{equipment_id}/permit-conflict", summary="§6.4 — Permit Agent's fail-closed conflict gate")
async def get_permit_conflict(equipment_id: int, request: Request, _principal=Depends(auth.require_roles(*_READ_ROLES))):
    reader = request.app.state.graph_reader
    conflicts = await reader.permit_conflict(equipment_id)
    return {"has_conflict": len(conflicts) > 0, "active_permits": conflicts}


@router.get("/zones/worker-exposure", summary="§6.5 — workers currently in a zone above the risk threshold")
async def get_worker_exposure(request: Request, min_score: float = Query(80, ge=0, le=100), within_minutes: int = Query(10, ge=1), _principal=Depends(auth.require_roles(*_READ_ROLES))):
    reader = request.app.state.graph_reader
    return {"exposed_workers": await reader.worker_exposure(min_score=min_score, within_minutes=within_minutes)}


@router.get("/regulations/{code}/compliance-gaps", summary="§6.6 — multi-hop compliance-gap traversal")
async def get_compliance_gaps(code: str, request: Request, required_interval_days: int = Query(180, ge=1), _principal=Depends(auth.require_roles(*_READ_ROLES))):
    reader = request.app.state.graph_reader
    return {"gaps": await reader.compliance_gaps(code, required_interval_days=required_interval_days)}


@router.get("/risk/{risk_id}/precursor-patterns", summary="§6.7 — precursor-pattern lookup")
async def get_precursor_patterns(risk_id: str, request: Request, _principal=Depends(auth.require_roles(*_READ_ROLES))):
    reader = request.app.state.graph_reader
    return {"patterns": await reader.precursor_pattern_lookup(risk_id)}


class RiskWriteRequest(BaseModel):
    """§5.3's Evidence Bundle anchoring write, exposed as a REST call any
    service can make on behalf of the (future) Risk Fusion Agent — the
    concrete "integrate with AI" hook: whenever a risk assessment is
    computed, it is also anchored into the graph as traversable structure."""

    id: str
    postgres_prediction_id: int | None = None
    hazard_class: str
    score: float = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=1)
    epistemic_flag: bool = False
    assessed_at: str
    gate_structure_version: str
    equipment_id: int | None = None
    zone_id: int | None = None
    evidence_sensor_ids: list[int] = Field(default_factory=list)


@router.post("/risk", status_code=201, summary="§5.3 — anchor a Risk assessment's Evidence Bundle into the graph")
async def post_risk(payload: RiskWriteRequest, request: Request, _principal=Depends(auth.require_roles(*_WRITE_ROLES))):
    writer = GraphWriter(request.app.state.neo4j_driver)
    await writer.create_risk(**payload.model_dump())
    return {"created": payload.id}


class CypherQueryRequest(BaseModel):
    query: str
    params: dict = Field(default_factory=dict)


@router.post(
    "/permits/{permit_id}/sync",
    summary="Incrementally sync one real permit row from Postgres into the graph -- for a single permit "
    "change (create/expire/status update), far cheaper than waiting on a full /graph/sync pull.",
)
async def post_sync_permit(permit_id: int, request: Request, _principal=Depends(auth.require_roles(*_WRITE_ROLES))):
    settings = request.app.state.settings
    dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(dsn)
    try:
        row = await conn.fetchrow(
            "SELECT p.id, p.permit_number, pt.name AS permit_type, p.status, p.valid_from, p.valid_to, "
            "p.worker_id, p.zone_id, p.equipment_id FROM permits p JOIN permit_types pt ON pt.id = p.permit_type_id WHERE p.id = $1",
            permit_id,
        )
    finally:
        await conn.close()
    if row is None:
        raise HTTPException(status_code=404, detail=f"No permit with id {permit_id}")

    writer = GraphWriter(request.app.state.neo4j_driver)
    await writer.upsert_permit(
        id=row["id"], permit_number=row["permit_number"], permit_type=row["permit_type"], status=row["status"],
        valid_from=row["valid_from"].isoformat(), valid_to=row["valid_to"].isoformat(),
        worker_id=row["worker_id"], zone_id=row["zone_id"], equipment_id=row["equipment_id"],
    )
    return {"synced_permit_id": permit_id}


@router.post("/cypher/query", summary="Read-only Cypher execution — the Copilot's graph-query tool")
async def post_cypher_query(payload: CypherQueryRequest, request: Request, _principal=Depends(auth.require_roles(*_READ_ROLES))):
    normalized = payload.query.upper()
    if any(keyword in normalized for keyword in _WRITE_KEYWORDS):
        raise HTTPException(status_code=422, detail="Only read-only Cypher is permitted through this endpoint")
    reader = request.app.state.graph_reader
    return {"results": await reader.run_read_only_cypher(payload.query, payload.params)}
