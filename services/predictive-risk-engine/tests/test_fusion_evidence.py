from datetime import datetime, timedelta, timezone

from app.fusion.evidence import build_equipment_health_evidence_node, build_sensor_evidence_node, normalize_against_baseline


def test_normalize_returns_midpoint_with_insufficient_history():
    assert normalize_against_baseline(50.0, [1.0, 2.0]) == 0.5


def test_normalize_above_baseline_reads_above_midpoint():
    history = [10.0, 10.5, 9.5, 10.0, 9.8, 10.2]
    normalized = normalize_against_baseline(30.0, history)
    assert normalized > 0.5


def test_normalize_at_baseline_reads_near_midpoint():
    history = [10.0, 10.5, 9.5, 10.0, 9.8, 10.2]
    normalized = normalize_against_baseline(10.0, history)
    assert 0.4 < normalized < 0.6


def test_build_sensor_evidence_node_missing_history():
    node = build_sensor_evidence_node(1, "GS-14", "ppm", [])
    assert node.quality_flag == "missing"
    assert node.normalized_value == 0.5
    assert node.raw_value is None


def test_build_sensor_evidence_node_with_history():
    # Anchored to "now" (not a fixed historical date) -- the latest reading
    # must be recent, or build_sensor_evidence_node's own staleness check
    # (a sensor that stopped transmitting a long time ago is excluded as
    # "missing", not trusted as a current value) correctly downgrades it,
    # which would defeat this test's actual purpose of exercising the
    # spike-normalization path, not the staleness path.
    base = datetime.now(timezone.utc) - timedelta(seconds=100)
    history = [(200.0 + i, base + timedelta(seconds=i * 10), "good") for i in range(10)]
    history.append((5000.0, base + timedelta(seconds=100), "good"))
    node = build_sensor_evidence_node(1, "GS-14", "ppm", history)
    assert node.raw_value == 5000.0
    assert node.normalized_value > 0.9  # a huge spike above a tight baseline
    assert node.quality_flag == "good"


def test_build_sensor_evidence_node_stuck_reading_excluded_as_missing():
    """A frozen sensor repeating the identical value has zero variance --
    its z-score would read as "right at baseline" forever without this
    explicit check, exactly the bug this fix addresses."""
    now = datetime.now(timezone.utc)
    history = [(200.0, now - timedelta(seconds=(10 - i) * 5), "good") for i in range(10)]
    node = build_sensor_evidence_node(1, "GS-14", "ppm", history)
    assert node.quality_flag == "missing"
    assert node.normalized_value == 0.5
    assert node.metadata["fault"] == "stuck_reading"


def test_build_sensor_evidence_node_stale_reading_excluded_as_missing():
    """A sensor that stopped transmitting still has a real 'latest' row --
    nothing else in this pipeline compares its age against 'now'."""
    stale_time = datetime.now(timezone.utc) - timedelta(minutes=10)
    history = [(200.0 + i, stale_time - timedelta(seconds=(10 - i) * 5), "good") for i in range(10)]
    node = build_sensor_evidence_node(1, "GS-14", "ppm", history)
    assert node.quality_flag == "missing"
    assert node.metadata["fault"] == "stale_reading"


def test_equipment_health_operational_is_low_severity():
    node = build_equipment_health_evidence_node("V-12", "operational", criticality=5)
    assert node.normalized_value < 0.3


def test_equipment_health_offline_is_high_severity():
    node = build_equipment_health_evidence_node("V-12", "offline", criticality=5)
    assert node.normalized_value > 0.7


def test_equipment_health_criticality_scales_severity():
    low_crit = build_equipment_health_evidence_node("EQ-A", "degraded", criticality=1)
    high_crit = build_equipment_health_evidence_node("EQ-B", "degraded", criticality=5)
    assert high_crit.normalized_value > low_crit.normalized_value
