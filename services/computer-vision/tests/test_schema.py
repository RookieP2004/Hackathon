from app.vision.schema import CAPABILITY_OF, FAST_PATH_CLASSES, BoundingBox, Detection, DetectionClass

REQUESTED_CLASSES = {
    "helmet", "vest", "gloves", "mask", "worker", "forklift", "fire", "smoke",
    "gas_leak", "fallen_worker", "running_worker", "crowd", "machine_obstruction",
}


def test_all_thirteen_requested_classes_are_present():
    assert {c.value for c in DetectionClass} == REQUESTED_CLASSES


def test_every_class_has_a_capability_mapping():
    assert set(CAPABILITY_OF.keys()) == set(DetectionClass)


def test_fast_path_classes_are_a_subset_of_detection_classes():
    assert FAST_PATH_CLASSES <= set(DetectionClass)


def test_detection_to_dict_round_trips_bounding_box():
    det = Detection(
        detection_class=DetectionClass.FIRE,
        confidence=0.876543,
        bounding_box=BoundingBox(x=0.1, y=0.2, width=0.3, height=0.4),
        camera_id="CAM-01",
        zone_id="boiler-room",
    )
    payload = det.to_dict()
    assert payload["detection_class"] == "fire"
    assert payload["confidence"] == 0.8765
    assert payload["bounding_box"] == {"x": 0.1, "y": 0.2, "width": 0.3, "height": 0.4}
    assert payload["source"] == "simulated"
