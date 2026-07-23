import pytest

from app.fusion.explainability import compute_counterfactuals, evidence_bundle_to_dict, generate_recommendations
from app.fusion.gates import LikelihoodContribution, rank_contributing_factors
from app.fusion.networks import NetworkResult
from app.fusion.scoring import estimate_confidence


def test_compute_counterfactuals_noisy_or_matches_worked_example():
    contributions = [
        LikelihoodContribution("gas_combustible", "sensor", 40, ["1"]),
        LikelihoodContribution("fuel_pressure", "sensor", 15, ["2"]),
        LikelihoodContribution("confinement_integrity", "equipment_health", 2.5, ["3"]),
        LikelihoodContribution("vision_smoke_thermal", "vision", 6, ["4"]),
    ]
    result = NetworkResult("fire", 0.878, 0.0008, contributions)
    counterfactuals = compute_counterfactuals(result)
    gas_cf = next(c for c in counterfactuals if c.removed_node_id == "gas_combustible")
    assert gas_cf.resulting_probability == pytest.approx(0.153, abs=0.01)


def test_recommendations_generated_for_top_factors():
    contributions = [
        LikelihoodContribution("gas_combustible", "sensor", 40, ["1"]),
        LikelihoodContribution("confinement_integrity", "equipment_health", 2.5, ["2"]),
    ]
    ranked = rank_contributing_factors(contributions)
    recs = generate_recommendations("explosion", ranked, "critical")
    assert any("gas" in r.lower() for r in recs)
    assert recs[0].lower().startswith("critical")


def test_recommendations_low_severity_no_forced_message():
    contributions = [LikelihoodContribution("unmapped_factor", "sensor", 1.1, ["1"])]
    recs = generate_recommendations("machine_failure", contributions, "low")
    assert recs == []


def test_evidence_bundle_to_dict_serializes_nested_dataclasses():
    from app.fusion.explainability import EvidenceBundle
    from app.fusion.scoring import ConfidenceEstimate

    confidence = estimate_confidence(posterior=0.5, num_contributions=1, num_admitted_sources=1, num_good_quality=1, precursor_similarity=None)
    bundle = EvidenceBundle(
        hazard_class="fire", equipment_id=1, equipment_tag="V-1", zone_id=1, assessed_at="2026-01-01T00:00:00Z",
        posterior_probability=0.5, score=50.0, severity="medium", confidence=confidence, time_to_event_seconds=None,
        contributing_factors=[], counterfactuals=[], recommendations=[], graph_context={}, gate_structure_version="v1", cpt_version="v1",
    )
    d = evidence_bundle_to_dict(bundle)
    assert isinstance(d["confidence"], dict)
    assert d["confidence"]["epistemic_flag"] in ("low", "elevated", "high")
