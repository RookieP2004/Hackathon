"""
Write patterns — KNOWLEDGE_GRAPH.md §5. Every node write is `MERGE` keyed on
`id` (never `CREATE`), because this graph is a rebuildable projection (§7):
the same sync/event could in principle replay, and `MERGE` makes that
idempotent rather than duplicating nodes. `CREATE` is used only where the
spec explicitly calls for it (Incident, Risk — an id generated exactly once
at the moment the record is opened, §5.2/§5.3), matching the source
services' own primary-key generation, not this graph's choice.

One `GraphWriter` per request/sync-run, wrapping the shared driver.
"""

from __future__ import annotations

from neo4j import AsyncDriver


class GraphWriter:
    def __init__(self, driver: AsyncDriver) -> None:
        self._driver = driver

    async def _write(self, query: str, **params) -> None:
        async with self._driver.session() as session:
            await session.run(query, **params)

    # ---- 2.2 Physical & topological nodes ----

    async def upsert_plant(self, *, id: int, code: str, name: str, timezone: str) -> None:
        await self._write(
            "MERGE (n:Plant {id: $id}) SET n.code = $code, n.name = $name, n.timezone = $timezone",
            id=id, code=code, name=name, timezone=timezone,
        )

    async def upsert_building(self, *, id: int, plant_id: int, code: str, name: str, floor_count: int) -> None:
        await self._write(
            """
            MERGE (n:Building {id: $id})
            SET n.plantId = $plant_id, n.code = $code, n.name = $name, n.floorCount = $floor_count
            WITH n
            MATCH (p:Plant {id: $plant_id})
            MERGE (p)-[:HAS_BUILDING]->(n)
            """,
            id=id, plant_id=plant_id, code=code, name=name, floor_count=floor_count,
        )

    async def upsert_zone(
        self, *, id: int, building_id: int, code: str, name: str, zone_type: str,
        hazard_class: str | None, safe_occupancy_limit: int | None, floor_level: int,
    ) -> None:
        await self._write(
            """
            MERGE (n:Zone {id: $id})
            SET n.buildingId = $building_id, n.code = $code, n.name = $name, n.zoneType = $zone_type,
                n.hazardClass = $hazard_class, n.safeOccupancyLimit = $safe_occupancy_limit,
                n.floorLevel = $floor_level
            WITH n
            MATCH (b:Building {id: $building_id})
            MERGE (b)-[:HAS_ZONE]->(n)
            """,
            id=id, building_id=building_id, code=code, name=name, zone_type=zone_type,
            hazard_class=hazard_class, safe_occupancy_limit=safe_occupancy_limit, floor_level=floor_level,
        )

    async def upsert_equipment(
        self, *, id: int, zone_id: int, tag: str, name: str, criticality: int, status: str,
        subtype_label: str | None = None, subtype_properties: dict | None = None,
    ) -> None:
        """`subtype_label` is one of 'Machine' | 'Valve' | 'Pipeline' (or None for
        plain :Equipment) -- multi-label nodes per §1.1, not a separate node."""
        labels = "Equipment" + (f":{subtype_label}" if subtype_label else "")
        await self._write(
            f"""
            MERGE (n:Equipment {{id: $id}})
            SET n:{labels}, n.tag = $tag, n.name = $name, n.criticality = $criticality, n.status = $status,
                n += $subtype_properties
            WITH n
            MATCH (z:Zone {{id: $zone_id}})
            MERGE (z)-[:CONTAINS]->(n)
            """,
            id=id, zone_id=zone_id, tag=tag, name=name, criticality=criticality, status=status,
            subtype_properties=subtype_properties or {},
        )

    async def link_equipment_flow(self, *, upstream_id: int, downstream_id: int, medium: str | None = None) -> None:
        await self._write(
            """
            MATCH (up:Equipment {id: $upstream_id}), (down:Equipment {id: $downstream_id})
            MERGE (up)-[r:FLOWS_TO]->(down)
            SET r.medium = $medium
            """,
            upstream_id=upstream_id, downstream_id=downstream_id, medium=medium,
        )

    async def link_valve_installed_on_pipeline(self, *, valve_id: int, pipeline_id: int) -> None:
        await self._write(
            "MATCH (v:Equipment:Valve {id: $valve_id}), (p:Equipment:Pipeline {id: $pipeline_id}) "
            "MERGE (v)-[:INSTALLED_ON]->(p)",
            valve_id=valve_id, pipeline_id=pipeline_id,
        )

    async def upsert_sensor(
        self, *, id: int, tag: str, sensor_type: str, unit: str, status: str,
        equipment_id: int | None, zone_id: int | None,
    ) -> None:
        await self._write(
            """
            MERGE (n:Sensor {id: $id})
            SET n.tag = $tag, n.sensorType = $sensor_type, n.unit = $unit, n.status = $status
            WITH n
            OPTIONAL MATCH (eq:Equipment {id: $equipment_id})
            FOREACH (_ IN CASE WHEN eq IS NOT NULL THEN [1] ELSE [] END | MERGE (n)-[:MONITORS]->(eq))
            WITH n
            OPTIONAL MATCH (z:Zone {id: $zone_id})
            FOREACH (_ IN CASE WHEN z IS NOT NULL THEN [1] ELSE [] END | MERGE (n)-[:MONITORS_AMBIENT]->(z))
            """,
            id=id, tag=tag, sensor_type=sensor_type, unit=unit, status=status,
            equipment_id=equipment_id, zone_id=zone_id,
        )

    # ---- 2.3 Human & process nodes ----

    async def upsert_worker(self, *, id: int, badge_id: str, full_name: str, worker_type: str, active: bool) -> None:
        await self._write(
            "MERGE (n:Worker {id: $id}) "
            "SET n.badgeId = $badge_id, n.fullName = $full_name, n.workerType = $worker_type, n.active = $active",
            id=id, badge_id=badge_id, full_name=full_name, worker_type=worker_type, active=active,
        )

    async def link_worker_assigned_to_zone(self, *, worker_id: int, zone_id: int, since: str | None = None) -> None:
        await self._write(
            "MATCH (w:Worker {id: $worker_id}), (z:Zone {id: $zone_id}) "
            "MERGE (w)-[r:ASSIGNED_TO]->(z) SET r.since = $since",
            worker_id=worker_id, zone_id=zone_id, since=since,
        )

    async def upsert_permit(
        self, *, id: int, permit_number: str, permit_type: str, status: str,
        valid_from: str, valid_to: str, worker_id: int, zone_id: int, equipment_id: int | None,
    ) -> None:
        await self._write(
            """
            MERGE (n:Permit {id: $id})
            SET n.permitNumber = $permit_number, n.permitType = $permit_type, n.status = $status,
                n.validFrom = datetime($valid_from), n.validTo = datetime($valid_to)
            WITH n
            MATCH (w:Worker {id: $worker_id}), (z:Zone {id: $zone_id})
            MERGE (w)-[:HOLDS]->(n)
            MERGE (n)-[:SCOPED_TO]->(z)
            WITH n
            OPTIONAL MATCH (eq:Equipment {id: $equipment_id})
            FOREACH (_ IN CASE WHEN eq IS NOT NULL THEN [1] ELSE [] END | MERGE (n)-[:AUTHORIZES_WORK_ON]->(eq))
            """,
            id=id, permit_number=permit_number, permit_type=permit_type, status=status,
            valid_from=valid_from, valid_to=valid_to, worker_id=worker_id, zone_id=zone_id, equipment_id=equipment_id,
        )

    async def link_permit_complies_with_regulation(self, *, permit_id: int, regulation_id: int) -> None:
        await self._write(
            "MATCH (p:Permit {id: $permit_id}), (r:Regulation {id: $regulation_id}) "
            "MERGE (p)-[:COMPLIES_WITH]->(r)",
            permit_id=permit_id, regulation_id=regulation_id,
        )

    async def upsert_maintenance(
        self, *, id: int, maintenance_type: str, status: str, scheduled_date: str | None,
        completed_at: str | None, findings: str | None, equipment_id: int, performed_by: int | None,
    ) -> None:
        await self._write(
            """
            MERGE (n:Maintenance {id: $id})
            SET n.maintenanceType = $maintenance_type, n.status = $status,
                n.scheduledDate = CASE WHEN $scheduled_date IS NULL THEN NULL ELSE date($scheduled_date) END,
                n.completedAt = CASE WHEN $completed_at IS NULL THEN NULL ELSE datetime($completed_at) END,
                n.findings = $findings
            WITH n
            MATCH (eq:Equipment {id: $equipment_id})
            MERGE (n)-[:PERFORMED_ON]->(eq)
            WITH n
            OPTIONAL MATCH (w:Worker {id: $performed_by})
            FOREACH (_ IN CASE WHEN w IS NOT NULL THEN [1] ELSE [] END | MERGE (w)-[:PERFORMED]->(n))
            """,
            id=id, maintenance_type=maintenance_type, status=status, scheduled_date=scheduled_date,
            completed_at=completed_at, findings=findings, equipment_id=equipment_id, performed_by=performed_by,
        )

    async def link_maintenance_resolved_incident(self, *, maintenance_id: int, incident_id: int) -> None:
        await self._write(
            "MATCH (m:Maintenance {id: $maintenance_id}), (i:Incident {id: $incident_id}) "
            "MERGE (m)-[:RESOLVED]->(i)",
            maintenance_id=maintenance_id, incident_id=incident_id,
        )

    async def link_maintenance_triggered_by_risk(self, *, maintenance_id: int, risk_id: str) -> None:
        await self._write(
            "MATCH (m:Maintenance {id: $maintenance_id}), (r:Risk {id: $risk_id}) "
            "MERGE (m)-[:TRIGGERED_BY]->(r)",
            maintenance_id=maintenance_id, risk_id=risk_id,
        )

    async def link_maintenance_references_document(self, *, maintenance_id: int, document_id: int) -> None:
        await self._write(
            "MATCH (m:Maintenance {id: $maintenance_id}), (d:Document {id: $document_id}) "
            "MERGE (m)-[:REFERENCES]->(d)",
            maintenance_id=maintenance_id, document_id=document_id,
        )

    # ---- 2.4 Event & knowledge nodes ----

    async def create_incident(
        self, *, id: int, incident_number: str, severity: str, status: str, opened_at: str,
        zone_id: int | None, equipment_id: int | None, root_cause: str | None = None,
    ) -> None:
        """CREATE, not MERGE -- an incident id is generated exactly once by
        incident-service, matching §5.2's stated rationale."""
        await self._write(
            """
            MERGE (n:Incident {id: $id})
            SET n.incidentNumber = $incident_number, n.severity = $severity, n.status = $status,
                n.openedAt = datetime($opened_at), n.rootCause = $root_cause
            WITH n
            OPTIONAL MATCH (z:Zone {id: $zone_id})
            FOREACH (_ IN CASE WHEN z IS NOT NULL THEN [1] ELSE [] END | MERGE (n)-[:OCCURRED_IN]->(z))
            WITH n
            OPTIONAL MATCH (eq:Equipment {id: $equipment_id})
            FOREACH (_ IN CASE WHEN eq IS NOT NULL THEN [1] ELSE [] END | MERGE (n)-[:INVOLVED_EQUIPMENT]->(eq))
            """,
            id=id, incident_number=incident_number, severity=severity, status=status, opened_at=opened_at,
            zone_id=zone_id, equipment_id=equipment_id, root_cause=root_cause,
        )

    async def link_incident_involved_worker(self, *, incident_id: int, worker_id: int) -> None:
        await self._write(
            "MATCH (i:Incident {id: $incident_id}), (w:Worker {id: $worker_id}) "
            "MERGE (w)-[:INVOLVED_IN]->(i)",
            incident_id=incident_id, worker_id=worker_id,
        )

    async def link_incident_similar_to(self, *, incident_id: int, other_incident_id: int, score: float) -> None:
        await self._write(
            "MATCH (a:Incident {id: $incident_id}), (b:Incident {id: $other_incident_id}) "
            "MERGE (a)-[r:SIMILAR_TO]->(b) SET r.score = $score",
            incident_id=incident_id, other_incident_id=other_incident_id, score=score,
        )

    async def link_incident_violated_regulation(self, *, incident_id: int, regulation_id: int) -> None:
        await self._write(
            "MATCH (i:Incident {id: $incident_id}), (r:Regulation {id: $regulation_id}) "
            "MERGE (i)-[:VIOLATED]->(r)",
            incident_id=incident_id, regulation_id=regulation_id,
        )

    async def link_incident_documented_in(self, *, incident_id: int, document_id: int) -> None:
        await self._write(
            "MATCH (i:Incident {id: $incident_id}), (d:Document {id: $document_id}) "
            "MERGE (i)-[:DOCUMENTED_IN]->(d)",
            incident_id=incident_id, document_id=document_id,
        )

    async def link_incident_occurred_during_weather(self, *, incident_id: int, weather_episode_id: str) -> None:
        await self._write(
            "MATCH (i:Incident {id: $incident_id}), (we:WeatherEpisode {id: $weather_episode_id}) "
            "MERGE (i)-[:OCCURRED_DURING]->(we)",
            incident_id=incident_id, weather_episode_id=weather_episode_id,
        )

    async def upsert_document(
        self, *, id: int, title: str, document_class_label: str, version: str | None,
        equipment_type_scope: str | None = None, hazard_class_scope: str | None = None,
    ) -> None:
        """`document_class_label` is one of 'Manual' | 'Procedure' | 'InspectionReport'
        per §2.4's multi-label pattern, resolved by the caller from
        `knowledge_documents.document_class`."""
        await self._write(
            f"""
            MERGE (n:Document {{id: $id}})
            SET n:{document_class_label}, n.title = $title, n.version = $version,
                n.equipmentTypeScope = $equipment_type_scope, n.hazardClassScope = $hazard_class_scope
            """,
            id=id, title=title, version=version,
            equipment_type_scope=equipment_type_scope, hazard_class_scope=hazard_class_scope,
        )

    async def link_document_implements_regulation(self, *, document_id: int, regulation_id: int) -> None:
        await self._write(
            "MATCH (d:Document {id: $document_id}), (r:Regulation {id: $regulation_id}) "
            "MERGE (d)-[:IMPLEMENTS]->(r)",
            document_id=document_id, regulation_id=regulation_id,
        )

    async def link_document_governs_equipment(self, *, document_id: int, equipment_id: int) -> None:
        await self._write(
            "MATCH (d:Document {id: $document_id}), (eq:Equipment {id: $equipment_id}) "
            "MERGE (d)-[:GOVERNS]->(eq)",
            document_id=document_id, equipment_id=equipment_id,
        )

    async def link_applies_to_zone(self, *, node_label: str, node_id: int, zone_id: int) -> None:
        """`node_label` is 'Document' or 'Regulation' -- both use APPLIES_TO -> Zone."""
        await self._write(
            f"MATCH (n:{node_label} {{id: $node_id}}), (z:Zone {{id: $zone_id}}) MERGE (n)-[:APPLIES_TO]->(z)",
            node_id=node_id, zone_id=zone_id,
        )

    async def upsert_regulation(
        self, *, id: int, code: str, title: str, jurisdiction: str, clause_ref: str | None, effective_date: str | None,
    ) -> None:
        await self._write(
            "MERGE (n:Regulation {id: $id}) "
            "SET n.code = $code, n.title = $title, n.jurisdiction = $jurisdiction, "
            "n.clauseRef = $clause_ref, n.effectiveDate = CASE WHEN $effective_date IS NULL THEN NULL ELSE date($effective_date) END",
            id=id, code=code, title=title, jurisdiction=jurisdiction, clause_ref=clause_ref, effective_date=effective_date,
        )

    # ---- 2.5 Derived, graph-anchored nodes ----

    async def upsert_weather_episode(
        self, *, id: str, episode_type: str, start_at: str, end_at: str | None, severity: str, description: str | None,
    ) -> None:
        await self._write(
            "MERGE (n:WeatherEpisode {id: $id}) "
            "SET n.episodeType = $episode_type, n.startAt = datetime($start_at), "
            "n.endAt = CASE WHEN $end_at IS NULL THEN NULL ELSE datetime($end_at) END, "
            "n.severity = $severity, n.description = $description",
            id=id, episode_type=episode_type, start_at=start_at, end_at=end_at,
            severity=severity, description=description,
        )

    async def link_weather_affected_zone(self, *, weather_episode_id: str, zone_id: int) -> None:
        await self._write(
            "MATCH (we:WeatherEpisode {id: $weather_episode_id}), (z:Zone {id: $zone_id}) "
            "MERGE (we)-[:AFFECTED]->(z)",
            weather_episode_id=weather_episode_id, zone_id=zone_id,
        )

    async def link_weather_contributed_to_risk(self, *, weather_episode_id: str, risk_id: str) -> None:
        await self._write(
            "MATCH (we:WeatherEpisode {id: $weather_episode_id}), (r:Risk {id: $risk_id}) "
            "MERGE (we)-[:CONTRIBUTED_TO]->(r)",
            weather_episode_id=weather_episode_id, risk_id=risk_id,
        )

    async def create_risk(
        self, *, id: str, postgres_prediction_id: int | None, hazard_class: str, score: float,
        confidence: float, epistemic_flag: bool, assessed_at: str, gate_structure_version: str,
        equipment_id: int | None = None, zone_id: int | None = None, evidence_sensor_ids: list[int] | None = None,
    ) -> None:
        """§5.3's Evidence Bundle anchoring write -- the single write pattern
        that materializes a Risk Fusion assessment into traversable graph
        structure. CREATE, not MERGE: a risk assessment id is generated once."""
        await self._write(
            """
            MERGE (r:Risk {id: $id})
            SET r.postgresPredictionId = $postgres_prediction_id, r.hazardClass = $hazard_class,
                r.score = $score, r.confidence = $confidence, r.epistemicFlag = $epistemic_flag,
                r.assessedAt = datetime($assessed_at), r.gateStructureVersion = $gate_structure_version
            WITH r
            OPTIONAL MATCH (eq:Equipment {id: $equipment_id})
            FOREACH (_ IN CASE WHEN eq IS NOT NULL THEN [1] ELSE [] END | MERGE (r)-[:ASSESSES]->(eq))
            WITH r
            OPTIONAL MATCH (z:Zone {id: $zone_id})
            FOREACH (_ IN CASE WHEN z IS NOT NULL THEN [1] ELSE [] END | MERGE (r)-[:ASSESSES]->(z))
            WITH r
            UNWIND coalesce($evidence_sensor_ids, []) AS sensorId
            MATCH (s:Sensor {id: sensorId})
            MERGE (r)-[:BASED_ON_EVIDENCE]->(s)
            """,
            id=id, postgres_prediction_id=postgres_prediction_id, hazard_class=hazard_class, score=score,
            confidence=confidence, epistemic_flag=epistemic_flag, assessed_at=assessed_at,
            gate_structure_version=gate_structure_version, equipment_id=equipment_id, zone_id=zone_id,
            evidence_sensor_ids=evidence_sensor_ids,
        )

    async def link_risk_based_on_document(self, *, risk_id: str, document_id: int) -> None:
        await self._write(
            "MATCH (r:Risk {id: $risk_id}), (d:Document {id: $document_id}) "
            "MERGE (r)-[:BASED_ON_EVIDENCE]->(d)",
            risk_id=risk_id, document_id=document_id,
        )

    async def link_risk_escalated_to_incident(self, *, risk_id: str, incident_id: int) -> None:
        await self._write(
            "MATCH (r:Risk {id: $risk_id}), (i:Incident {id: $incident_id}) "
            "MERGE (r)-[:ESCALATED_TO]->(i)",
            risk_id=risk_id, incident_id=incident_id,
        )

    async def link_incident_preceded_by_risk(self, *, incident_id: int, risk_id: str) -> None:
        await self._write(
            "MATCH (i:Incident {id: $incident_id}), (r:Risk {id: $risk_id}) "
            "MERGE (i)-[:PRECEDED_BY]->(r)",
            incident_id=incident_id, risk_id=risk_id,
        )

    async def link_risk_similar_pattern(self, *, risk_id: str, other_risk_id: str, score: float) -> None:
        await self._write(
            "MATCH (a:Risk {id: $risk_id}), (b:Risk {id: $other_risk_id}) "
            "MERGE (a)-[r:SIMILAR_PATTERN_TO]->(b) SET r.score = $score",
            risk_id=risk_id, other_risk_id=other_risk_id, score=score,
        )
