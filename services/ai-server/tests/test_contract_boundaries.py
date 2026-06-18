import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

ROOT = Path(__file__).resolve().parents[3]
SERVICE_DIR = ROOT / "services" / "ai-server"

client = TestClient(app)


def test_health_matches_api_contract_fields():
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "ai-server"
    assert body["status"] == "ok"
    assert body["service_version"] == "0.1.0"
    assert body["contract_version"] == "vision-event.v1"
    assert body["model_status"] in {"loaded", "disabled", "error"}
    assert body["models"]["marker"]["status"] == "loaded"
    assert body["models"]["marker"]["name"] == "opencv-marker-detector"
    assert body["models"]["lift_roi"]["status"] in {"loaded", "disabled", "error"}
    assert body["models"]["lift_roi"]["task"] in {"segment", "detect"}
    assert body["source_summary"]["configured"] == 3


def test_sources_match_api_contract_fields_and_do_not_require_ros_imports():
    response = client.get("/api/v1/sources")

    assert response.status_code == 200
    sources = {item["source"]: item for item in response.json()["sources"]}
    assert set(sources) == {"global_cam_01", "tb3_1_picam", "tb3_2_picam"}
    assert sources["global_cam_01"]["kind"] == "global_rgb"
    assert sources["global_cam_01"]["robot_id"] is None
    assert sources["tb3_1_picam"]["kind"] == "robot_pi_camera"
    assert sources["tb3_1_picam"]["robot_id"] == "tb3_1"
    assert all(item["enabled"] is True for item in sources.values())
    assert all(item["status"] in {"online", "stale", "offline", "disabled"} for item in sources.values())


def test_latest_detections_contract_limit_is_bounded_to_50():
    response = client.get("/api/v1/detections/latest", params={"limit": 51})

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["request_id"]


def test_common_error_response_shape_includes_request_id_header():
    response = client.get(
        "/api/v1/detections/latest",
        params={"source": "bad_cam"},
        headers={"X-Request-ID": "req-contract-test"},
    )

    assert response.status_code == 400
    assert response.headers["X-Request-ID"] == "req-contract-test"
    assert response.json() == {
        "error": {
            "code": "BAD_REQUEST",
            "message": "unknown source: bad_cam",
            "details": [],
            "request_id": "req-contract-test",
        }
    }


def test_openapi_exposes_lift_roi_metrics_and_error_contracts():
    schema = app.openapi()

    lift_evaluate = schema["paths"]["/api/v1/lift-roi/evaluate"]["post"]
    lift_evaluate_image = schema["paths"]["/api/v1/lift-roi/evaluate-image"]["post"]
    metrics = schema["paths"]["/api/v1/metrics"]["get"]

    assert lift_evaluate["responses"]["200"]["content"]["application/json"]["schema"][
        "title"
    ] == "SmartFactory LiftRoiEvidence v1"
    assert "400" in lift_evaluate["responses"]
    assert "503" in lift_evaluate_image["responses"]
    assert metrics["responses"]["200"]["content"]["application/json"]["schema"][
        "required"
    ] == ["generated_at", "metrics", "event_store", "frame_store"]


def test_openapi_exposes_lane_b_overlay_debug_surfaces():
    schema = app.openapi()

    assert "/api/v1/vision/synthetic/frame" in schema["paths"]
    assert "/api/v1/vision/worker/status" in schema["paths"]
    assert "/api/v1/vision/worker/tick" in schema["paths"]
    assert "/api/v1/vision/debug/sources" in schema["paths"]
    assert "/api/v1/vision/ros/topics" in schema["paths"]
    assert "/api/v1/vision/streams" in schema["paths"]
    assert "/api/v1/vision/frame" in schema["paths"]
    assert "/api/v1/vision/frame/process" in schema["paths"]
    assert "/api/v1/vision/frame/latest" in schema["paths"]
    assert "/api/v1/vision/frame/latest/image" in schema["paths"]
    assert "/api/v1/vision/overlay/latest" in schema["paths"]
    assert "/api/v1/vision/overlay/latest/image" in schema["paths"]
    assert "/api/v1/vision/stream/{source}.mjpeg" in schema["paths"]
    synthetic_responses = schema["paths"]["/api/v1/vision/synthetic/frame"]["post"][
        "responses"
    ]
    assert "200" in synthetic_responses
    assert "400" in synthetic_responses
    assert "422" in synthetic_responses
    worker_responses = schema["paths"]["/api/v1/vision/worker/tick"]["post"][
        "responses"
    ]
    assert "200" in worker_responses
    assert "400" in worker_responses
    assert "422" in worker_responses
    worker_status_responses = schema["paths"]["/api/v1/vision/worker/status"]["get"][
        "responses"
    ]
    assert "200" in worker_status_responses
    assert "400" in worker_status_responses
    assert "422" in worker_status_responses
    debug_source_responses = schema["paths"]["/api/v1/vision/debug/sources"]["get"][
        "responses"
    ]
    assert "200" in debug_source_responses
    assert "400" in debug_source_responses
    frame_ingest_responses = schema["paths"]["/api/v1/vision/frame"]["post"][
        "responses"
    ]
    assert "200" in frame_ingest_responses
    assert "400" in frame_ingest_responses
    assert "422" in frame_ingest_responses
    frame_process_responses = schema["paths"]["/api/v1/vision/frame/process"]["post"][
        "responses"
    ]
    assert "200" in frame_process_responses
    assert "400" in frame_process_responses
    assert "422" in frame_process_responses
    frame_process_schema = frame_process_responses["200"]["content"]["application/json"][
        "schema"
    ]
    assert "frame_seq" in frame_process_schema["required"]
    assert "event_count" in frame_process_schema["required"]
    latest_frame_responses = schema["paths"]["/api/v1/vision/frame/latest"]["get"][
        "responses"
    ]
    assert "200" in latest_frame_responses
    assert "400" in latest_frame_responses
    assert "404" in latest_frame_responses
    assert "404" in schema["paths"]["/api/v1/vision/frame/latest/image"]["get"]["responses"]
    ros_topic_responses = schema["paths"]["/api/v1/vision/ros/topics"]["get"][
        "responses"
    ]
    assert "200" in ros_topic_responses
    stream_get = schema["paths"]["/api/v1/vision/stream/{source}.mjpeg"]["get"]
    assert "404" in schema["paths"]["/api/v1/vision/overlay/latest"]["get"]["responses"]
    assert "400" in stream_get["responses"]
    params = {param["name"]: param for param in stream_get["parameters"]}
    assert params["max_fps"]["schema"]["default"] == 10
    assert params["max_fps"]["schema"]["minimum"] == 1
    assert params["max_fps"]["schema"]["maximum"] == 30


def test_generated_openapi_artifact_matches_current_app_schema():
    generated_path = ROOT / "docs" / "contracts" / "ai-server-openapi.json"

    generated_schema = json.loads(generated_path.read_text(encoding="utf-8"))

    assert generated_schema == app.openapi()


def test_ai_server_dependencies_exclude_yolo_torch_and_ros2_imports():
    dependency_text = "\n".join(
        (SERVICE_DIR / name).read_text(encoding="utf-8")
        for name in ("requirements.txt", "requirements-dev.txt", "requirements.lock")
    ).lower()
    assert "torch" not in dependency_text
    assert "ultralytics" not in dependency_text
    assert "yolo" not in dependency_text

    app_source = "\n".join(
        path.read_text(encoding="utf-8") for path in (SERVICE_DIR / "app").glob("*.py")
    ).lower()
    assert "rclpy" not in app_source
    assert "sensor_msgs" not in app_source


def test_ai_test_script_clears_ros_pythonpath_contamination():
    script = (ROOT / "scripts" / "test_ai_server.sh").read_text(encoding="utf-8")

    assert "unset PYTHONPATH" in script
    assert "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1" in script
    assert "PYTHONNOUSERSITE=1" in script


def test_ai_server_imports_do_not_require_ros2_yolo_or_torch_modules():
    code = r'''
import importlib
import importlib.abc
import sys

blocked = {"torch", "ultralytics", "rclpy", "sensor_msgs", "cv_bridge"}

class BlockForbidden(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".", 1)[0] in blocked:
            raise AssertionError(f"forbidden import attempted: {fullname}")
        return None

sys.meta_path.insert(0, BlockForbidden())
importlib.import_module("app.detectors")
importlib.import_module("app.model_adapters")
importlib.import_module("app.observability")
importlib.import_module("app.vision_interfaces")
importlib.import_module("app.main")
print("import guard ok")
'''
    import subprocess

    result = subprocess.run(
        [str(SERVICE_DIR / ".venv" / "bin" / "python"), "-c", code],
        cwd=SERVICE_DIR,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "import guard ok" in result.stdout
