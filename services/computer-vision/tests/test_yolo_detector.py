import io
from pathlib import Path

from PIL import Image

from app.vision.schema import DetectionClass
from app.vision.yolo_detector import YoloDetector

# Ships with the ultralytics package itself -- a real photograph containing
# real people, used here so this is a genuine inference test, not one against
# a blank/random frame that would trivially find nothing.
import ultralytics

_ZIDANE_JPG = Path(ultralytics.__file__).resolve().parent / "assets" / "zidane.jpg"


def _read_bytes(path: Path) -> bytes:
    with open(path, "rb") as f:
        return f.read()


def test_real_yolo_detects_people_in_sample_photo():
    detector = YoloDetector()
    image_bytes = _read_bytes(_ZIDANE_JPG)

    detections = detector.detect(image_bytes, camera_id="CAM-TEST", zone_id="test-zone")

    assert len(detections) > 0, "real YOLOv8n should detect at least one person in this sample photo"
    for det in detections:
        assert det.detection_class == DetectionClass.WORKER
        assert det.source == "yolo_inference"
        assert 0.0 <= det.confidence <= 1.0
        bbox = det.bounding_box
        assert 0 <= bbox.x <= 1 and 0 <= bbox.y <= 1
        assert 0 < bbox.width <= 1 and 0 < bbox.height <= 1
        assert det.camera_id == "CAM-TEST"
        assert det.zone_id == "test-zone"


def test_blank_frame_yields_no_detections():
    detector = YoloDetector()
    blank = Image.new("RGB", (640, 480), color=(128, 128, 128))
    buf = io.BytesIO()
    blank.save(buf, format="JPEG")

    detections = detector.detect(buf.getvalue(), camera_id="CAM-TEST")
    assert detections == []
