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
- Vision API base: `http://smartfactory-vision.local:8100`
- `smartfactory-vision.local` is temporary in this repo unless router/DNS/hostname is configured outside the repo.
- `WMS_EMIT_ENABLED=false` is the safe default.

## AI/Vision laptop quick start

The laptop does not need wired Ethernet. WiFi is acceptable when the Main PC and
AI/Vision laptop are on the same WiFi LAN and AP/client isolation is disabled.

Address rule:

- `http://127.0.0.1:8100`: local-only checks from the AI/Vision laptop itself.
- `http://<laptop_wifi_ip>:8100`: Main PC or another machine reaching the laptop.
- `http://smartfactory-vision.local:8100` or `http://smartfactory-ai:8100`: preferred hostname form when DNS/mDNS/hosts is configured.

On the laptop:

```bash
git checkout feature/ai-server-marker-detection
git pull --ff-only
./scripts/setup/setup_ubuntu24_ai_vision_laptop.sh --with-gopro --with-model
```

Bind the API to all interfaces when Main must reach it:

```bash
AI_SERVER_HOST=0.0.0.0 \
VISION_MODEL_WORKER_ENABLED=false \
./scripts/ai/run_ai_server.sh
```

Local check on the laptop:

```bash
curl http://127.0.0.1:8100/api/v1/health
```

Remote check from Main PC:

```bash
curl http://<laptop_wifi_ip>:8100/api/v1/health
curl http://<laptop_wifi_ip>:8100/api/v1/vision/monitors
```

Use [`docs/setup/ubuntu24-ai-vision-laptop.md`](docs/setup/ubuntu24-ai-vision-laptop.md) for the detailed laptop/WiFi/firewall/port runbook.

## Organization principle

Files are organized by actual purpose and callers, not by cosmetic folder names. Root scripts remain stable operator entrypoints until wrapper-backed moves are proven safe.
