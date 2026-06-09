from fastapi.testclient import TestClient

from app.main import app

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
    sources = {item["source_id"]: item for item in response.json()["sources"]}
    assert sources["global_cam_01"]["robot_id"] is None
    assert sources["tb3_1_picam"]["robot_id"] == "tb3_1"
    assert sources["tb3_2_picam"]["robot_id"] == "tb3_2"


def test_detect_image_returns_contract_valid_event():
    response = client.post(
        "/api/v1/detect/image",
        data={"source": "tb3_1_picam"},
        files={"image": ("frame.jpg", b"fake-image-bytes", "image/jpeg")},
    )
    assert response.status_code == 200
    event = response.json()["event"]
    assert event["schema_version"] == "vision-event.v1"
    assert event["source"] == "tb3_1_picam"
    assert event["robot_id"] == "tb3_1"
    assert event["depth_median_m"] is None


def test_latest_detections_can_filter_by_source():
    client.post(
        "/api/v1/detect/image",
        data={"source": "global_cam_01"},
        files={"image": ("frame.jpg", b"fake-image-bytes", "image/jpeg")},
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
        files={"image": ("frame.jpg", b"fake", "image/jpeg")},
    )
    assert response.status_code == 400
