"""
Stage 6 — Explainability & Evidence Generation (RISK_FUSION_ENGINE.md §3.6
and §7). Because Stages 2-4 are graph-structured and gate-explicit rather
than an opaque learned embedding, everything here is read directly off the
Bayesian network's own internal state -- no separate explanation model.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

from app.fusion.gates import counterfactual_without, rank_contributing_factors
from app.fusion.networks import NetworkResult
from app.fusion.scoring import ConfidenceEstimate, severity_for_score

GATE_STRUCTURE_VERSION = "risk-fusion-v1"
CPT_VERSION = "cpt-defaults-v1"  # see networks.py's LR_CURVE_PARAMS/DEFAULT_PRIOR_ODDS docstrings


@dataclass
class Counterfactual:
    removed_node_id: str
    resulting_probability: float
    delta: float


@dataclass
class EvidenceBundle:
    hazard_class: str
    equipment_id: int
    equipment_tag: str
    zone_id: int | None
    assessed_at: str
    posterior_probability: float
    score: float
    severity: str
    confidence: ConfidenceEstimate
    time_to_event_seconds: float | None
    contributing_factors: list[dict]
    counterfactuals: list[Counterfactual]
    recommendations: list[str]
    graph_context: dict
    gate_structure_version: str
    cpt_version: str
    sub_condition_probabilities: dict[str, float] = field(default_factory=dict)


def compute_counterfactuals(result: NetworkResult) -> list[Counterfactual]:
    """§3.6: "what would the posterior be if this one node were at its
    baseline value instead" -- for the noisy-OR-structured networks (fire,
    gas_leak, machine_failure), this is exactly gates.counterfactual_without
    on the flat contribution/odds list. Explosion's noisy-AND and Worker
    Injury's multiplicative structure don't have a single flat odds product
    to remove a term from in the same way, so their most-informative
    counterfactual is reported at the sub-condition level instead (still a
    real recomputation, not a placeholder)."""
    counterfactuals = []

    if result.sub_condition_probabilities and result.hazard_class == "explosion":
        from app.fusion.gates import noisy_and

        for name, value in result.sub_condition_probabilities.items():
            others = {k: v for k, v in result.sub_condition_probabilities.items() if k != name}
            baseline_value = 0.05  # a sub-condition "at baseline" -- near-absent, not exactly zero (avoids a divide/zero-collapse edge case)
            recomputed = noisy_and([*others.values(), baseline_value])
            counterfactuals.append(Counterfactual(name, recomputed, recomputed - result.posterior_probability))
        return counterfactuals

    if result.hazard_class == "worker_injury":
        sub = result.sub_condition_probabilities
        if sub:
            for name in ("p_any_hazard", "p_present", "p_injury_given_exposure"):
                others = {k: v for k, v in sub.items() if k != name}
                baseline = 0.0 if name == "p_present" else 0.05
                recomputed = baseline
                for v in others.values():
                    recomputed *= v
                counterfactuals.append(Counterfactual(name, recomputed, recomputed - result.posterior_probability))
        return counterfactuals

    for contribution in result.contributions:
        recomputed = counterfactual_without(result.contributions, result.prior_odds, contribution.evidence_node_id)
        counterfactuals.append(Counterfactual(contribution.evidence_node_id, recomputed, recomputed - result.posterior_probability))
    return counterfactuals


_RECOMMENDATION_TEMPLATES: dict[str, str] = {
    "gas_combustible": "Investigate the gas sensor reading immediately and consider restricting ignition sources in the affected zone.",
    "fuel_gas": "Investigate the gas concentration reading and verify containment integrity on the affected line.",
    "gas_direct": "Confirm source and extent of the gas concentration deviation; consider zone evacuation if levels continue rising.",
    "fuel_pressure": "Verify process pressure against the line's design envelope; a rise here alongside gas evidence suggests contained accumulation.",
    "ignition_temp": "Inspect for a developing electrical fault or hot surface near the affected equipment.",
    "ignition_vision": "Dispatch a visual inspection to confirm the camera-flagged thermal/smoke indication in person.",
    "vision_smoke_thermal": "Dispatch a visual inspection to confirm the camera-flagged thermal/smoke indication in person.",
    "vision_leak": "Confirm the camera-flagged visual leak indication and check for a spreading spill or vapor cloud.",
    "confinement_integrity": "Prioritize an inspection of pressure-relief and containment equipment in this equipment's neighborhood.",
    "electrical_fault_proxy": "Schedule an electrical inspection for this equipment given its current operational status.",
    "seal_gasket_age": "Schedule a seal/gasket inspection given this equipment's health status and service history.",
    "vibration": "Schedule a vibration analysis and bearing inspection before continued operation.",
    "overheating": "Reduce load or schedule a cooling-system inspection given the sustained temperature deviation.",
    "maintenance_overdue": "Prioritize the overdue maintenance item on this equipment -- it is a material contributing factor.",
    "worker_presence": "Confirm the present worker's PPE and permit compliance, and consider restricting zone access.",
    "ppe_violation": "Address the detected PPE violation immediately -- this is elevating worker injury risk directly.",
    "upstream_hazard_probability": "This assessment is driven by an active physical hazard elsewhere in the network -- review that hazard's own recommendations first.",
}


def generate_recommendations(hazard_class: str, ranked_factors: list, severity: str) -> list[str]:
    recommendations = []
    for factor in ranked_factors[:3]:
        template = _RECOMMENDATION_TEMPLATES.get(factor.evidence_node_id)
        if template:
            recommendations.append(template)
    if severity in ("high", "critical") and not recommendations:
        recommendations.append(f"Elevated {hazard_class.replace('_', ' ')} risk detected -- review contributing factors and dispatch an inspection.")
    if severity == "critical":
        recommendations.insert(0, f"Critical {hazard_class.replace('_', ' ')} risk -- consider immediate operational restriction pending investigation.")
    return recommendations


def assemble_evidence_bundle(
    *, result: NetworkResult, equipment_id: int, equipment_tag: str, zone_id: int | None,
    score: float, confidence: ConfidenceEstimate, time_to_event_seconds: float | None,
    graph_neighborhood_snapshot_id: str,
) -> EvidenceBundle:
    ranked = rank_contributing_factors(result.contributions)
    counterfactuals = compute_counterfactuals(result)
    severity = severity_for_score(score)
    recommendations = generate_recommendations(result.hazard_class, ranked, severity)

    return EvidenceBundle(
        hazard_class=result.hazard_class,
        equipment_id=equipment_id,
        equipment_tag=equipment_tag,
        zone_id=zone_id,
        assessed_at=datetime.now(timezone.utc).isoformat(),
        posterior_probability=round(result.posterior_probability, 4),
        score=score,
        severity=severity,
        confidence=confidence,
        time_to_event_seconds=time_to_event_seconds,
        contributing_factors=[
            {
                "evidence_node_id": c.evidence_node_id, "source_type": c.source_type,
                "likelihood_ratio": round(c.likelihood_ratio, 4), "evidence_refs": c.evidence_refs,
            }
            for c in ranked
        ],
        counterfactuals=counterfactuals,
        recommendations=recommendations,
        graph_context={"equipment_neighborhood_snapshot_id": graph_neighborhood_snapshot_id},
        gate_structure_version=GATE_STRUCTURE_VERSION,
        cpt_version=CPT_VERSION,
        sub_condition_probabilities=dict(result.sub_condition_probabilities),
    )


def evidence_bundle_to_dict(bundle: EvidenceBundle) -> dict:
    d = asdict(bundle)
    d["confidence"] = asdict(bundle.confidence)
    d["counterfactuals"] = [asdict(cf) for cf in bundle.counterfactuals]
    return d
