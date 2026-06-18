# Lane C safe vision frame gateway run report (2026-06-16 KST)

## Safety scope

- User authorized temporary Robot1 camera launch in `Smartfactory:3` SSH.
- No robot-side persistent files/config/package/system/network/calibration changes.
- No `/cmd_vel`, Nav2, teleop, or Movement/Safety calls.
- Existing robot bringup was not restarted or interrupted.
- Temporary camera launch was stopped with Ctrl-C after validation.

## Implemented artifacts

- `ros2/smartfactory_perception_ros/smartfactory_perception_ros/vision_frame_gateway.py`
- `ros2/smartfactory_perception_ros/launch/vision_frame_gateway.launch.py`
- `ros2/smartfactory_perception_ros/config/lane_c_domain_bridge_allowlist.yaml`
- `ros2/smartfactory_perception_ros/test/test_vision_frame_gateway.py`
- `docs/robot/lane-c-passive-robot1-camera-check-2026-06-16.md`

## Live Robot1 evidence

- Temporary camera launch: `ros2 launch turtlebot3_bringup camera.launch.py` with `QT_QPA_PLATFORM=offscreen`.
- `/camera/image_raw/compressed`: `sensor_msgs/msg/CompressedImage`.
- Robot-side hz: about 30.4-31.4 Hz during the check.
- Central PC domain 2 hz: about 29.1-29.5 Hz during the check.
- Lane C sidecar ran for 8 seconds against live `/camera/image_raw/compressed`.
- AI Server latest frame after sidecar: `source=tb3_1_picam`, `frame_seq=15`, `640x480`, `image/jpeg`, `size_bytes=88311`.
- AI Server overlay metadata after worker ticks: `latest_frame_seq=15`, `latest_overlay_frame_seq=15`, `overlay_lag_frames=0`, `visual_state=fresh`, `event_count=0`.

## Validation

- ROS package pytest: `28 passed`.
- Live sidecar smoke: POST `/api/v1/vision/frame`, POST `/api/v1/vision/worker/tick`, GET `/api/v1/vision/overlay/latest/image` repeated successfully.
- Final validation rerun is recorded in `/tmp/sf_lane_c_validation_final2.log` for this session and passed.
- Confluence API page updated/verified: `https://baksa2584.atlassian.net/wiki/spaces/KAN/pages/20119566/API`, version 62, with Lane C sidecar API usage and validation snippets.
