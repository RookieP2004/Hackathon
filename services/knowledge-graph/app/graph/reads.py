"""
Read & traversal patterns — KNOWLEDGE_GRAPH.md §6, "the queries that justify
§0's entire argument." Each function returns plain JSON-serializable dicts
(never raw neo4j.Node/Record objects) so the API layer can return them
directly and so callers outside this service (Risk Fusion Engine, Copilot)
never need a Neo4j-specific type on their side.
"""

from __future__ import annotations

from neo4j import AsyncDriver


def _node_to_dict(node) -> dict:
    return dict(node) | {"_labels": list(node.labels)}


class GraphReader:
    def __init__(self, driver: AsyncDriver) -> None:
        self._driver = driver

    async def _run(self, query: str, **params) -> list:
        async with self._driver.session() as session:
            result = await session.run(query, **params)
            return [record async for record in result]

    # ---- 6.1 Variable-depth downstream impact ----

    async def downstream_impact(self, equipment_tag: str, max_hops: int = 6) -> list[dict]:
        records = await self._run(
            f"""
            MATCH path = (v:Equipment {{tag: $tag}})-[:FLOWS_TO*1..{int(max_hops)}]->(downstream)
            RETURN downstream.tag AS tag, downstream.name AS name, length(path) AS hopsAway
            ORDER BY hopsAway
            """,
            tag=equipment_tag,
        )
        return [dict(r) for r in records]

    # ---- 6.2 Graph-constrained candidate generation (highest-frequency query) ----

    async def risk_context(self, equipment_id: int) -> dict:
        records = await self._run(
            """
            MATCH (eq:Equipment {id: $equipment_id})
            OPTIONAL MATCH (eq)-[:FLOWS_TO|INSTALLED_ON*1..2]-(neighbor:Equipment)
            OPTIONAL MATCH (s:Sensor)-[:MONITORS]->(eq)
            OPTIONAL MATCH (s2:Sensor)-[:MONITORS]->(neighbor)
            OPTIONAL MATCH (eq)<-[:CONTAINS]-(z:Zone)<-[:SCOPED_TO]-(p:Permit {status: 'active'})
            OPTIONAL MATCH (eq)<-[:INVOLVED_EQUIPMENT]-(pastIncident:Incident)
            RETURN eq,
                   collect(DISTINCT neighbor) AS graphNeighborhood,
                   collect(DISTINCT s) + collect(DISTINCT s2) AS admittedSensors,
                   collect(DISTINCT p) AS activePermits,
                   collect(DISTINCT pastIncident) AS historicalIncidents
            """,
            equipment_id=equipment_id,
        )
        if not records:
            return {
                "equipment": None, "graph_neighborhood": [], "admitted_sensors": [],
                "active_permits": [], "historical_incidents": [],
            }
        r = records[0]
        return {
            "equipment": _node_to_dict(r["eq"]) if r["eq"] else None,
            "graph_neighborhood": [_node_to_dict(n) for n in r["graphNeighborhood"] if n is not None],
            "admitted_sensors": [_node_to_dict(n) for n in r["admittedSensors"] if n is not None],
            "active_permits": [_node_to_dict(n) for n in r["activePermits"] if n is not None],
            "historical_incidents": [_node_to_dict(n) for n in r["historicalIncidents"] if n is not None],
        }

    # ---- 6.3 Incident similarity by topological role ----

    async def similar_incidents_by_topology(self, equipment_id: int, limit: int = 10) -> list[dict]:
        records = await self._run(
            """
            MATCH (target:Equipment {id: $equipment_id})<-[:CONTAINS]-(z:Zone)
            MATCH (target)-[:FLOWS_TO]-(targetNeighbor)
            WITH target, z, count(DISTINCT targetNeighbor) AS targetDegree
            MATCH (candidate:Equipment)<-[:CONTAINS]-(z2:Zone {hazardClass: z.hazardClass})
            WHERE candidate <> target
            MATCH (candidate)-[:FLOWS_TO]-(candidateNeighbor)
            WITH target, candidate, targetDegree, count(DISTINCT candidateNeighbor) AS candidateDegree
            WHERE abs(targetDegree - candidateDegree) <= 1
            MATCH (candidate)<-[:INVOLVED_EQUIPMENT]-(i:Incident)
            RETURN candidate.tag AS equipmentTag, i.incidentNumber AS incidentNumber,
                   i.severity AS severity, i.rootCause AS rootCause
            ORDER BY i.openedAt DESC
            LIMIT $limit
            """,
            equipment_id=equipment_id, limit=limit,
        )
        return [dict(r) for r in records]

    # ---- 6.4 Permit conflict check (Permit Agent's fail-closed gate) ----

    async def permit_conflict(self, equipment_id: int) -> list[dict]:
        records = await self._run(
            """
            MATCH (eq:Equipment {id: $equipment_id})<-[:AUTHORIZES_WORK_ON]-(p:Permit)
            WHERE p.status = 'active' AND p.validFrom <= datetime() <= p.validTo
            RETURN p.permitNumber AS permitNumber, p.permitType AS permitType, p.conditions AS conditions
            """,
            equipment_id=equipment_id,
        )
        return [dict(r) for r in records]

    # ---- 6.5 Worker exposure query ----

    async def worker_exposure(self, min_score: float = 80, within_minutes: int = 10) -> list[dict]:
        records = await self._run(
            """
            MATCH (w:Worker)-[:ASSIGNED_TO]->(z:Zone)<-[:ASSESSES]-(r:Risk)
            WHERE r.score >= $min_score AND r.assessedAt > datetime() - duration({minutes: $within_minutes})
            RETURN w.fullName AS workerName, w.badgeId AS badgeId, z.name AS zoneName,
                   r.hazardClass AS hazardClass, r.score AS score
            """,
            min_score=min_score, within_minutes=within_minutes,
        )
        return [dict(r) for r in records]

    # ---- 6.6 Compliance traversal ----

    async def compliance_gaps(self, regulation_code: str, required_interval_days: int) -> list[dict]:
        records = await self._run(
            """
            MATCH (reg:Regulation {code: $regulation_code})<-[:IMPLEMENTS]-(doc:Document)-[:GOVERNS]->(eq:Equipment)
            OPTIONAL MATCH (eq)<-[:PERFORMED_ON]-(m:Maintenance)
            WITH eq, reg, max(m.completedAt) AS lastServiced
            WHERE lastServiced IS NULL OR lastServiced < datetime() - duration({days: $required_interval_days})
            RETURN eq.tag AS equipmentTag, eq.name AS equipmentName, lastServiced AS lastServiced,
                   reg.code AS violatedRegulation
            """,
            regulation_code=regulation_code, required_interval_days=required_interval_days,
        )
        return [dict(r) for r in records]

    # ---- 6.7 Precursor-pattern lookup ----

    async def precursor_pattern_lookup(self, risk_id: str) -> list[dict]:
        records = await self._run(
            """
            MATCH (r:Risk {id: $risk_id})-[:SIMILAR_PATTERN_TO]->(pastRisk:Risk)
            OPTIONAL MATCH (pastRisk)-[:ESCALATED_TO]->(i:Incident)
            RETURN pastRisk.hazardClass AS hazardClass, pastRisk.score AS score,
                   pastRisk.assessedAt AS assessedAt, i.incidentNumber AS incidentNumber,
                   i.severity AS severity, i.rootCause AS rootCause
            ORDER BY pastRisk.assessedAt DESC
            """,
            risk_id=risk_id,
        )
        return [dict(r) for r in records]

    # ---- General-purpose, read-only Cypher execution (Copilot's graph-query tool) ----

    async def run_read_only_cypher(self, query: str, params: dict | None = None) -> list[dict]:
        """A deliberately narrow escape hatch for the future AI Copilot: only
        read queries are permitted (enforced by the router, not here -- see
        app/api/graph.py's keyword check), since an LLM-constructed Cypher
        string must never be allowed to write."""
        records = await self._run(query, **(params or {}))
        return [dict(r) for r in records]
