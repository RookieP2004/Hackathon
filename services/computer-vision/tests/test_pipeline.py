from unittest.mock import AsyncMock

import pytest

from app.config import Settings
from app.vision.pipeline import VisionPipeline


def _zone(zone_id="compressor-house", camera_id="CAM-01", event_type="normal", confidence=0.95,
          person_count=0, gas_pct_lel=2.0, smoke_pct=1.0, equipment=None):
    return {
        "zone_id": zone_id,
        "camera": {"camera_id": camera_id, "event_type": event_type, "confidence": confidence, "person_count": person_count},
        "ambient": {"gas_pct_lel": gas_pct_lel, "smoke_pct_obscuration": smoke_pct},
        "equipment": equipment or [],
    }


def _snapshot(**zone_kwargs):
    return {"zones": [_zone(**zone_kwargs)], "workers": [], "vehicles": []}


@pytest.fixture
def downstream():
    mock = AsyncMock()
    mock.raise_alert = AsyncMock(return_value={"id": 1})
    mock.submit_risk_score = AsyncMock(return_value={"id": 1})
    return mock


@pytest.fixture
def pipeline(downstream):
    return VisionPipeline(Settings(), downstream, required_consecutive=3)


async def test_single_tick_does_not_dispatch_anything(pipeline, downstream):
    events = await pipeline.process_tick(_snapshot(event_type="fire_detected"))
    assert events == []
    downstream.raise_alert.assert_not_called()
    downstream.submit_risk_score.assert_not_called()


async def test_three_consecutive_ticks_dispatch_exactly_once(pipeline, downstream):
    snapshot = _snapshot(event_type="fire_detected", confidence=0.99)

    await pipeline.process_tick(snapshot)
    await pipeline.process_tick(snapshot)
    events = await pipeline.process_tick(snapshot)

    assert len(events) == 1
    assert events[0].detection.detection_class.value == "fire"
    downstream.raise_alert.assert_awaited_once()
    downstream.submit_risk_score.assert_awaited_once()


async def test_sustained_detection_does_not_redispatch_every_tick(pipeline, downstream):
    snapshot = _snapshot(event_type="fire_detected", confidence=0.99)
    for _ in range(6):
        await pipeline.process_tick(snapshot)

    downstream.raise_alert.assert_awaited_once()
    downstream.submit_risk_score.assert_awaited_once()
    assert len(pipeline.live_detections()) == 1


async def test_detection_clearing_removes_it_from_live_view(pipeline, downstream):
    fire_snapshot = _snapshot(event_type="fire_detected", confidence=0.99)
    normal_snapshot = _snapshot(event_type="normal")

    for _ in range(3):
        await pipeline.process_tick(fire_snapshot)
    assert len(pipeline.live_detections()) == 1

    await pipeline.process_tick(normal_snapshot)
    assert pipeline.live_detections() == []


async def test_worker_detection_never_dispatches_downstream(pipeline, downstream):
    snapshot = _snapshot(person_count=1)
    for _ in range(3):
        await pipeline.process_tick(snapshot)

    downstream.raise_alert.assert_not_called()
    downstream.submit_risk_score.assert_not_called()
    assert len(pipeline.live_detections()) == 1  # still visible in the live view


async def test_non_fast_path_class_gets_risk_score_but_no_alert(pipeline, downstream):
    snapshot = _snapshot(person_count=5)  # >= CROWD_SIZE_THRESHOLD, not in FAST_PATH_CLASSES
    for _ in range(3):
        await pipeline.process_tick(snapshot)

    downstream.raise_alert.assert_not_called()
    assert downstream.submit_risk_score.await_count == 1  # crowd is risk-scored, worker (also present) is excluded


async def test_ticks_processed_counter_increments():
    downstream = AsyncMock()
    pipeline = VisionPipeline(Settings(), downstream, required_consecutive=3)
    await pipeline.process_tick(_snapshot())
    await pipeline.process_tick(_snapshot())
    assert pipeline.ticks_processed == 2
