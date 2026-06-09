# SmartFactory MVP1 AI Server Implementation Plan

- Date: 2026-06-09
- Status: Draft plan after user confirmation
- Confirmed decisions:
  - AI Server runs on the same Central PC as a separate process/container for MVP1.
  - Interfaces must allow later migration to a physically separate AI Server PC.
  - LiDAR hardware is LDS-03.
  - Camera set is one global RGB camera plus one Pi Camera per robot: `global_cam_01`, `tb3_1_picam`, `tb3_2_picam`.
  - Robot-mounted depth camera / RealSense D435 is out of MVP1 scope.

## 1. Evidence and context

### Live Confluence facts verified on 2026-06-09
- `/wiki/x/FgCc` resolves to `Designing` page id `10223638`.
- Children include `System Requirements`, `User Requirements`, and `Architecture`.
- Live SW Architecture page describes `AI Server` as: `ArUco Marker Detection`, `Obstacle Detection`, `Human Detection`.
- Live HW Architecture distinguishes `Main Server PC` and `AI Server PC`, but MVP1 implementation will start with logical separation on one Central PC.
- Live HW Architecture uses LDS-03 LiDAR.
- `/home/codelab/Downloads/ai-vision-pipeline-research.md` was checked on 2026-06-09; its Pi Camera-only section supports Level 0-2 without D435, while its D435/depth sections are now treated as background/future options after the user confirmed no robot depth camera.

### Repository-backed context
- `.omx/specs/deep-interview-smartfactory.md:15-22` defines the desired MVP: fixed webcam, WMS-lite state, GUI, central PC coordination, TurtleBot3 Nav2 execution, vision validation, and exception state transitions.
- `.omx/specs/deep-interview-smartfactory.md:24-37` scopes fixed/robot camera vision, WMS-lite, Nav2, QR/AprilTag, PyTorch/YOLO, and OpenCV into MVP1.
- `.omx/specs/deep-interview-smartfactory.md:62-90` places FastAPI WMS-lite, GUI, vision, ROS2/Nav2, and scheduler on the Central PC with minimal robot SBC workload.
- `.omx/specs/deep-interview-smartfactory.md:113-121` says Vision is evidence, WMS-lite owns final state transitions, and LiDAR/Nav2 owns motion safety behavior.
- `docs/final/03-system-requirements.md:8-21` requires WMS-lite DB/state, Vision Event ingestion, OpenCV, PyTorch/YOLO, scheduler, and API groups.
- `docs/final/03-system-requirements.md:30-37` requires scope clarity, safety boundary, observability, stale camera handling, and robot availability handling.
- `docs/technical/ai-vision-pipeline-research.md:10-16` separates WMS-lite as source of truth, LiDAR/Nav2 as driving safety layer, OpenCV/AprilTag/QR for deterministic verification, and YOLO for candidate detection.

## 2. Architecture decision

### Decision
Implement AI Server as a separate service on the Central PC for MVP1:

```text
Central PC
  ├─ Main Server / WMS-lite / GUI / DB / ROS bridge
  ├─ AI Server process or container
  │   ├─ Camera stream input adapter
  │   ├─ ArUco/AprilTag/QR detection
  │   ├─ Person / obstacle / box / dropped-item candidate detection
  │   ├─ Detection filtering and event normalization
  │   └─ VisionEvent API/client
  └─ ROS2/Nav2 stack using LDS-03 LiDAR scan data
```

### Why
- Matches live Confluence's logical `AI Server` block while avoiding premature multi-PC networking complexity.
- Preserves future physical separation by forcing clean API/event contracts from day one.
- Keeps AI vision as evidence and leaves task/slot/exception decisions to Main Server/WMS-lite.
- Keeps immediate stop/avoid/replan ownership with LDS-03 + Nav2/LiDAR, not YOLO.

## 3. API-first integration strategy

### Contract artifacts
- `docs/contracts/vision-event.schema.json` is the canonical event payload contract.
- `docs/contracts/ai-server-api.md` is the canonical endpoint/merge contract.
- `docs/contracts/fixtures/*.json` and `scripts/validate_contracts.py` are the local contract validation gate.
- Implementation branches must import or validate against these contracts instead of copying ad-hoc payload shapes.

### API ownership boundaries
| Surface | Owner | Contract role | Merge implication |
| --- | --- | --- | --- |
| AI Server `/api/v1/health`, `/api/v1/sources`, `/api/v1/detections/latest`, `/api/v1/detect/image` | AI Server lane | service health, source config, debug/latest detections, offline detector tests | WMS/GUI can mock AI Server by this API |
| Main Server `/api/v1/vision/events` | WMS/Main lane | authoritative ingest point for VisionEvent evidence | AI Server sends evidence only; no direct DB writes |
| Main Server `/api/v1/vision/events/latest`, `/api/v1/vision/sources`, `/ws/events` | WMS/Main + GUI lanes | GUI-visible normalized evidence and source health | GUI does not depend on AI Server internals |

### API versioning rules
- MVP1 endpoints use `/api/v1`.
- Event payloads include `schema_version: vision-event.v1`.
- Required field changes, enum removals/renames, or camera source changes require a v2 contract.
- Optional additive fields must first be tolerated by all lanes before being emitted in production demo flows.

### Contract tests before merge
- Valid fixture for `global_cam_01`.
- Valid fixture for `tb3_1_picam` with `robot_id: tb3_1`.
- Valid fixture for `tb3_2_picam` with `robot_id: tb3_2`.
- Valid fixture for `STALE`.
- Invalid fixture for mismatched source/robot pair.
- Invalid fixture for missing robot ID.
- Invalid fixture for non-null `depth_median_m` in MVP1.
- Invalid fixture for confirmed marker without `marker_id`.
- Invalid fixture for invalid bbox order.

## 4. API and event contract

### AI Server inbound
- Camera sources for MVP1:
  - `global_cam_01` — one global RGB camera for overview/slot/zone evidence
  - `tb3_1_picam` — Robot1 front Pi Camera for marker/dock/local item evidence
  - `tb3_2_picam` — Robot2 front Pi Camera for marker/dock/local item evidence
- Robot-mounted depth camera / D435 is not used in MVP1.
- Source configuration should be environment-driven so the AI Server can move to a separate machine later.

### AI Server outbound
Primary contract: `VisionEvent` sent to Main Server.

```json
{
  "schema_version": "vision-event.v1",
  "event_id": "uuid",
  "timestamp": "2026-06-09T15:30:00+09:00",
  "source": "global_cam_01 | tb3_1_picam | tb3_2_picam",
  "robot_id": null,
  "frame_id": "camera_frame",
  "event_kind": "CANDIDATE | CONFIRMED | CLEARED | STALE",
  "class_name": "aruco_marker | qr_marker | apriltag_marker | person | obstacle | box | dropped_item | unknown",
  "confidence": 0.82,
  "bbox_xyxy": [120, 80, 260, 210],
  "marker_id": "SLOT_A01",
  "zone": "STORAGE_A",
  "roi_id": "STORAGE_A01_ROI",
  "track_id": 12,
  "pose_estimate": null,
  "depth_median_m": null,
  "wms_hint": "TAG_DETECTED | PERSON_CANDIDATE | OBSTACLE_CANDIDATE | null",
  "metadata": {
    "n_frame_count": 3,
    "model": "yolo11n-or-selected-model",
    "policy_version": "mvp1"
  }
}
```

Recommended endpoints:
- `GET /api/v1/health`
- `GET /api/v1/sources`
- `GET /api/v1/detections/latest`
- `POST /api/v1/detect/image` for test images or offline validation
- AI -> Main Server: `POST {MAIN_SERVER_URL}/api/v1/vision/events`


## 5. Environment and version-control strategy

### Python environment
- Use a project-local Python environment for AI Server dependencies.
- Recommended: `uv` + committed `pyproject.toml` and `uv.lock` for deterministic dependency resolution.
- Acceptable fallback: standard `.venv` + committed `requirements.txt` and `requirements.lock`/`constraints.txt`.
- Do not commit `.venv`, model cache, camera captures, generated runs, or local `.env` files.
- Pin high-risk packages explicitly: `opencv-python` or system OpenCV choice, `ultralytics`, `torch`, `torchvision`, `fastapi`, `uvicorn`, `pydantic`.
- Keep ROS2/Jazzy system dependencies separate from AI Server Python deps when possible. AI Server should communicate by HTTP/event contracts rather than importing `rclpy` directly unless a dedicated ROS bridge process is intentionally added.

### Reproducibility files to create before implementation
- `.python-version` — target Python version for AI Server, likely Ubuntu 24.04 default Python 3.12 unless ROS/tooling forces otherwise.
- `services/ai-server/pyproject.toml` or `services/ai-server/requirements.txt`.
- Lockfile: `uv.lock` preferred, or `requirements.lock`/`constraints.txt`.
- `services/ai-server/.env.example` with non-secret keys only.
- `docs/contracts/vision-event.schema.json` as the merge contract between AI Server, Main Server/WMS, and GUI.
- `scripts/validate_contracts.py` for fixture/schema/policy validation.
- Optional later: `docker-compose.yml` for Central PC deployment, with AI Server as a separate service even when hosted on the same machine.

### Git / merge policy
- Git was initialized on 2026-06-09 and the API contract/planning baseline was committed on `main`. Continue using feature branches for multi-worker implementation.
- Suggested branches:
  - `main` — stable documentation and reviewed baseline.
  - `feature/ai-server` — AI Server service and vision processing.
  - `feature/wms-vision-ingest` — Main Server VisionEvent ingest and WMS policy mapping.
  - `feature/gui-vision-evidence` — GUI Evidence/Vision Detail/Debug Log surfaces.
  - `integration/mvp1` — merge branch for cross-lane integration before main.
- Merge order should be contract-first: merge `docs/contracts/vision-event.schema.json` before parallel implementation lanes depend on it.
- Use small PR/commit boundaries: schema, env scaffold, marker detection, YOLO candidate detection, WMS ingest, GUI evidence, scenario tests.
- Use Git LFS or external artifact storage for large model weights/datasets if they must be versioned; otherwise store only download scripts, checksums, and model metadata.

## 6. Implementation phases

### Phase 0 — Contract freeze
- Finalize `VisionEvent` schema.
- Fix MVP1 source IDs to `global_cam_01`, `tb3_1_picam`, `tb3_2_picam`.
- Define class names, confidence thresholds, stale timeout, and N-frame confirmation rules.
- Exclude depth/PointCloud2 fields from required processing; keep them nullable for future compatibility only.
- Decide initial model: stable YOLO line over latest-only model if integration risk matters.

### Phase 1 — AI Server skeleton
- Create Python service with FastAPI.
- Add config via `.env`: `MAIN_SERVER_URL`, `CAMERA_SOURCES`, `AI_SERVER_PORT`, `MODEL_PATH`.
- Add health check and mock event generation.
- Add local Dockerfile / compose service boundary if containerizing immediately.

### Phase 2 — Deterministic marker detection first
- Implement ArUco/AprilTag/QR detector using OpenCV-compatible flow.
- Emit `CONFIRMED` events for known slot/item/dock markers.
- Add tests with stored fixture images.

### Phase 3 — Candidate object/person detection
- Add YOLO detector for `person`, `box`, `dropped_item` candidates.
- Add frame skipping, ROI filtering, N-frame confirmation, and duplicate suppression.
- Emit `CANDIDATE` first; only emit `CONFIRMED` after policy threshold.

### Phase 4 — Main Server integration
- Main Server accepts and stores VisionEvents.
- WMS-lite maps vision evidence to events like:
  - `SLOT_MARKER_CONFIRMED`
  - `PERSON_CANDIDATE`
  - `OBSTACLE_CANDIDATE`
  - `ITEM_TAG_UNREADABLE`
  - `VISION_STALE`
- WMS-lite, not AI Server, decides task/slot/exception state.

### Phase 5 — Demo scenarios
- Normal: marker/slot evidence supports successful putaway/outbound state transition.
- Obstacle/Human: AI emits person/obstacle evidence; LDS-03/Nav2 owns motion stop/wait/replan behavior.
- Slot Fail: marker or occupancy mismatch produces WMS reassignment or confirmation wait.
- Item Exception: tag unreadable or item mismatch produces recovery options.

## 7. Critique / risk review

| Risk | Why it matters | Mitigation |
| --- | --- | --- |
| AI Server becomes decision authority | Breaks WMS-lite source-of-truth boundary | AI emits evidence only; WMS maps to state transitions |
| YOLO false positives disrupt demo | People/box detection can flicker | N-frame confirmation, ROI rules, debounce, CANDIDATE vs CONFIRMED |
| Future separate PC migration is forgotten | Rework later | Use HTTP/event contract, env URLs, no shared local imports between Main and AI service |
| Unpinned Python/vision dependencies | A working demo can break after package updates | Use venv/uv, committed lockfile, `.env.example`, and explicit package pins |
| Parallel worker merge conflict | AI/WMS/GUI lanes can diverge | Contract-first schema, branch strategy, small PRs/commits, integration branch |
| API drift between lanes | Integration breaks late | CI/local schema validation and fixtures must pass in AI/WMS/GUI lanes before merge |
| Endpoint ambiguity | Workers implement incompatible response shapes | `docs/contracts/ai-server-api.md` defines request/response bodies, status codes, and error object before coding |
| No depth camera in MVP1 | Dropped-item distance and 3D position are approximate | Use global-camera homography, Pi Camera tag pose, known-size estimates; avoid claiming accurate 3D localization |
| Camera stream latency blocks GUI/control | Vision is heavier than state updates | Run AI loop async; downsample/frame skip; never block WMS or GUI WebSocket |
| Safety overclaim | Portfolio demo can sound like safety system | GUI/docs must say LDS-03/Nav2 handles motion safety; AI is evidence only |
| LDS-03 mismatch in old docs | Conflicting diagrams/specs confuse implementation | Treat LDS-03 as confirmed; update local drafts/generator before publication |

## 8. Acceptance criteria

- AI Server can run independently on the Central PC and expose `/health`.
- AI Server dependencies are reproducible from committed env files and lockfile.
- Git repository and branch/merge policy are established before multi-worker implementation. Baseline branch: `main`.
- AI Server config contains exactly the MVP1 camera sources: `global_cam_01`, `tb3_1_picam`, `tb3_2_picam`.
- AI Server can emit a valid `VisionEvent` to Main Server without importing Main Server internals.
- `docs/contracts/vision-event.schema.json` and `docs/contracts/ai-server-api.md` are accepted as the cross-lane merge contracts.
- AI/WMS/GUI lanes can each run against mocks or fixtures generated from the same contract.
- `python3 scripts/validate_contracts.py` passes before implementation and before merges.
- Marker detection can confirm at least one known slot/item/dock marker from a test image or live camera.
- Person/obstacle detection emits `CANDIDATE` and only promotes after threshold policy.
- WMS-lite stores VisionEvents and shows them in GUI evidence/debug surfaces.
- No AI Server endpoint directly commands `/cmd_vel`, Nav2 actions, or robot emergency behavior.
- LDS-03 is consistently used in hardware docs/generator for future architecture publication.
- No MVP1 test or service requires D435/depth/PointCloud2 input.

## 9. Design critic result and applied revisions

A Critic review returned `REVISE` because the first draft was directionally sound but not strict enough for parallel API-first implementation. Applied revisions:

- Expanded endpoint contract with request/response examples, status codes, common error object, and WMS ingest behavior.
- Required `robot_id` and `frame_id` in `VisionEvent`.
- Added schema-level rules for camera source ↔ robot ID pairing, STALE convention, confirmed marker `marker_id`, and detection bbox presence.
- Added policy validation script for rules JSON Schema alone cannot express well, especially bbox ordering.
- Added valid and invalid fixtures under `docs/contracts/fixtures/`.
- Marked the research document as background where it conflicts with canonical contract files.

## 10. Recommended OMX next step

No additional user decision is required before planning. Recommended workflow:

1. If further architecture gate is desired, run `$ralplan` / consensus review.
2. Then execute via `$ultragoal` for durable implementation tracking.
3. Use `$team` only if implementation splits into parallel lanes:
   - AI Server service lane
   - Main Server/WMS VisionEvent ingest lane
   - GUI evidence/debug lane
   - ROS/Nav2/LDS-03 integration validation lane

