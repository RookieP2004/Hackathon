"""
Stage 4 — the five per-hazard Bayesian networks (RISK_FUSION_ENGINE.md §4).
Each hazard's causal shape is genuinely different (§4's own framing): Fire
and Gas Leak are disjunctive (noisy-OR across independent pathways),
Explosion is conjunctive (noisy-AND across simultaneously-necessary
sub-conditions), Worker Injury is a multiplicative exposure model, Machine
Failure leans hardest on the temporal-reasoning layer. Likelihood ratios are
computed from each Evidence Node's *normalized* ([0,1] deviation-from-
baseline) value via a continuous sigmoid curve (gates.sigmoid_likelihood_ratio)
-- never a step function -- per §3.4 point 1's explicit mechanism for
honoring a regulatory threshold without becoming an IF-statement.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.fusion.evidence import EvidenceNode
from app.fusion.gates import LikelihoodContribution, noisy_and, noisy_or, odds_from_probability
from app.fusion.temporal import TemporalFeatures

# (inflection_point, steepness, max_lr) per source_type, operating on the
# already-normalized [0,1] deviation-from-baseline value (evidence.py), not
# raw physical units -- sidesteps unit mismatches (ppm vs %LEL vs mm/s) while
# still honestly implementing "a regulatory threshold becomes a sigmoid's
# inflection point" (§3.4 point 1): a sensor sitting at the high end of its
# own historical deviation band is what "approaching the regulatory limit"
# operationally means here. Magnitudes are set to reproduce the *order* of
# LR RISK_FUSION_ENGINE.md §5's worked example uses for the same source
# types (gas ~40, pressure ~15, vision ~6, maintenance-context ~2.5), not
# fitted to real incident data (no such dataset exists in this environment).
LR_CURVE_PARAMS: dict[str, tuple[float, float, float]] = {
    "Gas Concentration": (0.72, 0.14, 45.0),
    "Pressure": (0.78, 0.14, 18.0),
    "Temperature": (0.78, 0.15, 20.0),
    "Vibration": (0.72, 0.14, 15.0),
    "Acoustic": (0.8, 0.15, 8.0),
    "Level": (0.8, 0.15, 6.0),
    "Flow Rate": (0.75, 0.15, 10.0),
    "vision": (0.5, 0.12, 25.0),  # computer-vision confidence is already near-direct evidence (§4.1)
    "equipment_health": (0.6, 0.2, 6.0),
}

# Prior odds per hazard class (Category C base rate) -- RISK_FUSION_ENGINE.md
# §5 uses 0.0008 for Explosion on a comparable process unit; the others are
# set relative to that using standard industrial-safety relative-frequency
# ordering (worker injury and machine failure are meaningfully more common
# events than explosion or fire), not fitted to this demo's 3-incident
# history (too sparse to estimate a real base rate from -- §3.4 point 2's
# empirical-base-rate mechanism needs materially more incident volume than
# exists in this environment; this is the documented, honest fallback).
DEFAULT_PRIOR_ODDS: dict[str, float] = {
    "fire": 0.002,
    "explosion": 0.0008,
    "gas_leak": 0.01,
    "worker_injury": 0.02,
    "machine_failure": 0.05,
}


def _lr_for_evidence(node: EvidenceNode, source_type_key: str, node_id: str) -> LikelihoodContribution | None:
    if node.quality_flag == "missing":
        return None
    params = LR_CURVE_PARAMS.get(source_type_key)
    if params is None:
        return None
    from app.fusion.gates import sigmoid_likelihood_ratio

    inflection, steepness, max_lr = params
    lr = sigmoid_likelihood_ratio(node.normalized_value, inflection_point=inflection, steepness=steepness, max_lr=max_lr)
    refs = [str(node.metadata.get("sensor_id", node.source_id))]
    return LikelihoodContribution(evidence_node_id=node_id, source_type=node.source_type, likelihood_ratio=lr, evidence_refs=refs)


@dataclass
class NetworkResult:
    hazard_class: str
    posterior_probability: float
    prior_odds: float
    contributions: list[LikelihoodContribution]
    sub_condition_probabilities: dict[str, float] = field(default_factory=dict)


@dataclass
class HazardAssessmentInput:
    equipment_tag: str
    sensor_nodes: dict[str, EvidenceNode]  # keyed by sensor_type ("Gas Concentration", "Pressure", ...)
    sensor_temporal: dict[str, TemporalFeatures]
    equipment_health: EvidenceNode
    vision_detection: EvidenceNode | None  # a computer-vision detection confidence, if any, already normalized [0,1]
    permit_active_hot_work: bool
    permit_active_confined_space: bool
    maintenance_overdue: bool
    worker_present: bool
    ppe_violation_detected: bool
    other_hazard_posteriors: dict[str, float] = field(default_factory=dict)
    prior_odds_override: dict[str, float] = field(default_factory=dict)


def _prior_odds(hazard_class: str, inp: HazardAssessmentInput) -> float:
    return inp.prior_odds_override.get(hazard_class, DEFAULT_PRIOR_ODDS[hazard_class])


def assess_fire(inp: HazardAssessmentInput) -> NetworkResult:
    """§4.1: Noisy-OR across independent ignition pathways (electrical fault,
    hot-work source, chemical exotherm). Vision's smoke/thermal detection is
    weighted with a strong max_lr since it is close to direct observation."""
    contributions = []
    if (temp := inp.sensor_nodes.get("Temperature")) is not None:
        c = _lr_for_evidence(temp, "Temperature", "temperature")
        if c:
            contributions.append(c)
    if inp.vision_detection is not None:
        c = _lr_for_evidence(inp.vision_detection, "vision", "vision_smoke_thermal")
        if c:
            contributions.append(c)
    if (gas := inp.sensor_nodes.get("Gas Concentration")) is not None:
        c = _lr_for_evidence(gas, "Gas Concentration", "gas_combustible")
        if c:
            contributions.append(c)
    if inp.equipment_health.normalized_value > 0.5:
        c = _lr_for_evidence(inp.equipment_health, "equipment_health", "electrical_fault_proxy")
        if c:
            contributions.append(c)

    prior_odds = _prior_odds("fire", inp)
    if inp.permit_active_hot_work:
        prior_odds *= 3.0  # Category B: raises the prior, per §4.1's dotted "raises prior" edge
    if inp.maintenance_overdue:
        prior_odds *= 1.5

    posterior, _ = noisy_or(contributions, prior_odds)
    return NetworkResult("fire", posterior, prior_odds, contributions)


def assess_explosion(inp: HazardAssessmentInput) -> NetworkResult:
    """§4.2: Noisy-AND across three sub-conditions -- Fuel-in-Range, Ignition
    Source, Confinement -- each itself a small noisy-OR over its own
    evidence. A near-miss on one sub-condition still yields a meaningfully
    elevated (if capped) joint probability, per §4.2's explicit design intent."""
    prior_odds = _prior_odds("explosion", inp)

    fuel_contributions = []
    if (gas := inp.sensor_nodes.get("Gas Concentration")) is not None:
        c = _lr_for_evidence(gas, "Gas Concentration", "fuel_gas")
        if c:
            fuel_contributions.append(c)
    if (pressure := inp.sensor_nodes.get("Pressure")) is not None:
        c = _lr_for_evidence(pressure, "Pressure", "fuel_pressure")
        if c:
            fuel_contributions.append(c)
    fuel_p, _ = noisy_or(fuel_contributions, prior_odds) if fuel_contributions else (prior_odds / (1 + prior_odds), prior_odds)

    ignition_contributions = []
    if (temp := inp.sensor_nodes.get("Temperature")) is not None:
        c = _lr_for_evidence(temp, "Temperature", "ignition_temp")
        if c:
            ignition_contributions.append(c)
    if inp.vision_detection is not None:
        c = _lr_for_evidence(inp.vision_detection, "vision", "ignition_vision")
        if c:
            ignition_contributions.append(c)
    ignition_prior = prior_odds * (0.5 if not inp.permit_active_hot_work else 1.0)  # null permit doesn't rule out other pathways (§5's t=3min note)
    ignition_p, _ = noisy_or(ignition_contributions, ignition_prior) if ignition_contributions else (ignition_prior / (1 + ignition_prior), ignition_prior)

    confinement_contributions = []
    c = _lr_for_evidence(inp.equipment_health, "equipment_health", "confinement_integrity")
    if c:
        confinement_contributions.append(c)
    confinement_prior = prior_odds * (1.8 if inp.maintenance_overdue else 1.0)  # overdue relief valve raises Confinement's likelihood (§5's t=3min)
    confinement_p, _ = noisy_or(confinement_contributions, confinement_prior) if confinement_contributions else (confinement_prior / (1 + confinement_prior), confinement_prior)

    joint = noisy_and([fuel_p, ignition_p, confinement_p])
    all_contributions = fuel_contributions + ignition_contributions + confinement_contributions
    return NetworkResult(
        "explosion", joint, prior_odds, all_contributions,
        sub_condition_probabilities={"fuel_in_range": fuel_p, "ignition_source": ignition_p, "confinement": confinement_p},
    )


def assess_gas_leak(inp: HazardAssessmentInput) -> NetworkResult:
    """§4.3: predominantly Noisy-OR -- direct concentration, a pressure/flow
    discrepancy, and visual/thermal confirmation are largely independent
    corroborating pathways to the same underlying fact."""
    contributions = []
    for key, node_id in (("Gas Concentration", "gas_direct"), ("Pressure", "pressure_drop"), ("Flow Rate", "flow_deviation")):
        if (node := inp.sensor_nodes.get(key)) is not None:
            c = _lr_for_evidence(node, key, node_id)
            if c:
                contributions.append(c)
    if inp.vision_detection is not None:
        c = _lr_for_evidence(inp.vision_detection, "vision", "vision_leak")
        if c:
            contributions.append(c)
    c = _lr_for_evidence(inp.equipment_health, "equipment_health", "seal_gasket_age")
    if c:
        contributions.append(c)

    prior_odds = _prior_odds("gas_leak", inp)
    if inp.maintenance_overdue:
        prior_odds *= 1.4
    posterior, _ = noisy_or(contributions, prior_odds)
    return NetworkResult("gas_leak", posterior, prior_odds, contributions)


def assess_machine_failure(inp: HazardAssessmentInput) -> NetworkResult:
    """§4.5: leans heaviest on temporal reasoning (rate-of-change / sustained
    deviation) rather than acute conjunctive/disjunctive logic -- a
    degradation/survival-analysis problem more than an event-detection one."""
    contributions = []
    for key, node_id in (("Vibration", "vibration"), ("Temperature", "overheating")):
        if (node := inp.sensor_nodes.get(key)) is not None:
            c = _lr_for_evidence(node, key, node_id)
            if c is None:
                continue
            temporal = inp.sensor_temporal.get(key)
            if temporal is not None and temporal.is_sustained:
                # A sustained deviation is materially more diagnostic than an instantaneous
                # one for this hazard specifically (§4.5/§3.3) -- amplify, don't just note it.
                c = LikelihoodContribution(c.evidence_node_id, c.source_type, c.likelihood_ratio * 1.6, c.evidence_refs)
            contributions.append(c)

    c = _lr_for_evidence(inp.equipment_health, "equipment_health", "maintenance_overdue")
    if c:
        contributions.append(c)

    prior_odds = _prior_odds("machine_failure", inp)
    posterior, _ = noisy_or(contributions, prior_odds)
    return NetworkResult("machine_failure", posterior, prior_odds, contributions)


def assess_worker_injury(inp: HazardAssessmentInput) -> NetworkResult:
    """§4.4: NOT disjunctive/conjunctive like the other four -- a
    multiplicative interaction: P(Worker Injury) ~= P(any active hazard) x
    P(worker present) x P(injury | exposure, PPE/permit compliance). Fire,
    Explosion, and Gas Leak's own posteriors are imported as upstream nodes
    (§4.6's causal ordering), not recomputed."""
    p_any_hazard = 1 - (
        (1 - inp.other_hazard_posteriors.get("fire", 0.0))
        * (1 - inp.other_hazard_posteriors.get("explosion", 0.0))
        * (1 - inp.other_hazard_posteriors.get("gas_leak", 0.0))
    )
    p_present = 1.0 if inp.worker_present else 0.0

    p_injury_given_exposure = 0.3
    if inp.ppe_violation_detected:
        p_injury_given_exposure += 0.35
    if not inp.permit_active_hot_work and not inp.permit_active_confined_space:
        p_injury_given_exposure += 0.1  # working without the situational permit context raises exposure risk
    p_injury_given_exposure = min(1.0, p_injury_given_exposure)

    posterior = p_any_hazard * p_present * p_injury_given_exposure
    contributions = [
        LikelihoodContribution("upstream_hazard_probability", "derived", max(p_any_hazard, 1e-6) / max(1 - p_any_hazard, 1e-6), ["fire", "explosion", "gas_leak"]),
        LikelihoodContribution("worker_presence", "worker_location", 50.0 if inp.worker_present else 1e-6, ["worker_location"]),
    ]
    if inp.ppe_violation_detected:
        contributions.append(LikelihoodContribution("ppe_violation", "vision", 3.0, ["ppe_detection"]))

    return NetworkResult(
        "worker_injury", posterior, 0.0, contributions,
        sub_condition_probabilities={"p_any_hazard": p_any_hazard, "p_present": p_present, "p_injury_given_exposure": p_injury_given_exposure},
    )


HAZARD_ASSESSORS = {
    "gas_leak": assess_gas_leak,
    "machine_failure": assess_machine_failure,
    "fire": assess_fire,
    "explosion": assess_explosion,
    "worker_injury": assess_worker_injury,
}

# §4.6: computed in this exact order -- Gas Leak and Machine Failure first
# (direct physical evidence only), then Fire and Explosion (each takes Gas
# Leak's posterior as an additional input), then Worker Injury last (takes
# Fire/Explosion/Gas Leak's posteriors as direct inputs).
ASSESSMENT_ORDER = ["gas_leak", "machine_failure", "fire", "explosion", "worker_injury"]


def run_all_networks(inp: HazardAssessmentInput) -> dict[str, NetworkResult]:
    results: dict[str, NetworkResult] = {}
    for hazard_class in ASSESSMENT_ORDER:
        inp.other_hazard_posteriors = {k: r.posterior_probability for k, r in results.items()}
        results[hazard_class] = HAZARD_ASSESSORS[hazard_class](inp)
    return results
