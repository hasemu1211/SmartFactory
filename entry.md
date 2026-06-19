# SmartFactory AI Server Recovery Index

- Last updated: 2026-06-18 Asia/Seoul
- Repo root: `/home/codelab/Desktop/Project/SmartFactory`
- Active branch at cleanup: `feature/ai-server-marker-detection`
- Purpose: compact recovery index for the AI/Vision Server lane. Historical implementation chronology moved to `docs/reports/entry-chronology-2026-06-18.md`.

## Architecture non-lock-in / OMX-first principle

- Treat the current structure as a verified baseline, not a permanent target architecture.
- Before feature/refactor/planning work, use OMX-native context first: setup/doctor when needed, then `omx code-intel`/MCP and repo evidence.
- Classify important claims as Fact / Decision / Temporary guard / Open option / Assumption.
- Do not promote current implementation guards into product invariants without explicit decision evidence.
- Keep ROS-aware, ROS-sidecar, hybrid, and real-robot validation paths open when evidence and safety gates justify them.
- For major direction changes, compare alternatives through plan -> architect -> critic before `$ultragoal`/`$team` execution, then record decisions separately from open options.

## Active refactor checkpoint policy

- During refactor cycles, use `.omx/` artifacts as the detailed ledger and keep this file as a compact recovery index.
- Update this file at phase boundaries only: P0 baseline, P0.5 ownership gate, P1 generator/app-factory seam, P1 route/script seam, P2 ROS seam, and final verification.
- Each cycle should leave: current goal/checkpoint id, changed files, validation commands/results, real-robot usage status, and next safe resume step.
- Do not edit live Confluence unless public API/operator wording changes and the live page has been freshly verified.
- If time runs short, stop after a green checkpoint rather than starting a cross-file move that cannot be verified.

## Current approved refactor route

- Approved planning path: `.omx/plans/smartfactory-cleanup-refactor-execution-plan-v2-20260618.md` plus P0.5 addendum `.omx/plans/smartfactory-filesystem-ownership-p05-addendum-20260618.md`.
- Consensus evidence: `.omx/reports/ralplan/smartfactory-filesystem-p05-consensus-handoff-20260618.md`.
- Next execution order: P0 robot-free baseline -> P0.5 ownership/compatibility gate -> P1 `app.factory:create_app` generator-safe seam -> AI Server route seams -> script helper seams -> P2 ROS decomposition.
- Current robot status for this route: real robot not used and not required; no live motion, `/cmd_vel`, Nav2 actions, teleop, robot-side persistence, or live systemd mutation.

## Latest safe checkpoint

- Checkpoint: G017 final review blocker resolution complete under Ultragoal; this resolves the prior G016 non-clean final gate (`SERVICE_VERSION` drift risk + runtime state injection WATCH).
- Changed files since the approved refactor route began: `services/ai-server/app/factory.py`, `services/ai-server/app/runtime_routes.py`, `services/ai-server/app/runtime_state.py`, `services/ai-server/app/service_metadata.py`, `services/ai-server/app/main.py`, `scripts/generate/generate_source_registry_surfaces.py`, `scripts/lib/vision_bundle_common.sh`, `scripts/vision/run_d1_vision_multi_source_gateway_bundle.sh`, `scripts/vision/run_d1_vision_bundle.sh`, `scripts/vision/run_d1_vision_domain_sidecar.sh`, `ros2/smartfactory_perception_ros/smartfactory_perception_ros/qos_profiles.py`, ROS gateway/bridge files/tests, AI Server API/contract tests, and this recovery index.
- Completed seams: G014 runtime-state seam, G015 shared script helper/default seam, G016 ROS QoS helper seam, and G017 explicit `RuntimeContext` injection + single `SERVICE_VERSION` source + MJPEG generator context capture.
- Evidence logs: `.omx/reports/ralplan/g017-stream-context-fix-focused-verification-20260618.log`, `.omx/reports/ralplan/g017-stream-fix-full-verification-20260618.log`, `.omx/reports/ralplan/g017-final-post-cleaner-verification-20260618.log`, `.omx/reports/ai-slop-cleaner-g017-report-20260618.md`, `.omx/reports/ralplan/final-code-review-g017-streamfix-20260618.md`, `.omx/reports/final-quality-gate-g017-20260618.json`, and `.omx/checkpoints/refactor-g017-final-review-watch-resolved-20260618.json`.
- Passed: focused stream-context regression (3 passed), `make ai-test` (142 passed), `make ros-test` (38 passed), contracts/deploy/docker/vision/source-registry gates, shell syntax, Python compile, `git diff --check`, ai-slop-cleaner, code-reviewer `APPROVE`, architect `CLEAR`.
- Robot status: real robot not used; no live motion, `/cmd_vel`, Nav2 actions, teleop, robot-side persistence, parameter mutation, live systemd mutation, or whole-graph rosbridge.
- Next safe resume step: after Ultragoal checkpoint reconciliation, discuss/choose the next bounded refactor slice; do not start broad folder moves without a fresh P0.5 ownership/compatibility gate.

## Current project boundaries

1. AI/Vision Server is evidence-only. Main/WMS remains the only source of truth for task, inventory, DB-persisted state, and robot state; AI/Vision may supply evidence but must not create, complete, fail, or mutate authoritative task/inventory/DB records.
2. MVP keeps Vision on the Central PC/process/container, but code and docs preserve a clean split for a later dedicated Vision/AI Server.
3. Nav/Movement owns motion and safety execution truth. Vision Gateway/stream bridge must not publish `/cmd_vel`, call Nav2 actions, expose teleop, mutate ROS parameters, execute safety stops/slows, or provide whole-graph rosbridge access.
4. Current FastAPI AI Server avoids direct ROS responsibilities; ROS/domain handling currently lives in sidecar processes such as `vision_frame_gateway` and stream bridges. This is an implementation boundary, not a permanent architecture lock.
5. MVP sources remain registry-driven: `global_cam_01`, `tb3_1_picam`, and `tb3_2_picam`.
6. Public detector/event baseline remains OpenCV ArUco for `VisionEvent v1`; optional model/segmentation paths are fail-closed and evidence-only.

## Recovery pointers

| Need | Source |
| --- | --- |
| Full prior chronology and validation history | `docs/reports/entry-chronology-2026-06-18.md` |
| Main API/contract surface | `docs/contracts/ai-server-api.md` |
| Main-facing proposal/contract notes | `docs/contracts/mainserver-vision-evidence-api-proposal-2026-06-16.md` |
| OpenAPI snapshot | `docs/contracts/ai-server-openapi.json` |
| Perception/control plan | `docs/technical/perception-control-plan.md` |
| ROS2 workspace direction | `omx_wiki/decision/ros2-workspace-direction-prefer-turtlebot3-workspace.md` |
| TurtleBot3 workspace migration | `omx_wiki/decision/ros2-workspace-migration-smartfactory-bringup-moved-to-turtlebot.md` |
| Latest D1 bundle/Main handoff | `docs/runbooks/d1-vision-bundle-main-handoff.md` |
| Local D1 usage | `docs/runbooks/d1-vision-bundle-local-main-usage.md` |

## Current implementation summary

- AI Server app: `services/ai-server/app/main.py`
  - Health, source registry, detections, metrics, raw frame ingest/process, latest frame/overlay, debug MJPEG, synthetic frame, worker status/tick, image detection, and lift ROI endpoints.
- Source registry: `config/vision/sources.yaml` plus generated snapshots under `docs/contracts/generated/` and `docs/contracts/fixtures/`.
- ROS sidecar code: `ros2/smartfactory_perception_ros`.
  - `vision_frame_gateway` posts latest frames to AI Server and can publish safe overlay/evidence topics.
  - `vision_overlay_stream_bridge` / Vision Stream Gateway provide read-only HTTP/MJPEG overlay/raw streams.
- Deployment helpers: `scripts/ai/run_ai_server.sh`, `scripts/ai/setup_ai_server_env.sh`, `scripts/vision/run_d1_vision_multi_source_gateway_bundle.sh`, `docker-compose.ai-server.yml`, `ops/systemd/smartfactory-ai-server.service`.

## Live Confluence verification snapshot

Verified during this cleanup before retaining public-page claims:

- Site: `https://baksa2584.atlassian.net`
- Page: `API`
- Page id: `20119566`
- Space: `KAN`
- Status: current
- Version: `68`
- Version timestamp: `2026-06-16T08:36:03.974Z`
- Version message: `D1 async QoS frame/process API and Main stream gateway update`
- URL: `https://baksa2584.atlassian.net/wiki/spaces/KAN/pages/20119566/API`

Treat older `entry.md` Confluence references as historical unless they are also present in this live verification snapshot or in a freshly fetched Confluence page.

## Resume commands

```bash
cd /home/codelab/Desktop/Project/SmartFactory
./scripts/ai/setup_ai_server_env.sh
./scripts/ai/test_ai_server.sh -q
make ros-build-bringup
```

Optional runtime smoke:

```bash
./scripts/ai/run_ai_server.sh
curl http://127.0.0.1:8100/api/v1/health
```

D1 multi-source gateway bundle check:

```bash
./scripts/vision/run_d1_vision_multi_source_gateway_bundle.sh --check
```

## Validation policy for future edits

- For API/Main-facing changes, update `docs/contracts/ai-server-api.md` and `docs/contracts/mainserver-vision-evidence-api-proposal-2026-06-16.md`.
- For source changes, regenerate registry/OpenAPI surfaces where applicable.
- Before claiming Confluence-public status, fetch the live Confluence page and record page id, version, timestamp, and URL.
- Keep detailed chronology in `docs/reports/` or `docs/runbooks/`; keep this file as a short recovery index.
