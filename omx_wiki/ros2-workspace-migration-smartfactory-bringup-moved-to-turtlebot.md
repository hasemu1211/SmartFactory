---
title: "ROS2 Workspace Migration: smartfactory_bringup moved to TurtleBot3 Workspace"
tags: ["ros2", "workspace", "turtlebot3", "bringup", "mvp1", "migration"]
created: 2026-06-11T00:46:54.315Z
updated: 2026-06-11T00:46:54.315Z
sources: ["/home/codelab/Desktop/Project/SmartFactory/entry.md", "/home/codelab/Desktop/Project/SmartFactory/.envrc", "/home/codelab/Desktop/Project/SmartFactory/Makefile"]
links: []
category: decision
confidence: high
schemaVersion: 1
---

# ROS2 Workspace Migration: smartfactory_bringup moved to TurtleBot3 Workspace

# ROS2 Workspace Migration: smartfactory_bringup moved to TurtleBot3 Workspace

## Decision / Result

On 2026-06-11 Asia/Seoul, `smartfactory_bringup` was copied from `/home/codelab/ros2_ws/src/smartfactory_bringup` to `/home/codelab/turtlebot3_ws/src/smartfactory_bringup` and validated there. SmartFactory now defaults to `/home/codelab/turtlebot3_ws` for ROS2 bringup.

## Validation

- `colcon build --symlink-install --packages-select smartfactory_bringup` from `/home/codelab/turtlebot3_ws`: success.
- ROS launch smoke from TurtleBot3 workspace with optional subsystems disabled: success.
- SmartFactory repo `make ros-build-bringup`: success and uses `/home/codelab/turtlebot3_ws`.
- `./scripts/test_ai_server.sh -q`: `26 passed, 1 warning`; contract fixtures behaved as expected.

## Environment changes

- SmartFactory `.envrc` loads ROS2 project-locally through direnv and defaults `SMARTFACTORY_ROS2_WS=/home/codelab/turtlebot3_ws` when `smartfactory_bringup` is present there.
- `Makefile` uses configurable `ROS2_WS ?= $(or $(SMARTFACTORY_ROS2_WS),/home/codelab/turtlebot3_ws)` and `ROS_DISTRO ?= jazzy`.
- The old active copy under `/home/codelab/ros2_ws/src/smartfactory_bringup` was moved to `/home/codelab/ros2_ws/src/smartfactory_bringup.migrated-backup-20260611` to avoid duplicate overlay confusion.

## Boundary

- AI Server remains independent under `services/ai-server` with its own venv and must not import `rclpy`.
- Main/WMS remains source of truth; AI Server emits evidence only.
- Do not reintroduce an active duplicate `smartfactory_bringup` package in `/home/codelab/ros2_ws/src` unless deliberately testing an overlay and documenting source order.
