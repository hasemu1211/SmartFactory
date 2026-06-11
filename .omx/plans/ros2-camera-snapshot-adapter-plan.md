# Plan: ROS2 Camera Snapshot Adapter for AI Server

- Date: 2026-06-11 Asia/Seoul
- Scope: MVP1 camera snapshot bridge from ROS2 image topics to AI Server `/api/v1/detect/image`
- Workspace: `/home/codelab/turtlebot3_ws`
- Status: APPROVED by Architect/Critic review on 2026-06-11

## Problem / Goal

AI Server can process uploaded images and optionally emit WMS events, but it does not yet ingest live camera frames. The design boundary remains: AI Server must not import ROS2 (`rclpy`) or YOLO/Torch. Therefore the next implementation should be a ROS2-side adapter that subscribes to image topics and POSTs snapshots to AI Server over HTTP.

## Selected Implementation Slice

Create a new ROS2 package in `/home/codelab/turtlebot3_ws/src`:

```text
smartfactory_perception_ros/
  package.xml
  setup.py
  setup.cfg
  resource/smartfactory_perception_ros
  smartfactory_perception_ros/
    __init__.py
    image_snapshot_client.py
  test/
    test_image_snapshot_client.py
```

Add a dedicated launch wrapper at `/home/codelab/turtlebot3_ws/src/smartfactory_bringup/launch/ai_snapshot_clients.launch.py`, included from the top-level bringup behind a default-false flag:

```text
use_ai_snapshot_clients:=false
```

When enabled, launch three adapter nodes:

- `global_cam_01` -> `/global_camera/image_raw`
- `tb3_1_picam` -> `/tb3_1/pi_camera/image_raw`
- `tb3_2_picam` -> `/tb3_2/pi_camera/image_raw`

## Design Principles

1. Keep AI Server ROS-free; all ROS-specific image handling lives in `smartfactory_perception_ros`.
2. Adapter does no inference and makes no WMS decisions.
3. Do not require live robots for this implementation; validate with generated `sensor_msgs/Image` and mocked HTTP.
4. Keep launch flags conservative; default off so smoke tests pass without cameras or AI Server.
5. Use ROS environment dependencies already present where possible. `requests` exists in ROS Python environment; `httpx` does not.
6. V1 supports raw `sensor_msgs/Image` only; defer `CompressedImage` until actual camera relay transport is confirmed.

## Node Behavior

`image_snapshot_client` parameters:

- `source_id`: one of `global_cam_01`, `tb3_1_picam`, `tb3_2_picam`
- `image_topic`: ROS image topic to subscribe to
- `ai_server_url`: default `http://127.0.0.1:8100`
- `detect_path`: default `/api/v1/detect/image`
- `emit`: default `false`
- `snapshot_period_sec`: default `1.0`
- `request_timeout_sec`: default `1.0`
- `image_format`: default `jpg`

Behavior:

1. Subscribe to raw `sensor_msgs/Image` only in v1.
2. Keep only the latest frame in memory.
3. Timer fires every `snapshot_period_sec` and POSTs the latest frame to AI Server.
4. HTTP request is bounded by `request_timeout_sec`.
5. Failures are logged and do not crash the node.
6. Keep counters for attempted/succeeded/failed posts for logging/debug.

## Implementation Steps

1. Create `smartfactory_perception_ros` ament_python package under `/home/codelab/turtlebot3_ws/src`.
2. Implement raw image encoding helper:
   - Raw `sensor_msgs/Image` via `cv_bridge.CvBridge().imgmsg_to_cv2(..., desired_encoding="bgr8")` then `cv2.imencode`.
   - Do not implement `CompressedImage` in v1.
3. Implement `ImageSnapshotClient` rclpy node:
   - parameters above
   - latest-frame buffer
   - timer-based POST using `requests.Session.post`
   - multipart form fields: `source`, `emit`, `image`
4. Add unit tests with no live ROS graph:
   - encode generated raw image to JPEG bytes
   - POST helper sends expected URL/data/files using fake session
   - non-2xx/exception returns failure result without raising
5. Add dedicated `smartfactory_bringup/launch/ai_snapshot_clients.launch.py` and include it from central bringup behind `use_ai_snapshot_clients:=false`:
   - launch arguments: `use_ai_snapshot_clients`, `ai_server_url`, `ai_snapshot_period_sec`, `ai_snapshot_emit`
   - default-false Node actions for canonical raw source mappings. If Critic says this is too broad, reduce to one global source instance.
6. Update `smartfactory_bringup` README/config docs and SmartFactory `entry.md` after validation.
7. Validate:
   - `source /opt/ros/jazzy/setup.bash && cd /home/codelab/turtlebot3_ws && colcon build --symlink-install --packages-select smartfactory_perception_ros smartfactory_bringup`
   - `colcon test --packages-select smartfactory_perception_ros --event-handlers console_direct+`
   - `colcon test-result --verbose --test-result-base /home/codelab/turtlebot3_ws/build/smartfactory_perception_ros/test_results`
   - Launch smoke with `use_ai_snapshot_clients:=false`.
   - Optional local integration only if cheap: start AI Server and publish one generated image to a test topic; not required unless unit/build tests leave uncertainty.

## Acceptance Criteria

- New adapter package builds in `/home/codelab/turtlebot3_ws`.
- Unit tests pass without live robots/cameras.
- `smartfactory_bringup` still builds.
- Central launch smoke still works with snapshot clients disabled.
- AI Server code remains ROS-free and unchanged for this slice.
- No YOLO/Torch dependency is introduced.
- Live robot SSH is not used.

## Deferred Work

- Real robot Pi camera launch/relay setup.
- Camera source health/staleness reporting in AI Server/Main/WMS.
- E2E live robot or global camera test.
- Add `sensor_msgs/CompressedImage` support if robot relay uses compressed topics or raw bandwidth is too high.
- Backpressure/queue metrics and structured observability.


## Architect Review Adjustments

- Approved separate `smartfactory_perception_ros` package as correct home.
- Narrowed v1 to raw `sensor_msgs/Image` only; compressed transport is deferred.
- Kept adapter-only boundary: no inference, no WMS policy, no AI Server ROS import.
- Added explicit validation for the new ROS package, because existing Makefile only builds `smartfactory_bringup`.


## Critic Verdict

- Critic: APPROVED. No user question needed. Guardrails: raw `sensor_msgs/Image` only in v1, declare `rclpy`, `sensor_msgs`, `cv_bridge`, `python3-requests`, and OpenCV dependency metadata; keep launch wrapper default-off and gate global adapter with `use_global_camera`, robot adapters with `use_robot_picams`; cover valid encode, no-latest no POST, fake HTTP success, non-2xx, timeout/exception.


## Implementation / Verification Result

Implemented on 2026-06-11:

- Added tracked ROS package source at `ros2/smartfactory_perception_ros`.
- Symlinked it into `/home/codelab/turtlebot3_ws/src/smartfactory_perception_ros`.
- Added raw `sensor_msgs/Image` snapshot node `image_snapshot_client`.
- Added default-off `ai_snapshot_clients.launch.py` in `smartfactory_bringup` and included it from `central_pc_bringup.launch.py`.

Verification:

- `make ros-build-bringup`: passed; built `smartfactory_perception_ros` and `smartfactory_bringup`.
- `colcon test --packages-select smartfactory_perception_ros --event-handlers console_direct+`: package tests passed (`10 passed`).
- `make ros-launch-smoke`: passed with `use_ai_snapshot_clients:=false`.
- Direct package launch smoke: `ros2 launch smartfactory_perception_ros ai_snapshot_clients.launch.py use_ai_snapshot_clients:=false` passed.
- Local no-robot E2E smoke passed: generated ArUco ROS Image -> snapshot client -> AI Server `/api/v1/detect/image` -> latest detection contained `ARUCO_4X4_50_7`.
- `./scripts/test_ai_server.sh -q`: passed (`33 passed, 1 warning`) and contract fixtures behaved as expected.

Known unrelated issue: workspace-level `colcon test-result --verbose` still reports pre-existing `my_turtlebot3_pkg` lint failures; `smartfactory_perception_ros` pytest XML shows 10 tests, 0 failures.

Code review blocker fixed: adapter now posts each received frame at most once, preventing stale-frame replay from creating false-fresh AI detections. Regression tests cover one-frame/two-timer skip and second-frame repost behavior.
