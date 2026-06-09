import cv2
import numpy as np
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _png_bytes(image: np.ndarray) -> bytes:
    ok, encoded = cv2.imencode(".png", image)
    assert ok
    return encoded.tobytes()




def _aruco_png_bytes(marker_id: int = 7) -> bytes:
    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    marker = cv2.aruco.generateImageMarker(dictionary, marker_id, 96)
    canvas = np.full((160, 160), 255, dtype=np.uint8)
    canvas[32:128, 32:128] = marker
    return _png_bytes(cv2.cvtColor(canvas, cv2.COLOR_GRAY2BGR))

def test_health_exposes_canonical_sources():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["schema_version"] == "vision-event.v1"
    assert body["sources"] == ["global_cam_01", "tb3_1_picam", "tb3_2_picam"]


def test_sources_include_robot_mapping():
    response = client.get("/api/v1/sources")
    assert response.status_code == 200
    sources = {item["source_id"]: item for item in response.json()["sources"]}
    assert sources["global_cam_01"]["robot_id"] is None
    assert sources["tb3_1_picam"]["robot_id"] == "tb3_1"
    assert sources["tb3_2_picam"]["robot_id"] == "tb3_2"


def test_detect_image_returns_empty_events_for_frame_without_markers():
    blank_frame = np.full((64, 64, 3), 255, dtype=np.uint8)
    response = client.post(
        "/api/v1/detect/image",
        data={"source": "tb3_1_picam"},
        files={"image": ("frame.png", _png_bytes(blank_frame), "image/png")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "tb3_1_picam"
    assert body["emitted"] is False
    assert len(body["events"]) == 1
    event = body["events"][0]
    assert event["schema_version"] == "vision-event.v1"
    assert event["event_kind"] == "CONFIRMED"
    assert event["class_name"] == "aruco_marker"
    assert event["marker_id"] == "ARUCO_4X4_50_7"
    assert event["source"] == "tb3_1_picam"
    assert event["robot_id"] == "tb3_1"
    assert event["depth_median_m"] is None


def test_detect_image_accepts_emit_flag_without_changing_mock_dispatch():
    response = client.post(
        "/api/v1/detect/image",
        data={"source": "tb3_2_picam", "emit": "true"},
        files={"image": ("frame.jpg", b"fake-image-bytes", "image/jpeg")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "tb3_2_picam"
    assert body["emitted"] is True
    assert len(body["events"]) == 1
    assert body["events"][0]["source"] == "tb3_2_picam"


def test_latest_detections_can_filter_by_source():
    client.post(
        "/api/v1/detect/image",
        data={"source": "global_cam_01"},
        files={"image": ("aruco.png", _aruco_png_bytes(8), "image/png")},
    )
    response = client.get("/api/v1/detections/latest", params={"source": "global_cam_01", "limit": 5})
    assert response.status_code == 200
    events = response.json()["events"]
    assert events
    assert all(event["source"] == "global_cam_01" for event in events)


def test_unknown_source_rejected():
    response = client.post(
        "/api/v1/detect/image",
        data={"source": "bad_cam"},
        files={"image": ("frame.png", _png_bytes(np.full((32, 32, 3), 255, dtype=np.uint8)), "image/png")},
    )
    assert response.status_code == 400
