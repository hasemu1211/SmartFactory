# SmartFactory AI Server Handoff Entry

- Last updated: 2026-06-16 Asia/Seoul
- Repo root: `/home/codelab/Desktop/Project/SmartFactory`
- Active branch: `feature/ai-server-marker-detection`
- Current purpose: Vision Gateway evolution of the AI Server: evidence-only perception API, Lane 0 Main/Camera contract alignment, Lane A registry-derived source contract, and Lane B robot-free synthetic frame/stream/overlay/ROS handoff groundwork. Central-PC process/container remains OK for MVP, with clean split to a dedicated Vision/AI Server later.

## User-confirmed project context

1. AI Server is API-first. Main/WMS remains the source of truth; AI Server emits evidence only.
2. Same Central PC process/container for MVP1 is OK, but keep deployment/network boundaries clean so it can be split later.
3. LiDAR is confirmed as `LDS-03`.
4. Robot depth camera is out of MVP1 scope.
5. MVP1 camera sources are:
   - `global_cam_01`
   - `tb3_1_picam`
   - `tb3_2_picam`
6. Marker detector base remains **OpenCV ArUco-only** for `VisionEvent v1`; lift-load verification has a later user-approved segmentation-primary path.
   - No QR/AprilTag in this finished marker slice.
   - Lift ROI can now consume detector boxes or instance masks through an internal seam.
   - A concrete YOLO/seg model weight is still not selected; optional Ultralytics runtime loading is fail-closed and not a mandatory startup dependency.
7. Keep AI Server FastAPI independent from ROS2 runtime packages for now. ROS2-friendly launch/bringup artifacts can orchestrate integration, but the FastAPI service itself should not import `rclpy`.
8. `/home/codelab/opencv_test/src` is reference-only. Prefer clean new code unless a specific script is clearly useful.
9. Lane 0 adopted decisions as of 2026-06-15:
   - AI/Vision reports to Main via `/api/v1/camera/events` only as interim audit/business reporting until Main implements `/api/v1/vision/events`.
   - `/api/v1/vision/events` remains target canonical VisionEvent ingest in Main, expected after Lane A-side alignment.
   - `task_id` final direction is integer/null migration to match Main; current AI schema/code still use string/null until migration work lands.
   - Main dedup should use `event_id` for VisionEvent and `report_id` for future Lift ROI push, backed by `inbound_reports` or equivalent storage.
   - Keep legacy `/mission/...` topics while adding `/sf/...` standard topics.
   - MVP safety reporting goes to Main first; direct Vision→Movement safety alert requires explicit approval; Vision never owns `/cmd_vel`/Nav2 authority.
   - Source registry becomes source of truth and should generate schema enum/OpenAPI/fixture surfaces to prevent drift.


## Lane C robot topology / domain bridge note (2026-06-15)

- Robot1: `codelab@192.168.10.75`, ROS2 Jazzy, Pi camera environment, `ROS_DOMAIN_ID=2`.
  - Confirmed from central PC domain 2: `/camera/image_raw`, `/camera/image_raw/compressed`, and `/camera/camera_info` are visible.
  - Preferred ingest topic for Lane C: `/camera/image_raw/compressed` (`sensor_msgs/msg/CompressedImage`).
  - Observed compressed topic rate from central PC: roughly 25-30 Hz; raw image CLI measurement was much lower/heavier, so raw should not be the normal network ingest path.
  - Current `camera_ros` launch includes `image_view_node`; over SSH/headless use a process-local workaround such as `QT_QPA_PLATFORM=offscreen`, or later create a camera-only launch without GUI viewer.
  - Camera calibration file was missing on robot1; not blocking MVP overlay, but future pose/docking precision needs calibration.
- Robot2: `mush@192.168.10.89`, ROS2 Jazzy/Pi camera environment expected, `ROS_DOMAIN_ID=5`, on a different Wi-Fi/network.
- User-selected Lane C direction: keep Robot2 on domain 5 and use a domain bridge instead of forcing every robot into one domain.
- Bridge/remap target should avoid default `/camera/...` collisions, e.g.:
  - robot1 local `/camera/image_raw/compressed` -> central/AI `/tb3_1/camera/image_raw/compressed` -> source `tb3_1_picam`
  - robot2 local `/camera/image_raw/compressed` -> central/AI `/tb3_2/camera/image_raw/compressed` -> source `tb3_2_picam`
- Credential handling: local runtime credentials were user-provided for this session, but `entry.md` is tracked and must not contain plaintext passwords. Local-only ignored wiki notes may hold the operator convenience details if needed.
- Boundary remains unchanged: AI Server FastAPI must not import/spin ROS2; Lane C should use a ROS adapter/domain bridge sidecar. Vision publishes/serves evidence/overlay only and never owns `/cmd_vel` or Nav2 authority.

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
- Latest local context snapshot for this lane:
  - `.omx/context/ai-server-source-registry-ros-handoff-20260616.md`
  - Previous: `.omx/context/ai-server-segmentation-lift-roi-20260612.md`

## Execution lanes snapshot

| Lane | Status | Meaning | Next action |
| --- | --- | --- | --- |
| Lane 0. Contract alignment | Done for current decisions; Main/Movement still have implementation follow-ups | Main/Vision API base ports, `/camera/events` interim behavior, `/vision/events` target, Pull-first Lift ROI path, `task_id` migration direction, dedup, topic migration, safety boundary, registry/schema generation direction are documented and published to Confluence | Use adopted decisions as implementation constraints; Main still needs `/vision/events`, dedup storage, Camera client/source health integration |
| A. Base architecture/refactor | Source registry slice done for current MVP1 sources | AI Server evidence API, ArUco detection, optional pose/profile support, source health/staleness, LiftRoiEvidence contract, pure docking math, lift ROI evaluator, passive ArUco pose monitor skeleton, synthetic tests, deployment assets, and registry-derived source/schema/OpenAPI/fixture surfaces | Keep registry as source of truth; future A work is task_id integer/null migration or model-selection support, not source enum hardcoding |
| B. Stream + overlay + evidence worker, robot-free | In progress; synthetic/debug frame + controlled worker tick + stale visual QA + stream metrics + source snapshot + MJPEG rate-limit + ROS handoff topic + latest raw frame + raw frame ingest seam + worker stale-frame guard + worker status summary + worker tick summary + registry-driven ROS ingest policy seam + ROS publish readiness + ROS topics source filter + stream source filter + metrics source filter + source-scoped discovery links + stream sync status + stream summary + ROS ingest readiness + source snapshot ROS ingest/publish readiness + summary breakdown + requested_source + overlay latest sync + ROS ingest/publish runtime plan + topic exposure policy + summary preflight + debug snapshot/stream discovery mirror plus debug subscription hints, ROS ingest adapter contract, and ROS overlay publish payload preview summary plus overlay/evidence publish policy plus evidence event readiness plus stream evidence readiness mirror plus stream ROS overlay publish readiness mirror plus stream ROS ingest readiness mirror plus stream runtime policy mirror plus stream motion-control safety mirror plus Lane B robot-free e2e consistency plus multi-source isolation plus API-served overlay visual QA plus multi-source latest-only/backpressure validation plus worker tick idempotency validation plus worker status idempotency preview plus OpenAPI/source-registry drift guard implemented | Latest-frame cache with drop counters, overlay renderer with stale warning band, synthetic ArUco frame ingest endpoint, one-shot latest-frame worker tick endpoint with stale-frame guard, read-only worker status endpoint with summary counts, worker tick summary counts, per-source debug snapshot endpoint with requested_source echo, registry-derived ROS ingest/publish readiness, and summary counts with status breakdown, raw frame ingest adapter/context plus raw frame metadata/image endpoints, overlay metadata/image endpoints with latest-frame sync metadata, ROS ingest/publish runtime plan metadata including ingest/publish adapter contracts, publish payload summary counts, and overlay/evidence publish QoS/policy and evidence event readiness mirrored through ROS topics, debug snapshots, and stream discovery, stream ROS overlay publish readiness, stream ROS ingest readiness, runtime policy, and motion/control safety flags mirrored through stream discovery, ROS topic exposure policy/summary preflight metadata and rosbridge subscription hints mirrored in debug snapshots and stream discovery, debug/fallback MJPEG stream discovery with source filter, frame/overlay sync status, summary counts, metrics, and per-client max_fps, read-only ROS2 handoff topic matrix with QoS/frame-drop/runtime policy seam, ingest readiness, and publish readiness, synthetic tests, integrated robot-free e2e consistency, multi-source isolation, API-served overlay visual QA tests/artifacts, multi-source latest-only/backpressure validation, worker tick idempotency validation, worker status idempotency preview, and OpenAPI/source-registry drift guard, OpenAPI/API docs updated | Next B slice can move to Lane C passive ROS2/domain-bridge implementation when a robot/replay window is available; no more source hardcoding before Lane C |
| C. ROS2 ingest/domain bridge passive | First safe sidecar slice implemented and live-smoked with temporary Robot1 camera launch | `vision_frame_gateway` subscribes to compressed image topics, POSTs latest frames to `/api/v1/vision/frame`, optionally ticks worker and publishes safe `/sf/vision/...` overlay/evidence topics; no robot motion | Preserve rosbridge 9090 as primary browser stream; keep `/mission/...` while adding `/sf/...`; no `/cmd_vel`; robot-side persistent changes forbidden |
| D1. Performance/GUI/Main integration | Waiting for Main and GUI surfaces | Vision-only performance/GUI evidence display can proceed; Main semantic ingest waits for `/vision/events` + dedup + Camera client | Do not treat `/camera/events` audit acceptance as semantic evidence ingest success |
| D2. Permission-gated active/safety validation | Blocked until explicit approval | Any direct Movement safety alert integration or active robot behavior validation | Vision may emit evidence/alerts only; Movement owns stop/slow; ask user first |

Main plan pointer: `docs/technical/perception-control-plan.md`.
Latest local plan/design-critique pointers: `.omx/plans/lane-a-b-source-registry-ros-ingest-prep-20260616.md`, `.omx/plans/vision-gateway-ros-domain-bridge-plan-20260615.md`, `.omx/plans/lane0-contract-alignment-plan-20260615.md`, plus historical `.omx/plans/wms-main-lift-roi-gate-plan-20260612.md`.

## Current implementation summary

AI Server package:

- `services/ai-server/app/main.py`
  - FastAPI API surface.
  - `GET /api/v1/health`
  - `GET /api/v1/sources`
  - `GET /api/v1/detections/latest`
  - `GET /api/v1/metrics`
  - `GET /api/v1/vision/streams`
  - `POST /api/v1/vision/frame` (robot-free raw frame ingest seam; stores latest frame only, no detection/overlay)
  - `GET /api/v1/vision/frame/latest`
  - `GET /api/v1/vision/frame/latest/image`
  - `GET /api/v1/vision/overlay/latest`
  - `GET /api/v1/vision/overlay/latest/image`
  - `GET /api/v1/vision/stream/{source}.mjpeg?max_fps=10` (debug/fallback, not production stream plane; per-client `max_fps` range `1..30`)
  - `GET /api/v1/vision/debug/sources` (per-source frame/overlay/stream readiness snapshot; debug/fallback only)
  - `GET /api/v1/vision/ros/topics` (read-only ROS2/domain-bridge handoff topic matrix with QoS/frame-drop/runtime policy seam, ingest readiness, and overlay publish readiness; no motion/control publish)
  - `POST /api/v1/vision/synthetic/frame` (robot-free debug ingest; not production camera ingest)
  - `GET /api/v1/vision/worker/status` (read-only next worker tick preview; debug/scheduling surface)
  - `POST /api/v1/vision/worker/tick` (one-shot latest-frame worker tick; debug/control surface)
  - `POST /api/v1/detect/image`
  - `POST /api/v1/lift-roi/evaluate`
  - `POST /api/v1/lift-roi/evaluate-image`
  - Upload endpoint validates source, rejects invalid image bytes with HTTP 400, runs ArUco detection, builds contract-valid `VisionEvent` objects, stores events in memory, and returns `{source, emitted, emit_disabled, emit_results, events}`.
  - Lift ROI JSON endpoint accepts caller-provided bbox/mask candidates and returns contract-valid `LiftRoiEvidence v1`.
  - Lift ROI image endpoint uses the configured optional detector/segmenter adapter, prefers instance masks when available, and returns HTTP 503 if the model path/package is unavailable.
  - Optional best-effort WMS emission is available for `VisionEvent` when request `emit=true` and `WMS_EMIT_ENABLED=true`; local detection still succeeds if WMS emission fails. Lane 0 says `/camera/events` is interim audit-only while `/vision/events` remains target canonical Main ingest.
  - Lane B debug/fallback frame/overlay endpoints expose raw frame ingest, latest raw frame metadata/JPEG, plus overlay metadata/JPEG/MJPEG for synthetic validation; production browser stream remains rosbridge 9090 unless later changed. `GET /api/v1/vision/ros/topics` exposes the planned `/mission`→parallel `/sf` topic handoff plus Lane C QoS/frame-drop/runtime policy, source-level ingest readiness, source snapshot ROS ingest/publish readiness, source-level overlay publish readiness, and optional source filtering without starting ROS2 or publishing control topics.
  - Overlay metadata now includes `visual_state=fresh|stale`; stale overlay JPEGs include a full-width amber warning band so old evidence is not confused with current task success.
  - `POST /api/v1/vision/synthetic/frame` generates a deterministic ArUco image and runs the same latest-frame/detection/overlay path as `/api/v1/detect/image`, returning `{source, emitted, emit_disabled, emit_results, events, overlay}`.
  - `GET /api/v1/vision/worker/status` previews `no_frame|processed|skipped|stale_frame` without processing. `POST /api/v1/vision/worker/tick` runs one controlled latest-frame processing tick for one source or all sources. It skips frames whose latest overlay already matches `frame_seq` unless `force=true`, and now skips frames older than `max_frame_age_s`/`SOURCE_STALE_AFTER_S` as `stale_frame`; it never publishes ROS motion commands.
  - `GET /api/v1/metrics` now includes optional source filtering plus Lane B stream metrics (`clients_total`, `active_clients`, `frames_sent_total`, `stale_polls_total`, `approx_fps`), worker tick counters, and frame-store drop counters.
  - `GET /api/v1/vision/streams` exposes `/api/v1/metrics` as the debug metrics path and includes response-level source summary counts including `ros_ingest_contract_ready_count`, `ros_ingest_runtime_subscriber_active_count`, `ros_ingest_status_counts`, `ros_publish_ready_count`, `ros_publish_payload_available_count`, `ros_publish_payload_blocked_count`, `ros_publish_status_counts`, and `evidence_event_publish_ready_count`, per-source frame/overlay sync state, per-source `ros_ingest_readiness`, per-source `ros_publish_readiness`, per-source `evidence_event_publish_readiness`, per-source debug stream metric snapshots, top-level `runtime_policy`, top-level `debug_only`, `motion_command_allowed=false`, `control_topics_published=[]`, plus `/api/v1/vision/ros/topics` as the ROS handoff pointer.
- `services/ai-server/app/detectors.py`
  - OpenCV image decode and deterministic ArUco `DICT_4X4_50` marker detection.
  - `generate_synthetic_aruco_frame` creates robot-free ArUco frames for Lane B synthetic validation.
  - Preserves ArUco corner coordinates so optional pose estimation can be computed when calibration input is provided.
  - No QR/YOLO/Torch/ROS2 dependency.
- `services/ai-server/app/contracts.py`
  - JSON schema validation wrapper.
- `services/ai-server/app/config.py`
  - Runtime settings plus `VISION_SOURCES_REGISTRY_PATH` (default `config/vision/sources.yaml`). Source IDs/topics are registry-derived first, with legacy env fallback only if the registry file is absent.
- `services/ai-server/app/source_registry.py`
  - Validates and loads the YAML source registry. Provides source IDs, robot IDs, frame IDs, physical input topics/message types/content types, legacy browser topics, normalized `/sf/...` topics, and source-registry snapshots for docs/tests.
- `services/ai-server/app/source_health.py`
  - Thread-safe source freshness tracker. Valid decoded frames update `last_frame_at`/`frame_count`; marker events additionally update `last_event_at`/`event_count`/last event metadata. Status is `online`, `stale`, `offline`, or `disabled` based on configurable thresholds.
- `services/ai-server/app/frame_store.py`
  - Thread-safe latest-frame cache keyed by source. Keeps only the latest frame per source with `frame_seq`/timestamp metadata; old frames are dropped by design and counted in `dropped_frames_by_source`/`dropped_frames_total`.
- `services/ai-server/app/evidence_cache.py`
  - Thread-safe latest overlay/evidence metadata cache per source.
- `services/ai-server/app/overlay.py`
  - Robot-free OpenCV overlay renderer for bbox/marker labels, stale/debug banners, and a full-width amber stale warning band. Produces JPEG overlay plus metadata (`frame_seq`, `frame_timestamp`, `evidence_timestamp`, `latency_ms`, `event_count`, `visual_state`). Overlay is visual evidence only, not task success.
- `services/ai-server/app/wms_client.py`
  - Async best-effort HTTP client for `POST {MAIN_SERVER_URL}/api/v1/vision/events`; treats HTTP 200/202 as success and reports non-2xx/timeout/transport failures in `emit_results`.
  - Note: this is only an outbound client seam; this repo currently does not contain a concrete Main/WMS service implementation.
- `services/ai-server/app/docking.py`
  - Robot-free pure math helpers for ArUco/marker docking: camera intrinsics, solvePnP marker pose, docking error, alignment tolerance, bounded differential-drive command proposal, and stable-alignment window counting.
  - Used by `/api/v1/detect/image` only when `pose_profile` or marker size/camera intrinsics are provided, filling `pose_estimate.method=ARUCO_POSE` in `VisionEvent v1`.
  - This is not a ROS publisher and must not directly publish `/cmd_vel`.
- `services/ai-server/app/pose_profiles.py`
  - JSON profile loader for named ArUco pose calibration/tuning data. Default path is `config/perception/aruco_pose_profiles.example.json` via `ARUCO_POSE_PROFILES_PATH`.
- `services/ai-server/app/lift_roi.py`
  - Robot-free pure evaluation helpers for lift ROI load evidence: bbox/ROI overlap, optional instance mask overlap, stable count checks, pickup verification, and dropoff verification.
  - This is evidence/policy helper logic; WMS/Main remains final task/inventory state owner.
- `services/ai-server/app/vision_interfaces.py`
  - Internal detector/segmenter seam with `DetectionBox`, `InstanceMask`, `DetectorResult`, and provider abstractions.
  - Normalizes bbox and mask results into Lift ROI candidates without selecting a concrete model.
- `services/ai-server/app/lift_roi_evidence.py`
  - Builds contract-valid `LiftRoiEvidence v1` from caller-provided candidates or adapter-produced detector/segmenter results.
  - Pickup confirmation requires lift-up, expected/stable count, and no dropped-item count; insufficient vision evidence stays `CANDIDATE` rather than being ignored.
- `services/ai-server/app/model_adapters.py`
  - Optional Ultralytics adapter for detection or instance segmentation.
  - Imports `ultralytics` only inside adapter construction; missing package/model path returns fail-closed endpoint errors instead of becoming an AI Server startup dependency.
- `services/ai-server/app/observability.py`
  - In-memory metrics and structured JSON log helper for HTTP, detection, and lift ROI verification counters.
  - Lane B debug stream metrics: MJPEG client open/close counts, active clients, frames sent, stale polls, approximate FPS, and worker tick status counters.
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
- `services/ai-server/tests/test_vision_interfaces.py`
  - Detector/segmenter seam tests for bbox and mask normalization into Lift ROI candidates.
- `services/ai-server/tests/test_model_adapters.py`
  - Fake Ultralytics tests proving instance masks are preferred and detection-only results fall back to bbox candidates without mandatory `ultralytics`/`torch` imports.
- `services/ai-server/tests/test_event_store.py` and `services/ai-server/tests/test_observability.py`
  - Bounded event retention, reset/stats behavior, request IDs, structured metrics, and lift ROI verification counters.
- `services/ai-server/tests/test_overlay.py`
  - Latest-frame store and overlay renderer smoke tests.
- `services/ai-server/tests/test_deployment_assets.py`
  - Static checks for Dockerfile, docker-compose, and systemd AI Server deployment assets.
- `services/ai-server/tests/test_wms_client.py`
  - WMS URL building, HTTP 200/202 success, non-2xx failure, and timeout result tests.

Contracts/docs/scripts:

- `docs/contracts/vision-event.schema.json`
- `docs/contracts/lift-roi-evidence.schema.json`
  - Separate contract for lift ROI count/verification evidence. It keeps count, mask-overlap, stability, lift-sensor and pickup/dropoff verification fields out of `VisionEvent v1`.
  - Validation policy rejects contradictory `CONFIRMED` payloads, e.g. pickup confirmation with count mismatch or missing lift-up.
- `docs/contracts/ai-server-openapi.json`
  - Generated OpenAPI 3.1 snapshot from the live FastAPI app for API client/contract review. Source query/form/body fields now expose registry-derived enum hints while runtime unknown-source errors remain HTTP 400 where handlers validate manually.
- `config/vision/sources.yaml`
  - Lane A source registry for `global_cam_01`, `tb3_1_picam`, and `tb3_2_picam`. Robot PiCam physical inputs use compressed handoff topics (`/tb3_1/camera/image_raw/compressed`, `/tb3_2/camera/image_raw/compressed`); legacy `/mission/.../camera/compressed` browser topics remain preserved.
- `docs/contracts/generated/source-registry.snapshot.json` and `docs/contracts/fixtures/source-registry.valid.json`
  - Generated source registry snapshot/fixture used to prevent source/schema/OpenAPI drift.
- `docs/contracts/ai-server-api.md`
  - Now includes Lane B debug/fallback stream with `max_fps`, synthetic frame ingest, raw frame ingest seam, controlled worker tick, stale overlay visual metadata, stream/FPS/drop metrics, per-source debug snapshot, raw frame APIs, and overlay APIs.
- `docs/reports/lane0-contract-brief-2026-06-15.md`
- `docs/reports/lane0-contract-confluence-summary-2026-06-15.md`
  - Lane 0 adopted decision artifacts used to update Confluence API page.
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
  - Validates both `VisionEvent v1` and `LiftRoiEvidence v1` valid/invalid fixtures with additional policy checks. It now also checks source registry snapshot/fixture and schema source enum drift.
- `scripts/generate_source_registry_surfaces.py`
  - Regenerates source-registry-derived schema enums, source registry snapshot/fixture, and `docs/contracts/ai-server-openapi.json`.
- `scripts/validate_deployment_assets.py`
  - Validates central-PC AI Server Dockerfile/docker-compose/systemd assets and runs `docker compose -f docker-compose.ai-server.yml config --quiet` when Docker Compose is available.
- `services/ai-server/Dockerfile`, `docker-compose.ai-server.yml`, `ops/systemd/smartfactory-ai-server.service`
  - Central-PC deployment assets for running AI Server as a container or service without ROS2 runtime imports.
- `Makefile`

ROS2 bringup side:

- ROS2 workspace root: `/home/codelab/turtlebot3_ws` after 2026-06-11 migration.
- Package scaffold: `/home/codelab/turtlebot3_ws/src/smartfactory_bringup`
- ROS2 snapshot adapter package: `/home/codelab/turtlebot3_ws/src/smartfactory_perception_ros` symlinked to tracked repo source `ros2/smartfactory_perception_ros`
- Local `smartfactory_bringup` in `/home/codelab/turtlebot3_ws/src` includes default-off `ai_snapshot_clients.launch.py`; the adapter package also provides a standalone `ros2 launch smartfactory_perception_ros ai_snapshot_clients.launch.py`.
- `smartfactory_perception_ros` now also provides `aruco_pose_monitor`, a passive central-PC monitor that subscribes to raw/compressed images, reuses AI Server pure ArUco/docking logic, logs pose/error/FPS/lost/stale state, and never publishes `/cmd_vel`.
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

Validated again on 2026-06-11 Asia/Seoul after central-PC passive ArUco pose monitor skeleton:

- `cd ros2/smartfactory_perception_ros && pytest -q`: `20 passed`.
- `source /opt/ros/jazzy/setup.bash && cd ros2 && colcon build --symlink-install --packages-select smartfactory_perception_ros --event-handlers console_direct+`: build OK; `aruco_pose_monitor` console script installed in the repo-local overlay. Colcon warned that the same package also exists in `/home/codelab/turtlebot3_ws/install`, so use the intended overlay/source order when running.
- `source /opt/ros/jazzy/setup.bash && cd ros2 && colcon test --packages-select smartfactory_perception_ros --event-handlers console_direct+`: `20 passed`.
- `./scripts/test_ai_server.sh -q`: `56 passed, 1 warning` and contract fixtures behaved as expected.

Validated again on 2026-06-11 Asia/Seoul after AI Server source health/staleness model:

- `./scripts/test_ai_server.sh -q`: `62 passed, 1 warning` and contract fixtures behaved as expected.
- Added fake-clock unit coverage for online/stale/offline/disabled transitions.
- Added API coverage proving marker-free valid frames refresh source health and marker events update last event metadata.

Validated again on 2026-06-11 Asia/Seoul after Lift ROI evidence API/contract design:

- `python3 scripts/validate_contracts.py`: `VisionEvent v1` and `LiftRoiEvidence v1` valid/invalid fixtures behaved as expected.
- Added `LiftRoiEvidence v1` schema and pickup/dropoff valid fixtures.
- Added invalid fixtures for lift count mismatch and source/robot mismatch.
- Documented planned `POST /api/v1/lift-roi/evaluate`; implementation remains after detector/segmenter seam.

Validated again on 2026-06-12 Asia/Seoul after detector/segmenter seam, segmentation-primary lift ROI image endpoint, observability/retention, and central-PC deployment assets:

- `python3 -m py_compile services/ai-server/app/model_adapters.py services/ai-server/app/lift_roi_evidence.py services/ai-server/app/main.py`: OK.
- `./scripts/test_ai_server.sh -q -k 'model_adapters or lift_roi_evaluate_image or pickup_gate or contract_boundaries or deployment_assets'`: `15 passed, 68 deselected, 1 warning`.
- `./scripts/test_ai_server.sh -q`: `83 passed, 1 warning` and contract fixtures behaved as expected.
- `python3 scripts/validate_deployment_assets.py`: `Deployment assets validated.`
- `make ros-build-bringup`: builds `smartfactory_perception_ros` and `smartfactory_bringup` successfully.
- `git diff --check -- services/ai-server/app services/ai-server/tests Makefile docker-compose.ai-server.yml services/ai-server/Dockerfile ops/systemd/smartfactory-ai-server.service scripts/validate_deployment_assets.py .omx/plans/segmentation-primary-lift-roi-20260612.md`: OK.
- Boundary checks found no mandatory `ultralytics`/`torch` dependency in AI Server requirements and no top-level `rclpy`/`sensor_msgs`/`torch`/`ultralytics` imports in `services/ai-server/app`.

Planning/design critique completed on 2026-06-12 Asia/Seoul for future WMS/Main Lift ROI gate integration:

- Artifact: `.omx/plans/wms-main-lift-roi-gate-plan-20260612.md`.
- Status: plan/design-critique complete; **not implemented**.
- Grounded conclusion: this repo currently has no concrete Main/WMS service implementation, only AI Server and an outbound `VisionEvent` client seam.
- Recommended future design: implement the authoritative gate in the real WMS/Main service when its repo/API exists.
- Required WMS rule: `LiftRoiEvidence.verification.status != CONFIRMED` must never advance pickup/dropoff state; it should lead to retry/no-progress/manual exception depending on WMS policy.
- Design critique verdict:
  - reject a local mini-WMS/task state machine inside AI Server;
  - treat any AI Server `LiftRoiEvidence` outbound client as a delivery seam only, not a state-transition gate;
  - require WMS idempotency by `evidence_id` and matching task/source/robot context before mutation;
  - keep raw masks internal and send only contract summaries.
- Implementation precondition: real WMS/Main service code or a confirmed endpoint contract must be provided before coding the actual gate.

Contract/API hardening completed on 2026-06-12 Asia/Seoul:

- Updated `docs/contracts/ai-server-api.md` from planned to implemented status for `POST /api/v1/lift-roi/evaluate`.
- Documented `POST /api/v1/lift-roi/evaluate-image`, `GET /api/v1/metrics`, common error envelope, and split model status in health.
- Generated `docs/contracts/ai-server-openapi.json` from the live FastAPI app.
- Updated `services/ai-server/README.md` endpoint list, Lift ROI runtime settings, and common error response shape.
- Implemented common AI Server error envelope: `{error: {code, message, details, request_id}}`, with `X-Request-ID` response header.
- Strengthened OpenAPI response schemas for `detect/image`, `lift-roi/evaluate`, `lift-roi/evaluate-image`, and `metrics`.
- Health now exposes `models.marker` and `models.lift_roi`; `model_status` remains a backward-compatible base/marker status.

- Packaged contract/API docs at project root: `smartfactory-contract-api-docs-20260612.zip`.
- Contract/API hardening verification:
  - `./scripts/test_ai_server.sh -q`: `85 passed, 1 warning`.
  - `python3 scripts/validate_deployment_assets.py`: `Deployment assets validated.`
  - `git diff --check` on touched contract/API files: OK.

Live Confluence API document published on 2026-06-12 Asia/Seoul:

- Parent: `Implementation` (`https://baksa2584.atlassian.net/wiki/x/KoAfAQ`).
- Live page: `https://baksa2584.atlassian.net/wiki/spaces/KAN/pages/20119566/API`.
- Page title: `API`; page id: `20119566`; space: `KAN`.
- Attached package: `smartfactory-contract-api-docs-20260612.zip`; attachment id: `att20414467`; media type: `application/zip`.
- API verification after publish confirmed page body contains `LiftRoiEvidence v1` and common error response content, and the zip attachment is present.


Live Confluence API page updated to Korean version on 2026-06-12 Asia/Seoul:

- Page: `API` version 3 at `https://baksa2584.atlassian.net/wiki/spaces/KAN/pages/20119566/API`.
- Body is now Korean-centered.
- Added explicit `AI Server API` section.
- Added bottom `API 요청 / 추가 요청란` table and `API 요청 템플릿` for other developers.
- Existing contract docs zip attachment remains linked on the page.

Lane 0 contract alignment and Confluence update completed on 2026-06-15 Asia/Seoul:

- Local artifacts:
  - `docs/reports/lane0-contract-brief-2026-06-15.md`
  - `.omx/plans/lane0-contract-alignment-plan-20260615.md`
  - `docs/reports/lane0-contract-confluence-summary-2026-06-15.md`
- OMX Critic reviews:
  - `.omx/reports/vision-gateway-api-review/critic-lane0-contract-brief-20260615.md`
  - `.omx/reports/vision-gateway-api-review/critic-lane0-contract-brief-rereview-20260615.md`
- Live Confluence API page updated to version 5: `https://baksa2584.atlassian.net/wiki/x/DgAzAQ`.

Lane B first robot-free overlay/debug stream slice implemented on 2026-06-15 Asia/Seoul:

- Added `LatestFrameStore`, `LatestEvidenceCache`, and `overlay.render_overlay`.
- `POST /api/v1/detect/image` now stores latest decoded frame and renders latest overlay image/metadata after detection, including marker-free overlays.
- Added debug/fallback endpoints:
  - `GET /api/v1/vision/streams`
  - `GET /api/v1/vision/overlay/latest?source=...`
  - `GET /api/v1/vision/overlay/latest/image?source=...`
  - `GET /api/v1/vision/stream/{source}.mjpeg`
- Updated `docs/contracts/ai-server-api.md` and regenerated `docs/contracts/ai-server-openapi.json`.
- Validation:
  - `./scripts/test_ai_server.sh -q tests/test_overlay.py tests/test_api.py`: `90 passed, 1 warning` and contract fixtures behaved as expected.
  - `./scripts/test_ai_server.sh -q`: `91 passed, 1 warning` and contract fixtures behaved as expected.

Lane B synthetic frame ingest slice implemented on 2026-06-15 Asia/Seoul:

- Added `generate_synthetic_aruco_frame` in `services/ai-server/app/detectors.py`.
- Added shared `_detect_and_overlay_decoded_frame` path so uploaded images and synthetic frames both update latest-frame cache, source health, event store, metrics, and overlay cache consistently.
- Added `POST /api/v1/vision/synthetic/frame`.
  - Request JSON: `source`, optional `marker_id`/`marker_size`/`padding`, optional `stale`, optional `emit`.
  - Response includes the normal detection fields plus `overlay` metadata.
  - Unknown sources return HTTP 400; invalid request bodies return HTTP 422.
- Updated API docs and regenerated `docs/contracts/ai-server-openapi.json`.
- Validation:
  - `./scripts/test_ai_server.sh -q`: `93 passed, 1 warning` and contract fixtures behaved as expected.

Lane B controlled latest-frame worker tick slice implemented on 2026-06-15 Asia/Seoul:

- Refactored detection/overlay processing into `_detect_and_overlay_frame_snapshot` so stored latest frames can be processed without re-ingesting a new frame.
- Added `POST /api/v1/vision/worker/tick`.
  - Request JSON: optional `source`, optional `force`, optional `stale`.
  - Response returns per-source `processed`, `skipped`, or `no_frame` status plus overlay metadata when available.
  - `force=false` skips when the latest overlay already matches the latest frame sequence; `force=true` reprocesses intentionally for debug.
  - Endpoint is a Lane B debug/control surface only; production browser video remains rosbridge 9090 and Vision still does not publish `/cmd_vel`/Nav2 actions.
- Updated API docs and regenerated `docs/contracts/ai-server-openapi.json`.
- Validation:
  - `./scripts/test_ai_server.sh -q tests/test_api.py tests/test_contract_boundaries.py`: `96 passed, 1 warning` and contract fixtures behaved as expected.
  - `./scripts/test_ai_server.sh -q`: `96 passed, 1 warning` and contract fixtures behaved as expected.

Optional manual API smoke test:

```bash
./scripts/run_ai_server.sh
curl http://127.0.0.1:8100/api/v1/health
```


Lane B stale overlay visual QA slice implemented on 2026-06-15 Asia/Seoul:

- Added `visual_state=fresh|stale` to overlay metadata.
- Strengthened stale overlay JPEG rendering with a full-width amber warning band and `STALE FRAME - DEBUG ONLY` text.
- Added pixel-level overlay test to verify stale overlays are visually different from fresh overlays and display the amber warning band.
- Updated API docs and regenerated `docs/contracts/ai-server-openapi.json`.
- Validation:
  - `./scripts/test_ai_server.sh -q tests/test_overlay.py tests/test_api.py tests/test_contract_boundaries.py`: `97 passed, 1 warning` and contract fixtures behaved as expected.
  - `./scripts/test_ai_server.sh -q`: `97 passed, 1 warning` and contract fixtures behaved as expected.


Lane B stream metrics/FPS/drop counter slice implemented on 2026-06-15 Asia/Seoul:

- Added latest-frame drop counters to `LatestFrameStore.stats()`: `dropped_frames_by_source`, `dropped_frames_total`.
- Added Lane B observability counters:
  - debug MJPEG `clients_total`, `active_clients`, `frames_sent_total`, `stale_polls_total`, `approx_fps`,
  - worker tick status totals/by-source counts,
  - frame-store stats exposed alongside event-store stats.
- `GET /api/v1/metrics` now returns `frame_store` and `metrics.stream`/`metrics.worker`.
- `GET /api/v1/vision/streams` now exposes `debug_fallback.metrics_path=/api/v1/metrics` and per-source `stream_metrics`.
- Debug stream metrics remain local MJPEG/fallback observability only; production browser stream remains rosbridge 9090.
- Updated API docs and regenerated `docs/contracts/ai-server-openapi.json`.
- Validation:
  - `./scripts/test_ai_server.sh -q tests/test_observability.py tests/test_api.py tests/test_contract_boundaries.py`: `99 passed, 1 warning` and contract fixtures behaved as expected.
  - `./scripts/test_ai_server.sh -q`: `99 passed, 1 warning` and contract fixtures behaved as expected.


Lane B source readiness snapshot slice implemented on 2026-06-15 Asia/Seoul:

- Added `GET /api/v1/vision/debug/sources`.
  - Optional `source` query filters to one configured source; omit it for all sources.
  - Response includes source health, latest frame metadata with `size_bytes`, latest overlay metadata, `overlay_lag_frames`, debug paths, stream metrics, and frame drop metrics.
  - `overlay_lag_frames > 0` makes it obvious that a newer frame exists but overlay has not caught up yet; `POST /api/v1/vision/worker/tick` can reconcile this in debug mode.
- `GET /api/v1/vision/streams` now advertises `source_snapshot_path`.
- Updated API docs and regenerated `docs/contracts/ai-server-openapi.json`.
- Validation:
  - `./scripts/test_ai_server.sh -q tests/test_api.py tests/test_contract_boundaries.py`: `102 passed, 1 warning` and contract fixtures behaved as expected.
  - `./scripts/test_ai_server.sh -q`: `102 passed, 1 warning` and contract fixtures behaved as expected.


Lane B debug MJPEG max_fps/rate-limit slice implemented on 2026-06-15 Asia/Seoul:

- Added per-client `max_fps` query parameter to `GET /api/v1/vision/stream/{source}.mjpeg`.
  - Default `10`, allowed range `1..30`.
  - Generator enforces a minimum interval of `1 / max_fps` seconds between sent multipart frames.
  - Each multipart frame includes `X-Debug-Max-FPS` for smoke/debug visibility.
- `GET /api/v1/vision/streams` now advertises `mjpeg_max_fps_default=10` and `mjpeg_max_fps_limit=30`; source entries include `mjpeg_default_max_fps`.
- `GET /api/v1/vision/debug/sources` debug paths now include `mjpeg_default_max_fps`.
- This rate limit applies only to the FastAPI MJPEG debug/fallback plane; production browser streaming remains rosbridge 9090.
- Updated API docs and regenerated `docs/contracts/ai-server-openapi.json`.
- Validation:
  - `./scripts/test_ai_server.sh -q tests/test_api.py tests/test_contract_boundaries.py`: `103 passed, 1 warning` and contract fixtures behaved as expected.
  - `./scripts/test_ai_server.sh -q`: `103 passed, 1 warning` and contract fixtures behaved as expected.


Lane B ROS2 handoff topic matrix slice implemented on 2026-06-15 Asia/Seoul:

- Added `GET /api/v1/vision/ros/topics`.
  - Returns a read-only source-to-topic matrix for Lane B/C planning.
  - Includes `physical_input_topic`, preserved `legacy_browser_topic`, planned `normalized_image_topic`, planned `normalized_overlay_topic`, and `evidence_event_topic=/sf/vision/events`.
  - Explicitly reports `primary_stream_plane=rosbridge`, `debug_only=true`, `motion_command_allowed=false`, and `control_topics_published=[]`.
  - This endpoint does not start ROS2, does not subscribe/publish, and does not expose `/cmd_vel`/Nav2.
- `GET /api/v1/vision/streams` and `GET /api/v1/vision/debug/sources` now point developers to `/api/v1/vision/ros/topics`.
- Updated API docs, Confluence handoff summary, and regenerated `docs/contracts/ai-server-openapi.json`.
- Validation:
  - `./scripts/test_ai_server.sh -q tests/test_api.py tests/test_contract_boundaries.py`: `104 passed, 1 warning` and contract fixtures behaved as expected.
  - `./scripts/test_ai_server.sh -q`: `104 passed, 1 warning` and contract fixtures behaved as expected.


Lane B latest raw frame debug API slice implemented on 2026-06-15 Asia/Seoul:

- Added `GET /api/v1/vision/frame/latest`.
  - Returns latest-frame cache metadata for one source: `source`, `frame_seq`, `frame_timestamp`, `image`, `content_type`, and `size_bytes`.
  - Returns `404` if the source has no cached frame yet.
- Added `GET /api/v1/vision/frame/latest/image`.
  - Returns the newest cached raw frame bytes, normally `image/jpeg`, for GUI/QA comparison against overlay JPEG.
  - This is debug/fallback only; it is not historical frame storage and not the production stream plane.
- `GET /api/v1/vision/streams` and `GET /api/v1/vision/debug/sources` now advertise raw frame metadata/image paths.
- Updated API docs, Confluence handoff summary, and regenerated `docs/contracts/ai-server-openapi.json`.
- Validation:
  - `./scripts/test_ai_server.sh -q tests/test_api.py tests/test_contract_boundaries.py`: `106 passed, 1 warning` and contract fixtures behaved as expected.
  - `./scripts/test_ai_server.sh -q`: `106 passed, 1 warning` and contract fixtures behaved as expected.


Lane B raw frame ingest seam slice implemented on 2026-06-15 Asia/Seoul:

- Added `POST /api/v1/vision/frame`.
  - Accepts `multipart/form-data` with `source` and `image`.
  - Stores a decodable uploaded image in latest-frame cache only.
  - Returns `{source, processed:false, frame, overlay:null, worker_tick_path}`.
  - Does not run detection, does not render overlay, does not start ROS2, and does not publish motion/control topics.
  - This lets future camera/ROS ingest push frames while `POST /api/v1/vision/worker/tick` remains the explicit debug processing step.
- `GET /api/v1/vision/streams` and `GET /api/v1/vision/debug/sources` now advertise the raw frame ingest path.
- Updated API docs, Confluence handoff summary, and regenerated `docs/contracts/ai-server-openapi.json`.
- Validation:
  - `./scripts/test_ai_server.sh -q tests/test_api.py tests/test_contract_boundaries.py`: `108 passed, 1 warning` and contract fixtures behaved as expected.
  - `./scripts/test_ai_server.sh -q`: `108 passed, 1 warning` and contract fixtures behaved as expected.


Lane B worker stale-frame guard slice implemented on 2026-06-15 Asia/Seoul:

- Extended `POST /api/v1/vision/worker/tick` with optional `max_frame_age_s`.
  - If omitted, the guard uses `SOURCE_STALE_AFTER_S`.
  - If latest frame age is greater than the threshold and `force=false`, the worker returns `status=stale_frame`, `event_count=0`, `overlay=null`, and does not run detection/overlay rendering.
  - `force=true` intentionally bypasses the guard for debug reprocessing.
  - Responses for processed/skipped frames include `frame_age_s` and `max_frame_age_s`.
- This prepares Lane C ROS2 ingest for keep-last=1 plus stale-frame drop semantics while keeping HTTP/MJPEG debug/fallback only.
- Updated API docs, Confluence handoff summary, and regenerated `docs/contracts/ai-server-openapi.json`.
- Validation:
  - `./scripts/test_ai_server.sh -q tests/test_api.py tests/test_contract_boundaries.py`: `109 passed, 1 warning` and contract fixtures behaved as expected.
  - `./scripts/test_ai_server.sh -q`: `109 passed, 1 warning` and contract fixtures behaved as expected.


Lane B read-only worker status slice implemented on 2026-06-15 Asia/Seoul:

- Added `GET /api/v1/vision/worker/status`.
  - Optional `source` filters one configured source; omit for all sources.
  - Optional `max_frame_age_s` uses the same stale-frame threshold semantics as worker tick.
  - Returns `summary` counts plus per-source `has_frame`, `has_overlay`, `latest_frame_seq`, `latest_overlay_frame_seq`, `frame_age_s`, `overlay_lag_frames`, `pending`, `next_tick_status`, and `reason`.
  - `next_tick_status` is one of `no_frame`, `processed`, `skipped`, `stale_frame`.
  - Read-only: does not run detection, render overlays, increment worker metrics, start ROS2, or publish motion/control topics.
- `GET /api/v1/vision/streams` and `GET /api/v1/vision/debug/sources` now advertise the worker status path.
- Updated API docs, Confluence handoff summary, and regenerated `docs/contracts/ai-server-openapi.json`.
- Validation:
  - `./scripts/test_ai_server.sh -q tests/test_api.py tests/test_contract_boundaries.py`: `110 passed, 1 warning` and contract fixtures behaved as expected.
  - `./scripts/test_ai_server.sh -q`: `110 passed, 1 warning` and contract fixtures behaved as expected.


Lane B worker status summary slice implemented on 2026-06-15 Asia/Seoul:

- Extended `GET /api/v1/vision/worker/status` with `summary`.
  - `summary.sources_total` counts returned sources.
  - `summary.pending_count` counts sources whose next tick would process a pending frame.
  - `summary.stale_frame_count` counts sources blocked by stale-frame guard.
  - `summary.status_counts` groups `no_frame`, `processed`, `skipped`, and `stale_frame`.
- This remains read-only and does not run detection, render overlays, increment worker metrics, start ROS2, or publish motion/control topics.
- Updated API docs, Confluence handoff summary, and regenerated `docs/contracts/ai-server-openapi.json`.
- Validation:
  - `./scripts/test_ai_server.sh -q tests/test_api.py tests/test_contract_boundaries.py`: `110 passed, 1 warning` and contract fixtures behaved as expected.
  - `./scripts/test_ai_server.sh -q`: `110 passed, 1 warning` and contract fixtures behaved as expected.


Lane B worker tick summary slice implemented on 2026-06-15 Asia/Seoul:

- Extended `POST /api/v1/vision/worker/tick` with response-level `summary`.
  - `summary.sources_total` counts ticked sources.
  - `summary.processed_count`, `summary.skipped_count`, and `summary.stale_frame_count` expose the main result buckets directly.
  - `summary.status_counts` groups `no_frame`, `processed`, `skipped`, and `stale_frame`.
  - `summary.event_count_total` totals events emitted/rendered by this tick response.
- This is still a Lane B debug/control surface only: it does not publish ROS motion commands and does not replace rosbridge `9090` as the production browser stream plane.
- Updated API docs, Confluence handoff summary, and regenerated `docs/contracts/ai-server-openapi.json`.
- Validation:
  - `./scripts/test_ai_server.sh -q tests/test_api.py tests/test_contract_boundaries.py`: `110 passed, 1 warning` and contract fixtures behaved as expected.
  - `./scripts/test_ai_server.sh -q`: `110 passed, 1 warning` and contract fixtures behaved as expected.


Lane B ROS ingest policy seam slice implemented on 2026-06-15 Asia/Seoul:

- Extended `GET /api/v1/vision/ros/topics` with machine-readable Lane C ingest policy:
  - top-level `image_ingest_qos={reliability: BEST_EFFORT, history: KEEP_LAST, depth: 1}`.
  - top-level/per-source `frame_drop_policy` for latest-only cache, stale-frame drop, offline threshold, and overwrite backpressure.
  - `runtime_policy` explicitly says HTTP requests do not start ROS2 and request handlers must not spin the ROS2 executor.
  - per-source message-type fields for physical input, legacy browser topic, normalized image, normalized overlay, and evidence event handoff.
- This keeps the FastAPI service free of ROS2 runtime imports while giving Lane C a concrete, test-covered implementation seam.
- Updated API docs, Confluence handoff summary, and regenerated `docs/contracts/ai-server-openapi.json`.
- Validation:
  - `./scripts/test_ai_server.sh -q tests/test_api.py tests/test_contract_boundaries.py`: `110 passed, 1 warning` and contract fixtures behaved as expected.
  - `./scripts/test_ai_server.sh -q`: `110 passed, 1 warning` and contract fixtures behaved as expected.


Lane B ROS overlay publish readiness slice implemented on 2026-06-15 Asia/Seoul:

- Extended `GET /api/v1/vision/ros/topics` with read-only ROS overlay publish preflight signals:
  - top-level `publish_readiness_summary` with source counts for `no_frame`, `no_overlay`, `overlay_lag`, `ready_fresh`, and `ready_stale`.
  - per-source `publish_readiness.latest_frame_seq`, `latest_overlay_frame_seq`, `frame_age_s`, `overlay_ready`, `readiness_state`, `overlay_visual_state`, `event_count`, and `reason`.
- This lets Lane C ROS publisher work distinguish: no camera frame, frame exists but no overlay, overlay behind latest frame, fresh overlay ready, and stale-marked overlay ready.
- It is still read-only: no ROS2 node is started, no overlay is published, and no motion/control topic is exposed.
- Updated API docs, Confluence handoff summary, and regenerated `docs/contracts/ai-server-openapi.json`.
- Validation:
  - `./scripts/test_ai_server.sh -q tests/test_api.py tests/test_contract_boundaries.py`: `111 passed, 1 warning` and contract fixtures behaved as expected.
  - `./scripts/test_ai_server.sh -q`: `111 passed, 1 warning` and contract fixtures behaved as expected.


Lane B ROS topics source filter slice implemented on 2026-06-15 Asia/Seoul:

- Extended `GET /api/v1/vision/ros/topics` with optional `source` query parameter.
  - Omit `source` to return all configured sources.
  - Provide `source=tb3_1_picam` or another configured source to return only that source.
  - `requested_source` echoes the requested filter, and `publish_readiness_summary` is scoped to the returned rows.
  - Unknown source returns HTTP `400` using the common error envelope.
- This keeps the endpoint read-only and does not start ROS2, publish overlay topics, or expose motion/control topics.
- Updated API docs, Confluence handoff summary, and regenerated `docs/contracts/ai-server-openapi.json`.
- Validation:
  - `./scripts/test_ai_server.sh -q tests/test_api.py tests/test_contract_boundaries.py`: `112 passed, 1 warning` and contract fixtures behaved as expected.
  - `./scripts/test_ai_server.sh -q`: `112 passed, 1 warning` and contract fixtures behaved as expected.


Lane B stream discovery source filter slice implemented on 2026-06-15 Asia/Seoul:

- Extended `GET /api/v1/vision/streams` with optional `source` query parameter.
  - Omit `source` to return all configured stream surfaces.
  - Provide `source=tb3_1_picam` or another configured source to return only that source.
  - `requested_source` echoes the requested filter.
  - Unknown source returns HTTP `400` using the common error envelope.
- This keeps HTTP/MJPEG/frame APIs debug/fallback only; rosbridge `9090` remains the production browser stream plane.
- Updated API docs, Confluence handoff summary, and regenerated `docs/contracts/ai-server-openapi.json`.
- Validation:
  - `./scripts/test_ai_server.sh -q tests/test_api.py tests/test_contract_boundaries.py`: `113 passed, 1 warning` and contract fixtures behaved as expected.
  - `./scripts/test_ai_server.sh -q`: `113 passed, 1 warning` and contract fixtures behaved as expected.


Lane B metrics source filter slice implemented on 2026-06-15 Asia/Seoul:

- Extended `GET /api/v1/metrics` with optional `source` query parameter.
  - Omit `source` to return the service-wide metrics snapshot.
  - Provide `source=tb3_1_picam` or another configured source to scope Lane B `stream`, `worker`, and `frame_store` counters to that source.
  - `requested_source` echoes the requested filter.
  - Unknown source returns HTTP `400` using the common error envelope.
- HTTP/model counters remain service-level even when a source filter is used; this keeps the endpoint honest about what is global vs per-camera.
- Updated API docs, Confluence handoff summary, and regenerated `docs/contracts/ai-server-openapi.json`.
- Validation:
  - `./scripts/test_ai_server.sh -q tests/test_api.py tests/test_contract_boundaries.py`: `115 passed, 1 warning` and contract fixtures behaved as expected.
  - `./scripts/test_ai_server.sh -q`: `115 passed, 1 warning` and contract fixtures behaved as expected.


Lane B source-scoped discovery links slice implemented on 2026-06-15 Asia/Seoul:

- Updated source-level discovery links to advertise source-scoped observability/handoff paths now that those filters exist.
  - `GET /api/v1/vision/streams` source entries now include `metrics_path=/api/v1/metrics?source={source}` and `ros_handoff_source_path=/api/v1/vision/ros/topics?source={source}`.
  - `GET /api/v1/vision/debug/sources` `debug_paths.metrics` now points to `/api/v1/metrics?source={source}` and keeps `metrics_all=/api/v1/metrics`.
  - `debug_paths.ros_handoff` now points to `/api/v1/vision/ros/topics?source={source}` and keeps `ros_handoff_all=/api/v1/vision/ros/topics`.
- This is a read-only discovery consistency slice only; no ROS2 node is started and no overlay/motion topic is published.
- Updated API docs, Confluence handoff summary, and regenerated `docs/contracts/ai-server-openapi.json`.
- Validation:
  - `./scripts/test_ai_server.sh -q tests/test_api.py tests/test_contract_boundaries.py`: `115 passed, 1 warning` and contract fixtures behaved as expected.
  - `./scripts/test_ai_server.sh -q`: `115 passed, 1 warning` and contract fixtures behaved as expected.


Lane B stream frame/overlay sync status slice implemented on 2026-06-15 Asia/Seoul:

- Extended `GET /api/v1/vision/streams` source entries with lightweight frame/overlay synchronization state:
  - `latest_frame_seq`
  - `latest_overlay_frame_seq`
  - `overlay_lag_frames`
  - `overlay_visual_state`
- This lets GUI/debug users see whether the latest overlay has caught up to the latest frame directly from stream discovery, without opening `/api/v1/vision/debug/sources`.
- This is read-only metadata only; it does not start ROS2, publish overlays, or change the debug/fallback stream plane.
- Updated API docs, Confluence handoff summary, and regenerated `docs/contracts/ai-server-openapi.json`.
- Validation:
  - `./scripts/test_ai_server.sh -q tests/test_api.py tests/test_contract_boundaries.py`: `115 passed, 1 warning` and contract fixtures behaved as expected.
  - `./scripts/test_ai_server.sh -q`: `115 passed, 1 warning` and contract fixtures behaved as expected.


Lane B stream discovery summary slice implemented on 2026-06-15 Asia/Seoul:

- Extended `GET /api/v1/vision/streams` with response-level `summary`.
  - `summary.sources_total`
  - `summary.with_frame_count`
  - `summary.with_overlay_count`
  - `summary.overlay_lag_count`
  - `summary.synced_overlay_count`
  - `summary.stale_overlay_count`
- Summary is computed over returned `sources`; if `source` query is set, it summarizes that one source only.
- This is read-only discovery metadata only; it does not start ROS2, publish overlays, or change the debug/fallback stream plane.
- Updated API docs, Confluence handoff summary, and regenerated `docs/contracts/ai-server-openapi.json`.
- Validation:
  - `./scripts/test_ai_server.sh -q tests/test_api.py tests/test_contract_boundaries.py`: `115 passed, 1 warning` and contract fixtures behaved as expected.
  - `./scripts/test_ai_server.sh -q`: `115 passed, 1 warning` and contract fixtures behaved as expected.


Lane B ROS ingest readiness preflight slice implemented on 2026-06-15 Asia/Seoul:

- Extended `GET /api/v1/vision/ros/topics` with read-only ROS image subscriber preflight metadata.
  - top-level `ingest_readiness_summary.sources_total`
  - `ingest_readiness_summary.contract_ready_count`
  - `ingest_readiness_summary.missing_physical_topic_count`
  - `ingest_readiness_summary.runtime_subscriber_active_count`
  - per-source `ingest_readiness.readiness_state=contract_ready|missing_physical_topic`
  - per-source `ingest_readiness.physical_input_topic_configured`
  - per-source `ingest_readiness.runtime_subscriber_active=false` in Lane B
- This makes Lane C ROS image subscriber preparation explicit without starting ROS2 from FastAPI or changing the debug/fallback stream plane.
- Updated API docs, Confluence handoff summary, and regenerated `docs/contracts/ai-server-openapi.json`.
- Validation:
  - `./scripts/test_ai_server.sh -q tests/test_api.py tests/test_contract_boundaries.py`: `116 passed, 1 warning` and contract fixtures behaved as expected.
  - `./scripts/test_ai_server.sh -q`: `116 passed, 1 warning` and contract fixtures behaved as expected.


Lane B source snapshot ROS ingest readiness slice implemented on 2026-06-15 Asia/Seoul:

- Extended `GET /api/v1/vision/debug/sources` source entries with `ros_ingest_readiness`.
  - `readiness_state=contract_ready|missing_physical_topic`
  - `physical_input_topic_configured`
  - `runtime_subscriber_active=false` in Lane B
  - `http_debug_ingest_path=/api/v1/vision/frame`
  - `required_qos_profile` and `frame_drop_policy` copied from the ROS handoff contract
- This lets GUI/debug users inspect frame/overlay/stream state and ROS ingest preflight from one source snapshot endpoint without starting ROS2.
- Updated API docs, Confluence handoff summary, and regenerated `docs/contracts/ai-server-openapi.json`.
- Validation:
  - `./scripts/test_ai_server.sh -q tests/test_api.py tests/test_contract_boundaries.py`: `116 passed, 1 warning` and contract fixtures behaved as expected.
  - `./scripts/test_ai_server.sh -q`: `116 passed, 1 warning` and contract fixtures behaved as expected.


Lane B source snapshot ROS publish readiness slice implemented on 2026-06-15 Asia/Seoul:

- Extended `GET /api/v1/vision/debug/sources` source entries with `ros_publish_readiness`.
  - `readiness_state=no_frame|no_overlay|overlay_lag|ready_fresh|ready_stale`
  - `overlay_ready`
  - `latest_frame_seq` and `latest_overlay_frame_seq`
  - `overlay_visual_state`, `event_count`, and human-readable `reason`
- This lets GUI/debug users inspect ROS ingest and overlay publish preflight from the same source snapshot endpoint without starting ROS2 or publishing overlays.
- Updated API docs, Confluence handoff summary, and regenerated `docs/contracts/ai-server-openapi.json`.
- Validation:
  - `./scripts/test_ai_server.sh -q tests/test_api.py tests/test_contract_boundaries.py`: `116 passed, 1 warning` and contract fixtures behaved as expected.
  - `./scripts/test_ai_server.sh -q`: `116 passed, 1 warning` and contract fixtures behaved as expected.


Lane B source snapshot summary slice implemented on 2026-06-15 Asia/Seoul:

- Extended `GET /api/v1/vision/debug/sources` with response-level `summary`.
  - `sources_total`
  - `with_frame_count`
  - `with_overlay_count`
  - `overlay_lag_count`
  - `ros_ingest_contract_ready_count`
  - `ros_publish_ready_count`
  - `stale_overlay_count`
- Summary is computed over returned `sources`; if `source` query is set, it summarizes that one source only.
- This gives GUI/debug users a one-call overview of frame, overlay, lag, ROS ingest, and ROS publish readiness without starting ROS2.
- Updated API docs, Confluence handoff summary, and regenerated `docs/contracts/ai-server-openapi.json`.
- Validation:
  - `./scripts/test_ai_server.sh -q tests/test_api.py tests/test_contract_boundaries.py`: `116 passed, 1 warning` and contract fixtures behaved as expected.
  - `./scripts/test_ai_server.sh -q`: `116 passed, 1 warning` and contract fixtures behaved as expected.


Lane B source snapshot requested_source slice implemented on 2026-06-15 Asia/Seoul:

- Extended `GET /api/v1/vision/debug/sources` with top-level `requested_source`.
  - `null` when all sources are returned.
  - source ID when `source=...` filter is used.
- This aligns debug source snapshots with `GET /api/v1/vision/streams`, `GET /api/v1/vision/ros/topics`, and `GET /api/v1/metrics`, so GUI/debug logs can distinguish all-source vs source-scoped responses.
- Updated API docs, Confluence handoff summary, and regenerated `docs/contracts/ai-server-openapi.json`.
- Validation:
  - `./scripts/test_ai_server.sh -q tests/test_api.py tests/test_contract_boundaries.py`: `116 passed, 1 warning` and contract fixtures behaved as expected.
  - `./scripts/test_ai_server.sh -q`: `116 passed, 1 warning` and contract fixtures behaved as expected.


Lane B source snapshot summary breakdown slice implemented on 2026-06-15 Asia/Seoul:

- Extended `GET /api/v1/vision/debug/sources` response-level `summary` with state breakdowns.
  - `health_status_counts`
  - `ros_ingest_status_counts`
  - `ros_publish_status_counts`
- These counts are computed over returned `sources`; if `source` query is set, they describe that one source only.
- This lets GUI/debug users distinguish online/offline/stale health and ROS ingest/publish readiness categories without inspecting every source row.
- Updated API docs, Confluence handoff summary, and regenerated `docs/contracts/ai-server-openapi.json`.
- Validation:
  - `./scripts/test_ai_server.sh -q tests/test_api.py tests/test_contract_boundaries.py`: `116 passed, 1 warning` and contract fixtures behaved as expected.
  - `./scripts/test_ai_server.sh -q`: `116 passed, 1 warning` and contract fixtures behaved as expected.


Lane B overlay latest sync metadata slice implemented on 2026-06-15 Asia/Seoul:

- Extended `GET /api/v1/vision/overlay/latest` with top-level `requested_source` and `sync`.
  - `sync.latest_frame_seq`
  - `sync.latest_overlay_frame_seq`
  - `sync.overlay_lag_frames`
  - `sync.overlay_visual_state`
- Existing `overlay` payload remains unchanged; sync metadata is additive and read-only.
- This lets GUI/debug users detect when an overlay image is behind the latest frame before opening `/api/v1/vision/overlay/latest/image` or the MJPEG stream.
- Updated API docs, Confluence handoff summary, and regenerated `docs/contracts/ai-server-openapi.json`.
- Validation:
  - `./scripts/test_ai_server.sh -q tests/test_api.py tests/test_contract_boundaries.py`: `117 passed, 1 warning` and contract fixtures behaved as expected.
  - `./scripts/test_ai_server.sh -q`: `117 passed, 1 warning` and contract fixtures behaved as expected.


Lane B ROS ingest runtime plan metadata slice implemented on 2026-06-15 Asia/Seoul:

- Extended per-source `ingest_readiness` metadata in `GET /api/v1/vision/ros/topics` and `GET /api/v1/vision/debug/sources` with `runtime_plan`.
  - `runtime_plan.executor=MultiThreadedExecutor`
  - `runtime_plan.spin_location=background_thread`
  - `runtime_plan.shared_state=LatestFrameStore`
  - `runtime_plan.http_handler_role=read_latest_state_only_never_spin_ros2`
  - `runtime_plan.backpressure=overwrite_latest_frame_per_source`
  - `runtime_plan.startup_owner=process_startup_or_launch_file_not_http_request`
- This remains read-only Lane B metadata: it does not import/start/spin ROS2 and does not publish `/cmd_vel`, Nav2, image, or overlay topics.
- Purpose: make the Lane C implementation shape explicit before adding real ROS2 subscribers/publishers.
- Updated API docs, Confluence handoff summary, and regenerated `docs/contracts/ai-server-openapi.json`.
- Validation:
  - `./scripts/test_ai_server.sh -q tests/test_api.py tests/test_contract_boundaries.py`: `117 passed, 1 warning` and contract fixtures behaved as expected.
  - `./scripts/test_ai_server.sh -q`: `117 passed, 1 warning` and contract fixtures behaved as expected.


Lane B ROS overlay publish runtime plan metadata slice implemented on 2026-06-15 Asia/Seoul:

- Extended per-source `publish_readiness` metadata in `GET /api/v1/vision/ros/topics` and `GET /api/v1/vision/debug/sources` with `runtime_plan`.
  - `runtime_plan.executor=MultiThreadedExecutor`
  - `runtime_plan.spin_location=background_thread`
  - `runtime_plan.publish_topic=/sf/vision/sources/{source}/overlay/compressed`
  - `runtime_plan.publish_condition=overlay_ready_true_and_latest_overlay_frame_seq_matches_latest_frame_seq`
  - `runtime_plan.lag_behavior=do_not_publish_lagging_overlay`
  - `runtime_plan.stale_behavior=publish_ready_stale_overlay_with_visual_warning_band`
  - `runtime_plan.control_publish_allowed=false`
- This remains read-only Lane B metadata: it does not import/start/spin ROS2 and does not publish `/cmd_vel`, Nav2, image, or overlay topics.
- Purpose: make the Lane C overlay publisher shape explicit and separate it from motion/control publishing.
- Updated API docs, Confluence handoff summary, and regenerated `docs/contracts/ai-server-openapi.json`.
- Validation:
  - `./scripts/test_ai_server.sh -q tests/test_api.py tests/test_contract_boundaries.py`: `117 passed, 1 warning` and contract fixtures behaved as expected.
  - `./scripts/test_ai_server.sh -q`: `117 passed, 1 warning` and contract fixtures behaved as expected.


Lane B ROS topic exposure policy metadata slice implemented on 2026-06-15 Asia/Seoul:

- Added top-level `topic_exposure_policy` to `GET /api/v1/vision/ros/topics`.
  - `policy=explicit_allowlist_only`
  - `rosbridge_exposes_all_topics=false`
  - `client_publish_allowed=false`
  - `server_publish_control_allowed=false`
  - `forbidden_topic_globs` includes `/cmd_vel`, `*/cmd_vel`, Nav2 action-like topics, `/parameter_events`, `/rosout`, `/tf`, and `/tf_static`.
- Added per-source `topic_exposure` with allowed browser, ingest, and publish topics.
- This is read-only Lane B contract metadata: it does not configure rosbridge, start ROS2, or publish any topic.
- Purpose: make the Lane C/GUI safety boundary explicit before real ROS bridge configuration.
- Updated API docs, Confluence handoff summary, and regenerated `docs/contracts/ai-server-openapi.json`.
- Validation:
  - `./scripts/test_ai_server.sh -q tests/test_api.py tests/test_contract_boundaries.py`: `117 passed, 1 warning` and contract fixtures behaved as expected.
  - `./scripts/test_ai_server.sh -q`: `117 passed, 1 warning` and contract fixtures behaved as expected.


Lane B ROS topic exposure summary metadata slice implemented on 2026-06-15 Asia/Seoul:

- Added top-level `topic_exposure_summary` to `GET /api/v1/vision/ros/topics`.
  - Counts allowed browser, ingest, and publish topics over the returned source rows.
  - Counts forbidden topic globs and forbidden capabilities from `topic_exposure_policy`.
  - Confirms safe defaults: `control_topic_allowed_count=0`, `client_publish_allowed_source_count=0`, `rosbridge_exposes_all_topics=false`, `server_publish_control_allowed=false`.
- The summary respects `source` filtering; `source=tb3_2_picam` summarizes only that source.
- This remains read-only Lane B metadata: it does not configure rosbridge, start ROS2, or publish any topic.
- Updated API docs, Confluence handoff summary, and regenerated `docs/contracts/ai-server-openapi.json`.
- Validation:
  - `./scripts/test_ai_server.sh -q tests/test_api.py tests/test_contract_boundaries.py`: `117 passed, 1 warning` and contract fixtures behaved as expected.
  - `./scripts/test_ai_server.sh -q`: `117 passed, 1 warning` and contract fixtures behaved as expected.


Lane B ROS topic exposure summary preflight slice implemented on 2026-06-15 Asia/Seoul:

- Extended `topic_exposure_summary` in `GET /api/v1/vision/ros/topics` with safety gate fields.
  - `policy_status=safe` when no exposure violations are present.
  - `policy_violation_count=0` and `policy_violations=[]` for the current Lane B contract.
  - Violations are designed to surface future drift such as full rosbridge graph exposure, control topic exposure, server control publishing, or client publish enablement.
- The preflight respects `source` filtering because it is computed from returned source rows.
- This remains read-only Lane B metadata: it does not configure rosbridge, start ROS2, or publish any topic.
- Updated API docs, Confluence handoff summary, and regenerated `docs/contracts/ai-server-openapi.json`.
- Validation:
  - `./scripts/test_ai_server.sh -q tests/test_api.py tests/test_contract_boundaries.py`: `117 passed, 1 warning` and contract fixtures behaved as expected.
  - `./scripts/test_ai_server.sh -q`: `117 passed, 1 warning` and contract fixtures behaved as expected.


Lane B source debug snapshot topic exposure mirror slice implemented on 2026-06-15 Asia/Seoul:

- Mirrored ROS/rosbridge topic exposure metadata into `GET /api/v1/vision/debug/sources`.
  - Added top-level `topic_exposure_policy`.
  - Added top-level `topic_exposure_summary` computed over returned source rows.
  - Added per-source `topic_exposure` with allowed browser, ingest, and publish topics.
- The mirror respects `source` filtering; `source=tb3_1_picam` summarizes only that source.
- This lets GUI/Main developers inspect frame/overlay readiness and ROS topic allowlist safety from one debug snapshot endpoint without opening `/api/v1/vision/ros/topics` separately.
- This remains read-only Lane B metadata: it does not configure rosbridge, start ROS2, or publish any topic.
- Updated API docs, Confluence handoff summary, and regenerated `docs/contracts/ai-server-openapi.json`.
- Validation:
  - `./scripts/test_ai_server.sh -q tests/test_api.py tests/test_contract_boundaries.py`: `117 passed, 1 warning` and contract fixtures behaved as expected.
  - `./scripts/test_ai_server.sh -q`: `117 passed, 1 warning` and contract fixtures behaved as expected.


Lane B stream discovery topic exposure mirror slice implemented on 2026-06-15 Asia/Seoul:

- Mirrored ROS/rosbridge topic exposure metadata into `GET /api/v1/vision/streams`.
  - Added top-level `topic_exposure_policy`.
  - Added top-level `topic_exposure_summary` computed over returned stream source rows.
  - Added per-source `topic_exposure`.
  - Added per-source `rosbridge_subscription_hints` with recommended normalized image/overlay topics and preserved legacy browser topic.
- The mirror respects `source` filtering; `source=tb3_1_picam` summarizes only that source.
- This lets GUI choose safe rosbridge subscription topics directly from stream discovery while HTTP/MJPEG remains debug/fallback only.
- This remains read-only Lane B metadata: it does not configure rosbridge, start ROS2, or publish any topic.
- Updated API docs, Confluence handoff summary, and regenerated `docs/contracts/ai-server-openapi.json`.
- Validation:
  - `./scripts/test_ai_server.sh -q tests/test_api.py tests/test_contract_boundaries.py`: `117 passed, 1 warning` and contract fixtures behaved as expected.
  - `./scripts/test_ai_server.sh -q`: `117 passed, 1 warning` and contract fixtures behaved as expected.


Lane B debug source rosbridge subscription hints mirror slice implemented on 2026-06-15 Asia/Seoul:

- Added per-source `rosbridge_subscription_hints` to `GET /api/v1/vision/debug/sources`.
  - `recommended_image_topic=/sf/vision/sources/{source}/image/compressed`
  - `recommended_overlay_topic=/sf/vision/sources/{source}/overlay/compressed`
  - `legacy_browser_topic=/mission/...` where applicable
  - `client_publish_allowed=false`
  - `control_topics_allowed=[]`
- Reused the same helper as `GET /api/v1/vision/streams` so stream discovery and debug source snapshots stay aligned.
- This lets GUI/Main developers inspect source health, latest frame/overlay state, ROS readiness, and safe rosbridge subscription topics from one debug snapshot endpoint.
- This remains read-only Lane B metadata: it does not configure rosbridge, start ROS2, or publish any topic.
- Updated API docs, Confluence handoff summary, and regenerated `docs/contracts/ai-server-openapi.json`.
- Validation:
  - `./scripts/test_ai_server.sh -q tests/test_api.py tests/test_contract_boundaries.py`: `117 passed, 1 warning` and contract fixtures behaved as expected.
  - `./scripts/test_ai_server.sh -q`: `117 passed, 1 warning` and contract fixtures behaved as expected.


Lane B ROS ingest adapter contract slice implemented on 2026-06-15 Asia/Seoul:

- Added `_store_latest_frame_from_bytes` as the shared latest-frame ingest adapter for current HTTP debug ingest and future background ROS subscriber callbacks.
  - Inputs: `source`, encoded image bytes, `content_type`.
  - Output: `StoredFrame` in `LatestFrameStore`.
  - Side effect: source health frame count/timestamp update.
  - Explicit non-goals: no inline detection, no overlay rendering, no ROS2 spin, no ROS publish.
- `POST /api/v1/vision/frame` now uses that adapter and returns `ingest_context`.
  - `transport=http_debug`
  - `stored_in_latest_frame_cache=true`
  - `processed_inline=false`
  - `source_health_updated=true`
  - `ros_callback_compatible=true`
- `GET /api/v1/vision/ros/topics` and mirrored readiness views now expose the adapter contract in `ingest_readiness.runtime_plan.ingest_adapter_contract`.
- This narrows Lane C implementation risk: a future ROS subscriber callback should call the same store/update seam rather than duplicating frame-cache logic or running work inside HTTP handlers.
- Updated API docs, Confluence handoff summary, and regenerated `docs/contracts/ai-server-openapi.json`.
- Validation:
  - `./scripts/test_ai_server.sh -q tests/test_api.py tests/test_contract_boundaries.py`: `118 passed, 1 warning` and contract fixtures behaved as expected.
  - `./scripts/test_ai_server.sh -q`: `118 passed, 1 warning` and contract fixtures behaved as expected.


Lane B ROS overlay publish payload preview slice implemented on 2026-06-15 Asia/Seoul:

- Added `_overlay_publish_payload_preview_for_source` as a read-only publish adapter preview for future ROS overlay publisher callbacks.
  - Returns publishable compressed overlay metadata only when latest frame and latest overlay image exist and their `frame_seq` values match.
  - Returns `payload_available=false` for `no_frame`, `no_overlay`, and `overlay_lag` states.
  - Allows stale overlays only through the existing visually-marked stale overlay path.
  - Exposes topic/message/content metadata but never publishes ROS and never returns image bytes in JSON.
- Extended `ros_publish_readiness` with `publish_payload_preview`.
  - `topic=/sf/vision/sources/{source}/overlay/compressed`
  - `message_type=sensor_msgs/msg/CompressedImage`
  - `payload_available=true|false`
  - `frame_seq`, `content_type`, `size_bytes`, and `reason`
- Extended `publish_readiness.runtime_plan` with `publish_adapter` and `publish_adapter_contract` so Lane C implementation can reuse the same safe publish eligibility rule.
- This remains read-only Lane B metadata: it does not configure rosbridge, start ROS2, or publish any topic.
- Updated API docs, Confluence handoff summary, and regenerated `docs/contracts/ai-server-openapi.json`.
- Validation:
  - `./scripts/test_ai_server.sh -q tests/test_api.py tests/test_contract_boundaries.py`: `119 passed, 1 warning` and contract fixtures behaved as expected.
  - `./scripts/test_ai_server.sh -q`: `119 passed, 1 warning` and contract fixtures behaved as expected.


Lane B ROS publish payload summary slice implemented on 2026-06-15 Asia/Seoul:

- Added response-level publish payload eligibility counts for future ROS overlay publisher handoff.
- `GET /api/v1/vision/ros/topics` `publish_readiness_summary` now includes:
  - `publish_payload_available_count`: returned sources whose cached compressed overlay is eligible for future ROS publish.
  - `publish_payload_blocked_count`: returned sources blocked by no frame, no overlay, or overlay lag.
- `GET /api/v1/vision/debug/sources` `summary` now includes:
  - `ros_publish_payload_available_count` over returned source rows.
- This lets GUI/Main see the publish plane readiness at a glance without iterating every source entry.
- This remains read-only Lane B metadata: it does not configure rosbridge, start ROS2, publish overlays, or expose image bytes in JSON.
- Updated API docs, Confluence handoff summary, and regenerated `docs/contracts/ai-server-openapi.json`.
- Validation:
  - `./scripts/test_ai_server.sh -q tests/test_api.py tests/test_contract_boundaries.py`: `119 passed, 1 warning` and contract fixtures behaved as expected.
  - `./scripts/test_ai_server.sh -q`: `119 passed, 1 warning` and contract fixtures behaved as expected.


Lane B ROS overlay publish QoS/policy slice implemented on 2026-06-15 Asia/Seoul:

- Added structured future overlay publisher settings to `GET /api/v1/vision/ros/topics`.
  - Top-level `overlay_publish_qos`: `BEST_EFFORT`, `KEEP_LAST`, `depth=1`, `VOLATILE`.
  - Top-level `overlay_publish_policy`: JPEG compressed image, `max_publish_fps=10`, keep-last/drop-old-overlay behavior, no lagging overlay publish, no control topic publish, and no HTTP handler publish.
  - Per-source `overlay_publish_qos` and `overlay_publish_policy` mirror the top-level policy so source rows are self-contained.
  - `publish_readiness.runtime_plan` now includes `publish_qos_profile` and `publish_policy`.
- This turns the previously prose-only publish behavior into a structured Lane C handoff contract.
- This remains read-only Lane B metadata: it does not configure rosbridge, start ROS2, publish overlays, or expose image bytes in JSON.
- Updated API docs, Confluence handoff summary, and regenerated `docs/contracts/ai-server-openapi.json`.
- Validation:
  - `./scripts/test_ai_server.sh -q tests/test_api.py tests/test_contract_boundaries.py`: `119 passed, 1 warning` and contract fixtures behaved as expected.
  - `./scripts/test_ai_server.sh -q`: `119 passed, 1 warning` and contract fixtures behaved as expected.


Lane B ROS evidence event publish policy slice implemented on 2026-06-15 Asia/Seoul:

- Added structured future evidence-event publisher policy to `GET /api/v1/vision/ros/topics`.
  - Top-level `evidence_event_publish_policy` for `/sf/vision/events`.
  - Per-source `evidence_event_publish_policy` mirrors the top-level policy so source rows are self-contained.
- Policy states:
  - message type: `smartfactory_msgs/msg/VisionEvent or JSON bridge payload`
  - schema: `vision-event.v1`
  - QoS: `RELIABLE`, `KEEP_LAST`, `depth=10`, `VOLATILE`
  - publish condition: schema-valid VisionEvent emitted by detector/worker path
  - dedup key: `event_id`
  - Main/WMS remains authoritative; Vision publishes evidence only
  - no image bytes, no control topics, no HTTP handler publish
- This keeps the evidence event plane separate from high-bandwidth overlay image publishing.
- This remains read-only Lane B metadata: it does not start ROS2 or publish events.
- Updated API docs, Confluence handoff summary, and regenerated `docs/contracts/ai-server-openapi.json`.
- Validation:
  - `./scripts/test_ai_server.sh -q tests/test_api.py tests/test_contract_boundaries.py`: `119 passed, 1 warning` and contract fixtures behaved as expected.
  - `./scripts/test_ai_server.sh -q`: `119 passed, 1 warning` and contract fixtures behaved as expected.


Lane B ROS evidence event publish readiness slice implemented on 2026-06-15 Asia/Seoul:

- Added read-only future evidence-event publish readiness to `GET /api/v1/vision/ros/topics`.
  - Per-source `evidence_event_publish_readiness` checks whether the source currently has a latest `VisionEvent` eligible for future `/sf/vision/events` publishing.
  - Top-level `evidence_event_publish_readiness_summary` counts `publish_ready_count` and `no_event_count` over returned source rows.
- Readiness includes latest event id/kind/timestamp/schema when available, uses `event_id` as dedup key, and confirms the payload contains no image bytes.
- This keeps evidence publishing separate from overlay image publishing while giving Lane C a simple preflight check.
- This remains read-only Lane B metadata: it does not start ROS2 or publish events.
- Updated API docs, Confluence handoff summary, and regenerated `docs/contracts/ai-server-openapi.json`.
- Validation:
  - `./scripts/test_ai_server.sh -q tests/test_api.py tests/test_contract_boundaries.py`: `119 passed, 1 warning` and contract fixtures behaved as expected.
  - `./scripts/test_ai_server.sh -q`: `119 passed, 1 warning` and contract fixtures behaved as expected.


Lane B stream evidence event readiness mirror slice implemented on 2026-06-15 Asia/Seoul:

- Mirrored `evidence_event_publish_readiness` into `GET /api/v1/vision/streams` source entries.
- Added stream `summary.evidence_event_publish_ready_count` over returned source rows.
- This lets GUI stream discovery show whether a source has a latest `VisionEvent` eligible for future `/sf/vision/events` publish without opening `/vision/ros/topics` or `/vision/debug/sources`.
- This remains read-only Lane B metadata: no ROS2 start, no event publish, no image bytes in JSON, and no motion/control topic exposure.
- Updated API docs, Confluence handoff summary, and regenerated `docs/contracts/ai-server-openapi.json`.
- Validation:
  - `./scripts/test_ai_server.sh -q tests/test_api.py tests/test_contract_boundaries.py`: `119 passed, 1 warning` and contract fixtures behaved as expected.
  - `./scripts/test_ai_server.sh -q`: `119 passed, 1 warning` and contract fixtures behaved as expected.


Lane B stream ROS overlay publish readiness mirror slice implemented on 2026-06-15 Asia/Seoul:

- Mirrored `ros_publish_readiness` into `GET /api/v1/vision/streams` source entries.
- Added stream summary counts over returned source rows:
  - `ros_publish_ready_count`
  - `ros_publish_payload_available_count`
  - `ros_publish_payload_blocked_count`
  - `ros_publish_status_counts`
- This lets GUI stream discovery show whether a source has a latest overlay payload eligible for future `/sf/vision/sources/{source}/overlay/compressed` publish without opening `/vision/ros/topics` or `/vision/debug/sources`.
- This remains read-only Lane B metadata: no ROS2 start, no overlay publish, no image bytes in JSON, no `/cmd_vel`, and no Nav2/control topic exposure.
- Updated API docs, Confluence handoff summary, and regenerated `docs/contracts/ai-server-openapi.json`.
- Validation:
  - `./scripts/test_ai_server.sh -q tests/test_api.py tests/test_contract_boundaries.py`: `119 passed, 1 warning` and contract fixtures behaved as expected.
  - `./scripts/test_ai_server.sh -q`: `119 passed, 1 warning` and contract fixtures behaved as expected.
  - app code guard: no `sensor_msgs`/`rclpy` text in `services/ai-server/app` excluding `*.pyc`.


Lane B stream ROS ingest readiness mirror slice implemented on 2026-06-15 Asia/Seoul:

- Mirrored `ros_ingest_readiness` into `GET /api/v1/vision/streams` source entries.
- Added stream summary counts over returned source rows:
  - `ros_ingest_contract_ready_count`
  - `ros_ingest_runtime_subscriber_active_count`
  - `ros_ingest_status_counts`
- This lets GUI stream discovery show whether a source has a configured physical ROS image topic and is ready for future Lane C subscriber attachment without opening `/vision/ros/topics` or `/vision/debug/sources`.
- This remains read-only Lane B metadata: no ROS2 start, no subscriber activation, no image bytes in JSON, no `/cmd_vel`, and no Nav2/control topic exposure.
- Updated API docs, Confluence handoff summary, and regenerated `docs/contracts/ai-server-openapi.json`.
- Validation:
  - `./scripts/test_ai_server.sh -q tests/test_api.py tests/test_contract_boundaries.py`: `119 passed, 1 warning` and contract fixtures behaved as expected.
  - `./scripts/test_ai_server.sh -q`: `119 passed, 1 warning` and contract fixtures behaved as expected.
  - app code guard: no `sensor_msgs`/`rclpy` text in `services/ai-server/app` excluding `*.pyc`.


Lane B stream runtime policy mirror slice implemented on 2026-06-15 Asia/Seoul:

- Mirrored top-level `runtime_policy` into `GET /api/v1/vision/streams`.
- The stream discovery response now explicitly states:
  - HTTP requests do not start ROS2.
  - HTTP handlers must not spin the ROS2 executor.
  - Lane C should use a background `MultiThreadedExecutor` with lock-protected latest-frame handoff.
- This lets GUI/Main confirm the stream API's runtime safety boundary without opening `/vision/ros/topics`.
- This remains read-only Lane B metadata: no ROS2 start, no spin, no publish, no image bytes in JSON, no `/cmd_vel`, and no Nav2/control topic exposure.
- Updated API docs, Confluence handoff summary, and regenerated `docs/contracts/ai-server-openapi.json`.
- Validation:
  - `./scripts/test_ai_server.sh -q tests/test_api.py tests/test_contract_boundaries.py`: `119 passed, 1 warning` and contract fixtures behaved as expected.
  - `./scripts/test_ai_server.sh -q`: `119 passed, 1 warning` and contract fixtures behaved as expected.
  - app code guard: no `sensor_msgs`/`rclpy` text in `services/ai-server/app` excluding `*.pyc`.


Lane B stream motion-control safety mirror slice implemented on 2026-06-15 Asia/Seoul:

- Mirrored top-level motion/control safety fields into `GET /api/v1/vision/streams`:
  - `debug_only=true`
  - `motion_command_allowed=false`
  - `control_topics_published=[]`
- This lets GUI/Main confirm from stream discovery that Vision Gateway remains evidence/stream-only and does not publish `/cmd_vel`, Nav2, or any control topic.
- This remains read-only Lane B metadata: no ROS2 start, no spin, no publish, no image bytes in JSON, no `/cmd_vel`, and no Nav2/control topic exposure.
- Updated API docs, Confluence handoff summary, and regenerated `docs/contracts/ai-server-openapi.json`.
- Validation:
  - `./scripts/test_ai_server.sh -q tests/test_api.py tests/test_contract_boundaries.py`: `119 passed, 1 warning` and contract fixtures behaved as expected.
  - `./scripts/test_ai_server.sh -q`: `119 passed, 1 warning` and contract fixtures behaved as expected.
  - app code guard: no `sensor_msgs`/`rclpy` text in `services/ai-server/app` excluding `*.pyc`.


Lane B robot-free e2e consistency validation implemented on 2026-06-15 Asia/Seoul:

- Added integrated scenario test `test_lane_b_robot_free_e2e_surfaces_stay_consistent_across_stream_debug_ros_and_metrics`.
- The test validates the full robot-free flow:
  - raw frame ingest stores latest frame without inline processing,
  - worker status reports pending work,
  - worker tick creates a contract-valid event and overlay,
  - latest frame/overlay image endpoints return visual artifacts,
  - `/vision/streams`, `/vision/debug/sources`, `/vision/ros/topics`, and `/metrics` agree on frame seq, overlay seq, ROS ingest readiness, ROS overlay publish readiness, evidence event readiness, safety flags, and metrics,
  - a newer raw frame creates overlay lag and all surfaces agree that overlay publish payload is blocked.
- This shifts Lane B from only field-by-field validation toward an integrated user/system scenario validation.
- Safety boundaries remain verified: no ROS2 start/spin/publish, no image bytes in JSON metadata, no `/cmd_vel`, no Nav2/control topic exposure.
- Updated API docs and Confluence handoff summary.
- Validation:
  - `./scripts/test_ai_server.sh -q tests/test_api.py tests/test_contract_boundaries.py`: `122 passed, 1 warning` and contract fixtures behaved as expected.
  - `./scripts/test_ai_server.sh -q`: `122 passed, 1 warning` and contract fixtures behaved as expected.
  - app code guard: no `sensor_msgs`/`rclpy` text in `services/ai-server/app` excluding `*.pyc`.


Lane B multi-source e2e isolation validation implemented on 2026-06-15 Asia/Seoul:

- Added integrated multi-source scenario test `test_lane_b_multi_source_e2e_keeps_frame_overlay_event_and_metrics_isolated`.
- The test validates the multi-camera target behavior:
  - `tb3_1_picam` and `tb3_2_picam` can ingest raw latest frames independently,
  - worker tick for one source creates overlay/evidence only for that source,
  - the other robot source remains `no_overlay` and event-not-ready,
  - `global_cam_01` remains `no_frame`,
  - `/vision/streams`, `/vision/debug/sources`, `/vision/ros/topics`, and source-filtered `/metrics` agree on source-scoped readiness and counters,
  - processing the second source later increases overlay/event readiness counts without contaminating the global source.
- This directly addresses the real multi-camera goal and guards against cross-source state leakage.
- Safety boundaries remain verified: no ROS2 start/spin/publish, no image bytes in JSON metadata, no `/cmd_vel`, no Nav2/control topic exposure.
- Updated API docs and Confluence handoff summary.
- Validation:
  - `./scripts/test_ai_server.sh -q tests/test_api.py tests/test_contract_boundaries.py`: `122 passed, 1 warning` and contract fixtures behaved as expected.
  - `./scripts/test_ai_server.sh -q`: `122 passed, 1 warning` and contract fixtures behaved as expected.
  - app code guard: no `sensor_msgs`/`rclpy` text in `services/ai-server/app` excluding `*.pyc`.


Lane B API-served overlay visual QA implemented on 2026-06-15 Asia/Seoul:

- Added API-level visual QA test `test_lane_b_api_served_overlay_visual_qa_distinguishes_fresh_and_stale_warning_band`.
- The test decodes the actual JPEG returned by `GET /api/v1/vision/overlay/latest/image` and verifies:
  - fresh overlay renders as normal evidence visualization,
  - stale overlay has a full-width amber warning band,
  - stale metadata reports `visual_state=stale`,
  - API sync metadata agrees with stale visual state.
- Visual QA found and fixed two small-frame readability issues:
  - shortened stale header text on narrow frames to `STALE FRAME`,
  - shortened bottom banner on narrow stale frames to avoid label clipping.
- Generated visual QA artifacts under `docs/reports/lane-b-visual-qa-2026-06-15/`:
  - `fresh_overlay.jpg`
  - `stale_overlay.jpg`
  - `fresh_vs_stale_overlay_comparison.jpg`
  - `README.md`
- Safety boundaries remain verified: no ROS2 start/spin/publish, no image bytes in JSON metadata, no `/cmd_vel`, no Nav2/control topic exposure.
- Updated API docs and Confluence handoff summary.
- Validation:
  - `./scripts/test_ai_server.sh -q tests/test_api.py tests/test_overlay.py tests/test_contract_boundaries.py`: `122 passed, 1 warning` and contract fixtures behaved as expected.
  - `./scripts/test_ai_server.sh -q`: `122 passed, 1 warning` and contract fixtures behaved as expected.
  - visual inspection of `fresh_vs_stale_overlay_comparison.jpg`: stale amber warning band and compact labels are readable.
  - app code guard: no `sensor_msgs`/`rclpy` text in `services/ai-server/app` excluding `*.pyc`.


Lane B multi-source latest-only/backpressure validation implemented on 2026-06-15 Asia/Seoul:

- Added integrated multi-source burst/backpressure scenario test `test_lane_b_multi_source_latest_only_backpressure_drops_old_frames_per_source`.
- The test validates the production-relevant multi-camera pressure behavior:
  - `tb3_1_picam` can receive three raw frames and `tb3_2_picam` can receive two raw frames before worker processing,
  - `LatestFrameStore` keeps only the newest frame per source and records source-scoped drops (`tb3_1_picam=2`, `tb3_2_picam=1`),
  - all-source worker tick processes only the latest frame seq per robot camera while `global_cam_01` remains `no_frame`,
  - `/vision/streams`, `/vision/debug/sources`, `/vision/ros/topics`, and source-filtered `/metrics` agree on ready/publish/event state,
  - a later new frame for only `tb3_1_picam` creates `overlay_lag` and publish-payload blocking for that source only while `tb3_2_picam` remains `ready_fresh`.
- This moves Lane B from small field/API checks toward realistic multi-camera flow validation without changing the architecture boundary.
- Safety boundaries remain verified: no ROS2 start/spin/publish, no image bytes in JSON metadata, no `/cmd_vel`, no Nav2/control topic exposure.
- Updated API docs, OpenAPI artifact, and Confluence handoff summary.
- Validation:
  - `./scripts/test_ai_server.sh -q tests/test_api.py::test_lane_b_multi_source_latest_only_backpressure_drops_old_frames_per_source`: `123 passed, 1 warning` and contract fixtures behaved as expected.
  - `./scripts/test_ai_server.sh -q`: `123 passed, 1 warning` and contract fixtures behaved as expected.
  - app code guard: no `sensor_msgs`/`rclpy` text in `services/ai-server/app` excluding `*.pyc`.



Lane B worker tick idempotency validation implemented on 2026-06-15 Asia/Seoul:

- Added result/summary fields to `POST /api/v1/vision/worker/tick` so callers can distinguish represented/reused evidence from newly created evidence:
  - result `new_event_count`,
  - result `evidence_action=created|reused|none`,
  - summary `new_event_count_total`,
  - summary `reused_event_count_total`.
- Added integrated test `test_lane_b_worker_tick_is_idempotent_and_does_not_duplicate_evidence_events`.
- The test validates:
  - first all-source tick over `tb3_1_picam` and `tb3_2_picam` creates two events and reports `new_event_count_total=2`,
  - second all-source tick over the same latest frames skips both robot sources with `evidence_action=reused`,
  - second tick reports `new_event_count_total=0` while `event_count_total=2` still describes reused overlay evidence in the response,
  - `/api/v1/detections/latest` keeps the same two event IDs and `/api/v1/metrics.event_store.current_size` remains 2,
  - stream and ROS handoff summaries remain publish/event-ready after the skipped tick.
- This protects Lane B from duplicate evidence growth before Lane C/Main dedup storage is implemented.
- Safety boundaries remain verified: no ROS2 start/spin/publish, no image bytes in JSON metadata, no `/cmd_vel`, no Nav2/control topic exposure.
- Updated API docs, OpenAPI artifact, and Confluence handoff summary.
- Validation:
  - `./scripts/test_ai_server.sh -q tests/test_api.py::test_lane_b_worker_tick_is_idempotent_and_does_not_duplicate_evidence_events`: `124 passed, 1 warning` and contract fixtures behaved as expected.
  - `./scripts/test_ai_server.sh -q tests/test_api.py tests/test_contract_boundaries.py`: `124 passed, 1 warning` and contract fixtures behaved as expected.
  - `./scripts/test_ai_server.sh -q`: `124 passed, 1 warning` and contract fixtures behaved as expected.
  - app code guard: no `sensor_msgs`/`rclpy` text in `services/ai-server/app` excluding `*.pyc`.



Lane B worker status idempotency preview implemented on 2026-06-15 Asia/Seoul:

- Extended `GET /api/v1/vision/worker/status` with read-only idempotency preview fields:
  - source `would_create_new_evidence`,
  - source `evidence_action_if_ticked=created|reused|none`,
  - source `expected_new_event_count`,
  - source `reused_event_count_if_ticked`,
  - summary `would_create_new_evidence_count`,
  - summary `expected_new_event_count_total`,
  - summary `reused_event_count_if_ticked_total`.
- Strengthened `test_vision_worker_status_reports_pending_skipped_and_stale_without_processing` to verify pending, skipped/reused, stale, and no-frame preview semantics without processing frames or changing metrics.
- This makes the read-only scheduler/debug surface agree with worker tick idempotency semantics before Lane C background workers are added.
- Safety boundaries remain verified: no ROS2 start/spin/publish, no image bytes in JSON metadata, no `/cmd_vel`, no Nav2/control topic exposure.
- Updated API docs, OpenAPI artifact, and Confluence handoff summary.
- Validation:
  - `./scripts/test_ai_server.sh -q tests/test_api.py::test_vision_worker_status_reports_pending_skipped_and_stale_without_processing`: `124 passed, 1 warning` and contract fixtures behaved as expected.



Lane B OpenAPI drift guard implemented on 2026-06-15 Asia/Seoul:

- Added contract-boundary test `test_generated_openapi_artifact_matches_current_app_schema`.
- The test compares `docs/contracts/ai-server-openapi.json` against current FastAPI `app.openapi()` so Lane B handoff docs fail fast if API fields/routes change without regenerating the OpenAPI artifact.
- Regenerated `docs/contracts/ai-server-openapi.json` from the current app schema.
- This is a Lane B final contract freeze guard; it does not add runtime ROS2 behavior.
- Safety boundaries remain verified: no ROS2 start/spin/publish, no image bytes in JSON metadata, no `/cmd_vel`, no Nav2/control topic exposure.
- Updated API docs and Confluence handoff summary.
- Validation:
  - `./scripts/test_ai_server.sh -q tests/test_contract_boundaries.py::test_generated_openapi_artifact_matches_current_app_schema`: `125 passed, 1 warning` and contract fixtures behaved as expected.
  - `./scripts/test_ai_server.sh -q tests/test_api.py tests/test_contract_boundaries.py`: `125 passed, 1 warning` and contract fixtures behaved as expected.
  - `./scripts/test_ai_server.sh -q`: `125 passed, 1 warning` and contract fixtures behaved as expected.
  - app code guard: no `sensor_msgs`/`rclpy` text in `services/ai-server/app` excluding `*.pyc`.


Lane A/B source registry + ROS ingest handoff prep implemented on 2026-06-16 Asia/Seoul:

- Planning/critic/design/verification artifact: `.omx/plans/lane-a-b-source-registry-ros-ingest-prep-20260616.md`.
- Real robot environment exploration was judged **not required** for this implementation cycle because the work is registry/contract/runtime-seam prep. Physical checks remain Lane C/passive.
- Added `config/vision/sources.yaml` as the source of truth for source IDs, robot IDs, frame IDs, physical input topics/message types/content types, legacy browser topics, normalized `/sf/...` topics, and evidence event topics.
- Added `services/ai-server/app/source_registry.py` and rewired AI Server source helpers to read registry definitions instead of hardcoded source mappings.
- Updated `/api/v1/sources`, `/api/v1/vision/streams`, `/api/v1/vision/debug/sources`, and `/api/v1/vision/ros/topics` so ROS ingest readiness/runtime plans show registry-derived physical input metadata.
- Added OpenAPI source enum hints for source query/form/body fields while keeping manual unknown-source HTTP 400 behavior.
- Added `scripts/generate_source_registry_surfaces.py`; generated/updated:
  - `docs/contracts/vision-event.schema.json` source enum,
  - `docs/contracts/lift-roi-evidence.schema.json` source enum,
  - `docs/contracts/generated/source-registry.snapshot.json`,
  - `docs/contracts/fixtures/source-registry.valid.json`,
  - `docs/contracts/ai-server-openapi.json`.
- Updated `scripts/validate_contracts.py` to validate source registry snapshot/fixture and schema enum drift.
- Added `services/ai-server/tests/test_source_registry.py` and registry-aware API expectations.
- Updated API docs, README, and local Confluence update source `docs/reports/api-confluence-update-2026-06-16.md`.
- Live Confluence API page updated to version 61: `https://baksa2584.atlassian.net/wiki/spaces/KAN/pages/20119566/API`. The page now includes concise API descriptions, request shapes where applicable, and output snippets for each AI/Main API.
- Validation:
  - `python3 scripts/generate_source_registry_surfaces.py`: generated all registry/OpenAPI surfaces.
  - `./scripts/test_ai_server.sh -q`: `129 passed, 1 warning` and contract fixtures behaved as expected.
  - `python3 scripts/validate_contracts.py`: all contract fixtures behaved as expected.
  - `python3 scripts/validate_deployment_assets.py`: `Deployment assets validated.`
  - `make ros-build-bringup`: `smartfactory_perception_ros` and `smartfactory_bringup` built successfully.
  - `git diff --check -- config/vision services/ai-server/app services/ai-server/tests scripts docs/contracts Makefile entry.md .omx/plans/lane-a-b-source-registry-ros-ingest-prep-20260616.md`: OK.
  - ROS app dependency string guard: no `rclpy`, `sensor_msgs`, or `cv_bridge` text in `services/ai-server/app/*.py`.


## Recommended next work

Use `docs/technical/perception-control-plan.md` as the main plan pointer. It now separates:

- completed robot-free base,
- remaining work that does **not** require physical tuning,
- robot-available passive tuning,
- permission-gated low-speed active tuning.

### 1. No-physical-tuning work that can start now

1. Continue Lane B in small slices:
   - prepare ROS2 ingest/domain bridge handoff while keeping MJPEG/HTTP stream debug/fallback only; rosbridge 9090 remains production browser stream plane,
   - source/topic drift is now guarded by `config/vision/sources.yaml` plus generated schema/OpenAPI/snapshot surfaces.
2. Plan `task_id` integer/null migration:
   - update `lift-roi-evidence.schema.json`, code, fixtures, docs, and Main alignment notes in one change.
3. Select and validate actual model weights offline.
   - Recommended default direction: instance segmentation primary, bbox detection fallback.
   - Inputs still needed: model weight path, runtime install method, target classes, sample images, and acceptable latency on the target CPU/GPU.
   - Until configured, `/api/v1/lift-roi/evaluate-image` must fail closed with HTTP 503 rather than pretending success.
4. Implement future WMS/Main gate only after its concrete service/repo/API exists, using `.omx/plans/wms-main-lift-roi-gate-plan-20260612.md` as the handoff plan.
   - This repo currently has an outbound `VisionEvent` WMS client seam, but no actual WMS/Main service implementation.
   - A mock-only AI Server outbound `LiftRoiEvidence` emitter can be implemented now if explicitly requested, but it would be a delivery seam, not the real WMS state transition gate.
   - Real WMS logic should treat `verification.status != CONFIRMED` as no-progress/retry/exception, never as success.
5. Keep observability/deployment assets under regression coverage.
   - Request IDs, structured logs, metrics, bounded event retention, Dockerfile, docker-compose, and systemd assets are now implemented; future edits should keep `./scripts/test_ai_server.sh -q` and `python3 scripts/validate_deployment_assets.py` green.

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


Lane C safe vision frame gateway slice implemented on 2026-06-16 Asia/Seoul:

- Safe ultragoal brief/artifacts were created under `.omx/ultragoal/` with hard boundaries: Lane C only, no Lane D2 active motion, no robot-side persistent changes, no package/launch/systemd/ROS_DOMAIN_ID/network/calibration edits, no `/cmd_vel`, no Nav2, no teleop, and no whole-graph rosbridge/domain bridge exposure.
- Added ROS sidecar `smartfactory_perception_ros.vision_frame_gateway`:
  - subscribes to raw/compressed ROS image topics with sensor QoS,
  - posts latest frames to existing `POST /api/v1/vision/frame`, keeping FastAPI free of ROS runtime imports,
  - optionally calls `POST /api/v1/vision/worker/tick`,
  - optionally publishes overlay JPEG to `/sf/vision/sources/{source}/overlay/compressed` and evidence JSON to `/sf/vision/events`,
  - validates publish topics under `/sf/vision/` and rejects motion/control topics.
- Added launch/config/runbook artifacts:
  - `ros2/smartfactory_perception_ros/launch/vision_frame_gateway.launch.py`, disabled by default and source-gated,
  - `ros2/smartfactory_perception_ros/config/lane_c_domain_bridge_allowlist.yaml`, with allowed camera/overlay/evidence topics and forbidden motion/control/introspection globs,
  - `docs/robot/lane-c-passive-robot1-camera-check-2026-06-16.md`,
  - `docs/reports/lane-c-safe-vision-frame-gateway-2026-06-16.md`,
  - `.omx/context/lane-c-safe-vision-frame-gateway-20260616.md`.
- User-authorized temporary Robot1 camera launch in `Smartfactory:3` was used only for live passive validation and then stopped with Ctrl-C. No robot files/config/packages/system/network/calibration were changed.
- Live Robot1 evidence:
  - `/camera/image_raw/compressed` was `sensor_msgs/msg/CompressedImage`, publisher `/camera`, about 30.4-31.4 Hz on robot and about 29.1-29.5 Hz from central PC domain 2,
  - Lane C sidecar ran for 8 seconds with `source_id=tb3_1_picam`, direct topic override `/camera/image_raw/compressed`, `process_with_worker_tick=true`, `publish_overlay=true`, and `publish_evidence=true`,
  - AI Server latest frame became `frame_seq=15`, `640x480`, `image/jpeg`, and latest overlay matched `frame_seq=15` with `overlay_lag_frames=0`, `visual_state=fresh`, `event_count=0`.
- Validation so far:
  - `pytest -q ros2/smartfactory_perception_ros/test`: `28 passed`,
  - live Lane C sidecar smoke: `POST /api/v1/vision/frame`, `POST /api/v1/vision/worker/tick`, and `GET /api/v1/vision/overlay/latest/image` succeeded repeatedly,
  - `./scripts/test_ai_server.sh -q`: `129 passed, 1 warning`,
  - `python3 scripts/validate_contracts.py`: OK,
  - `python3 scripts/validate_deployment_assets.py`: OK,
  - `make ros-build-bringup`: `smartfactory_perception_ros` and `smartfactory_bringup` built successfully,
  - static safety guards passed: AI Server has no ROS runtime imports; Lane C ROS package creates no motion publisher/action client; allowlist allowed sections expose no motion/control topics,
  - `git diff --check`: OK.
- API/OpenAPI note: no new FastAPI endpoint or schema was added. Local API docs were updated to document the Lane C ROS sidecar's use of existing `/api/v1/vision/frame`, `/api/v1/vision/worker/tick`, and overlay endpoints.
- Confluence API page updated/verified: `https://baksa2584.atlassian.net/wiki/spaces/KAN/pages/20119566/API`, version 62, with Lane C sidecar API usage and validation snippets.


Mainserver Vision Evidence API connection proposal documented on 2026-06-16 Asia/Seoul:

- Added/updated local proposal document: `docs/contracts/mainserver-vision-evidence-api-proposal-2026-06-16.md`.
- User clarified Mainserver is already being implemented by another person, so the document is framed as an AI Server/Lane C → Main API connection proposal, not a Main implementation spec.
- It explains Robot camera → `vision_frame_gateway` → AI Server responsibilities, current raw/overlay image retrieval APIs, and safe ROS topics.
- It documents AI Server outbound settings for Main connection: `MAIN_SERVER_URL`, `WMS_VISION_EVENTS_PATH`, `WMS_EMIT_ENABLED`, timeout, and retries.
- Clarified that APIs do not launch the robot camera; camera bringup must already be running on the robot/operator side, while local PC runs AI Server plus `vision_frame_gateway` against a visible camera topic.
- Main-side minimum connection expectation is accepting schema-valid `VisionEvent v1` at `POST /api/v1/vision/events` and returning HTTP `200` or `202`; image bytes are kept out of event JSON and can be pulled from AI Server raw/overlay endpoints when needed.
- Safety/API boundary: proposal is metadata-push/image-pull, idempotent by `event_id`, and no motion/control API or robot-side persistent change is introduced.
- Confluence/API page was not changed in this documentation-only cycle; publish after Main API connection direction is accepted.


Lane C live runtime bringup executed on 2026-06-16 11:05 Asia/Seoul:

- Runtime snapshot: `.omx/context/lane-c-live-runtime-bringup-20260616-1105.md`.
- `Smartfactory:3.2` SSH pane is running temporary Robot1 camera launch with `ROS_DOMAIN_ID=2`, `RMW_IMPLEMENTATION=rmw_fastrtps_cpp`, and `QT_QPA_PLATFORM=offscreen`; no robot-side persistent changes were made.
- `Smartfactory:3.3` local pane is running AI Server at `http://127.0.0.1:8100`.
- `Smartfactory:3.5` local pane is running `vision_frame_gateway` for `source_id=tb3_1_picam`, subscribing `/camera/image_raw/compressed`, posting to AI Server, ticking worker, and publishing safe `/sf/vision/...` overlay/evidence topics.
- Validation observed local camera topic around 25 Hz, AI Server `source_summary.online=1`, latest frame/overlay sync at `overlay_lag_frames=0`, frame/overlay image endpoints returning JPEGs, overlay ROS topic around 5 Hz, and `/sf/vision/events` evidence JSON emission.
- Stop with Ctrl-C in panes 3.2, 3.3, and 3.5 when this temporary runtime is no longer needed.


Mainserver connection proposal updated with local runtime snapshot on 2026-06-16 11:07 KST:

- Updated `docs/contracts/mainserver-vision-evidence-api-proposal-2026-06-16.md` with current local PC runtime state for Main implementer convenience.
- Snapshot records `Smartfactory:3.2` Robot1 camera launch, `Smartfactory:3.3` AI Server at `http://127.0.0.1:8100`, and `Smartfactory:3.5` `vision_frame_gateway` for `tb3_1_picam` subscribing `/camera/image_raw/compressed`.
- Snapshot notes current AI Server bind is `127.0.0.1`, so same-PC Main/GUI can access directly; remote Main needs tunnel or a deliberate host bind/network decision.
- Snapshot notes Main HTTP auto-post is not currently enabled by this runtime; worker tick updates AI cache/overlay/evidence and safe ROS topics, while Main push needs `MAIN_SERVER_URL`/`WMS_EMIT_ENABLED=true` or a later auto-emitter slice.


AI Server runtime re-bound for LAN access on 2026-06-16 Asia/Seoul:

- User requested AI/Vision Server restart on `0.0.0.0:8100`.
- Restarted `Smartfactory:3.3` AI Server with `AI_SERVER_HOST=0.0.0.0 AI_SERVER_PORT=8100 ./scripts/run_ai_server.sh`.
- Verified listener: `0.0.0.0:8100`; local health OK; LAN URL `http://192.168.10.63:8100/api/v1/health` OK.
- Gateway in `Smartfactory:3.5` remained pointed at `http://127.0.0.1:8100` and resumed frame/overlay POST successfully.
- Updated `docs/contracts/mainserver-vision-evidence-api-proposal-2026-06-16.md` runtime snapshot to show LAN base `http://192.168.10.63:8100`.


Lane D1 safe ultragoal planning prepared on 2026-06-16 Asia/Seoul:

- Added plan: `.omx/plans/lane-d1-safe-main-gui-stream-integration-20260616.md`.
- Added summary report: `docs/reports/lane-d1-safe-ultragoal-plan-2026-06-16.md`.
- Updated API docs with D1 planning notes: `docs/contracts/ai-server-api.md` and `docs/contracts/mainserver-vision-evidence-api-proposal-2026-06-16.md`.
- D1 is safe only if scoped to Main/GUI/performance/read-only stream integration. It must not include Lane D2 active motion, `/cmd_vel`, Nav2, teleop, or robot-side persistent changes.
- High-FPS browser stream should use Movement rosbridge/WebSocket `9090` or another allowlisted read-only stream bridge; AI Server HTTP image/MJPEG endpoints remain debug/fallback and evidence display surfaces.
- AI model attachment is not part of the first D1 ultragoal by default. Current marker evidence uses OpenCV ArUco; optional Lift ROI model remains disabled/fail-closed unless a separate model subgoal supplies weights/classes/sample images/runtime/latency gates.
- D1 should start with Main HTTP evidence handshake using synthetic/offline events before live camera auto-emission.
- Because the prior Lane C OMX/Codex ultragoal had a goal reconciliation mismatch in this thread, use a fresh Codex goal context before terminal D1 ultragoal checkpointing.


D1-AI model environment discovery captured on 2026-06-16 Asia/Seoul:

- User clarified the working YOLO environment is `~/venv/venv`.
- Verified `~/venv/venv` has `ultralytics 8.4.63`, `torch 2.12.0+cu130`, CUDA available, and NVIDIA GeForce RTX 5060; it lacks FastAPI/uvicorn/pydantic/httpx/jsonschema.
- Verified current `services/ai-server/.venv` has FastAPI service dependencies but lacks `ultralytics`/`torch`.
- Recommended project setup is not copying the external venv blindly, but creating a reproducible project-local model env such as `services/ai-server/.venv-yolo` from service requirements plus pinned model extras, then allowing `scripts/run_ai_server.sh` to use `AI_SERVER_VENV_DIR`.
- Candidate YOLO models exist under `/home/codelab/yolo_test/runs/segment/bottle_detection_yolov8s_seg/weights/best.pt` and `/home/codelab/yolo_test/runs/detect/bottle_detection_yolov8s/weights/best.pt`.
- Contract caveat: local model classes are `bottle1`, `bottle2`, `bottle3`; Main-facing contracts currently need normalized classes such as `box`/`pallet`/`unknown`, so a class mapping slice is required before Main delivery.
- Do not reuse `/home/codelab/yolo_test/src/yolo_robot_control.py` in D1 because it publishes robot control; only model parsing ideas may be reused.

## Recovery checklist for the next assistant

1. Read this file first.
2. Confirm branch: `git status --short --branch`.
3. Do not resume `smartfactory-ai-serve-ff431175`; it was intentionally shut down.
4. Use `/home/codelab/turtlebot3_ws` as the default ROS2 workspace for `smartfactory_bringup`; do not reintroduce an active duplicate under `/home/codelab/ros2_ws/src`.
5. Run validation commands above before further edits; for contract/API changes also run `./scripts/test_ai_server.sh -q -k 'contract or lift_roi_evaluate or generated_fixture_decode or detect_image_rejects or metrics or health'`.
6. Preserve the ArUco-only `VisionEvent` marker API scope; the separate Lift ROI path may use optional segmentation/detection adapters but must remain evidence-only and fail closed when unconfigured.
7. Preserve the key design decision: AI Server evidence loop can be slower, but precision docking requires a faster future central-PC ROS loop; robot should remain bringup/camera-only unless user permits robot-side changes.
8. Do not treat future WMS/Main behavior as implemented in this repo; actual state-transition gates belong in the concrete WMS/Main service when it exists.
9. For WMS/Main gate work, start from `.omx/plans/wms-main-lift-roi-gate-plan-20260612.md`; do not code a local mini-WMS in AI Server.
10. `.omx/` artifacts are local/ignored handoff artifacts; `entry.md` is the tracked recovery source.
11. Latest contract/API docs package is at project root: `smartfactory-contract-api-docs-20260612.zip`.
12. Live Confluence API page is `https://baksa2584.atlassian.net/wiki/spaces/KAN/pages/20119566/API` under Implementation; zip attachment `smartfactory-contract-api-docs-20260612.zip` is uploaded there.

Lane D1/D1-AI Architect -> Critic gate locked on 2026-06-16 12:25 KST:

- Added report: `docs/reports/lane-d1-ai-architect-critic-gate-2026-06-16.md`.
- Review order was Architect first, Critic second.
- Architect verdict: WATCH / conditional approval for a safe evidence/GUI/read-only stream lane.
- Critic verdict: REVISE before executing as one broad ultragoal.
- Fixed document gate: each implementation cycle must update `entry.md`; API/Main-facing behavior changes must also update `docs/contracts/ai-server-api.md` and `docs/contracts/mainserver-vision-evidence-api-proposal-2026-06-16.md`; Confluence publication is a separate verified G5 step.
- D1 is safe only if scoped to evidence delivery, GUI display, and read-only streaming. D2 active motion, `/cmd_vel`, Nav2, teleop, robot-side persistent changes, and whole-graph ROS exposure remain excluded.
- D1-AI is included only as a separately gated model subgoal: project-local model env, sample-image smoke, latency/fail-closed evidence, and class normalization are required before Main delivery.
- Current local model labels `bottle1`, `bottle2`, and `bottle3` cannot be sent to Main as-is; user/Main owner must choose mapping to `box`, mapping to `unknown`, or contract expansion.
- Runtime refresh note: at 2026-06-16 12:25 KST, AI Server health failed on both `127.0.0.1:8100` and `192.168.10.63:8100`, no `:8100` listener was present, and panes showed AI Server/gateway had been stopped with Ctrl-C. Treat prior live URLs as stale until G0 restarts/revalidates them.

Lane D1-AI ROS overlay stream implementation cycle on 2026-06-16 KST:

- User clarified the original plan: AI-included high-FPS video must stream through ROS overlay topics / read-only bridge, not repeated HTTP image pulls.
- Implemented optional AI Server model worker candidates that can be enabled with `VISION_MODEL_WORKER_ENABLED=true` and `VISION_MODEL_PATH=yolov8n.pt`.
- Added public class normalization for pretrained YOLO outputs: default mapping `bottle -> box`, `person -> person`, unmapped labels -> `unknown`.
- Model candidates are emitted as `VisionEvent v1` `CANDIDATE` evidence and rendered into overlay images; they do not imply Main/WMS task completion.
- Preserved primary stream path: `vision_frame_gateway publish_overlay=true` republishes cached AI overlay to `/sf/vision/sources/tb3_1_picam/overlay/compressed`, which Main/GUI should view through read-only rosbridge/stream bridge.
- HTTP frame/overlay image and MJPEG endpoints remain debug/fallback only, not high-FPS acceptance surfaces.
- Added `AI_SERVER_VENV_DIR` support to `scripts/run_ai_server.sh`, plus `services/ai-server/requirements-model.txt` and `scripts/setup_ai_server_model_env.sh` for a project-local `.venv-yolo` model runtime.
- Updated local docs: `.omx/plans/lane-d1-safe-main-gui-stream-integration-20260616.md`, `docs/contracts/ai-server-api.md`, `docs/contracts/mainserver-vision-evidence-api-proposal-2026-06-16.md`, and `docs/reports/lane-d1-ai-ros-overlay-stream-implementation-2026-06-16.md`.
- Local validation completed: `./scripts/test_ai_server.sh -q tests/test_model_adapters.py tests/test_api.py::test_worker_tick_includes_pretrained_model_candidates_for_ros_overlay tests/test_api.py::test_lift_roi_evaluate_image_uses_segmentation_mask_when_model_is_available tests/test_contract_boundaries.py::test_health_response_reports_model_and_contract_boundaries` -> `131 passed, 1 warning`; contract fixture validation passed.
- Main PC validation remains checklist-only: bridge reachability, overlay topic subscription FPS, forbidden-topic absence, GUI bridge video view, and Main `POST /api/v1/vision/events` idempotency.
- Confluence API page updated in same cycle: `https://baksa2584.atlassian.net/wiki/spaces/KAN/pages/20119566/API`, version 63, message `D1-AI ROS overlay stream and pretrained model worker update`.

D1 read-only ROS overlay stream bridge implemented on 2026-06-16 KST:

- Added `vision_overlay_stream_bridge` to `ros2/smartfactory_perception_ros`.
- Purpose: browser-view AI overlay video from ROS overlay topic, without repeated HTTP snapshot polling.
- Primary input topic: `/sf/vision/sources/tb3_1_picam/overlay/compressed` (`sensor_msgs/msg/CompressedImage`).
- Browser/status APIs served by the bridge:
  - `GET /api/v1/vision/bridge/status` -> JSON status for enabled sources and stream paths.
  - `GET /api/v1/vision/overlay/view?source=tb3_1_picam` -> simple HTML viewer.
  - `GET /api/v1/vision/overlay/stream?source=tb3_1_picam&max_fps=30` -> MJPEG stream.
  - aliases: `/view/tb3_1_picam`, `/stream/tb3_1_picam.mjpeg`.
- Added launch file: `ros2/smartfactory_perception_ros/launch/vision_overlay_stream_bridge.launch.py`.
- Added console script: `vision_overlay_stream_bridge`.
- Safety boundary preserved: read-only HTTP GET/OPTIONS, mutation methods return 405, no ROS publishers, no ROS service/action clients, no `/cmd_vel`, no Nav2, no teleop, no parameter mutation, no whole-graph rosbridge exposure.
- Updated docs: `ros2/smartfactory_perception_ros/README.md`, `docs/contracts/ai-server-api.md`, and `docs/contracts/mainserver-vision-evidence-api-proposal-2026-06-16.md`.
- Local validation:
  - `source /opt/ros/jazzy/setup.bash && cd ros2/smartfactory_perception_ros && pytest -q` -> `34 passed`.
  - `source /opt/ros/jazzy/setup.bash && colcon build --symlink-install --packages-select smartfactory_perception_ros` -> passed.
  - `source /opt/ros/jazzy/setup.bash && colcon test --packages-select smartfactory_perception_ros --event-handlers console_direct+` -> `34 passed`.
- Runtime note: bridge is prepared but not yet left running in `3:Development` in this cycle. To run after AI Server + `vision_frame_gateway publish_overlay:=true` are live:

```bash
source /opt/ros/jazzy/setup.bash
source /home/codelab/Desktop/Project/SmartFactory/install/setup.bash
ros2 launch smartfactory_perception_ros vision_overlay_stream_bridge.launch.py \
  use_vision_overlay_stream_bridge:=true \
  host:=0.0.0.0 \
  port:=8090 \
  sources:=tb3_1_picam \
  max_fps:=30
```

Confluence API page updated in same D1 bridge cycle:

- URL: https://baksa2584.atlassian.net/wiki/spaces/KAN/pages/20119566/API
- Version: 64
- Message: `D1 read-only ROS overlay stream bridge API update`
- Added bridge APIs: `GET /api/v1/vision/bridge/status`, `GET /api/v1/vision/overlay/view`, `GET /api/v1/vision/overlay/stream`, `/view/{source}`, `/stream/{source}.mjpeg`.

D1 read-only ROS overlay stream bridge live runtime started on 2026-06-16 14:18 KST:

- All runtime/process work was kept inside `Smartfactory:3:Development` as requested.
- Current panes after split/reindex:
  - `Smartfactory:3.3`: SSH Robot1 camera launch, publishing `/camera/image_raw/compressed`.
  - `Smartfactory:3.4`: AI Server on `0.0.0.0:8100`, model worker enabled with `yolov8n.pt`, `VISION_MODEL_TASK=detect`, `VISION_MODEL_DEVICE=0`, class map `bottle -> box`, `person -> person`, unmapped -> `unknown`.
  - `Smartfactory:3.6`: `vision_frame_gateway`, ROS_DOMAIN_ID=2, subscribing `/camera/image_raw/compressed`, posting to `http://127.0.0.1:8100`, `process_with_worker_tick=true`, `publish_overlay=true`, `publish_evidence=true`.
  - `Smartfactory:3.2`: `vision_overlay_stream_bridge`, ROS_DOMAIN_ID=2, serving `0.0.0.0:8090` from `/sf/vision/sources/tb3_1_picam/overlay/compressed`.
- LAN/browser URL for operator confirmation:
  - `http://192.168.10.63:8090/api/v1/vision/overlay/view?source=tb3_1_picam`
- Runtime validation:
  - `GET http://192.168.10.63:8100/api/v1/health` -> OK, `source_summary.online=1`, model worker active.
  - `GET http://127.0.0.1:8100/api/v1/vision/overlay/latest?source=tb3_1_picam` -> fresh overlay, `overlay_lag_frames=0`, `640x480`, `image/jpeg`.
  - `GET http://192.168.10.63:8090/api/v1/vision/bridge/status` -> OK, `read_only=true`, `motion_command_allowed=false`, `has_frame=true`, `stale=false`.
  - `GET http://192.168.10.63:8090/api/v1/vision/overlay/view?source=tb3_1_picam` -> `200 text/html`.
  - `GET http://127.0.0.1:8090/api/v1/vision/overlay/stream?source=tb3_1_picam&max_fps=5` -> `200 multipart/x-mixed-replace`, sample bytes received.
  - `ros2 topic hz /sf/vision/sources/tb3_1_picam/overlay/compressed` -> about `4.9-5.0 Hz`.
  - Topic list check showed only `/camera/image_raw/compressed`, `/sf/vision/events`, `/sf/vision/sources/tb3_1_picam/overlay/compressed`; no `/cmd_vel`/Nav2/teleop topics in this path.
- Temporary model runtime note: AI Server used service `.venv` plus `PYTHONPATH=/home/codelab/venv/venv/lib/python3.12/site-packages` to reuse the known YOLO/Torch env for this live smoke. Project-local `.venv-yolo` setup remains available via `./scripts/setup_ai_server_model_env.sh` for reproducible future runs.
- Stop/rollback: Ctrl-C panes `Smartfactory:3.2`, `3.4`, `3.6`; Robot camera pane `3.3` only if user wants camera stopped.

D1 detection overlay runtime fix on 2026-06-16 14:23 KST:

- User reported browser video is visible but detection boxes were not visible.
- Diagnosis:
  - AI Server health showed model worker env flags active, but latest overlay had `event_count=0`.
  - Direct YOLO inference on the current live frame with `/home/codelab/Desktop/Project/SmartFactory/yolov8n.pt` found detections (`bottle`, `person`, `tv`, `keyboard`), proving the camera scene/model were not the issue.
  - Root cause: `scripts/run_ai_server.sh` intentionally unsets `PYTHONPATH` to isolate AI Server from ROS2. The temporary `~/venv/venv` YOLO/Torch path was therefore removed before uvicorn started, so worker model import failed closed and emitted zero candidates.
- Fix:
  - Updated `scripts/run_ai_server.sh` to keep the default ROS-isolation behavior but allow an explicit `AI_SERVER_EXTRA_PYTHONPATH` model-only override after unsetting inherited `PYTHONPATH`.
  - Restarted AI Server in `Smartfactory:3.4` with `AI_SERVER_EXTRA_PYTHONPATH=/home/codelab/venv/venv/lib/python3.12/site-packages`.
- Current live validation:
  - AI Server process env now includes both `AI_SERVER_EXTRA_PYTHONPATH` and `PYTHONPATH=/home/codelab/venv/venv/lib/python3.12/site-packages`.
  - `GET /api/v1/vision/overlay/latest?source=tb3_1_picam` -> fresh overlay, `overlay_lag_frames=0`, `event_count=5`, `latency_ms≈4.967`.
  - `GET /api/v1/detections/latest?source=tb3_1_picam&limit=10` -> schema-valid `CANDIDATE` events including `box` from YOLO `bottle -> box` mapping and `person` from YOLO person detections; unmapped COCO classes such as `tv`/`keyboard` are normalized to `unknown`.
  - Stream bridge remains healthy at `http://192.168.10.63:8090/api/v1/vision/overlay/view?source=tb3_1_picam`.
- Safety preserved: AI Server still does not inherit ROS2 PYTHONPATH by default; the extra path is explicit and model-only. No robot-side persistent changes, no `/cmd_vel`, no Nav2, no teleop.

D1 AI overlay FPS tuning on 2026-06-16 KST:

- User asked to maximize FPS after confirming the browser overlay video is visible.
- Confirmed bottleneck was not the read-only stream bridge; bridge `max_fps` was already `30`. The limiting factors are `vision_frame_gateway publish_period_sec`, AI worker loop, and live camera/DDS burst/stall behavior.
- Tried gateway `publish_period_sec:=0.05` with model `VISION_MODEL_IMGSZ=320`; detection remained active but live updates showed burst/stall behavior.
- Switched to high-speed smoke profile:
  - AI Server pane `Smartfactory:3.4`: `VISION_MODEL_IMGSZ=224`, `VISION_MODEL_CONF=0.35`, `VISION_MODEL_DEVICE=0`, `AI_SERVER_EXTRA_PYTHONPATH=/home/codelab/venv/venv/lib/python3.12/site-packages`.
  - Gateway pane `Smartfactory:3.6`: `publish_period_sec:=0.05`, `request_timeout_sec:=1.2`, `force_worker_tick:=true`, `publish_overlay:=true`, `publish_evidence:=true`.
  - Bridge pane `Smartfactory:3.2`: unchanged, `max_fps=30`, serving `0.0.0.0:8090`.
- Observed validation:
  - `ros2 topic hz /sf/vision/sources/tb3_1_picam/overlay/compressed` reached about `19.0-19.4 Hz` during warm measured window.
  - Bridge status sampled once per second showed variable deltas from `5` to `20` frames/sec depending on live camera/processing burst behavior; `stale=false` and frame age remained low during samples.
  - `GET /api/v1/vision/overlay/latest?source=tb3_1_picam` stayed fresh with `event_count≈3-5`, `overlay_lag_frames≈0-1`, and model latency around `4-6 ms`.
- Current browser URL remains:
  - `http://192.168.10.63:8090/api/v1/vision/overlay/view?source=tb3_1_picam`
- Safety unchanged: no robot motion/control topics, no Nav2, no teleop, no robot-side persistent changes.
- Tradeoff note: this profile is a high-FPS smoke/demo profile. If detection quality looks worse, use the previous quality profile `VISION_MODEL_IMGSZ=320` with `publish_period_sec:=0.10` or `0.05` depending on stability.

D1 current video/runtime state and Main evidence handoff recommendation on 2026-06-16 KST:

- User confirmed the current browser video/FPS is visually acceptable for now.
- Current running path is still read-only vision only:
  - Robot camera/domain bridge -> local ROS `/camera/image_raw/compressed`.
  - `Smartfactory:3.4` AI Server on `0.0.0.0:8100`, model worker active.
  - `Smartfactory:3.6` `vision_frame_gateway` high-speed profile, `publish_period_sec:=0.05`, `publish_overlay:=true`, `publish_evidence:=true`.
  - `Smartfactory:3.2` `vision_overlay_stream_bridge` on `0.0.0.0:8090`, `max_fps=30`.
- Browser/Main video URL remains:
  - `http://192.168.10.63:8090/api/v1/vision/overlay/view?source=tb3_1_picam`
  - stream-only: `http://192.168.10.63:8090/api/v1/vision/overlay/stream?source=tb3_1_picam&max_fps=30`
- Latest spot-check state:
  - AI Server health OK, `source_summary.online=1`, model worker active.
  - Overlay latest was fresh with `overlay_lag_frames=0`, `visual_state=fresh`, and detection `event_count` present.
  - Stream bridge status was `read_only=true`, `motion_command_allowed=false`, `has_frame=true`, `stale=false`.
  - FPS is a bursty live path: previous warm window reached about `19 Hz` on `/sf/vision/sources/tb3_1_picam/overlay/compressed`, but spot checks can be lower due live DDS/camera/HTTP processing stalls. Do not claim stable 30fps for AI overlay.
- Main Server evidence handoff clarification:
  - Existing AI Server outbound client exists in `services/ai-server/app/wms_client.py`.
  - It posts single `VisionEvent v1` JSON to `{MAIN_SERVER_URL}/{WMS_VISION_EVENTS_PATH}` and treats HTTP `200`/`202` as success.
  - Runtime knobs already exist: `MAIN_SERVER_URL`, `WMS_VISION_EVENTS_PATH=/api/v1/vision/events`, `WMS_EMIT_ENABLED=true`, `WMS_EMIT_TIMEOUT_S`, `WMS_EMIT_RETRIES`.
  - Current implemented emit surfaces are `POST /api/v1/detect/image?emit=true` and `POST /api/v1/vision/synthetic/frame` with `emit=true`; these can send recognized events to Main when `WMS_EMIT_ENABLED=true`.
  - Current live camera `worker/tick` path updates AI cache/overlay and publishes `/sf/vision/events`, but it does not yet auto-POST every live event to Main. A small auto-emitter slice is still needed if Main should receive live camera tags continuously without polling.
- Recommended Main Server contract:
  - Main exposes `POST /api/v1/vision/events` and accepts one `VisionEvent v1` per request.
  - Main deduplicates by `event_id` and returns `200` or `202`.
  - Main stores semantic evidence at controlled cadence, not every video frame: e.g. every `1-2s` per source/class/track, or on state change, or on `CONFIRMED` marker/tag events.
  - Store event metadata in DB; do not store high-FPS image bytes in the event JSON. Store image URLs or fetch overlay snapshots to object storage only when needed.
  - Video remains MJPEG pull from `:8090`; semantic evidence remains HTTP JSON ingest on Main.

D1 vision bundle / Main handoff packaging on 2026-06-16 KST:

- Added `scripts/run_d1_vision_bundle.sh` as the local one-command supervisor for the current AI-included vision path.
- The bundle starts and stops these local child processes together:
  - AI Server on `0.0.0.0:8100` by default.
  - `vision_frame_gateway` subscribing `VISION_IMAGE_TOPIC` (default `/camera/image_raw/compressed`), posting to AI Server, ticking worker, and publishing `/sf/vision/...` overlay/evidence topics.
  - `vision_overlay_stream_bridge` on `0.0.0.0:8090`, serving the AI overlay ROS topic as read-only MJPEG.
- This is intentionally a supervisor/process-group wrapper, not a single merged Python process. AI Server remains ROS-free; ROS work remains in sidecars.
- It does not start robot motion, Nav2, teleop, `/cmd_vel`, or robot-side persistent services. Robot camera/domain bridge must already be running.
- Added runbook: `docs/runbooks/d1-vision-bundle-main-handoff.md`.
- Updated Main handoff proposal: `docs/contracts/mainserver-vision-evidence-api-proposal-2026-06-16.md`, section 18.
- Main/GUI receive surfaces for the bundled process:
  - `GET http://<vision-pc>:8090/api/v1/vision/overlay/view?source=tb3_1_picam` -> operator HTML view.
  - `GET http://<vision-pc>:8090/api/v1/vision/overlay/stream?source=tb3_1_picam&max_fps=30` -> MJPEG overlay stream.
  - `GET http://<vision-pc>:8090/api/v1/vision/bridge/status` -> read-only bridge/source status.
  - `GET http://<vision-pc>:8100/api/v1/detections/latest?source=tb3_1_picam&limit=10` -> latest semantic tags/events.
  - Future/optional push target remains Main `POST /api/v1/vision/events`; current live worker path does not auto-POST continuously yet, so Main should poll `/detections/latest` or wait for a small event relay/emitter slice.
- Local validation:
  - `bash -n scripts/run_d1_vision_bundle.sh` -> passed.
  - `./scripts/run_d1_vision_bundle.sh --check` -> passed; local ROS modules found and current LAN candidate printed as `192.168.10.63`.
- Confluence API page updated in same D1 bundle cycle:
  - URL: https://baksa2584.atlassian.net/wiki/spaces/KAN/pages/20119566/API
  - Version: 66
  - Message: `D1 vision bundle process and Main handoff update`
  - Added bundled local process, Main/GUI receive URLs, polling-vs-push handoff recommendation, and safety boundary recap.

D1 dual robot overlay streaming live smoke on 2026-06-16 KST:

- Goal: deliver AI overlay streams for two robot cameras to Main/GUI simultaneously.
- Domain topology:
  - `tb3_1_picam`: Robot1 camera on ROS_DOMAIN_ID=2.
  - `tb3_2_picam`: Robot2 camera on ROS_DOMAIN_ID=5.
- Kept domains separate for the safe smoke. A single ROS process cannot subscribe to both domains, so Robot2 uses a second read-only domain sidecar and a second HTTP port instead of a cross-domain bridge.
- Added `scripts/run_d1_vision_domain_sidecar.sh` to supervise one extra source/domain as one process group: `vision_frame_gateway` + `vision_overlay_stream_bridge`, using the already-running AI Server.
- Long-running process placement respected the user boundary: started only inside tmux `Smartfactory:3:Development`.
- Current panes/process groups:
  - `Smartfactory:3.2`: Robot1 camera SSH launch.
  - `Smartfactory:3.4`: Robot2 camera SSH launch.
  - `Smartfactory:3.3`: `./scripts/run_d1_vision_bundle.sh`, serving AI Server `:8100` and Robot1 stream bridge `:8090`.
  - `Smartfactory:3.5`: Robot2 sidecar, `ROS_DOMAIN_ID=5 VISION_SOURCE_ID=tb3_2_picam VISION_STREAM_PORT=8091 ./scripts/run_d1_vision_domain_sidecar.sh`.
- Main/GUI receive URLs:
  - Robot1 view: `http://192.168.10.63:8090/api/v1/vision/overlay/view?source=tb3_1_picam`
  - Robot2 view: `http://192.168.10.63:8091/api/v1/vision/overlay/view?source=tb3_2_picam`
  - Robot1 stream: `http://192.168.10.63:8090/api/v1/vision/overlay/stream?source=tb3_1_picam&max_fps=30.0`
  - Robot2 stream: `http://192.168.10.63:8091/api/v1/vision/overlay/stream?source=tb3_2_picam&max_fps=30.0`
  - Tags: `http://192.168.10.63:8100/api/v1/detections/latest?source=tb3_1_picam&limit=10` and `source=tb3_2_picam`.
- Live validation:
  - `GET /api/v1/health` -> OK, `source_summary.online=2`.
  - `GET :8090/api/v1/vision/bridge/status` -> Robot1 `read_only=true`, `motion_command_allowed=false`, `has_frame=true`, `stale=false`.
  - `GET :8091/api/v1/vision/bridge/status` -> Robot2 `read_only=true`, `motion_command_allowed=false`, `has_frame=true`, `stale=false`.
  - Robot1 overlay latest -> fresh, `overlay_lag_frames=0`, `event_count` present.
  - Robot2 overlay latest -> fresh, `overlay_lag_frames=0`, `event_count` present, `320x240`.
  - ROS topic list checks show only camera/vision topics in each domain: `/camera/image_raw/compressed`, `/sf/vision/events`, `/sf/vision/sources/{source}/overlay/compressed`.
- Safety unchanged: no `/cmd_vel`, no Nav2, no teleop, no parameter mutation, no robot-side persistent changes.

D1 Main-compatible single 8090 Vision Stream Gateway on 2026-06-16 KST:

- Main clarified desired contract: one HTTP gateway base URL, multiple cameras selected by `source`, no public per-camera ports.
- Added ROS-free public source-mux gateway: `scripts/run_d1_vision_stream_gateway.py`.
- Added one-command bundle: `scripts/run_d1_vision_multi_source_gateway_bundle.sh`.
- Public Main contract now matches:
  - `LMS_VISION_STREAM_BASE_URL=http://192.168.10.63:8090`
  - `GET /api/v1/vision/overlay/stream?source={source_id}&max_fps={1..30}`
  - `GET /api/v1/vision/frame/stream?source={source_id}&max_fps={1..30}`
  - `GET /api/v1/vision/overlay/view?source={source_id}`
  - `GET /api/v1/vision/bridge/status`
- Internal implementation hides domain-specific bridges from Main:
  - `127.0.0.1:18090` -> `tb3_1_picam`, ROS_DOMAIN_ID=2.
  - `127.0.0.1:18091` -> `tb3_2_picam`, ROS_DOMAIN_ID=5.
  - Public `0.0.0.0:8090` muxes by source and proxies overlay MJPEG; raw MJPEG comes from AI Server latest-frame cache.
- Runtime started only inside tmux `Smartfactory:3`:
  - `Smartfactory:3.4`: `./scripts/run_d1_vision_multi_source_gateway_bundle.sh`.
  - `Smartfactory:3.5`: Robot1 SSH camera launch.
  - `Smartfactory:3.7`/new pane attempts: Robot2 SSH became unresponsive after old camera process was stopped; `192.168.10.89` later failed ping and SSH.
- Validation:
  - `ss` showed listeners on `0.0.0.0:8100`, `0.0.0.0:8090`, `127.0.0.1:18090`, `127.0.0.1:18091`.
  - `GET http://192.168.10.63:8090/api/v1/vision/bridge/status` -> 200, `service=vision-stream-bridge`, `source_count=2`, `read_only=true`, `motion_command_allowed=false`.
  - Overlay stream and raw stream endpoints returned `multipart/x-mixed-replace` sample bytes for both source IDs while cached frames were available.
  - `tb3_1_picam` frame sequence continued increasing.
  - `tb3_2_picam` delivered initial frames then became stale; blocker is Robot2 network/SSH reachability, not Main gateway shape.

D1 async/QoS high-FPS AI overlay pipeline update on 2026-06-16 KST:

- Scope: safe read-only Vision/Main streaming only. No `/cmd_vel`, Nav2, teleop, parameter mutation, robot-side persistent services, or whole-graph rosbridge exposure.
- Architect/Critic decision applied: use a bounded latest-only async pipeline, not unbounded queues or per-frame thread spawning; make QoS configurable instead of hard-coding one reliability policy for every deployment.
- AI Server hot path added:
  - `POST /api/v1/vision/frame/process`
  - Request: multipart form `source`, `image`, optional `force`, optional `stale`.
  - Output: stores latest frame and immediately updates detection/overlay cache in one ROS-free request; returns `source`, `processed`, `status`, `frame_seq`, `event_count`, `new_event_count`, `frame`, `overlay`, optional `events`, `reason`, and `ingest_context`.
  - Purpose: replace the high-FPS gateway path `POST /frame -> POST /worker/tick -> GET overlay metadata/image` with a single ingest+process call before publishing overlay to ROS.
- ROS sidecar update:
  - `vision_frame_gateway` now supports configurable image subscription QoS, overlay publisher QoS, `async_pipeline`, `retry_failed_frame`, `publish_lagging_overlay`, and `process_frame_inline`.
  - Default D1 bundle profile uses `image_qos_reliability=reliable`, `overlay_pub_qos_reliability=reliable`, `overlay_sub_qos_reliability=reliable`, depth `1`, `async_pipeline=true`, `process_frame_inline=true`, and `publish_period_sec=0.033333`.
  - Backpressure policy is latest-only: if processing lags, old pending work is replaced by the newest frame; no unbounded frame queue is allowed.
- Main/GUI contract remains one public gateway:
  - `LMS_VISION_STREAM_BASE_URL=http://192.168.10.63:8090`
  - `GET /api/v1/vision/overlay/stream?source=tb3_1_picam&max_fps=30`
  - `GET /api/v1/vision/overlay/stream?source=tb3_2_picam&max_fps=30`
  - `GET /api/v1/vision/frame/stream?source={source_id}&max_fps=30`
  - `GET /api/v1/vision/bridge/status`
  - Main should select by `source`; internal ports `18090/18091` are local implementation details only.
- Live runtime restarted only inside tmux `Smartfactory:3.3`:
  - `./scripts/run_d1_vision_multi_source_gateway_bundle.sh`
  - listeners: AI Server `0.0.0.0:8100`, public stream gateway `0.0.0.0:8090`, internal bridges `127.0.0.1:18090` and `127.0.0.1:18091`.
  - startup logs confirmed `frame_process_url=http://127.0.0.1:8100/api/v1/vision/frame/process`, `async_pipeline=True`, `process_frame_inline=True`, reliable image/overlay QoS.
- Validation:
  - `python3 -m py_compile ...` passed for AI Server, ROS nodes, launch files, and public gateway.
  - `bash -n scripts/run_ai_server.sh scripts/run_d1_vision_multi_source_gateway_bundle.sh scripts/run_d1_vision_bundle.sh scripts/run_d1_vision_domain_sidecar.sh` passed.
  - ROS tests: `18 passed` for `test_vision_frame_gateway.py` and `test_vision_overlay_stream_bridge.py`.
  - AI targeted tests: frame ingest, frame/process, and overlay tests passed (`6 passed`).
  - OpenAPI drift guard passed after regenerating `docs/contracts/ai-server-openapi.json`.
  - `./scripts/run_d1_vision_multi_source_gateway_bundle.sh --check` passed and printed the Main single-base URL.
  - Live status sample after restart: both `tb3_1_picam` and `tb3_2_picam` online; public status sequence deltas were about 29-30 frames/s over a 3-second sample. Direct internal MJPEG samples were about 20-24 fps depending on source/frame size. Public browser/client FPS can still vary with Wi-Fi, frame byte size, and simultaneous viewers; if strict 30fps browser delivery is required, reduce camera/JPEG size or add a future compressed video transport.
- Main guidance:
  - Video bytes should stay on MJPEG stream endpoints, not DB/event JSON.
  - Semantic tags remain `GET /api/v1/detections/latest?...` polling or future `POST /api/v1/vision/events` push at controlled cadence.
  - Main should store evidence metadata and selected snapshots/object-storage keys, not every high-FPS frame.

D1 local/Main bundle usage document added on 2026-06-16 KST:

- Added `docs/runbooks/d1-vision-bundle-local-main-usage.md`.
- It summarizes local Vision PC execution, `Smartfactory:3` bundle operation, status/browser check URLs, Main Server `LMS_VISION_STREAM_BASE_URL` usage, source-based proxy requirements, semantic evidence polling/push guidance, FPS notes, and troubleshooting.
- No API surface changed in this documentation-only update; Confluence API page was not updated again because version 68 already contains the same D1 async QoS and Main stream gateway contract.
