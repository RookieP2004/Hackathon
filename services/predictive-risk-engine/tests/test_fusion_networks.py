from app.fusion.evidence import EvidenceNode
from app.fusion.networks import HazardAssessmentInput, assess_explosion, assess_fire, assess_gas_leak, assess_machine_failure, assess_worker_injury
from app.fusion.temporal import TemporalFeatures


def _node(source_type: str, normalized: float, source_id: str = "test") -> EvidenceNode:
    return EvidenceNode(source_type=source_type, source_id=source_id, raw_value=None, normalized_value=normalized, unit=None, timestamp=None, quality_flag="good")


def _baseline_input(**overrides) -> HazardAssessmentInput:
    defaults = dict(
        equipment_tag="TEST-EQ", sensor_nodes={}, sensor_temporal={},
        equipment_health=_node("equipment_health", 0.1), vision_detection=None,
        permit_active_hot_work=False, permit_active_confined_space=False,
        maintenance_overdue=False, worker_present=False, ppe_violation_detected=False,
    )
    defaults.update(overrides)
    return HazardAssessmentInput(**defaults)


def test_explosion_needs_all_three_subconditions_for_high_posterior():
    strong_all = _baseline_input(
        sensor_nodes={"Gas Concentration": _node("sensor", 0.95), "Pressure": _node("sensor", 0.95), "Temperature": _node("sensor", 0.9)},
        equipment_health=_node("equipment_health", 0.9), maintenance_overdue=True,
    )
    weak_confinement = _baseline_input(
        sensor_nodes={"Gas Concentration": _node("sensor", 0.95), "Pressure": _node("sensor", 0.95), "Temperature": _node("sensor", 0.9)},
        equipment_health=_node("equipment_health", 0.05), maintenance_overdue=False,
    )
    strong_result = assess_explosion(strong_all)
    weak_result = assess_explosion(weak_confinement)
    assert strong_result.posterior_probability > weak_result.posterior_probability
    assert set(strong_result.sub_condition_probabilities) == {"fuel_in_range", "ignition_source", "confinement"}


def test_explosion_baseline_evidence_yields_low_posterior():
    calm = _baseline_input(
        sensor_nodes={"Gas Concentration": _node("sensor", 0.5), "Pressure": _node("sensor", 0.5), "Temperature": _node("sensor", 0.5)},
    )
    result = assess_explosion(calm)
    assert result.posterior_probability < 0.1


def test_fire_corroborating_vision_raises_posterior_over_temperature_alone():
    temp_only = _baseline_input(sensor_nodes={"Temperature": _node("sensor", 0.9)})
    temp_and_vision = _baseline_input(
        sensor_nodes={"Temperature": _node("sensor", 0.9)}, vision_detection=_node("vision", 0.9),
    )
    result_a = assess_fire(temp_only)
    result_b = assess_fire(temp_and_vision)
    assert result_b.posterior_probability > result_a.posterior_probability


def test_fire_active_hot_work_permit_raises_prior():
    without_permit = assess_fire(_baseline_input(sensor_nodes={"Temperature": _node("sensor", 0.8)}))
    with_permit = assess_fire(_baseline_input(sensor_nodes={"Temperature": _node("sensor", 0.8)}, permit_active_hot_work=True))
    assert with_permit.posterior_probability > without_permit.posterior_probability


def test_gas_leak_multiple_corroborating_signals():
    single = assess_gas_leak(_baseline_input(sensor_nodes={"Gas Concentration": _node("sensor", 0.9)}))
    multiple = assess_gas_leak(_baseline_input(
        sensor_nodes={"Gas Concentration": _node("sensor", 0.9), "Pressure": _node("sensor", 0.85), "Flow Rate": _node("sensor", 0.85)},
    ))
    assert multiple.posterior_probability > single.posterior_probability


def test_machine_failure_sustained_deviation_amplified_over_instantaneous():
    instantaneous = assess_machine_failure(_baseline_input(
        sensor_nodes={"Vibration": _node("sensor", 0.85)},
        sensor_temporal={"Vibration": TemporalFeatures(rate_of_change=0.1, persistence_ticks=0, is_sustained=False)},
    ))
    sustained = assess_machine_failure(_baseline_input(
        sensor_nodes={"Vibration": _node("sensor", 0.85)},
        sensor_temporal={"Vibration": TemporalFeatures(rate_of_change=0.1, persistence_ticks=5, is_sustained=True)},
    ))
    assert sustained.posterior_probability > instantaneous.posterior_probability


def test_worker_injury_zero_without_worker_present():
    result = assess_worker_injury(_baseline_input(
        worker_present=False, other_hazard_posteriors={"fire": 0.9, "explosion": 0.8, "gas_leak": 0.1},
    ))
    assert result.posterior_probability == 0.0


def test_worker_injury_scales_with_ppe_violation_and_upstream_hazard():
    no_hazard = assess_worker_injury(_baseline_input(worker_present=True, other_hazard_posteriors={"fire": 0.01, "explosion": 0.01, "gas_leak": 0.01}))
    high_hazard = assess_worker_injury(_baseline_input(worker_present=True, other_hazard_posteriors={"fire": 0.9, "explosion": 0.1, "gas_leak": 0.1}))
    high_hazard_ppe = assess_worker_injury(_baseline_input(
        worker_present=True, ppe_violation_detected=True, other_hazard_posteriors={"fire": 0.9, "explosion": 0.1, "gas_leak": 0.1},
    ))
    assert high_hazard.posterior_probability > no_hazard.posterior_probability
    assert high_hazard_ppe.posterior_probability > high_hazard.posterior_probability


def test_worker_injury_graph_topologically_irrelevant_to_other_networks():
    # Per §4.4/§4.6: worker presence must not itself alter Fire/Explosion/Gas Leak's own posteriors.
    without_worker = assess_fire(_baseline_input(sensor_nodes={"Temperature": _node("sensor", 0.85)}, worker_present=False))
    with_worker = assess_fire(_baseline_input(sensor_nodes={"Temperature": _node("sensor", 0.85)}, worker_present=True))
    assert without_worker.posterior_probability == with_worker.posterior_probability
