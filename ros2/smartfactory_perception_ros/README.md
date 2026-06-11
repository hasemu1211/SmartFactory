# smartfactory_perception_ros

Thin ROS2 camera snapshot adapter for the SmartFactory AI Server.

## Boundary

- Subscribes to raw `sensor_msgs/Image` topics.
- Encodes each newly received frame at most once.
- POSTs snapshots to AI Server `POST /api/v1/detect/image`.
- Does **not** run inference.
- Does **not** make WMS decisions.
- Does **not** depend on YOLO/Torch.

## Build/test

```bash
source /opt/ros/jazzy/setup.bash
cd /home/codelab/turtlebot3_ws
colcon build --symlink-install --packages-select smartfactory_perception_ros
colcon test --packages-select smartfactory_perception_ros --event-handlers console_direct+
```

## Launch directly

```bash
source /opt/ros/jazzy/setup.bash
source /home/codelab/turtlebot3_ws/install/setup.bash
ros2 launch smartfactory_perception_ros ai_snapshot_clients.launch.py \
  use_ai_snapshot_clients:=true \
  use_global_camera:=true \
  use_robot_picams:=false \
  ai_server_url:=http://127.0.0.1:8100
```

The launch file is conservative: all snapshot clients are disabled unless
`use_ai_snapshot_clients:=true`, and individual adapters are gated by
`use_global_camera` / `use_robot_picams`.
