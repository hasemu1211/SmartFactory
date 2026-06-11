# smartfactory_perception_ros

Thin ROS2 camera snapshot adapter for the SmartFactory AI Server.

## Boundary

- Subscribes to ROS camera topics as either:
  - raw `sensor_msgs/Image`, or
  - compressed `sensor_msgs/CompressedImage`.
- Encodes/posts each newly received frame at most once.
- POSTs snapshots to AI Server `POST /api/v1/detect/image`.
- Does **not** run inference.
- Does **not** make WMS decisions.
- Does **not** depend on YOLO/Torch.

It also includes a passive central-PC ArUco pose monitor for docking tuning:

- Subscribes to raw or compressed ROS camera topics.
- Reuses AI Server pure logic (`app.detectors` + `app.docking`) to compute
  marker pose, docking error, FPS, marker-lost and stale state.
- Logs advisory-only correction values for sign/gain tuning.
- Creates no command publishers and **never publishes `/cmd_vel`**.

For TurtleBot3 Pi Camera streams, prefer compressed transport. In live testing,
`/camera/image_raw/compressed` was ~30 Hz while `/camera/image_raw` was ~13 Hz.

## Build/test

```bash
source /opt/ros/jazzy/setup.bash
cd /home/codelab/turtlebot3_ws
colcon build --symlink-install --packages-select smartfactory_perception_ros
colcon test --packages-select smartfactory_perception_ros --event-handlers console_direct+
```

## Launch directly

Global camera/raw example:

```bash
source /opt/ros/jazzy/setup.bash
source /home/codelab/turtlebot3_ws/install/setup.bash
ros2 launch smartfactory_perception_ros ai_snapshot_clients.launch.py \
  use_ai_snapshot_clients:=true \
  use_global_camera:=true \
  use_robot_picams:=false \
  ai_server_url:=http://127.0.0.1:8100
```

Robot PiCam/compressed example for the current un-namespaced robot camera launch:

```bash
ros2 run smartfactory_perception_ros image_snapshot_client --ros-args \
  -p source_id:=tb3_1_picam \
  -p image_topic:=/camera/image_raw/compressed \
  -p image_transport:=compressed \
  -p ai_server_url:=http://127.0.0.1:8100 \
  -p snapshot_period_sec:=0.5 \
  -p request_timeout_sec:=1.0 \
  -p emit:=false
```

## Passive ArUco pose monitor

Use this for robot-available passive tuning or central-PC synthetic checks. It
does not contact AI Server and does not move the robot.

Direct run example:

```bash
source /opt/ros/jazzy/setup.bash
source /home/codelab/turtlebot3_ws/install/setup.bash
export SMARTFACTORY_AI_SERVER_PYTHONPATH=/home/codelab/Desktop/Project/SmartFactory/services/ai-server
ros2 run smartfactory_perception_ros aruco_pose_monitor --ros-args \
  -p image_topic:=/camera/image_raw/compressed \
  -p image_transport:=compressed \
  -p target_marker_id:=ARUCO_4X4_50_0 \
  -p marker_size_m:=0.08 \
  -p camera_fx:=600.0 \
  -p camera_fy:=600.0 \
  -p camera_cx:=320.0 \
  -p camera_cy:=240.0 \
  -p target_distance_m:=0.45
```

Launch-file example, disabled unless explicitly enabled:

```bash
ros2 launch smartfactory_perception_ros aruco_pose_monitor.launch.py \
  use_aruco_pose_monitor:=true \
  image_topic:=/camera/image_raw/compressed \
  image_transport:=compressed \
  target_marker_id:=ARUCO_4X4_50_0
```

Calibration values above are placeholders from the tuning template. Before any
permission-gated active docking, replace them with measured camera intrinsics
and station-specific target offsets.

The launch file is conservative: all snapshot clients are disabled unless
`use_ai_snapshot_clients:=true`, and individual adapters are gated by
`use_global_camera` / `use_robot_picams`.

## Live Robot1 QA evidence

Robot1 PiCam compressed transport was live-tested on 2026-06-11:

- `/camera/image_raw/compressed`: `sensor_msgs/msg/CompressedImage`, about 30 Hz.
- OpenCV viewer detected phone-displayed ArUco ID `0`.
- `image_snapshot_client` posted compressed frames to AI Server with `source_id=tb3_1_picam` and `emit=false`.
- AI Server produced `ARUCO_4X4_50_0` events for `tb3_1_picam` during the marker window.

Detailed runbook/evidence: [`docs/robot/robot1-picam-aruco-ai-server-qa-2026-06-11.md`](../../docs/robot/robot1-picam-aruco-ai-server-qa-2026-06-11.md).
