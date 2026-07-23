"""
The Bayesian fusion primitives — RISK_FUSION_ENGINE.md §3.4 and §5. Sequential
Bayesian updating via odds multiplication, exactly as the worked example
computes it by hand: `posterior_odds = prior_odds * LR_1 * LR_2 * ... * LR_n`.
No neural network, no learned weights -- every number here is a probability
or an explicit likelihood ratio, which is what makes Stage 6's explainability
"read off the computation" rather than a separate model (§3.6).
"""

from __future__ import annotations

import math
from dataclasses import dataclass


def odds_from_probability(p: float) -> float:
    p = min(max(p, 1e-9), 1 - 1e-9)
    return p / (1 - p)


def probability_from_odds(odds: float) -> float:
    return odds / (1 + odds)


@dataclass(frozen=True)
class LikelihoodContribution:
    """One Evidence Node's contribution to a gate -- the atomic unit Stage 6's
    contributing-factor ranking and counterfactual generation both operate on."""

    evidence_node_id: str
    source_type: str
    likelihood_ratio: float
    evidence_refs: list[str]

    @property
    def log_lr(self) -> float:
        return math.log(max(self.likelihood_ratio, 1e-9))


def sigmoid_likelihood_ratio(
    value: float, *, inflection_point: float, steepness: float, max_lr: float, min_lr: float = 1.0 / 20
) -> float:
    """§3.4 point 1: "a regulatory threshold ... becomes the inflection point
    of a continuous sigmoid likelihood-ratio curve" -- not a step function.
    Below the inflection point the LR decays toward `min_lr` (mild
    evidence *against* the hazard); at and above it, LR rises toward
    `max_lr`. `steepness` controls how sharp the transition is (a tighter
    regulatory tolerance band -> steeper curve)."""
    x = (value - inflection_point) / max(steepness, 1e-9)
    s = 1.0 / (1.0 + math.exp(-x))  # in [0, 1]
    log_min, log_max = math.log(min_lr), math.log(max_lr)
    return math.exp(log_min + s * (log_max - log_min))


def noisy_or(contributions: list[LikelihoodContribution], prior_odds: float) -> tuple[float, float]:
    """Disjunctive gate (§3.4): independent pathways, any one sufficient.
    Combined via straight odds multiplication across all contributing LRs --
    this is the standard noisy-OR update rule expressed in odds form, which
    is exactly the mechanism the worked example (§5) walks through by hand.
    Returns (posterior_probability, posterior_odds)."""
    odds = prior_odds
    for c in contributions:
        odds *= c.likelihood_ratio
    return probability_from_odds(odds), odds


def noisy_and(sub_condition_probabilities: list[float]) -> float:
    """Conjunctive gate (§3.4/§4.2): several conditions that must *jointly*
    hold. Modeled as the product of each sub-condition's own probability --
    a graded joint condition, not a boolean AND: a near-miss on one dimension
    (e.g., 0.95 instead of 1.0) combined with strong evidence on the other
    two still yields a meaningfully elevated (if capped) joint probability,
    exactly as §4.2 specifies, rather than an all-or-nothing gate."""
    result = 1.0
    for p in sub_condition_probabilities:
        result *= max(0.0, min(1.0, p))
    return result


def rank_contributing_factors(contributions: list[LikelihoodContribution]) -> list[LikelihoodContribution]:
    """§3.6: ranked by |log(likelihood_ratio)| magnitude -- how much a factor
    moved the posterior, in either direction, not just raw LR size."""
    return sorted(contributions, key=lambda c: abs(c.log_lr), reverse=True)


def counterfactual_without(contributions: list[LikelihoodContribution], prior_odds: float, exclude_id: str) -> float:
    """§3.6/§7: "what would the posterior be if this one node were at its
    baseline value instead" -- recomputed by simply omitting that node's LR
    from the odds product, since each contribution is an explicit
    multiplicative factor (not a hidden weight inside a learned model)."""
    odds = prior_odds
    for c in contributions:
        if c.evidence_node_id != exclude_id:
            odds *= c.likelihood_ratio
    return probability_from_odds(odds)
