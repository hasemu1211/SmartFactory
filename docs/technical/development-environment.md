# SmartFactory Development Environment

- Date: 2026-06-09
- Updated: 2026-06-11
- Primary repository: `/home/codelab/Desktop/Project/SmartFactory`
- ROS2 workspace: `/home/codelab/turtlebot3_ws`
- ROS2 distro detected: Jazzy at `/opt/ros/jazzy`

## Git status

The SmartFactory repository is initialized on branch `main`.

Current important commits:

```text
87da937 Record ROS2 bringup scaffold validation
def836f Add ROS2-friendly environment plan
a841cd9 Plan AI server API contract baseline
```

SmartFactory ROS2 runtime now defaults to `/home/codelab/turtlebot3_ws`.
`smartfactory_bringup` lives directly under that workspace, and
`smartfactory_perception_ros` is symlinked from the tracked repo source
`ros2/smartfactory_perception_ros` into `/home/codelab/turtlebot3_ws/src`.
The old active bringup copy under `/home/codelab/ros2_ws/src` was moved aside as
`smartfactory_bringup.migrated-backup-20260611`.

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
./scripts/ai/run_ai_server.sh --reload
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
python3 scripts/validate/validate_contracts.py
```

This validates all `docs/contracts/fixtures/*.json` against
`docs/contracts/vision-event.schema.json` plus extra MVP1 policy checks.

## ROS2 bringup package

The launch scaffold lives in:

```text
/home/codelab/turtlebot3_ws/src/smartfactory_bringup
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

1. Confirm real camera source bringup/relay for `global_cam_01`, `tb3_1_picam`, and `tb3_2_picam`.
2. Add source health/staleness reporting for camera snapshots.
3. Add ROS2 `smartfactory_ros_bridge` package once WMS task/state endpoints are ready.
4. Extend beyond OpenCV ArUco-only only after a new scope decision: QR/AprilTag or YOLO candidate detection behind the existing `/api/v1/detect/image` endpoint.
