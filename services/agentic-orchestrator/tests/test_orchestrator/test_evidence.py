import json
from pathlib import Path

from app.orchestrator.evidence import capture_sensor_data, store_evidence_bundle

POSTGRES_DSN = "postgresql://aegis:changeme_local_only@localhost:5432/aegis"
V12_EQUIPMENT_ID = 2  # real seeded equipment with real sensors (GS-14, PT-22, TE-201, AC-241, FL-281)


async def test_capture_sensor_data_returns_real_sensors_for_equipment():
    snapshot = capture_sensor_data
    result = await snapshot(POSTGRES_DSN, V12_EQUIPMENT_ID)
    assert result["equipment_id"] == V12_EQUIPMENT_ID
    tags = {s["tag"] for s in result["sensors"]}
    assert "GS-14" in tags
    assert "PT-22" in tags


async def test_capture_sensor_data_handles_none_equipment():
    result = await capture_sensor_data(POSTGRES_DSN, None)
    assert result["equipment_id"] is None
    assert result["sensors"] == []


async def test_store_evidence_bundle_writes_a_real_retrievable_file():
    sensor_snapshot = await capture_sensor_data(POSTGRES_DSN, V12_EQUIPMENT_ID)
    evidence_bundle = {"hazard_class": "explosion", "score": 88.0, "contributing_factors": [{"evidence_node_id": "gas", "source_type": "sensor", "likelihood_ratio": 40.0, "evidence_refs": ["1"]}]}

    file_path = store_evidence_bundle(999999, evidence_bundle, sensor_snapshot)

    assert Path(file_path).exists()
    content = json.loads(Path(file_path).read_text(encoding="utf-8"))
    assert content["incident_id"] == 999999
    assert content["evidence_bundle"]["hazard_class"] == "explosion"
    assert content["sensor_snapshot"]["equipment_id"] == V12_EQUIPMENT_ID

    Path(file_path).unlink()
