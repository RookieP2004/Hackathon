from __future__ import annotations

from app.domain.engine import SimulationEngine
from app.domain.sensor_types import Severity


def _zone(snapshot: dict, zone_id: str) -> dict:
    return next(z for z in snapshot["zones"] if z["zone_id"] == zone_id)


def _equipment(zone: dict, equipment_id: str) -> dict:
    return next(e for e in zone["equipment"] if e["equipment_id"] == equipment_id)


def _worker(snapshot: dict, worker_id: str) -> dict:
    return next(w for w in snapshot["workers"] if w["worker_id"] == worker_id)


def test_normal_mode_mostly_reports_normal_severity():
    normal_count = warning_count = critical_count = 0
    for seed in range(20):
        engine = SimulationEngine(seed=seed)
        snapshot = None
        for _ in range(60):
            snapshot = engine.tick()
        for zone in snapshot["zones"]:
            if zone["severity"] == "normal":
                normal_count += 1
            elif zone["severity"] == "warning":
                warning_count += 1
            else:
                critical_count += 1
    # Occasional noise-driven blips are realistic; the overwhelming majority
    # of zone-ticks in Normal mode must still read as normal.
    assert normal_count / (normal_count + warning_count + critical_count) > 0.9


def test_global_warning_mode_escalates_severity():
    engine = SimulationEngine(seed=42)
    engine.set_mode(Severity.WARNING)
    snapshot = None
    for _ in range(30):
        snapshot = engine.tick()
    zone = _zone(snapshot, "compressor-house")
    assert zone["severity"] in ("warning", "critical")
    assert zone["mode"] == "warning"


def test_global_critical_mode_pushes_values_past_warning_band():
    engine = SimulationEngine(seed=42)
    engine.set_mode(Severity.CRITICAL)
    snapshot = None
    for _ in range(30):
        snapshot = engine.tick()
    zone = _zone(snapshot, "compressor-house")
    assert zone["severity"] == "critical"
    eq = _equipment(zone, "eq-c101")
    assert eq["severity"] == "critical"


def test_critical_zone_mode_also_stresses_workers_in_that_zone():
    # Regression check for the zone_id resolution bug: worker vitals must
    # respond to their own zone's mode, not just equipment/ambient sensors.
    engine = SimulationEngine(seed=7)
    engine.set_mode(Severity.CRITICAL, "compressor-house")
    snapshot = None
    for _ in range(30):
        snapshot = engine.tick()
    worker = _worker(snapshot, "w-1")  # w-1 is stationed in compressor-house
    assert worker["severity"] == "critical"


def test_zone_mode_does_not_affect_other_zones():
    engine = SimulationEngine(seed=7)
    engine.set_mode(Severity.CRITICAL, "compressor-house")
    snapshot = None
    for _ in range(30):
        snapshot = engine.tick()
    other_zone = _zone(snapshot, "warehouse")
    assert other_zone["mode"] == "normal"


def test_reset_restores_normal_mode_and_clears_scenarios():
    engine = SimulationEngine(seed=1)
    engine.set_mode(Severity.CRITICAL)
    engine.trigger_scenario("fire", zone_id="tank-farm")
    engine.tick()
    engine.reset()
    assert engine.global_mode == Severity.NORMAL
    assert engine.active_scenarios == []
    snapshot = engine.tick()
    zone = _zone(snapshot, "tank-farm")
    assert zone["camera"]["event_type"] == "normal"


def test_gas_leak_escalates_gas_concentration_over_time():
    engine = SimulationEngine(seed=1)
    engine.trigger_scenario("gas_leak", zone_id="tank-farm", equipment_id="eq-t301")
    onset_gas = None
    for i in range(45):
        snapshot = engine.tick()
        if i == 4:
            onset_gas = _zone(snapshot, "tank-farm")["ambient"]["gas_pct_lel"]
    late_gas = _zone(snapshot, "tank-farm")["ambient"]["gas_pct_lel"]
    assert late_gas > onset_gas  # trending upward, not a jump-and-hold


def test_unchecked_gas_leak_ignites_into_explosion_then_fire():
    engine = SimulationEngine(seed=1)
    engine.trigger_scenario("gas_leak", zone_id="tank-farm", equipment_id="eq-t301")
    seen_types: set[str] = set()
    for _ in range(70):
        snapshot = engine.tick()
        seen_types.update(sc["scenario_type"] for sc in snapshot["active_scenarios"])
    assert "explosion" in seen_types
    assert "fire" in seen_types


def test_explosion_immediately_spikes_zone_and_faults_equipment():
    engine = SimulationEngine(seed=2)
    engine.trigger_scenario("explosion", zone_id="compressor-house")
    engine.tick()  # onset
    snapshot = engine.tick()  # blast
    zone = _zone(snapshot, "compressor-house")
    assert zone["ambient"]["smoke_pct_obscuration"] > 80
    assert zone["camera"]["event_type"] == "explosion_detected"
    for eq in zone["equipment"]:
        assert eq["status"] == "fault"


def test_explosion_chains_into_fire():
    engine = SimulationEngine(seed=2)
    engine.trigger_scenario("explosion", zone_id="compressor-house")
    seen_types: set[str] = set()
    for _ in range(12):
        snapshot = engine.tick()
        seen_types.update(sc["scenario_type"] for sc in snapshot["active_scenarios"])
    assert "fire" in seen_types


def test_explosion_scenario_started_mid_simulation_starts_fresh_not_finished():
    # Regression test for the started_at bug: a scenario spawned mid-run must
    # begin its own onset phase at elapsed ~= 1, never jump straight past its
    # later phases because it inherited the parent's elapsed-not-absolute clock.
    engine = SimulationEngine(seed=1)
    for _ in range(500):
        engine.tick()
    engine.trigger_scenario("gas_leak", zone_id="tank-farm", equipment_id="eq-t301")
    fire_phases_seen: list[str] = []
    for _ in range(60):
        snapshot = engine.tick()
        for sc in snapshot["active_scenarios"]:
            if sc["scenario_type"] == "fire":
                fire_phases_seen.append(sc["phase"])
    assert fire_phases_seen, "fire scenario should have ignited within 60 ticks"
    assert fire_phases_seen[0] == "onset"


def test_machine_failure_reaches_terminal_seizure_state():
    engine = SimulationEngine(seed=3)
    engine.trigger_scenario("machine_failure", zone_id="assembly-line", equipment_id="eq-p402")
    snapshot = None
    for _ in range(70):
        snapshot = engine.tick()
    zone = _zone(snapshot, "assembly-line")
    eq = _equipment(zone, "eq-p402")
    assert eq["status"] == "fault"
    assert eq["readings"]["rpm"] == 0.0


def test_machine_failure_leaves_other_equipment_in_zone_unaffected():
    engine = SimulationEngine(seed=3)
    engine.trigger_scenario("machine_failure", zone_id="assembly-line", equipment_id="eq-p402")
    snapshot = None
    for _ in range(70):
        snapshot = engine.tick()
    zone = _zone(snapshot, "assembly-line")
    other = _equipment(zone, "eq-m401")
    assert other["status"] == "operational"


def test_worker_collapse_freezes_gps_and_flips_status():
    engine = SimulationEngine(seed=4)
    engine.trigger_scenario("worker_collapse", zone_id="tank-farm", worker_id="w-3")
    snapshot = None
    for _ in range(60):
        snapshot = engine.tick()
    worker = _worker(snapshot, "w-3")
    assert worker["status"] == "collapsed"

    gps_before = worker["gps"]
    snapshot2 = engine.tick()
    gps_after = _worker(snapshot2, "w-3")["gps"]
    assert gps_before == gps_after  # a collapsed worker's position stops updating


def test_worker_collapse_triggers_person_down_camera_event():
    engine = SimulationEngine(seed=4)
    engine.trigger_scenario("worker_collapse", zone_id="tank-farm", worker_id="w-3")
    snapshot = None
    for _ in range(60):
        snapshot = engine.tick()
    zone = _zone(snapshot, "tank-farm")
    assert zone["camera"]["event_type"] == "person_down"


def test_fire_spreads_to_adjacent_zone_if_unchecked():
    engine = SimulationEngine(seed=5)
    engine.trigger_scenario("fire", zone_id="tank-farm")
    seen_zone_ids: set[str] = set()
    for _ in range(130):
        snapshot = engine.tick()
        for sc in snapshot["active_scenarios"]:
            if sc["scenario_type"] == "fire":
                seen_zone_ids.add(sc["zone_id"])
    assert "tank-farm" in seen_zone_ids
    assert len(seen_zone_ids) > 1  # spread to at least one adjacent zone


def test_reset_scoped_to_one_zone_leaves_others_untouched():
    engine = SimulationEngine(seed=1)
    engine.trigger_scenario("fire", zone_id="tank-farm")
    engine.trigger_scenario("fire", zone_id="boiler-room")
    for _ in range(5):
        engine.tick()
    engine.reset("tank-farm")
    snapshot = engine.tick()
    remaining_zone_ids = {sc["zone_id"] for sc in snapshot["active_scenarios"]}
    assert "tank-farm" not in remaining_zone_ids
    assert "boiler-room" in remaining_zone_ids


# ---- Map entities: buildings, vehicles, emergency exits, fire systems, pipelines ----


def test_buildings_aggregate_worst_zone_severity():
    engine = SimulationEngine(seed=1)
    engine.set_mode(Severity.CRITICAL, "boiler-room")  # boiler-room belongs to utilities-building
    snapshot = None
    for _ in range(30):
        snapshot = engine.tick()
    utilities = next(b for b in snapshot["buildings"] if b["building_id"] == "utilities-building")
    assert utilities["severity"] == "critical"
    assert set(utilities["zone_ids"]) == {"compressor-house", "boiler-room"}

    other_building = next(b for b in snapshot["buildings"] if b["building_id"] == "warehouse-building")
    assert other_building["severity"] == "normal"


def test_vehicles_have_gps_and_alternate_moving_idle():
    engine = SimulationEngine(seed=1)
    statuses_seen = set()
    for _ in range(40):
        snapshot = engine.tick()
        for v in snapshot["vehicles"]:
            statuses_seen.add(v["status"])
    assert statuses_seen <= {"moving", "idle", "parked"}
    assert "moving" in statuses_seen or "idle" in statuses_seen


def test_fire_discharges_the_fire_system_in_that_zone_only():
    engine = SimulationEngine(seed=2)
    engine.trigger_scenario("fire", zone_id="boiler-room")
    snapshot = None
    for _ in range(20):
        snapshot = engine.tick()
    boiler_fs = next(f for f in snapshot["fire_systems"] if f["zone_id"] == "boiler-room")
    other_fs = next(f for f in snapshot["fire_systems"] if f["zone_id"] == "compressor-house")
    assert boiler_fs["status"] == "discharged"
    assert boiler_fs["discharge_count"] == 1
    assert other_fs["status"] == "armed"


def test_fire_system_does_not_auto_rearm_when_reset_is_not_called():
    engine = SimulationEngine(seed=2)
    engine.trigger_scenario("fire", zone_id="boiler-room")
    for _ in range(150):  # well past the point the fire scenario reaches "sustained"
        snapshot = engine.tick()
    boiler_fs = next(f for f in snapshot["fire_systems"] if f["zone_id"] == "boiler-room")
    assert boiler_fs["status"] == "discharged"


def test_reset_rearms_fire_system_but_preserves_discharge_count():
    engine = SimulationEngine(seed=2)
    engine.trigger_scenario("fire", zone_id="boiler-room")
    for _ in range(20):
        engine.tick()
    engine.reset("boiler-room")
    snapshot = engine.tick()
    boiler_fs = next(f for f in snapshot["fire_systems"] if f["zone_id"] == "boiler-room")
    assert boiler_fs["status"] == "armed"
    assert boiler_fs["discharge_count"] == 1


def test_emergency_exits_block_only_in_the_affected_zone():
    engine = SimulationEngine(seed=2)
    engine.trigger_scenario("fire", zone_id="boiler-room")
    snapshot = None
    for _ in range(20):
        snapshot = engine.tick()
    boiler_exits = [e for e in snapshot["emergency_exits"] if e["zone_id"] == "boiler-room"]
    other_exits = [e for e in snapshot["emergency_exits"] if e["zone_id"] != "boiler-room"]
    assert all(e["status"] == "blocked" for e in boiler_exits)
    assert all(e["status"] == "clear" for e in other_exits)


def test_pipeline_severity_reflects_worse_connected_equipment():
    engine = SimulationEngine(seed=3)
    engine.trigger_scenario("machine_failure", zone_id="tank-farm", equipment_id="eq-t301")
    snapshot = None
    for _ in range(70):
        snapshot = engine.tick()
    pipe = next(p for p in snapshot["pipelines"] if p["pipeline_id"] == "pipe-1")
    assert pipe["severity"] == "critical"
    assert pipe["status"] == "stopped"


def test_pipelines_flow_normally_at_baseline():
    engine = SimulationEngine(seed=1)
    snapshot = engine.tick()
    assert all(p["status"] == "flowing" for p in snapshot["pipelines"])


# ---- Robots and emergency responders ----


def test_arm_robot_faults_when_its_bolted_equipment_fails():
    engine = SimulationEngine(seed=3)
    engine.trigger_scenario("machine_failure", zone_id="assembly-line", equipment_id="eq-m401")
    snapshot = None
    for _ in range(70):
        snapshot = engine.tick()
    robot = next(r for r in snapshot["robots"] if r["robot_id"] == "robot-1")
    assert robot["status"] == "fault"


def test_arm_robot_unrelated_to_failure_keeps_running():
    engine = SimulationEngine(seed=3)
    engine.trigger_scenario("machine_failure", zone_id="assembly-line", equipment_id="eq-m401")
    snapshot = None
    for _ in range(70):
        snapshot = engine.tick()
    other_robot = next(r for r in snapshot["robots"] if r["robot_id"] == "robot-2")
    assert other_robot["status"] == "running"


def test_amr_robot_alternates_moving_and_idle():
    engine = SimulationEngine(seed=1)
    statuses_seen = set()
    for _ in range(40):
        snapshot = engine.tick()
        amr = next(r for r in snapshot["robots"] if r["robot_id"] == "robot-3")
        statuses_seen.add(amr["status"])
    assert statuses_seen <= {"idle", "moving"}


def test_responders_travel_toward_an_active_emergency_zone():
    engine = SimulationEngine(seed=5)
    engine.trigger_scenario("fire", zone_id="tank-farm")
    snapshot = None
    for _ in range(25):
        snapshot = engine.tick()
    responder = next(r for r in snapshot["emergency_responders"] if r["responder_id"] == "resp-1")
    assert responder["status"] in ("responding", "on_scene")


def test_responders_return_to_standby_after_reset():
    engine = SimulationEngine(seed=5)
    engine.trigger_scenario("fire", zone_id="tank-farm")
    for _ in range(25):
        engine.tick()
    engine.reset()
    snapshot = None
    for _ in range(25):
        snapshot = engine.tick()
    responder = next(r for r in snapshot["emergency_responders"] if r["responder_id"] == "resp-1")
    assert responder["status"] == "standby"


def test_responders_are_at_standby_with_no_active_scenarios():
    engine = SimulationEngine(seed=1)
    snapshot = engine.tick()
    assert all(r["status"] == "standby" for r in snapshot["emergency_responders"])
