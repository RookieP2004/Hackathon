"""
Builds a small, fully-isolated (`test-` prefixed) graph and exercises every
KNOWLEDGE_GRAPH.md §6 read/traversal query against it, running for real
against the live Neo4j instance -- not mocked.
"""

from datetime import datetime, timedelta, timezone

import pytest


@pytest.fixture
async def small_graph(writer):
    now = datetime.now(timezone.utc)
    await writer.upsert_plant(id="test-plant-1", code="TEST-PLANT", name="Test Plant", timezone="Asia/Kolkata")
    await writer.upsert_building(id="test-bldg-1", plant_id="test-plant-1", code="TB1", name="Test Building", floor_count=1)
    await writer.upsert_zone(
        id="test-zone-1", building_id="test-bldg-1", code="TZ1", name="Test Zone", zone_type="process",
        hazard_class="H1", safe_occupancy_limit=5, floor_level=1,
    )
    await writer.upsert_equipment(
        id="test-eq-1", zone_id="test-zone-1", tag="TEST-EQ-1", name="Upstream Valve", criticality=3,
        status="operational", subtype_label="Valve", subtype_properties={"valveType": "gate"},
    )
    await writer.upsert_equipment(
        id="test-eq-2", zone_id="test-zone-1", tag="TEST-EQ-2", name="Downstream Pump", criticality=4,
        status="operational", subtype_label="Machine", subtype_properties={"machineClass": "pump"},
    )
    await writer.link_equipment_flow(upstream_id="test-eq-1", downstream_id="test-eq-2", medium="process_fluid")

    await writer.upsert_sensor(
        id="test-sensor-1", tag="TEST-SENSOR-1", sensor_type="Pressure", unit="bar", status="active",
        equipment_id="test-eq-1", zone_id=None,
    )

    await writer.upsert_worker(id="test-worker-1", badge_id="TEST-BADGE-1", full_name="Test Worker", worker_type="employee", active=True)
    await writer.link_worker_assigned_to_zone(worker_id="test-worker-1", zone_id="test-zone-1")

    await writer.upsert_permit(
        id="test-permit-1", permit_number="TEST-PERMIT-1", permit_type="hot_work", status="active",
        valid_from=(now - timedelta(hours=1)).isoformat(), valid_to=(now + timedelta(hours=1)).isoformat(),
        worker_id="test-worker-1", zone_id="test-zone-1", equipment_id="test-eq-1",
    )

    await writer.create_incident(
        id="test-incident-1", incident_number="TEST-INC-1", severity="high", status="open",
        opened_at=now.isoformat(), zone_id="test-zone-1", equipment_id="test-eq-1", root_cause="test root cause",
    )

    await writer.create_risk(
        id="test-risk-1", postgres_prediction_id=None, hazard_class="test_hazard", score=91.0, confidence=0.9,
        epistemic_flag=False, assessed_at=now.isoformat(), gate_structure_version="test-v1",
        equipment_id="test-eq-1", evidence_sensor_ids=["test-sensor-1"],
    )
    await writer.link_risk_escalated_to_incident(risk_id="test-risk-1", incident_id="test-incident-1")

    return now


async def test_downstream_impact(reader, small_graph):
    result = await reader.downstream_impact("TEST-EQ-1")
    assert len(result) == 1
    assert result[0]["tag"] == "TEST-EQ-2"
    assert result[0]["hopsAway"] == 1


async def test_risk_context(reader, small_graph):
    ctx = await reader.risk_context("test-eq-1")
    assert ctx["equipment"]["tag"] == "TEST-EQ-1"
    neighbor_tags = {n["tag"] for n in ctx["graph_neighborhood"]}
    assert "TEST-EQ-2" in neighbor_tags
    sensor_tags = {s["tag"] for s in ctx["admitted_sensors"]}
    assert "TEST-SENSOR-1" in sensor_tags
    permit_numbers = {p["permitNumber"] for p in ctx["active_permits"]}
    assert "TEST-PERMIT-1" in permit_numbers
    incident_numbers = {i["incidentNumber"] for i in ctx["historical_incidents"]}
    assert "TEST-INC-1" in incident_numbers


async def test_permit_conflict_detects_active_permit(reader, small_graph):
    conflicts = await reader.permit_conflict("test-eq-1")
    assert len(conflicts) == 1
    assert conflicts[0]["permitNumber"] == "TEST-PERMIT-1"


async def test_permit_conflict_empty_for_unpermitted_equipment(reader, small_graph):
    conflicts = await reader.permit_conflict("test-eq-2")
    assert conflicts == []


async def test_worker_exposure_flags_assigned_worker_in_high_risk_zone(reader, writer, small_graph):
    # risk_context/create_risk above assessed the equipment, not the zone -- worker_exposure
    # needs a Risk that ASSESSES the Zone directly, so create one for this specific traversal.
    now = small_graph
    await writer.create_risk(
        id="test-risk-zone-1", postgres_prediction_id=None, hazard_class="test_hazard", score=95.0,
        confidence=0.9, epistemic_flag=False, assessed_at=now.isoformat(), gate_structure_version="test-v1",
        zone_id="test-zone-1",
    )
    exposed = await reader.worker_exposure(min_score=80, within_minutes=10)
    badge_ids = {w["badgeId"] for w in exposed}
    assert "TEST-BADGE-1" in badge_ids


async def test_precursor_pattern_lookup(reader, writer, small_graph):
    await writer.create_risk(
        id="test-risk-2", postgres_prediction_id=None, hazard_class="test_hazard_2", score=70.0,
        confidence=0.7, epistemic_flag=False, assessed_at=small_graph.isoformat(), gate_structure_version="test-v1",
        equipment_id="test-eq-2",
    )
    await writer.link_risk_similar_pattern(risk_id="test-risk-2", other_risk_id="test-risk-1", score=0.87)

    patterns = await reader.precursor_pattern_lookup("test-risk-2")
    assert len(patterns) == 1
    assert patterns[0]["hazardClass"] == "test_hazard"
    assert patterns[0]["incidentNumber"] == "TEST-INC-1"


async def test_similar_incidents_by_topological_role(reader, small_graph):
    # test-eq-2 (target) and test-eq-1 (candidate) share a zone hazardClass and both
    # have FLOWS_TO degree 1 (connected only to each other); test-eq-1 carries the
    # incident from small_graph's setup, so it should surface as a topological match.
    results = await reader.similar_incidents_by_topology("test-eq-2")
    tags = {r["equipmentTag"] for r in results}
    assert "TEST-EQ-1" in tags


async def test_compliance_gaps_flags_equipment_with_no_maintenance(reader, writer, small_graph):
    await writer.upsert_regulation(
        id="test-reg-1", code="TEST-REG-1", title="Test Regulation", jurisdiction="India",
        clause_ref="1.1", effective_date=None,
    )
    await writer.upsert_document(id="test-doc-1", title="Test Manual", document_class_label="Manual", version="1")
    await writer.link_document_implements_regulation(document_id="test-doc-1", regulation_id="test-reg-1")
    await writer.link_document_governs_equipment(document_id="test-doc-1", equipment_id="test-eq-1")

    gaps = await reader.compliance_gaps("TEST-REG-1", required_interval_days=1)
    tags = {g["equipmentTag"] for g in gaps}
    assert "TEST-EQ-1" in tags  # never serviced -> always a gap
