# SmartFactory AI Server Handoff Entry

- Last updated: 2026-06-11 Asia/Seoul
- Repo root: `/home/codelab/Desktop/Project/SmartFactory`
- Active branch: `feature/ai-server-marker-detection`
- Current purpose: MVP1 AI Server marker-evidence API for SmartFactory, implemented as a separate Central-PC process/container now and separable to a dedicated AI Server PC later.

## User-confirmed project context

1. AI Server is API-first. Main/WMS remains the source of truth; AI Server emits evidence only.
2. Same Central PC process/container for MVP1 is OK, but keep deployment/network boundaries clean so it can be split later.
3. LiDAR is confirmed as `LDS-03`.
4. Robot depth camera is out of MVP1 scope.
5. MVP1 camera sources are:
   - `global_cam_01`
   - `tb3_1_picam`
   - `tb3_2_picam`
6. Current detector scope is **OpenCV ArUco-only**.
   - No QR in this finished slice.
   - No AprilTag/YOLO/Torch unless a later scope decision explicitly adds them.
7. Keep AI Server independent from ROS2 runtime packages for now. ROS2-friendly launch/bringup artifacts can orchestrate or document integration, but the FastAPI service itself should not import `rclpy`.
8. `/home/codelab/opencv_test/src` is reference-only. Prefer clean new code unless a specific script is clearly useful.

## OMX team status

- Team used: `smartfactory-ai-serve-ff431175`
- Team was shut down with `omx team shutdown smartfactory-ai-serve-ff431175`.
- `.omx/state/team/smartfactory-ai-serve-ff431175` is absent after shutdown.
- Therefore later nudges pointing to `.omx/state/team/smartfactory-ai-serve-ff431175/mailbox/leader-fixed.json` are stale and should not restart the team by themselves.
- Team reports retained for audit:
  - `.omx/reports/team-commit-hygiene/smartfactory-ai-server-marker.md`
  - `.omx/reports/team-commit-hygiene/smartfactory-ai-server-marker.ledger.json`
  - `.omx/reports/team-commit-hygiene/smartfactory-ai-server-marker.context.json`
- Team context snapshot:
  - `.omx/context/ai-server-marker-detection-20260609T071419Z.md`

## Execution lanes snapshot

| Lane | Status | Meaning | Next action |
| --- | --- | --- | --- |
| A. Completed robot-free stack | Done | AI Server evidence API, ArUco detection, optional pose/profile support, pure docking math, lift ROI evaluator, synthetic tests, tuning prep assets | Keep as stable base; validate with `./scripts/test_ai_server.sh -q` |
| B. Remaining no-physical-tuning work | Open | Work that can be implemented now without robot/camera availability | Start with central-PC passive ArUco pose monitor skeleton |
| C. Robot-available passive tuning | Waiting for hardware window | Requires robot/camera availability but no active motion | Use `docs/robot/docking-tuning-runbook.md`; measure topics/FPS/pose noise; no `/cmd_vel` |
| D. Permission-gated active tuning | Blocked until explicit approval | Any low-speed motion command or robot-side change | Ask user first; enforce marker-loss/stale timeout stop |

Main plan pointer: `docs/technical/perception-control-plan.md`.

## Current implementation summary

AI Server package:

- `services/ai-server/app/main.py`
  - FastAPI API surface.
  - `GET /api/v1/health`
  - `GET /api/v1/sources`
  - `GET /api/v1/detections/latest`
  - `POST /api/v1/detect/image`
  - Upload endpoint validates source, rejects invalid image bytes with HTTP 400, runs ArUco detection, builds contract-valid `VisionEvent` objects, stores events in memory, and returns `{source, emitted, emit_disabled, emit_results, events}`.
  - Optional best-effort WMS emission is available when request `emit=true` and `WMS_EMIT_ENABLED=true`; local detection still succeeds if WMS emission fails.
- `services/ai-server/app/detectors.py`
  - OpenCV image decode and deterministic ArUco `DICT_4X4_50` marker detection.
  - Preserves ArUco corner coordinates so optional pose estimation can be computed when calibration input is provided.
  - No QR/YOLO/Torch/ROS2 dependency.
- `services/ai-server/app/contracts.py`
  - JSON schema validation wrapper.
- `services/ai-server/app/config.py`
  - Source IDs and environment-driven settings, including WMS emit toggles.
- `services/ai-server/app/wms_client.py`
  - Async best-effort HTTP client for `POST {MAIN_SERVER_URL}/api/v1/vision/events`; treats HTTP 200/202 as success and reports non-2xx/timeout/transport failures in `emit_results`.
- `services/ai-server/app/docking.py`
  - Robot-free pure math helpers for ArUco/marker docking: camera intrinsics, solvePnP marker pose, docking error, alignment tolerance, bounded differential-drive command proposal, and stable-alignment window counting.
  - Used by `/api/v1/detect/image` only when `pose_profile` or marker size/camera intrinsics are provided, filling `pose_estimate.method=ARUCO_POSE` in `VisionEvent v1`.
  - This is not a ROS publisher and must not directly publish `/cmd_vel`.
- `services/ai-server/app/pose_profiles.py`
  - JSON profile loader for named ArUco pose calibration/tuning data. Default path is `config/perception/aruco_pose_profiles.example.json` via `ARUCO_POSE_PROFILES_PATH`.
- `services/ai-server/app/lift_roi.py`
  - Robot-free pure evaluation helpers for lift ROI load evidence: bbox/ROI overlap, optional instance mask overlap, stable count checks, pickup verification, and dropoff verification.
  - This is evidence/policy helper logic; WMS/Main remains final task/inventory state owner.
- `services/ai-server/tests/generated_fixtures.py`
  - Deterministic generated ArUco/blank image fixtures.
- `services/ai-server/tests/test_api.py`
  - API behavior tests.
- `services/ai-server/tests/test_docking.py`
  - Synthetic projected marker tests for pose recovery, docking error, marker-lost/aligned stop behavior, bounded turn commands, and stable alignment counting.
- `services/ai-server/tests/test_generated_fixtures.py`
  - Generated fixture and contract-validation tests.
- `services/ai-server/tests/test_lift_roi.py`
  - Synthetic lift ROI tests for inside/outside/partial detections, instance-mask overlap, stable counts, pickup verification, and dropoff verification.
- `services/ai-server/tests/test_wms_client.py`
  - WMS URL building, HTTP 200/202 success, non-2xx failure, and timeout result tests.

Contracts/docs/scripts:

- `docs/contracts/vision-event.schema.json`
- `docs/contracts/ai-server-api.md`
- `docs/robot/docking-tuning-runbook.md`
  - Standalone tuning runbook for whenever a robot becomes available. Default lane is passive observation only: robot bringup/camera, central PC ROS topic inspection, no `/cmd_vel`.
- `docs/technical/development-environment.md`
- `docs/technical/perception-control-plan.md`
  - User-approved robot-free-first plan: split slow AI Server evidence loop from faster future ROS docking control loop; use ArUco as pose-based precision docking primitive; use lift sensor + ROI/segmentation evidence for pickup; keep dropoff MVP as lower/drop + backoff + WMS state success; keep robot-side changes minimal.
- `docs/technical/ros2-friendly-environment-plan.md`
- `config/perception/docking_tuning.example.yaml`
  - Copy-per-session template for marker IDs, marker size, camera intrinsics, station target offsets, tolerances, gains/speed caps, and lift ROI polygons.
- `config/perception/aruco_pose_profiles.example.json`
  - AI Server-readable named pose profiles for robot-free/passive tuning. Values are tuning/config data and should be edited per station/camera after passive measurement.
- `scripts/prepare_docking_tuning_session.sh`
  - Creates `.omx/reports/docking-tuning/<timestamp>/`, copies the tuning config template, and prints safe passive ROS commands. `--passive-check` runs topic list/type/hz only and never publishes motion commands.
- `scripts/setup_ai_server_env.sh`
- `scripts/run_ai_server.sh`
- `scripts/test_ai_server.sh`
- `scripts/validate_contracts.py`
- `Makefile`

ROS2 bringup side:

- ROS2 workspace root: `/home/codelab/turtlebot3_ws` after 2026-06-11 migration.
- Package scaffold: `/home/codelab/turtlebot3_ws/src/smartfactory_bringup`
- ROS2 snapshot adapter package: `/home/codelab/turtlebot3_ws/src/smartfactory_perception_ros` symlinked to tracked repo source `ros2/smartfactory_perception_ros`
- Local `smartfactory_bringup` in `/home/codelab/turtlebot3_ws/src` includes default-off `ai_snapshot_clients.launch.py`; the adapter package also provides a standalone `ros2 launch smartfactory_perception_ros ai_snapshot_clients.launch.py`.
- Previous copy moved aside at `/home/codelab/ros2_ws/src/smartfactory_bringup.migrated-backup-20260611` to avoid duplicate overlay confusion.
- Historical ROS2 workspace commit recorded earlier: `8d9a28e Add SmartFactory ROS2 bringup scaffold`
  - Note: this is retained as historical handoff context and may not be directly verifiable from the current tracked repo alone.
- Rebuild command from SmartFactory repo: `make ros-build-bringup`

## Environment conventions

From repo root:

```bash
./scripts/setup_ai_server_env.sh
./scripts/test_ai_server.sh -q
./scripts/run_ai_server.sh
```

The setup script creates/uses `services/ai-server/.venv`, installs pinned runtime/test dependencies, and avoids mixing AI Server Python packages into the ROS2 overlay.

## Validation commands for next session

Run these after pulling/resuming the branch:

```bash
cd /home/codelab/Desktop/Project/SmartFactory
./scripts/test_ai_server.sh -q
make ros-build-bringup
```

Validated on 2026-06-09 Asia/Seoul before final handoff:

- `./scripts/test_ai_server.sh -q`: `26 passed, 1 warning` plus contract fixtures behaved as expected.
- `make ros-build-bringup`: `smartfactory_bringup` finished successfully.

Validated again on 2026-06-11 Asia/Seoul after ROS workspace migration:

- `make ros-build-bringup`: builds from `/home/codelab/turtlebot3_ws` successfully.
- `./scripts/test_ai_server.sh -q`: `26 passed, 1 warning` and contract fixtures behaved as expected.

Validated again on 2026-06-11 Asia/Seoul after WMS ingest client implementation:

- `./scripts/test_ai_server.sh -q`: `33 passed, 1 warning` and contract fixtures behaved as expected.

Validated again on 2026-06-11 Asia/Seoul after ROS2 snapshot adapter implementation:

- `make ros-build-bringup`: builds `smartfactory_bringup` and `smartfactory_perception_ros` successfully.
- `colcon test --packages-select smartfactory_perception_ros --event-handlers console_direct+`: `13 passed` after compressed transport support.
- `make ros-launch-smoke`: succeeds with `use_ai_snapshot_clients:=false`.
- Local no-robot E2E smoke: generated ArUco ROS `sensor_msgs/Image` -> `image_snapshot_client` -> AI Server `/api/v1/detect/image` -> latest detection contained `ARUCO_4X4_50_7`.
- Robot1 PiCam live QA evidence is documented in `docs/robot/robot1-picam-aruco-ai-server-qa-2026-06-11.md`.
  - `/camera/image_raw/compressed` was `sensor_msgs/msg/CompressedImage` at about 30 Hz.
  - OpenCV viewer detected the phone-displayed marker as ID `0`.
  - `image_snapshot_client` posted to AI Server with `source_id=tb3_1_picam`, `image_transport=compressed`, `emit=false`.
  - AI Server latest detections contained `ARUCO_4X4_50_0` events for `tb3_1_picam` during the marker window.
- `./scripts/test_ai_server.sh -q`: `33 passed, 1 warning` and contract fixtures behaved as expected.

Validated again on 2026-06-11 Asia/Seoul after perception-control pure logic implementation:

- `./scripts/test_ai_server.sh`: `46 passed, 1 warning` and contract fixtures behaved as expected.
- Added robot-free synthetic coverage for ArUco docking math and lift ROI load/pickup/dropoff evidence helpers.

Validated again on 2026-06-11 Asia/Seoul after standalone docking tuning prep:

- `bash -n scripts/prepare_docking_tuning_session.sh`: OK.
- `./scripts/prepare_docking_tuning_session.sh --print-commands`: creates a timestamped `.omx/reports/docking-tuning/` session folder, copies `docking_tuning.yaml`, and prints passive-only ROS commands.

Validated again on 2026-06-11 Asia/Seoul after optional ArUco pose integration:

- `./scripts/test_ai_server.sh -q`: `49 passed, 1 warning` and contract fixtures behaved as expected.
- Default marker events remain compatible with `pose_estimate=null`; optional calibration form fields produce contract-valid `ARUCO_POSE` payloads.

Validated again on 2026-06-11 Asia/Seoul after named ArUco pose profile support:

- `./scripts/test_ai_server.sh -q`: `56 passed, 1 warning` and contract fixtures behaved as expected.
- `/api/v1/detect/image` accepts `pose_profile`; profile/source/marker mismatch keeps `pose_estimate=null`; unknown profiles or mixing profile+manual intrinsics return HTTP 400.

Optional manual API smoke test:

```bash
./scripts/run_ai_server.sh
curl http://127.0.0.1:8100/api/v1/health
```

## Recommended next work

Use `docs/technical/perception-control-plan.md` as the main plan pointer. It now separates:

- completed robot-free base,
- remaining work that does **not** require physical tuning,
- robot-available passive tuning,
- permission-gated low-speed active tuning.

### 1. No-physical-tuning work that can start now

1. Add a central-PC **passive ArUco pose monitor skeleton** around `app.docking`.
   - Must not publish `/cmd_vel`.
   - Validate with synthetic image/frame tests.
   - Later, when a robot is available, the same monitor becomes the passive tuning tool.
2. Add source health/staleness reporting.
   - Track `last_frame_at`, last event time, source online/stale/offline.
   - Replace placeholder health values in AI Server/source endpoints.
3. Add API/event contract planning for count/segmentation summaries.
   - Do not force mask/count fields into `vision-event.v1`.
   - Decide between `vision-event.v2` and a separate ROI/count endpoint.
4. Add detector/segmenter interface seams with mock/synthetic tests.
   - Actual YOLO/segmentation model choice remains a later scope decision.
5. Add observability/persistence improvements after API contract stabilizes.
   - structured logs, request IDs, metrics, bounded event retention.
6. Add docker-compose/systemd launch assets if the team wants reproducible Central-PC deployment.

### 2. Physical robot/camera available, passive only

1. Open the standalone tuning lane from `docs/robot/docking-tuning-runbook.md`.
2. Run passive checks only:
   - robot bringup/camera,
   - central PC topic list/type/hz,
   - ArUco pose FPS/noise/loss measurements,
   - no `/cmd_vel`.
3. Update copied session config/profile values:
   - marker size,
   - camera intrinsics,
   - station target offsets,
   - docking tolerances.
4. Repeat validated Robot1 PiCam compressed QA on Robot2 only when Robot2 is available and not in use.
5. Add real camera source bringup/relay for `global_cam_01` when the global camera is ready.

### 3. Permission-gated tuning, not normal development

1. Low-speed active docking tuning.
   - publish bounded low-speed commands only after explicit permission,
   - stop on marker loss, stale frames, timeout, operator stop, or obstacle/person entry.
2. Any robot-side file/config/package/system/network change.
3. Touching Robot2 while another person is using it.
4. Switching from detection-only to a real YOLO/segmentation model if it changes deployment dependencies or runtime behavior.

### 4. Later integration decisions

1. Add ROS2 bridge only after WMS task/state endpoints are stable.
2. Revisit best-effort WMS emission only if production policy requires durable retries or hard failure behavior.

## Recovery checklist for the next assistant

1. Read this file first.
2. Confirm branch: `git status --short --branch`.
3. Do not resume `smartfactory-ai-serve-ff431175`; it was intentionally shut down.
4. Use `/home/codelab/turtlebot3_ws` as the default ROS2 workspace for `smartfactory_bringup`; do not reintroduce an active duplicate under `/home/codelab/ros2_ws/src`.
5. Run validation commands above before further edits.
6. Preserve the ArUco-only detector API scope unless the user explicitly changes it; `app.docking` is pure docking math, not a new live detector API.
7. Preserve the key design decision: AI Server evidence loop can be slower, but precision docking requires a faster future central-PC ROS loop; robot should remain bringup/camera-only unless user permits robot-side changes.
