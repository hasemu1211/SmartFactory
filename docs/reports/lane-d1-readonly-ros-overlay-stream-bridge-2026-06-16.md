# Lane D1 read-only ROS overlay stream bridge implementation

Date: 2026-06-16 KST

## Summary

Implemented a dedicated read-only bridge for D1 AI-included overlay video. The
bridge subscribes to safe ROS overlay `CompressedImage` topics and serves MJPEG
to browsers/Main GUI. This keeps the production stream path on ROS topics and
avoids repeated HTTP snapshot polling.

## Primary path

```text
Robot camera
  -> vision_frame_gateway
  -> AI Server worker/tick + overlay render
  -> /sf/vision/sources/tb3_1_picam/overlay/compressed
  -> vision_overlay_stream_bridge
  -> browser/Main GUI MJPEG view
```

## Files changed

- `ros2/smartfactory_perception_ros/smartfactory_perception_ros/vision_overlay_stream_bridge.py`
- `ros2/smartfactory_perception_ros/launch/vision_overlay_stream_bridge.launch.py`
- `ros2/smartfactory_perception_ros/test/test_vision_overlay_stream_bridge.py`
- `ros2/smartfactory_perception_ros/setup.py`
- `ros2/smartfactory_perception_ros/README.md`
- `docs/contracts/ai-server-api.md`
- `docs/contracts/mainserver-vision-evidence-api-proposal-2026-06-16.md`
- `.omx/plans/lane-d1-safe-main-gui-stream-integration-20260616.md`
- `entry.md`

## API surface

- `GET /api/v1/vision/bridge/status` — bridge health/status JSON.
- `GET /api/v1/vision/overlay/view?source=tb3_1_picam` — browser HTML viewer.
- `GET /api/v1/vision/overlay/stream?source=tb3_1_picam&max_fps=30` — MJPEG stream.
- `GET /view/tb3_1_picam` — simple viewer alias.
- `GET /stream/tb3_1_picam.mjpeg?max_fps=30` — simple MJPEG alias.

## Safety result

- Read-only HTTP surface: `GET`/`OPTIONS` only; mutation methods return `405`.
- ROS side subscribes only to allowlisted `/sf/vision/sources/<source>/overlay/compressed` topics.
- No ROS publishers, service clients, or action clients are created by the bridge.
- Forbidden surfaces remain excluded: `/cmd_vel`, Nav2, teleop, parameters,
  `/rosout`, `/tf`, `/tf_static`, and whole-graph access.

## Validation

```bash
source /opt/ros/jazzy/setup.bash
cd ros2/smartfactory_perception_ros
pytest -q
# 34 passed

source /opt/ros/jazzy/setup.bash
colcon build --symlink-install --packages-select smartfactory_perception_ros
# passed

source /opt/ros/jazzy/setup.bash
colcon test --packages-select smartfactory_perception_ros --event-handlers console_direct+
# 34 passed
```

## Remaining live check

When user wants to view live AI overlay video, restart only in `Smartfactory:3:Development` panes:

1. AI Server with optional model worker.
2. `vision_frame_gateway` with `publish_overlay:=true`.
3. `vision_overlay_stream_bridge` on `0.0.0.0:8090`.
4. Browser URL: `http://<local-pc-ip>:8090/api/v1/vision/overlay/view?source=tb3_1_picam`.
