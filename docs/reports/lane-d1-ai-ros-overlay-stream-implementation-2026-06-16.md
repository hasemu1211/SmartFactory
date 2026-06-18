# Lane D1-AI ROS Overlay Stream Implementation Report

- Date: 2026-06-16 KST
- Scope: optional pretrained YOLO candidates feeding AI overlay/evidence, with high-FPS viewing via ROS overlay topic / read-only bridge.

## Implemented locally

- Added optional model-worker configuration to AI Server:
  - `VISION_MODEL_WORKER_ENABLED`
  - `VISION_MODEL_CLASS_MAP_JSON`
  - `VISION_MODEL_UNMAPPED_CLASS`
  - `VISION_MODEL_MAX_EVENTS`
- Added class normalization inside the Ultralytics adapter and event builder.
- Added worker/tick model candidate integration: when enabled and configured, model detections become `VisionEvent v1` `CANDIDATE` events and are rendered into the overlay.
- Kept model integration fail-closed: if optional model runtime is absent/misconfigured, marker/evidence overlay still runs and no model candidates are emitted.
- Added `AI_SERVER_VENV_DIR` support to `scripts/run_ai_server.sh`.
- Added `services/ai-server/requirements-model.txt` and `scripts/setup_ai_server_model_env.sh` for a project-local `.venv-yolo` model runtime.

## Streaming decision

The primary AI-included video path is:

```text
AI Server overlay cache
  -> vision_frame_gateway publish_overlay=true
  -> /sf/vision/sources/tb3_1_picam/overlay/compressed
  -> read-only rosbridge/stream bridge
  -> Main/GUI browser view
```

HTTP image/MJPEG endpoints remain debug/fallback and are not the high-FPS acceptance path.

## Local validation completed

Command:

```bash
./scripts/test_ai_server.sh -q tests/test_model_adapters.py tests/test_api.py::test_worker_tick_includes_pretrained_model_candidates_for_ros_overlay tests/test_api.py::test_lift_roi_evaluate_image_uses_segmentation_mask_when_model_is_available tests/test_contract_boundaries.py::test_health_response_reports_model_and_contract_boundaries
```

Result: `131 passed, 1 warning`; contract fixture validation passed.

## Main PC verification left as checklist

- Bridge endpoint reachable from Main/GUI PC.
- `/sf/vision/sources/tb3_1_picam/overlay/compressed` subscribable at target FPS.
- No forbidden control/whole-graph topics exposed.
- GUI uses bridge stream for video, not repeated HTTP image polling.
- Main evidence ingest remains `POST /api/v1/vision/events` with idempotent `event_id` handling.

## Confluence update

- Updated API page: `https://baksa2584.atlassian.net/wiki/spaces/KAN/pages/20119566/API`
- Version: 63
- Version message: `D1-AI ROS overlay stream and pretrained model worker update`
