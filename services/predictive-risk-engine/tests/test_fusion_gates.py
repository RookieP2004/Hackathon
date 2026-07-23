"""
Reproduces RISK_FUSION_ENGINE.md §5's worked example by hand, using the
exact prior and likelihood-ratio values the document itself states, as a
golden-value test: if this module's odds-multiplication math doesn't land on
the document's own stated probabilities, the implementation is wrong.
"""

import pytest

from app.fusion.gates import (
    LikelihoodContribution,
    counterfactual_without,
    noisy_and,
    noisy_or,
    odds_from_probability,
    probability_from_odds,
    rank_contributing_factors,
)


def _lc(evidence_node_id: str, lr: float) -> LikelihoodContribution:
    return LikelihoodContribution(evidence_node_id=evidence_node_id, source_type="test", likelihood_ratio=lr, evidence_refs=[])


def test_odds_probability_round_trip():
    assert odds_from_probability(0.878) == pytest.approx(7.2, rel=0.02)
    assert probability_from_odds(7.2) == pytest.approx(0.878, abs=0.001)


def test_worked_example_sequential_updates():
    prior_odds = 0.0008

    p1, odds1 = noisy_or([_lc("gs14", 40)], prior_odds)
    assert p1 == pytest.approx(0.031, abs=0.002)

    p2, odds2 = noisy_or([_lc("gs14", 40), _lc("pt22", 15)], prior_odds)
    assert p2 == pytest.approx(0.324, abs=0.005)

    p3, odds3 = noisy_or([_lc("gs14", 40), _lc("pt22", 15), _lc("rv9", 2.5)], prior_odds)
    assert p3 == pytest.approx(0.545, abs=0.01)

    p4, odds4 = noisy_or([_lc("gs14", 40), _lc("pt22", 15), _lc("rv9", 2.5), _lc("vision", 6)], prior_odds)
    assert p4 == pytest.approx(0.878, abs=0.01)


def test_worked_example_counterfactual():
    prior_odds = 0.0008
    contributions = [_lc("gs14", 40), _lc("pt22", 15), _lc("rv9", 2.5), _lc("vision", 6)]

    result = counterfactual_without(contributions, prior_odds, exclude_id="gs14")
    assert result == pytest.approx(0.153, abs=0.01)


def test_contributing_factors_ranked_by_log_lr_magnitude():
    contributions = [_lc("rv9", 2.5), _lc("gs14", 40), _lc("vision", 6), _lc("pt22", 15)]
    ranked = rank_contributing_factors(contributions)
    assert [c.evidence_node_id for c in ranked] == ["gs14", "pt22", "vision", "rv9"]


def test_noisy_and_caps_on_weak_sub_condition():
    strong_and_strong = noisy_and([0.9, 0.9, 0.9])
    strong_and_weak = noisy_and([0.9, 0.9, 0.1])
    assert strong_and_weak < strong_and_strong
    assert strong_and_weak == pytest.approx(0.081, abs=0.005)


def test_noisy_and_graded_near_miss_still_elevated():
    # A "near miss" on one dimension (0.95 instead of 1.0) combined with two
    # strong dimensions should stay meaningfully elevated, not collapse --
    # unlike a boolean AND, which would treat 0.95 as full failure.
    near_miss = noisy_and([0.95, 0.9, 0.9])
    assert near_miss > 0.7
