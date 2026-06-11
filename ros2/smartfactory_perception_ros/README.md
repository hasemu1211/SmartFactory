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

The launch file is conservative: all snapshot clients are disabled unless
`use_ai_snapshot_clients:=true`, and individual adapters are gated by
`use_global_camera` / `use_robot_picams`.
