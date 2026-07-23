from datetime import datetime, timedelta, timezone

from app.fusion.scoring import (
    estimate_confidence,
    record_and_estimate_time_to_event,
    reset_history,
    scalar_confidence,
    severity_for_score,
)


def test_severity_bands():
    assert severity_for_score(10) == "low"
    assert severity_for_score(50) == "medium"
    assert severity_for_score(70) == "high"
    assert severity_for_score(90) == "critical"


def test_confidence_high_completeness_and_known_pattern_is_low_epistemic():
    estimate = estimate_confidence(
        posterior=0.88, num_contributions=4, num_admitted_sources=4, num_good_quality=4, precursor_similarity=0.8,
    )
    assert estimate.epistemic_flag == "low"
    assert estimate.graph_relationship_novelty == "known"
    assert estimate.data_completeness == 1.0


def test_confidence_degraded_data_is_elevated_or_high_epistemic():
    estimate = estimate_confidence(
        posterior=0.88, num_contributions=4, num_admitted_sources=4, num_good_quality=1, precursor_similarity=0.8,
    )
    assert estimate.epistemic_flag in ("elevated", "high")


def test_confidence_novel_pattern_flagged():
    estimate = estimate_confidence(
        posterior=0.5, num_contributions=2, num_admitted_sources=2, num_good_quality=2, precursor_similarity=0.1,
    )
    assert estimate.graph_relationship_novelty == "novel"


def test_scalar_confidence_in_valid_range():
    estimate = estimate_confidence(posterior=0.7, num_contributions=3, num_admitted_sources=3, num_good_quality=3, precursor_similarity=0.5)
    value = scalar_confidence(estimate)
    assert 0.0 <= value <= 1.0


def test_time_to_event_none_with_insufficient_history():
    reset_history()
    now = datetime.now(timezone.utc)
    assert record_and_estimate_time_to_event(999, "explosion", now, 0.1) is None
    assert record_and_estimate_time_to_event(999, "explosion", now + timedelta(seconds=5), 0.12) is None


def test_time_to_event_projects_forward_for_rising_trend():
    reset_history()
    now = datetime.now(timezone.utc)
    record_and_estimate_time_to_event(1, "explosion", now, 0.05)
    record_and_estimate_time_to_event(1, "explosion", now + timedelta(seconds=60), 0.15)
    result = record_and_estimate_time_to_event(1, "explosion", now + timedelta(seconds=120), 0.35)
    assert result is not None
    assert result > 0


def test_time_to_event_none_for_flat_trend():
    reset_history()
    now = datetime.now(timezone.utc)
    record_and_estimate_time_to_event(2, "fire", now, 0.2)
    record_and_estimate_time_to_event(2, "fire", now + timedelta(seconds=60), 0.2)
    result = record_and_estimate_time_to_event(2, "fire", now + timedelta(seconds=120), 0.2)
    assert result is None


def test_time_to_event_zero_when_already_past_threshold():
    reset_history()
    now = datetime.now(timezone.utc)
    record_and_estimate_time_to_event(3, "explosion", now, 0.5)
    record_and_estimate_time_to_event(3, "explosion", now + timedelta(seconds=60), 0.8)
    result = record_and_estimate_time_to_event(3, "explosion", now + timedelta(seconds=120), 0.95)
    assert result == 0.0
