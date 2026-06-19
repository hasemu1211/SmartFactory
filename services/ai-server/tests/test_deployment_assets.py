from __future__ import annotations

import configparser
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]


def test_ai_server_docker_compose_declares_isolated_api_service():
    compose = yaml.safe_load((ROOT / "docker-compose.ai-server.yml").read_text(encoding="utf-8"))
    service = compose["services"]["ai-server"]

    assert service["build"]["dockerfile"] == "services/ai-server/Dockerfile"
    assert service["environment"]["AI_SERVER_HOST"] == "0.0.0.0"
    assert service["environment"]["ARUCO_POSE_PROFILES_PATH"] == (
        "/app/config/perception/aruco_pose_profiles.example.json"
    )
    assert service["environment"]["VISION_MODEL_TASK"] == "${VISION_MODEL_TASK:-segment}"
    assert service["environment"]["VISION_MODEL_DEVICE"] == "${VISION_MODEL_DEVICE:-cpu}"
    assert service["environment"]["MAIN_SERVER_URL"] == (
        "${MAIN_SERVER_URL:-http://smartfactory-main.local:8088}"
    )
    assert "./config/perception:/app/config/perception:ro" in service["volumes"]
    assert "/api/v1/health" in " ".join(service["healthcheck"]["test"])


def test_ai_server_docker_compose_does_not_publish_ros_or_internal_stream_ports():
    compose = yaml.safe_load((ROOT / "docker-compose.ai-server.yml").read_text(encoding="utf-8"))
    ports = compose["services"]["ai-server"].get("ports", [])
    published = "\n".join(str(port) for port in ports)

    assert "${AI_SERVER_PORT:-8100}:8100" in ports
    for forbidden_port in ("9090", "11311", "11811", "18090", "18091", "7400", "7600"):
        assert forbidden_port not in published


def test_ai_server_dockerfile_keeps_service_independent_from_ros_runtime():
    text = (ROOT / "services/ai-server/Dockerfile").read_text(encoding="utf-8").lower()

    assert "from python:3.12-slim" in text
    assert "requirements.lock" in text
    assert "/app/docs/contracts" in text
    assert "rclpy" not in text
    assert "sensor_msgs" not in text
    assert "turtlebot3" not in text


def test_systemd_unit_launches_existing_isolated_runner():
    parser = configparser.ConfigParser(strict=True, interpolation=None)
    parser.optionxform = str
    with (ROOT / "ops/systemd/smartfactory-ai-server.service").open("r", encoding="utf-8") as f:
        parser.read_file(f)

    assert parser["Service"]["WorkingDirectory"] == str(ROOT)
    assert parser["Service"]["ExecStart"] == str(ROOT / "scripts/ai/run_ai_server.sh")
    assert "PYTHONPATH=" in parser["Service"]["Environment"]
    assert "VISION_MODEL_TASK=segment" in parser["Service"]["Environment"]
    assert "MAIN_SERVER_URL=http://smartfactory-main.local:8088" in parser["Service"]["Environment"]
    assert parser["Service"]["Restart"] == "on-failure"
    assert parser["Service"]["NoNewPrivileges"] == "true"


def test_deployment_asset_validator_passes():
    result = subprocess.run(
        ["python3", "scripts/validate/validate_deployment_assets.py"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "Deployment assets validated." in result.stdout
