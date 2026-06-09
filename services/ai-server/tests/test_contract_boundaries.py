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
