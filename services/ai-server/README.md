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
