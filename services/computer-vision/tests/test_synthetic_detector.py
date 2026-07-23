from app.vision.schema import DetectionClass
from app.vision.synthetic_detector import detect_from_snapshot


def _zone(zone_id="compressor-house", camera_id="CAM-01", event_type="normal", confidence=0.95,
          person_count=0, gas_pct_lel=2.0, smoke_pct=1.0, equipment=None):
    return {
        "zone_id": zone_id,
        "camera": {"camera_id": camera_id, "event_type": event_type, "confidence": confidence, "person_count": person_count},
        "ambient": {"gas_pct_lel": gas_pct_lel, "smoke_pct_obscuration": smoke_pct},
        "equipment": equipment or [],
    }


def _worker(worker_id="w-1", zone_id="compressor-house", status="active", heart_rate=75.0):
    return {
        "worker_id": worker_id,
        "zone_id": zone_id,
        "status": status,
        "vitals": {"heart_rate_bpm": heart_rate},
    }


def _snapshot(zones=None, workers=None, vehicles=None):
    return {"zones": zones or [_zone()], "workers": workers or [], "vehicles": vehicles or []}


def test_quiet_snapshot_produces_no_detections():
    snapshot = _snapshot()
    assert detect_from_snapshot(snapshot) == []


def test_fire_detected_camera_event_yields_fire_detection():
    snapshot = _snapshot(zones=[_zone(event_type="fire_detected", confidence=0.99)])
    detections = detect_from_snapshot(snapshot)
    classes = {d.detection_class for d in detections}
    assert DetectionClass.FIRE in classes
    fire = next(d for d in detections if d.detection_class == DetectionClass.FIRE)
    assert fire.source == "simulated"
    assert fire.camera_id == "CAM-01"
    assert 0 <= fire.confidence <= 1


def test_explosion_detected_also_maps_to_fire():
    snapshot = _snapshot(zones=[_zone(event_type="explosion_detected", confidence=0.99)])
    classes = {d.detection_class for d in detect_from_snapshot(snapshot)}
    assert DetectionClass.FIRE in classes


def test_high_smoke_obscuration_yields_smoke_regardless_of_camera_event():
    snapshot = _snapshot(zones=[_zone(event_type="normal", smoke_pct=40.0)])
    classes = {d.detection_class for d in detect_from_snapshot(snapshot)}
    assert DetectionClass.SMOKE in classes


def test_low_smoke_does_not_trigger_smoke_detection():
    snapshot = _snapshot(zones=[_zone(event_type="normal", smoke_pct=2.0)])
    classes = {d.detection_class for d in detect_from_snapshot(snapshot)}
    assert DetectionClass.SMOKE not in classes


def test_gas_leak_camera_event_yields_gas_leak():
    snapshot = _snapshot(zones=[_zone(event_type="gas_leak_detected", gas_pct_lel=55.0)])
    classes = {d.detection_class for d in detect_from_snapshot(snapshot)}
    assert DetectionClass.GAS_LEAK in classes


def test_high_ambient_gas_yields_gas_leak_even_without_camera_event():
    snapshot = _snapshot(zones=[_zone(event_type="normal", gas_pct_lel=45.0)])
    classes = {d.detection_class for d in detect_from_snapshot(snapshot)}
    assert DetectionClass.GAS_LEAK in classes


def test_ppe_violation_event_yields_exactly_one_ppe_class():
    snapshot = _snapshot(zones=[_zone(event_type="ppe_violation")])
    detections = detect_from_snapshot(snapshot)
    ppe_detections = [d for d in detections if d.detection_class in
                      (DetectionClass.HELMET, DetectionClass.VEST, DetectionClass.GLOVES, DetectionClass.MASK)]
    assert len(ppe_detections) == 1


def test_ppe_violation_class_choice_is_stable_across_calls():
    snapshot = _snapshot(zones=[_zone(zone_id="tank-farm", event_type="ppe_violation")])
    first = detect_from_snapshot(snapshot)
    second = detect_from_snapshot(snapshot)
    first_ppe = next(d for d in first if d.detection_class.value in ("helmet", "vest", "gloves", "mask"))
    second_ppe = next(d for d in second if d.detection_class.value in ("helmet", "vest", "gloves", "mask"))
    assert first_ppe.detection_class == second_ppe.detection_class


def test_person_count_yields_worker_detection():
    snapshot = _snapshot(zones=[_zone(person_count=2)])
    classes = {d.detection_class for d in detect_from_snapshot(snapshot)}
    assert DetectionClass.WORKER in classes
    assert DetectionClass.CROWD not in classes


def test_person_count_above_threshold_also_yields_crowd():
    snapshot = _snapshot(zones=[_zone(person_count=5)])
    classes = {d.detection_class for d in detect_from_snapshot(snapshot)}
    assert DetectionClass.CROWD in classes


def test_equipment_fault_yields_machine_obstruction():
    equipment = [{"equipment_id": "eq-c101", "status": "fault"}, {"equipment_id": "eq-c102", "status": "operational"}]
    snapshot = _snapshot(zones=[_zone(equipment=equipment)])
    detections = [d for d in detect_from_snapshot(snapshot) if d.detection_class == DetectionClass.MACHINE_OBSTRUCTION]
    assert len(detections) == 1
    assert detections[0].object_id == "eq-c101"


def test_forklift_vehicle_yields_forklift_detection():
    vehicles = [{"vehicle_id": "veh-1", "vehicle_type": "forklift", "zone_id": "compressor-house", "status": "moving"}]
    snapshot = _snapshot(vehicles=vehicles)
    detections = [d for d in detect_from_snapshot(snapshot) if d.detection_class == DetectionClass.FORKLIFT]
    assert len(detections) == 1
    assert detections[0].object_id == "veh-1"


def test_tanker_truck_does_not_yield_forklift_detection():
    vehicles = [{"vehicle_id": "veh-3", "vehicle_type": "tanker_truck", "zone_id": "compressor-house", "status": "idle"}]
    snapshot = _snapshot(vehicles=vehicles)
    classes = {d.detection_class for d in detect_from_snapshot(snapshot)}
    assert DetectionClass.FORKLIFT not in classes


def test_collapsed_worker_yields_fallen_worker_not_running():
    workers = [_worker(status="collapsed", heart_rate=150.0)]
    snapshot = _snapshot(workers=workers)
    detections = detect_from_snapshot(snapshot)
    classes = {d.detection_class for d in detections}
    assert DetectionClass.FALLEN_WORKER in classes
    assert DetectionClass.RUNNING_WORKER not in classes
    fallen = next(d for d in detections if d.detection_class == DetectionClass.FALLEN_WORKER)
    assert fallen.object_id == "w-1"


def test_elevated_heart_rate_yields_running_worker():
    workers = [_worker(status="active", heart_rate=135.0)]
    snapshot = _snapshot(workers=workers)
    classes = {d.detection_class for d in detect_from_snapshot(snapshot)}
    assert DetectionClass.RUNNING_WORKER in classes


def test_normal_heart_rate_yields_no_running_worker():
    workers = [_worker(status="active", heart_rate=75.0)]
    snapshot = _snapshot(workers=workers)
    classes = {d.detection_class for d in detect_from_snapshot(snapshot)}
    assert DetectionClass.RUNNING_WORKER not in classes
