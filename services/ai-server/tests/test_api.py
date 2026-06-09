from __future__ import annotations

import cv2
import numpy as np
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _png_bytes(image: np.ndarray) -> bytes:
    ok, encoded = cv2.imencode(".png", image)
    assert ok
    return encoded.tobytes()


def _blank_frame(width: int = 160, height: int = 120) -> bytes:
    return _png_bytes(np.full((height, width, 3), 255, dtype=np.uint8))


def _aruco_marker_frame(marker_id: int = 7, marker_size: int = 120, margin: int = 40) -> bytes:
    aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    if hasattr(cv2.aruco, "generateImageMarker"):
        marker = cv2.aruco.generateImageMarker(aruco_dict, marker_id, marker_size)
    else:
        marker = np.zeros((marker_size, marker_size), dtype=np.uint8)
        cv2.aruco.drawMarker(aruco_dict, marker_id, marker_size, marker, 1)

    canvas = np.full((marker_size + margin * 2, marker_size + margin * 2), 255, dtype=np.uint8)
    canvas[margin : margin + marker_size, margin : margin + marker_size] = marker
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


def test_detect_image_returns_contract_valid_aruco_event():
    response = client.post(
        "/api/v1/detect/image",
        data={"source": "tb3_1_picam"},
        files={"image": ("marker.png", _aruco_marker_frame(marker_id=7), "image/png")},
    )
    assert response.status_code == 200
    body = response.json()
    event = body["event"]
    assert body["events"] == [event]
    assert event["schema_version"] == "vision-event.v1"
    assert event["source"] == "tb3_1_picam"
    assert event["robot_id"] == "tb3_1"
    assert event["event_kind"] == "CONFIRMED"
    assert event["class_name"] == "aruco_marker"
    assert event["marker_id"] == "7"
    assert event["wms_hint"] == "TAG_DETECTED"
    assert event["depth_median_m"] is None
    assert event["metadata"]["image_width"] == 200
    assert event["metadata"]["image_height"] == 200
    assert event["bbox_xyxy"][0] < event["bbox_xyxy"][2]
    assert event["bbox_xyxy"][1] < event["bbox_xyxy"][3]


def test_detect_image_returns_unknown_candidate_for_decoded_frame_without_marker():
    response = client.post(
        "/api/v1/detect/image",
        data={"source": "global_cam_01"},
        files={"image": ("blank.png", _blank_frame(), "image/png")},
    )
    assert response.status_code == 200
    event = response.json()["event"]
    assert event["source"] == "global_cam_01"
    assert event["robot_id"] is None
    assert event["event_kind"] == "CANDIDATE"
    assert event["class_name"] == "unknown"
    assert event["confidence"] == 0.0
    assert event["marker_id"] is None
    assert event["bbox_xyxy"] == [0, 0, 160, 120]


def test_detect_image_rejects_malformed_image():
    response = client.post(
        "/api/v1/detect/image",
        data={"source": "tb3_1_picam"},
        files={"image": ("frame.jpg", b"fake-image-bytes", "image/jpeg")},
    )
    assert response.status_code == 400


def test_latest_detections_can_filter_by_source():
    client.post(
        "/api/v1/detect/image",
        data={"source": "global_cam_01"},
        files={"image": ("frame.png", _blank_frame(), "image/png")},
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
        files={"image": ("frame.png", _blank_frame(), "image/png")},
    )
    assert response.status_code == 400
