# SmartFactory AI Server

API-first AI Server skeleton for MVP1.

The service is intentionally separate from ROS2. ROS2 bringup can start this
process, but the AI Server exposes HTTP APIs and emits `VisionEvent` evidence
instead of directly controlling robots.

## Setup

```bash
cd /home/codelab/Desktop/Project/SmartFactory
./scripts/setup_ai_server_env.sh
```

## Run

```bash
cd /home/codelab/Desktop/Project/SmartFactory/services/ai-server
source .venv/bin/activate
cp .env.example .env.local  # optional; edit if needed
./scripts/run_ai_server.sh --reload
```

## Test

```bash
cd /home/codelab/Desktop/Project/SmartFactory
./scripts/test_ai_server.sh
```

## Current endpoints

- `GET /api/v1/health`
- `GET /api/v1/sources`
- `GET /api/v1/detections/latest`
- `POST /api/v1/detect/image`

`POST /api/v1/detect/image` decodes uploaded images with OpenCV and emits
contract-valid `VisionEvent` objects for deterministic ArUco marker
detections. Frames without ArUco markers return an empty `events` array. QR, AprilTag, YOLO/Torch
object detection is intentionally not part of this MVP1 marker-detection slice.

## Optional WMS ingest emission

The AI Server can optionally POST generated `VisionEvent` evidence to the
Main/WMS ingest endpoint:

```text
POST {MAIN_SERVER_URL}/api/v1/vision/events
```

Runtime emission is disabled by default. To enable it for local integration:

```env
MAIN_SERVER_URL=http://127.0.0.1:8000
WMS_EMIT_ENABLED=true
WMS_EMIT_TIMEOUT_S=2.0
WMS_EMIT_RETRIES=0
WMS_VISION_EVENTS_PATH=/api/v1/vision/events
```

`emit=true` on `POST /api/v1/detect/image` only requests emission. The endpoint
returns `emitted=true` only when WMS emission is enabled, at least one event was
generated, and every attempted WMS POST returned HTTP `200` or `202`. WMS
failures are best-effort integration failures: image detection still returns
HTTP `200` with local `events` and per-event `emit_results`.
