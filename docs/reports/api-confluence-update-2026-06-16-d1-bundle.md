# Confluence API update — D1 vision bundle

Date: 2026-06-16 KST

Page: https://baksa2584.atlassian.net/wiki/spaces/KAN/pages/20119566/API

Updated version: 66

Version message: `D1 vision bundle process and Main handoff update`

Summary:

- Added D1 local bundle process: `./scripts/run_d1_vision_bundle.sh`.
- Documented that the bundle supervises AI Server, `vision_frame_gateway`, and `vision_overlay_stream_bridge` while keeping AI Server ROS-free.
- Added Main/GUI receive URLs:
  - `GET /api/v1/vision/overlay/view?source=tb3_1_picam`
  - `GET /api/v1/vision/overlay/stream?source=tb3_1_picam&max_fps=30`
  - `GET /api/v1/vision/bridge/status`
  - `GET /api/v1/health`
  - `GET /api/v1/detections/latest?source=tb3_1_picam&limit=10`
- Clarified Main handoff recommendation: MJPEG pull for video, controlled `/detections/latest` polling now, `POST /api/v1/vision/events` push after a live auto-emitter/relay slice is enabled.
- Restated safety boundary: no `/cmd_vel`, Nav2, teleop, parameter mutation, or whole-graph bridge.
