from datetime import datetime, timedelta, timezone

from app.fusion.temporal import (
    compute_persistence,
    compute_rate_of_change,
    compute_temporal_features,
    dtw_distance,
    lead_lag_cross_correlation,
    normalize_series,
    precursor_similarity,
)


def _series(values: list[float], interval_seconds: float = 30.0) -> list[tuple[float, datetime, str]]:
    base = datetime(2026, 7, 22, 12, 0, 0, tzinfo=timezone.utc)
    return [(v, base + timedelta(seconds=i * interval_seconds), "good") for i, v in enumerate(values)]


def test_rate_of_change_positive_for_rising_series():
    history = _series([2.0, 4.0, 6.0, 8.0, 18.0], interval_seconds=30)
    rate = compute_rate_of_change(history)
    assert rate > 0


def test_rate_of_change_zero_for_flat_series():
    history = _series([5.0, 5.0, 5.0, 5.0])
    assert compute_rate_of_change(history) == 0.0


def test_persistence_counts_consecutive_sustained_deviation():
    # Stable baseline around 2, then a sustained climb in the last several ticks.
    history = _series([2.0, 2.1, 1.9, 2.0, 8.0, 9.0, 10.0])
    persistence = compute_persistence(history)
    assert persistence >= 3


def test_persistence_low_for_a_single_spike_that_returns():
    history = _series([2.0, 2.1, 1.9, 9.0, 2.0, 2.1])
    persistence = compute_persistence(history)
    assert persistence <= 1  # the old spike (index 3) already resolved; must not still be counted


def test_temporal_features_flags_sustained_when_persistence_high():
    history = _series([2.0, 2.0, 2.0, 8.0, 9.0, 10.0, 11.0])
    features = compute_temporal_features(history)
    assert features.is_sustained is True
    assert features.persistence_ticks >= 3


def test_lead_lag_cross_correlation_detects_shifted_relationship():
    series_a = [1, 2, 3, 4, 5, 4, 3, 2, 1, 2, 3]
    series_b = [0, 0, 1, 2, 3, 4, 5, 4, 3, 2, 1]  # same shape, shifted later
    lag, corr = lead_lag_cross_correlation(series_a, series_b, max_lag=4)
    assert lag > 0  # series_a leads series_b
    assert corr > 0.5


def test_dtw_distance_zero_for_identical_series():
    assert dtw_distance([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]) == 0.0


def test_dtw_distance_small_for_similar_shape_different_scale():
    a = [0.0, 1.0, 2.0, 1.0, 0.0]
    b = [0.0, 10.0, 20.0, 10.0, 0.0]
    normalized_distance = dtw_distance(normalize_series(a), normalize_series(b))
    assert normalized_distance < 0.5  # same shape after normalization


def test_precursor_similarity_high_for_matching_shape():
    current = [0.1, 0.3, 0.6, 0.9, 0.95]
    reference = [0.1, 0.35, 0.55, 0.85, 0.9]
    similarity = precursor_similarity(current, reference)
    assert similarity > 0.7


def test_precursor_similarity_low_for_dissimilar_shape():
    current = [0.9, 0.1, 0.9, 0.1, 0.9]
    reference = [0.1, 0.2, 0.3, 0.4, 0.5]
    similarity = precursor_similarity(current, reference)
    assert similarity < 0.7
