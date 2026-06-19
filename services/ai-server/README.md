# SmartFactory AI Server

API-first AI Server skeleton for MVP1.

The service is intentionally separate from ROS2. ROS2 bringup can start this
process, but the AI Server exposes HTTP APIs and emits `VisionEvent` evidence
instead of directly controlling robots.

## Setup

```bash
cd /home/codelab/Desktop/Project/SmartFactory
./scripts/ai/setup_ai_server_env.sh
```

## Run

```bash
cd /home/codelab/Desktop/Project/SmartFactory/services/ai-server
source .venv/bin/activate
cp .env.example .env.local  # optional; edit if needed
./scripts/ai/run_ai_server.sh --reload
```

## Test

```bash
cd /home/codelab/Desktop/Project/SmartFactory
./scripts/ai/test_ai_server.sh
```

## Current endpoints

- `GET /api/v1/health`
- `GET /api/v1/sources`
- `GET /api/v1/detections/latest`
- `GET /api/v1/metrics`
- `GET /api/v1/vision/streams`
- `GET /api/v1/vision/debug/sources`
- `GET /api/v1/vision/ros/topics`
- `POST /api/v1/vision/frame`
- `GET /api/v1/vision/frame/latest`
- `GET /api/v1/vision/frame/latest/image`
- `GET /api/v1/vision/overlay/latest`
- `GET /api/v1/vision/overlay/latest/image`
- `GET /api/v1/vision/stream/{source}.mjpeg`
- `POST /api/v1/vision/synthetic/frame`
- `GET /api/v1/vision/worker/status`
- `POST /api/v1/vision/worker/tick`
- `POST /api/v1/detect/image`
- `POST /api/v1/lift-roi/evaluate`
- `POST /api/v1/lift-roi/evaluate-image`

`POST /api/v1/detect/image` decodes uploaded images with OpenCV and emits
contract-valid `VisionEvent` objects for deterministic ArUco marker
detections. Frames without ArUco markers return an empty `events` array.


## Source registry

`config/vision/sources.yaml` is the source of truth for MVP1 source IDs, robot IDs, frame IDs, and ROS topic handoff metadata. Regenerate schema/OpenAPI/fixture surfaces after source edits:

```bash
python3 scripts/generate/generate_source_registry_surfaces.py
```

Generated surfaces include `docs/contracts/generated/source-registry.snapshot.json`, `docs/contracts/fixtures/source-registry.valid.json`, source enums in both contract schemas, and `docs/contracts/ai-server-openapi.json`.

`GET /api/v1/sources` reports source freshness from successfully decoded
frames, not only marker detections. A valid blank frame updates
`last_frame_at`, `frame_count`, and `online/stale/offline` status; marker
events additionally update `last_event_at`, `event_count`, and last event
metadata.

For robot-free docking development, the endpoint can optionally compute
`pose_estimate.method=ARUCO_POSE` in two ways:

1. provide `pose_profile`, loaded from `ARUCO_POSE_PROFILES_PATH`
   (default `config/perception/aruco_pose_profiles.example.json`); or
2. provide manual `marker_size_m`, `camera_fx`, `camera_fy`, `camera_cx`, and
   `camera_cy` (`camera_dist_coeffs` is optional).

Without those calibration inputs, `pose_estimate` remains `null`. Profile values
are tuning/config data; restart the server after editing the profile file. QR,
AprilTag, YOLO/Torch object detection is intentionally not part of this MVP1
marker-detection slice.

## Lift ROI evidence endpoints

`POST /api/v1/lift-roi/evaluate` accepts caller-provided bbox or instance-mask
candidate summaries and returns a contract-valid `LiftRoiEvidence v1` payload.
It is useful for synthetic tests, offline fixtures, and future model-provider
seams.

`POST /api/v1/lift-roi/evaluate-image` runs the configured optional vision model
on an uploaded image and then returns `LiftRoiEvidence v1`. Instance segmentation
is preferred when available; bbox detection remains supported as fallback. The
endpoint fails closed with HTTP `503` when `VISION_MODEL_PATH` is not configured
or the optional model runtime is unavailable.

Optional model settings:

```env
VISION_MODEL_PATH=/models/lift-load-seg.pt
VISION_MODEL_TASK=segment
VISION_MODEL_CONF=0.5
VISION_MODEL_IOU=0.5
VISION_MODEL_IMGSZ=640
VISION_MODEL_DEVICE=cpu
```

`GET /api/v1/metrics` reports in-memory HTTP, detection, lift ROI, and event
retention counters for local operations. It is not a WMS state API.

## Optional WMS ingest emission

The AI Server can optionally POST generated `VisionEvent` evidence to the
Main/WMS ingest endpoint:

```text
POST {MAIN_SERVER_URL}/api/v1/vision/events
```

Runtime emission is disabled by default. To enable it for local integration:

```env
MAIN_SERVER_URL=http://smartfactory-main.local:8088
WMS_EMIT_ENABLED=true
WMS_EMIT_TIMEOUT_S=2.0
WMS_EMIT_RETRIES=0
WMS_VISION_EVENTS_PATH=/api/v1/vision/events
```

Source health thresholds are environment configurable:

```env
SOURCE_TARGET_FPS=10.0
SOURCE_STALE_AFTER_S=2.0
SOURCE_OFFLINE_AFTER_S=30.0
```

`emit=true` on `POST /api/v1/detect/image` only requests emission. The endpoint
returns `emitted=true` only when WMS emission is enabled, at least one event was
generated, and every attempted WMS POST returned HTTP `200` or `202`. WMS
failures are best-effort integration failures: image detection still returns
HTTP `200` with local `events` and per-event `emit_results`.

## Error response shape

AI Server errors use a common envelope and also return `X-Request-ID`:

```json
{
  "error": {
    "code": "BAD_REQUEST",
    "message": "unknown source: bad_cam",
    "details": [],
    "request_id": "..."
  }
}
```

## Optional D1-AI pretrained model runtime

The default service environment keeps heavy model packages out of the API path. For D1-AI overlay streaming, create a project-local model environment:

```bash
./scripts/ai/setup_ai_server_model_env.sh
```

Then run AI Server with pretrained YOLO candidates enabled:

```bash
AI_SERVER_VENV_DIR=/home/codelab/Desktop/Project/SmartFactory/services/ai-server/.venv-yolo \
AI_SERVER_HOST=0.0.0.0 \
AI_SERVER_PORT=8100 \
VISION_MODEL_WORKER_ENABLED=true \
VISION_MODEL_PATH=yolov8n.pt \
VISION_MODEL_TASK=detect \
VISION_MODEL_CLASS_MAP_JSON='{"bottle":"box","person":"person"}' \
VISION_MODEL_UNMAPPED_CLASS=unknown \
./scripts/ai/run_ai_server.sh
```

When enabled, worker/tick model candidates are normalized to public `VisionEvent v1` classes and rendered into overlays. The high-FPS AI overlay viewing path remains ROS: `vision_frame_gateway publish_overlay=true` publishes `/sf/vision/sources/<source>/overlay/compressed`, and GUI/Main should view that topic through an allowlisted read-only bridge. HTTP image/MJPEG endpoints are debug/fallback only.
