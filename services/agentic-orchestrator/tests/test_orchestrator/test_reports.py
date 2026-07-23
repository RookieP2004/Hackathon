from pathlib import Path

from app.orchestrator.reports import generate_incident_report, generate_regulatory_report


def test_generate_incident_report_writes_a_real_pdf():
    path = generate_incident_report(
        incident_id=888001, incident_number="INC-TEST-1", hazard_class="explosion", equipment_tag="V-12",
        zone_id=3, score=88.0, severity="critical", confidence=0.9,
        contributing_factors=[{"source_type": "sensor", "evidence_node_id": "gas", "likelihood_ratio": 40.0, "evidence_refs": ["1"]}],
        recommendations=["Investigate the gas sensor reading immediately."],
        ai_summary="Test AI summary text.",
        timeline_events=[{"event_type": "created", "occurred_at": "2026-07-22T00:00:00Z"}],
    )
    file_bytes = Path(path).read_bytes()
    assert file_bytes.startswith(b"%PDF")  # a genuine PDF file, not a placeholder string
    assert len(file_bytes) > 500

    Path(path).unlink()


def test_generate_regulatory_report_writes_a_real_pdf_with_citations():
    path = generate_regulatory_report(
        incident_id=888002, incident_number="INC-TEST-2", hazard_class="fire", equipment_tag="B-201",
        zone_id=2, score=90.0, severity="critical",
        citations=["OISD-STD-118, Clause 4.3 (Rev. 3, 2021)", "DGMS Circular No. 7/2019"],
        sensor_snapshot={"sensors": [{"tag": "TE-201", "sensor_type": "Temperature", "unit": "celsius", "readings": [{"value": 210.5, "recorded_at": "2026-07-22T00:00:00Z"}]}]},
    )
    file_bytes = Path(path).read_bytes()
    assert file_bytes.startswith(b"%PDF")
    assert len(file_bytes) > 500

    Path(path).unlink()


def test_generate_regulatory_report_handles_no_citations():
    path = generate_regulatory_report(
        incident_id=888003, incident_number="INC-TEST-3", hazard_class="gas_leak", equipment_tag="T-301",
        zone_id=1, score=70.0, severity="high", citations=[], sensor_snapshot={"sensors": []},
    )
    assert Path(path).read_bytes().startswith(b"%PDF")
    Path(path).unlink()
