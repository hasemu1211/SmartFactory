#!/usr/bin/env python3
from __future__ import annotations

import configparser
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCKERFILE = ROOT / "services/ai-server/Dockerfile"
COMPOSE = ROOT / "docker-compose.ai-server.yml"
SYSTEMD_UNIT = ROOT / "ops/systemd/smartfactory-ai-server.service"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def validate_dockerfile() -> None:
    text = DOCKERFILE.read_text(encoding="utf-8")
    require("FROM python:3.12-slim" in text, "Dockerfile must use Python runtime image")
    require("requirements.lock" in text, "Dockerfile must install pinned requirements.lock")
    require("/app/docs/contracts" in text, "Dockerfile must include contract schemas")
    forbidden = ["rclpy", "sensor_msgs", "ros:jazzy", "turtlebot3"]
    lowered = text.lower()
    for token in forbidden:
        require(token not in lowered, f"Dockerfile must not depend on ROS runtime: {token}")


def validate_compose() -> None:
    text = COMPOSE.read_text(encoding="utf-8")
    require("services:" in text, "compose must define services")
    require("ai-server:" in text, "compose must define ai-server service")
    require("services/ai-server/Dockerfile" in text, "compose must point to AI Server Dockerfile")
    require("/app/config/perception:ro" in text, "compose must mount perception config read-only")
    require("/api/v1/health" in text, "compose healthcheck must use AI health endpoint")
    require("VISION_MODEL_TASK" in text, "compose must expose optional model task config")
    require("VISION_MODEL_PATH" in text, "compose must expose optional model path config")
    require(
        "MAIN_SERVER_URL: ${MAIN_SERVER_URL:-http://smartfactory-main.local:8088}" in text,
        "compose must default Main callback URL to current handoff port",
    )

    docker = shutil.which("docker")
    if docker is None:
        print("SKIP docker compose config: docker CLI not found")
        return
    result = subprocess.run(
        [docker, "compose", "-f", str(COMPOSE), "config", "--quiet"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    require(
        result.returncode == 0,
        "docker compose config failed:\n" + result.stdout + result.stderr,
    )


def validate_systemd_unit() -> None:
    parser = configparser.ConfigParser(strict=True, interpolation=None)
    parser.optionxform = str
    with SYSTEMD_UNIT.open("r", encoding="utf-8") as f:
        parser.read_file(f)
    require(parser.has_section("Unit"), "systemd unit missing [Unit]")
    require(parser.has_section("Service"), "systemd unit missing [Service]")
    require(parser.has_section("Install"), "systemd unit missing [Install]")
    service = parser["Service"]
    require(
        service.get("ExecStart", "").endswith("scripts/run_ai_server.sh"),
        "systemd unit must launch scripts/run_ai_server.sh",
    )
    require(service.get("Restart") == "on-failure", "systemd unit must restart on failure")
    require(service.get("NoNewPrivileges") == "true", "systemd unit must set NoNewPrivileges")
    require(service.get("ProtectSystem") == "full", "systemd unit must set ProtectSystem=full")
    environment = service.get("Environment", "")
    require("VISION_MODEL_TASK=segment" in environment, "systemd unit must default to segment task")
    require("VISION_MODEL_PATH=" in environment, "systemd unit must expose optional model path")
    require(
        "MAIN_SERVER_URL=http://smartfactory-main.local:8088" in environment,
        "systemd unit must default Main callback URL to current handoff port",
    )


def main() -> int:
    try:
        validate_dockerfile()
        validate_compose()
        validate_systemd_unit()
    except Exception as exc:  # noqa: BLE001 - command-line validator reports all failures simply
        print(f"Deployment asset validation failed: {exc}", file=sys.stderr)
        return 1
    print("Deployment assets validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
