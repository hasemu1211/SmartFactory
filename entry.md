# SmartFactory AI Server Handoff Entry

- Last updated: 2026-06-09 Asia/Seoul
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
  - No QR/YOLO/Torch/ROS2 dependency.
- `services/ai-server/app/contracts.py`
  - JSON schema validation wrapper.
- `services/ai-server/app/config.py`
  - Source IDs and environment-driven settings, including WMS emit toggles.
- `services/ai-server/app/wms_client.py`
  - Async best-effort HTTP client for `POST {MAIN_SERVER_URL}/api/v1/vision/events`; treats HTTP 200/202 as success and reports non-2xx/timeout/transport failures in `emit_results`.
- `services/ai-server/tests/generated_fixtures.py`
  - Deterministic generated ArUco/blank image fixtures.
- `services/ai-server/tests/test_api.py`
  - API behavior tests.
- `services/ai-server/tests/test_generated_fixtures.py`
  - Generated fixture and contract-validation tests.
- `services/ai-server/tests/test_wms_client.py`
  - WMS URL building, HTTP 200/202 success, non-2xx failure, and timeout result tests.

Contracts/docs/scripts:

- `docs/contracts/vision-event.schema.json`
- `docs/contracts/ai-server-api.md`
- `docs/technical/development-environment.md`
- `docs/technical/ros2-friendly-environment-plan.md`
- `scripts/setup_ai_server_env.sh`
- `scripts/run_ai_server.sh`
- `scripts/test_ai_server.sh`
- `scripts/validate_contracts.py`
- `Makefile`

ROS2 bringup side:

- ROS2 workspace root: `/home/codelab/turtlebot3_ws` after 2026-06-11 migration.
- Package scaffold: `/home/codelab/turtlebot3_ws/src/smartfactory_bringup`
- Previous copy moved aside at `/home/codelab/ros2_ws/src/smartfactory_bringup.migrated-backup-20260611` to avoid duplicate overlay confusion.
- ROS2 workspace commit recorded earlier: `8d9a28e Add SmartFactory ROS2 bringup scaffold`
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

Optional manual API smoke test:

```bash
./scripts/run_ai_server.sh
curl http://127.0.0.1:8001/api/v1/health
```

## Recommended next work

1. Add camera-frame adapter/snapshot ingestion while keeping AI Server decoupled from ROS2 imports.
2. Add ROS2 bridge only after WMS task/state endpoints are stable.
3. Add QR/AprilTag/YOLO only after a new scope decision; do not silently reintroduce QR tests into this ArUco-only branch.
4. Add docker-compose/systemd launch assets if the team wants a reproducible Central-PC deployment.
5. Consider persistence/observability after API contract stabilizes: structured logs, request IDs, metrics, and bounded event retention.
6. Later, if production policy requires it, revisit best-effort WMS emission and decide whether some WMS failures should become hard failures or durable retry-queue entries.

## Recovery checklist for the next assistant

1. Read this file first.
2. Confirm branch: `git status --short --branch`.
3. Do not resume `smartfactory-ai-serve-ff431175`; it was intentionally shut down.
4. Use `/home/codelab/turtlebot3_ws` as the default ROS2 workspace for `smartfactory_bringup`; do not reintroduce an active duplicate under `/home/codelab/ros2_ws/src`.
5. Run validation commands above before further edits.
5. Preserve the ArUco-only scope unless the user explicitly changes it.
