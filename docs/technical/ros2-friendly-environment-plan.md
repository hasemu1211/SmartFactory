# SmartFactory ROS2-Friendly Environment Plan

- Date: 2026-06-09
- Scope: MVP1 Central PC bringup for WMS-lite, GUI, ROS2/Nav2, LDS-03, camera sources, and separate AI Server process/container.
- Status: Planning baseline updated 2026-06-11. `smartfactory_bringup` runs from `/home/codelab/turtlebot3_ws/src`; raw-image `smartfactory_perception_ros` snapshot adapter source is tracked under `ros2/smartfactory_perception_ros` and symlinked into the TurtleBot3 workspace.

## 1. Design goals

1. Keep the AI Server API-first and portable. For MVP1 it runs on the Central PC, but it must be movable to a separate AI Server PC by changing environment variables and URLs.
2. Keep ROS2 responsibilities explicit: ROS2 launches sensors, robot namespaces, LDS-03/Nav2, and bridge nodes; the AI Server exposes HTTP APIs and emits normalized `VisionEvent` evidence.
3. Keep Main Server/WMS-lite as the source of truth. Vision events are evidence, not direct robot commands.
4. Make camera and robot naming deterministic so AI/WMS/GUI teams can merge without naming drift.
5. Keep reproducibility stable with ROS2 workspace dependencies, AI Server Python lockfiles, and small launch/config files committed to Git.

## 2. Recommended workspace layout

Use `/home/codelab/turtlebot3_ws` as the ROS2 runtime workspace so TurtleBot3/Nav2/LDS-03 packages and SmartFactory bringup share one overlay. Keep this SmartFactory repository as the contract/planning source and track new SmartFactory-owned ROS packages under `ros2/`, symlinked into the workspace when needed.

```text
/home/codelab/turtlebot3_ws/
  src/
    smartfactory_bringup/             # launch-only package for Central PC and robot bringup
      package.xml
      CMakeLists.txt
      launch/
        central_pc_bringup.launch.py  # top-level MVP1 launch
        perception_sources.launch.py  # global cam + robot Pi camera topics/bridges
        ai_server.launch.py           # ExecuteProcess/container boundary for AI Server
        wms_bridge.launch.py          # ROS <-> Main Server/WMS bridge nodes
        nav2_fleet.launch.py          # per-robot Nav2 include placeholders
      config/
        cameras.yaml
        ai_server.env.example
        ros2_network.env.example
        namespaces.yaml
      scripts/
        check_devices.sh
        setup_ros2_env.sh

    smartfactory_ros_bridge/           # rclpy bridge package; no heavy AI model dependency
      package.xml
      setup.py
      smartfactory_ros_bridge/
        __init__.py
        vision_event_publisher.py      # optional: republishes WMS/AI evidence to ROS topic
        robot_state_reporter.py        # ROS robot status -> WMS/Main API
        task_dispatcher.py             # WMS/Main task -> Nav2 action interface
      test/
        test_contract_mapping.py

    smartfactory_perception_ros/        # thin ROS-side camera adapters only
      package.xml
      setup.py
      smartfactory_perception_ros/
        __init__.py
        camera_health_monitor.py        # publishes source health/stale status
        image_snapshot_client.py        # raw Image snapshot adapter to AI Server
      # v1 source is tracked in SmartFactory repo at ros2/smartfactory_perception_ros
      # and symlinked into /home/codelab/turtlebot3_ws/src

    smartfactory_msgs/                  # optional once message contracts are stable
      package.xml
      CMakeLists.txt
      msg/
        VisionEvent.msg                 # optional mirror of JSON contract for ROS tooling
        RobotAvailability.msg
      srv/
        SubmitTask.srv
```

### Package boundary rule

- `services/ai-server` should not depend on `rclpy` for MVP1 unless a deliberate ROS bridge process is introduced.
- `smartfactory_ros_bridge` may depend on `rclpy`, `nav2_msgs`, `geometry_msgs`, and HTTP clients, but not on Torch/YOLO.
- `smartfactory_perception_ros` may depend on `rclpy`, `sensor_msgs`, `cv_bridge`, OpenCV, and `python3-requests`, but model inference stays in the AI Server. V1 supports raw `sensor_msgs/Image`; add compressed transport later only if deployment needs it.
- `smartfactory_msgs` is optional. The canonical cross-team payload remains `docs/contracts/vision-event.schema.json`.

## 3. Canonical ROS names for MVP1

| Purpose | Canonical name/topic | Notes |
| --- | --- | --- |
| Global RGB camera | `/global_camera/image_raw` | Source ID `global_cam_01` |
| Global camera info | `/global_camera/camera_info` | Calibrate before demo if possible |
| Robot 1 Pi Camera | `/tb3_1/pi_camera/image_raw` | Source ID `tb3_1_picam`, `robot_id=tb3_1` |
| Robot 2 Pi Camera | `/tb3_2/pi_camera/image_raw` | Source ID `tb3_2_picam`, `robot_id=tb3_2` |
| Robot 1 LiDAR | `/tb3_1/scan` | LDS-03 |
| Robot 2 LiDAR | `/tb3_2/scan` | LDS-03 |
| Robot 1 Nav2 action namespace | `/tb3_1/navigate_to_pose` | WMS task bridge calls Nav2 |
| Robot 2 Nav2 action namespace | `/tb3_2/navigate_to_pose` | WMS task bridge calls Nav2 |
| Vision events in ROS, optional | `/smartfactory/vision/events` | Prefer JSON string or `VisionEvent.msg` after contract freeze |
| Robot state report | `/smartfactory/robots/state` | Optional aggregate topic for GUI/debug |

## 4. Launch layering

### `central_pc_bringup.launch.py`

Top-level Central PC launch. It should include the other launch files and expose only high-level arguments.

Recommended launch arguments:

```text
use_global_camera:=true
use_robot_picams:=true
use_ai_server:=true
use_wms_bridge:=true
use_nav2:=true
use_ai_snapshot_clients:=false
robot_names:=[tb3_1,tb3_2]
ai_server_host:=127.0.0.1
ai_server_port:=8100
main_server_url:=http://127.0.0.1:8000
camera_config:=<pkg_share>/config/cameras.yaml
```

Startup order:

1. ROS2 environment/network variables loaded.
2. Camera/device checks run.
3. Sensor/camera launch starts.
4. Nav2/fleet launch starts.
5. Main/WMS bridge starts.
6. AI Server process/container starts or is health-checked.
7. Optional GUI/debug tools start.

### `perception_sources.launch.py`

Responsibilities:

- Start or include global RGB camera driver.
- Start or subscribe to robot Pi Camera streams under robot namespaces.
- Publish source health for `global_cam_01`, `tb3_1_picam`, and `tb3_2_picam`.
- Keep camera topics stable even if the underlying driver changes.

Driver choice should be deployment-specific:

- USB/global camera on Central PC: `v4l2_camera` or `usb_cam`.
- Robot Pi Camera: native Pi camera stack or compressed stream relay to Central PC.
- Browser preview: use compressed image or web bridge, not raw unbounded streaming.

### `ai_server.launch.py`

The AI Server is not a ROS node in MVP1. Launch it as a separate process or container boundary.

Process mode example responsibilities:

```text
ExecuteProcess(
  cmd=["uv", "run", "uvicorn", "app.main:app", "--host", ai_server_host, "--port", ai_server_port],
  cwd="<smartfactory_repo>/services/ai-server",
  env={
    "MAIN_SERVER_URL": main_server_url,
    "CAMERA_SOURCES": "global_cam_01,tb3_1_picam,tb3_2_picam",
    "ROS_IMAGE_TOPICS": "/global_camera/image_raw,/tb3_1/pi_camera/image_raw,/tb3_2/pi_camera/image_raw"
  }
)
```

Container mode can be added later with Docker Compose. Keep the same environment variable names in both modes.

### `wms_bridge.launch.py`

Responsibilities:

- Convert WMS/Main tasks into ROS2/Nav2 actions.
- Report robot availability/state back to WMS/Main API.
- Optionally republish `VisionEvent` evidence to ROS debug topic.
- Never let AI Server directly command `/cmd_vel` or emergency behavior.

### `nav2_fleet.launch.py`

Responsibilities:

- Include per-robot TurtleBot3/Nav2 launch files using namespaces `tb3_1` and `tb3_2`.
- Use LDS-03 scan topics.
- Keep maps, robot poses, and goals namespaced.
- Support simulated mode first if physical robots are unavailable.

## 5. Configuration files

### `config/cameras.yaml`

```yaml
sources:
  - source_id: global_cam_01
    robot_id: null
    ros_topic: /global_camera/image_raw
    frame_id: global_camera_frame
    role: global_overview
    stale_timeout_sec: 2.0

  - source_id: tb3_1_picam
    robot_id: tb3_1
    ros_topic: /tb3_1/pi_camera/image_raw
    frame_id: tb3_1_pi_camera_frame
    role: robot_front
    stale_timeout_sec: 2.0

  - source_id: tb3_2_picam
    robot_id: tb3_2
    ros_topic: /tb3_2/pi_camera/image_raw
    frame_id: tb3_2_pi_camera_frame
    role: robot_front
    stale_timeout_sec: 2.0
```

### `config/ros2_network.env.example`

```bash
ROS_DISTRO=jazzy
ROS_DOMAIN_ID=42
# Prefer one middleware project-wide after testing. Do not mix silently.
RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
# If using CycloneDDS, add CYCLONEDDS_URI after the network topology is fixed.
```

### `config/ai_server.env.example`

```bash
AI_SERVER_HOST=127.0.0.1
AI_SERVER_PORT=8100
MAIN_SERVER_URL=http://127.0.0.1:8000
CAMERA_SOURCES=global_cam_01,tb3_1_picam,tb3_2_picam
ROS_IMAGE_TOPICS=/global_camera/image_raw,/tb3_1/pi_camera/image_raw,/tb3_2/pi_camera/image_raw
VISION_EVENT_SCHEMA_VERSION=vision-event.v1
MODEL_PATH=models/mvp1-detector.pt
```

## 6. Dependency strategy

### ROS2 dependencies

Install with `rosdep` where possible:

```bash
cd /home/codelab/turtlebot3_ws
rosdep install --from-paths src --ignore-src -r -y
colcon build --symlink-install
```

Likely ROS packages:

- `rclpy`, `launch`, `launch_ros`
- `sensor_msgs`, `geometry_msgs`, `nav_msgs`, `std_msgs`
- `nav2_msgs`, `tf2_ros`
- camera package: `v4l2_camera` or `usb_cam`
- optional: `image_transport`, `compressed_image_transport`, `cv_bridge`
- optional web bridge: `rosbridge_suite` only if browser needs direct ROS access

### AI Server dependencies

Keep separate from ROS2 workspace:

```text
services/ai-server/.venv or uv environment
services/ai-server/pyproject.toml
services/ai-server/uv.lock
```

The AI Server may read camera frames through a small adapter, but heavy AI dependencies must not leak into ROS bridge packages.

## 7. Testing and QA plan

1. Contract validation: `python3 scripts/validate_contracts.py` from this repository.
2. ROS package build: `colcon build --symlink-install` in `/home/codelab/turtlebot3_ws`; `make ros-build-bringup` currently builds `smartfactory_bringup smartfactory_perception_ros`.
3. Launch smoke test: `ros2 launch smartfactory_bringup central_pc_bringup.launch.py use_ai_server:=false use_nav2:=false`.
4. Topic smoke test: verify camera topics exist with `ros2 topic list` and `ros2 topic hz`.
5. API smoke test: AI Server `/api/v1/health` and Main Server `/api/v1/vision/events`.
6. Integration test: publish or replay one valid `VisionEvent` fixture and confirm WMS/GUI visibility.
7. Demo safety review: confirm AI Server does not publish `/cmd_vel` and does not call Nav2 directly.

## 8. Skill import and future usage

The ROS2-related skills are useful project knowledge. Import/use them selectively:

- `ros2-development` for packages, launch files, QoS, colcon, ament.
- `robot-bringup` for layered launch, systemd, device checks, production startup.
- `robot-perception` for camera/LiDAR calibration, image topics, latency, stale camera handling.
- `ros2-web-integration` for GUI/WebSocket/REST/ROS bridge choices.
- `robotics-testing` for launch tests, sensor mocks, replay tests, and CI.
- `docker-ros2-development` later if the Central PC deploys ROS2 or AI Server in containers.
- `robotics-security` later before networked multi-PC deployment.

## 9. Immediate next scaffold tasks

Completed/updated through 2026-06-11 in `/home/codelab/turtlebot3_ws`:

1. Created/migrated `smartfactory_bringup` launch package in `/home/codelab/turtlebot3_ws/src`.
2. Added `cameras.yaml`, `namespaces.yaml`, `ai_server.env.example`, and `ros2_network.env.example`.
3. Added `central_pc_bringup.launch.py`, `perception_sources.launch.py`, `ai_server.launch.py`, `wms_bridge.launch.py`, and `nav2_fleet.launch.py` with conservative launch flags.
4. Verified `colcon build --symlink-install --packages-select smartfactory_bringup smartfactory_perception_ros`.
5. Verified launch smoke test with all unavailable hardware/service flags disabled.
6. Initial ROS2 workspace scaffold was recorded earlier as commit `8d9a28e` before TurtleBot3 workspace consolidation.
7. Added raw `sensor_msgs/Image` snapshot adapter package `smartfactory_perception_ros` and default-off `ai_snapshot_clients.launch.py`.
8. Verified local no-robot E2E: generated ArUco ROS Image -> snapshot client -> AI Server `/api/v1/detect/image` -> latest detection.

Next tasks:

1. Add actual global camera driver config after confirming `/dev/video*` mapping and calibration.
2. Add robot Pi Camera relay implementation after deciding robot-side streaming path.
3. Add source health/staleness reporting for snapshot streams.
4. Add `smartfactory_ros_bridge` after Main/WMS task/state endpoint shape is ready.
5. Add namespaced TurtleBot3/Nav2 includes for `tb3_1` and `tb3_2` using LDS-03 scan topics.
6. Add launch/integration tests once bridge nodes exist.

## 10. Acceptance criteria for ROS2-friendly setup

- One command can start the MVP1 Central PC stack, with flags to disable unavailable hardware. Initial smoke test passed with all optional services disabled.
- All robot and camera names match the API contract: `global_cam_01`, `tb3_1_picam`, `tb3_2_picam`, `tb3_1`, `tb3_2`.
- AI Server can be started by launch as a separate process/container, not as an implicit in-process ROS dependency.
- ROS2 camera topic changes do not force WMS/GUI API changes.
- `colcon build` and contract validation both pass before integration.
- The same config names work when the AI Server later moves from `127.0.0.1` to a separate host.
