---
title: "ROS2 Workspace Direction: Prefer TurtleBot3 Workspace"
tags: ["ros2", "workspace", "turtlebot3", "bringup", "mvp1"]
created: 2026-06-09T08:01:27.748Z
updated: 2026-06-09T08:01:27.748Z
sources: []
links: []
category: decision
confidence: medium
schemaVersion: 1
---

# ROS2 Workspace Direction: Prefer TurtleBot3 Workspace

## Decision

If SmartFactory ROS2 bringup can be maintained cleanly inside `/home/codelab/turtlebot3_ws`, prefer that direction instead of splitting active ROS2 work between `/home/codelab/ros2_ws` and `/home/codelab/turtlebot3_ws`.

## Reasoning

- `/home/codelab/turtlebot3_ws` already contains TurtleBot3 runtime packages such as `turtlebot3_bringup`, `turtlebot3_navigation2`, `turtlebot3_node`, `turtlebot3_msgs`, TurtleBot3 descriptions, simulations, and Dynamixel SDK packages.
- `/home/codelab/ros2_ws` currently contains the `smartfactory_bringup` scaffold plus unrelated/example packages. Building it proves the SmartFactory package compiles, but it does not prove TurtleBot3/LDS-03/Nav2 runtime packages are available.
- Consolidating ROS2 robot bringup in the TurtleBot3 workspace should reduce overlay/source-order confusion for MVP1.

## Boundary

- This decision is about ROS2 bringup/package location only.
- The AI Server should remain API-first and independent under `services/ai-server`, using its own Python venv and not importing `rclpy`.
- Main/WMS remains the source of truth; AI Server emits evidence only.

## Migration note

If moving `smartfactory_bringup` from `/home/codelab/ros2_ws/src` to `/home/codelab/turtlebot3_ws/src`, update helper commands/Makefile variables accordingly, ideally with configurable paths:

```makefile
ROS2_WS ?= /home/codelab/turtlebot3_ws
ROS_DISTRO ?= jazzy
```

Recommended source order after consolidation:

```bash
source /opt/ros/jazzy/setup.bash
source /home/codelab/turtlebot3_ws/install/setup.bash
```

If keeping two workspaces temporarily, source TurtleBot3 first and SmartFactory overlay second:

```bash
source /opt/ros/jazzy/setup.bash
source /home/codelab/turtlebot3_ws/install/setup.bash
source /home/codelab/ros2_ws/install/setup.bash
```

## Open checks before actual migration

- Confirm no package-name conflicts.
- Confirm `smartfactory_bringup` installs and launches from `turtlebot3_ws`.
- Confirm global camera driver choice; `v4l2_camera` was not visible in the current ROS2 environment at the time of this note.
- Keep `./scripts/test_ai_server.sh -q` independent from any ROS2 workspace.
