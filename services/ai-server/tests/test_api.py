from fastapi.testclient import TestClient

import app.main as main_module
from app.config import get_settings
from app.main import app
from generated_fixtures import aruco_png_bytes, blank_png_bytes

client = TestClient(app)


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
    sources = {item["source"]: item for item in response.json()["sources"]}
    assert sources["global_cam_01"]["robot_id"] is None
    assert sources["tb3_1_picam"]["robot_id"] == "tb3_1"
    assert sources["tb3_2_picam"]["robot_id"] == "tb3_2"


def test_detect_image_returns_empty_events_for_frame_without_markers():
    response = client.post(
        "/api/v1/detect/image",
        data={"source": "tb3_1_picam"},
        files={"image": ("frame.png", blank_png_bytes(), "image/png")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "tb3_1_picam"
    assert body["emitted"] is False
    assert body["emit_disabled"] is False
    assert body["emit_results"] == []
    assert body["events"] == []


def test_detect_image_returns_contract_valid_marker_event():
    response = client.post(
        "/api/v1/detect/image",
        data={"source": "tb3_1_picam"},
        files={"image": ("aruco.png", aruco_png_bytes(), "image/png")},
    )
    assert response.status_code == 200
    events = response.json()["events"]
    assert len(events) == 1
    event = events[0]
    assert event["schema_version"] == "vision-event.v1"
    assert event["event_kind"] == "CONFIRMED"
    assert event["class_name"] == "aruco_marker"
    assert event["marker_id"] == "ARUCO_4X4_50_7"
    assert event["source"] == "tb3_1_picam"
    assert event["robot_id"] == "tb3_1"
    assert event["depth_median_m"] is None


def test_detect_image_emit_flag_is_disabled_by_default(monkeypatch):
    async def fail_if_called(*_, **__):
        raise AssertionError("WMS emit should not be called when disabled")

    monkeypatch.setattr(main_module, "emit_vision_events", fail_if_called)
    response = client.post(
        "/api/v1/detect/image",
        data={"source": "tb3_2_picam", "emit": "true"},
        files={"image": ("aruco.png", aruco_png_bytes(9), "image/png")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "tb3_2_picam"
    assert body["emitted"] is False
    assert body["emit_disabled"] is True
    assert body["emit_results"] == []
    assert len(body["events"]) == 1
    assert body["events"][0]["source"] == "tb3_2_picam"


def test_detect_image_emits_to_wms_when_enabled(monkeypatch):
    monkeypatch.setenv("WMS_EMIT_ENABLED", "true")
    get_settings.cache_clear()

    async def fake_emit(events, *, settings):
        assert settings.wms_emit_enabled is True
        return [
            {
                "event_id": event["event_id"],
                "attempted": True,
                "ok": True,
                "status_code": 202,
                "error": None,
                "response": {
                    "accepted": True,
                    "duplicate": False,
                    "wms_processing_status": "queued",
                },
            }
            for event in events
        ]

    monkeypatch.setattr(main_module, "emit_vision_events", fake_emit)
    try:
        response = client.post(
            "/api/v1/detect/image",
            data={"source": "tb3_1_picam", "emit": "true"},
            files={"image": ("aruco.png", aruco_png_bytes(11), "image/png")},
        )
    finally:
        get_settings.cache_clear()

    assert response.status_code == 200
    body = response.json()
    assert body["emitted"] is True
    assert body["emit_disabled"] is False
    assert len(body["events"]) == 1
    assert len(body["emit_results"]) == 1
    assert body["emit_results"][0]["event_id"] == body["events"][0]["event_id"]
    assert body["emit_results"][0]["status_code"] == 202


def test_detect_image_reports_wms_failure_without_failing_detection(monkeypatch):
    monkeypatch.setenv("WMS_EMIT_ENABLED", "true")
    get_settings.cache_clear()

    async def fake_emit(events, *, settings):
        return [
            {
                "event_id": event["event_id"],
                "attempted": True,
                "ok": False,
                "status_code": 503,
                "error": "WMS ingest returned HTTP 503",
                "response": None,
            }
            for event in events
        ]

    monkeypatch.setattr(main_module, "emit_vision_events", fake_emit)
    try:
        response = client.post(
            "/api/v1/detect/image",
            data={"source": "tb3_1_picam", "emit": "true"},
            files={"image": ("aruco.png", aruco_png_bytes(12), "image/png")},
        )
    finally:
        get_settings.cache_clear()

    assert response.status_code == 200
    body = response.json()
    assert body["emitted"] is False
    assert len(body["events"]) == 1
    assert body["emit_results"][0]["ok"] is False
    assert body["emit_results"][0]["status_code"] == 503




def test_detect_image_can_emit_optional_aruco_pose_estimate():
    response = client.post(
        "/api/v1/detect/image",
        data={
            "source": "tb3_1_picam",
            "marker_size_m": "0.08",
            "camera_fx": "600",
            "camera_fy": "600",
            "camera_cx": "80",
            "camera_cy": "80",
            "camera_dist_coeffs": "0,0,0,0,0",
        },
        files={"image": ("aruco.png", aruco_png_bytes(), "image/png")},
    )

    assert response.status_code == 200
    events = response.json()["events"]
    assert len(events) == 1
    pose = events[0]["pose_estimate"]
    assert pose is not None
    assert pose["method"] == "ARUCO_POSE"
    assert abs(pose["x"]) < 0.02
    assert 0.45 < pose["y"] < 0.60
    assert abs(pose["yaw"]) < 0.10
    assert 0.0 <= pose["confidence"] <= 1.0


def test_detect_image_rejects_partial_aruco_pose_calibration():
    response = client.post(
        "/api/v1/detect/image",
        data={"source": "tb3_1_picam", "marker_size_m": "0.08"},
        files={"image": ("aruco.png", aruco_png_bytes(), "image/png")},
    )

    assert response.status_code == 400
    assert "ArUco pose requires" in response.json()["detail"]


def test_detect_image_rejects_invalid_pose_numbers():
    response = client.post(
        "/api/v1/detect/image",
        data={
            "source": "tb3_1_picam",
            "marker_size_m": "-0.08",
            "camera_fx": "600",
            "camera_fy": "600",
            "camera_cx": "80",
            "camera_cy": "80",
        },
        files={"image": ("aruco.png", aruco_png_bytes(), "image/png")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "marker_size_m must be positive"


def test_invalid_image_rejected():
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
        files={"image": ("aruco.png", aruco_png_bytes(8), "image/png")},
    )
    response = client.get(
        "/api/v1/detections/latest", params={"source": "global_cam_01", "limit": 5}
    )
    assert response.status_code == 200
    events = response.json()["events"]
    assert events
    assert all(event["source"] == "global_cam_01" for event in events)


def test_unknown_source_rejected():
    response = client.post(
        "/api/v1/detect/image",
        data={"source": "bad_cam"},
        files={
            "image": ("frame.png", blank_png_bytes(width=32, height=32), "image/png")
        },
    )
    assert response.status_code == 400
