# SmartFactory

Local project guide for the SmartFactory AI/Vision/ROS integration workspace.

Korean version: [`README.ko.md`](README.ko.md).

## Start here

- Scripts/operator guide: [`scripts/README.md`](scripts/README.md)
- Korean scripts/operator guide: [`scripts/README.ko.md`](scripts/README.ko.md)
- Filesystem ownership and placement rules: [`docs/technical/project-filesystem-ownership.md`](docs/technical/project-filesystem-ownership.md)
- AI Server guide: [`services/ai-server/README.md`](services/ai-server/README.md)
- ROS perception package guide: [`ros2/smartfactory_perception_ros/README.md`](ros2/smartfactory_perception_ros/README.md)

## Current Main/Vision contract

- Main callback base: `http://smartfactory-main.local:8088`
- Vision public stream base: `http://smartfactory-vision.local:8090`
- `smartfactory-vision.local` is temporary in this repo unless router/DNS/hostname is configured outside the repo.
- `WMS_EMIT_ENABLED=false` is the safe default.

## Organization principle

Files are organized by actual purpose and callers, not by cosmetic folder names. Root scripts remain stable operator entrypoints until wrapper-backed moves are proven safe.
