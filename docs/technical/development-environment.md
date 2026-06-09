# SmartFactory Development Environment

- Date: 2026-06-09
- Primary repository: `/home/codelab/Desktop/Project/SmartFactory`
- ROS2 workspace: `/home/codelab/ros2_ws`
- ROS2 distro detected: Jazzy at `/opt/ros/jazzy`

## Git status

The SmartFactory repository is initialized on branch `main`.

Current important commits:

```text
87da937 Record ROS2 bringup scaffold validation
def836f Add ROS2-friendly environment plan
a841cd9 Plan AI server API contract baseline
```

The ROS2 workspace `/home/codelab/ros2_ws` is also a Git repository. The initial
SmartFactory bringup package was committed there as:

```text
8d9a28e Add SmartFactory ROS2 bringup scaffold
```

Note: `/home/codelab/ros2_ws` already had unrelated dirty/untracked files before
this work. Keep SmartFactory bringup changes in small commits to avoid mixing old
workspace cleanup with project implementation.

## AI Server environment

The AI Server uses a local venv under `services/ai-server/.venv`. This directory
is ignored by Git. Dependency versions are frozen into:

```text
services/ai-server/requirements.lock
```

Setup:

```bash
cd /home/codelab/Desktop/Project/SmartFactory
make ai-setup
```

Run API server:

```bash
make ai-run
# or
./scripts/run_ai_server.sh --reload
```

Health check:

```bash
curl http://127.0.0.1:8100/api/v1/health
```

Test:

```bash
make ai-test
```

`make ai-test` intentionally unsets ROS2 `PYTHONPATH` before pytest so ROS2
pytest plugins do not leak into the API service tests.

## Contract validation

```bash
make contracts
# or
python3 scripts/validate_contracts.py
```

This validates all `docs/contracts/fixtures/*.json` against
`docs/contracts/vision-event.schema.json` plus extra MVP1 policy checks.

## ROS2 bringup package

The launch scaffold lives in:

```text
/home/codelab/ros2_ws/src/smartfactory_bringup
```

Build:

```bash
make ros-build-bringup
```

Smoke launch with all optional hardware/services disabled:

```bash
make ros-launch-smoke
```

When hardware/services are ready, enable flags one by one:

```bash
ros2 launch smartfactory_bringup central_pc_bringup.launch.py \
  use_global_camera:=true \
  use_robot_picams:=false \
  use_ai_server:=true \
  use_wms_bridge:=false \
  use_nav2:=false
```

## Naming contract

Do not rename these without updating API schema, ROS2 config, and GUI/WMS code together:

- `global_cam_01` -> `/global_camera/image_raw`
- `tb3_1_picam` -> `/tb3_1/pi_camera/image_raw`
- `tb3_2_picam` -> `/tb3_2/pi_camera/image_raw`
- Robot IDs: `tb3_1`, `tb3_2`
- LiDAR: LDS-03

## Next implementation branch suggestion

```bash
git checkout -b feature/ai-server-marker-detection
```

Recommended next tasks:

1. Add real OpenCV ArUco/QR detection behind the existing `/api/v1/detect/image` endpoint.
2. Add camera-frame adapter or snapshot path without making AI Server directly depend on ROS2.
3. Add WMS ingest client for `POST {MAIN_SERVER_URL}/api/v1/vision/events`.
4. Add ROS2 `smartfactory_ros_bridge` package once WMS task/state endpoints are ready.
