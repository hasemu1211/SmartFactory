# AI Server / Vision Laptop Verification Report — Ubuntu 24.04

Date: 2026-06-30  
Host role: AI/Vision laptop  
Repository: `SmartFactory`  
Branch: `feature/ai-server-marker-detection`  
Commit checked: `0b65a80`  
Primary setup guide: `docs/setup/ubuntu24-ai-vision-laptop.md`

## Summary

The Ubuntu 24.04 AI/Vision laptop setup is ready for no-hardware AI Server and Vision preflight use.

Verified outcomes:

- AI Server Python environment exists and passes the documented no-hardware smoke suite.
- ROS 2 Jazzy prerequisites are installed and the Vision gateway preflight passes.
- CUDA-capable NVIDIA GPU is visible to the installed Python stack.
- MediaMTX is installed for WebRTC sidecar usage and its repo preflight passes.
- The lab Vision profile now passes after adding a local compatibility symlink for model paths.
- `smartfactory-vision.local` can be published to the current laptop WiFi IP by the repo mDNS helper.
- No tracked source/config changes were required for setup.

Hardware-dependent GoPro/camera validation was intentionally not performed.

## Environment

| Item | Value |
| --- | --- |
| OS | Ubuntu 24.04.4 LTS |
| Kernel | `6.17.0-35-generic` |
| Python venv | `services/ai-server/.venv` |
| Python | `Python 3.12.3` |
| ROS | `jazzy` from `/opt/ros/jazzy/setup.bash` |
| GPU | `NVIDIA GeForce MX450`, driver `595.71.05`, `2048 MiB` |
| Current WiFi/LAN IP | `192.168.30.3` on `wlp0s20f3` |
| MediaMTX | `/usr/local/bin/mediamtx`, `v1.19.2` |

## Setup actions completed

1. Checked out repo branch `feature/ai-server-marker-detection`.
2. Installed Ubuntu system prerequisites for Python, OpenCV/video tooling, ROS 2 Jazzy, Avahi/mDNS, and build tooling.
3. Created/recreated the AI Server venv with project requirements, model extras, and GoPro extras.
4. Downloaded YOLO smoke weights:
   - `/home/hasam/yolo_test/yolov8n.pt`
   - `/home/hasam/yolo_test/yolov8s-seg.pt`
5. Installed MediaMTX `v1.19.2` from the official GitHub release and verified checksum before installing the binary to `/usr/local/bin/mediamtx`.
6. Added a local compatibility symlink so repo lab profiles that reference `/home/codelab/yolo_test/...` resolve on this laptop:

   ```text
   /home/codelab/yolo_test -> /home/hasam/yolo_test
   ```

7. Verified the repo mDNS helper can publish the current laptop IP:

   ```text
   smartfactory-vision.local -> 192.168.30.3
   ```

## Verification evidence

### 1. No-hardware AI Server smoke tests

Command:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
PYTHONPATH=services/ai-server \
PYTHONNOUSERSITE=1 \
services/ai-server/.venv/bin/python -m pytest \
  services/ai-server/tests/test_vision_monitor_event_contract.py \
  services/ai-server/tests/test_api_vision_monitors.py \
  services/ai-server/tests/test_dropped_item_policy.py \
  services/ai-server/tests/test_lift_load_evidence_policy.py \
  services/ai-server/tests/test_main_db_adapter_shape.py \
  -q
```

Result:

```text
45 passed, 1 warning in 1.00s
```

The warning is a Starlette/FastAPI test-client deprecation warning from the installed dependency set; it did not fail the smoke suite.

### 2. Local API smoke

The AI Server was run locally with model worker disabled:

```bash
AI_SERVER_HOST=127.0.0.1 \
VISION_MODEL_WORKER_ENABLED=false \
./scripts/ai/run_ai_server.sh
```

Validated endpoints:

- `GET /api/v1/health`
- `GET /api/v1/vision/monitors`
- `PUT /api/v1/vision/monitors/person_drive/state`
- `GET /api/v1/vision/hazards/person/latest?robot_id=tb3_1`

Observed health payload included:

- `status: ok`
- marker detector: `opencv-marker-detector`
- sources: `global_cam_01`, `tb3_1_picam`, `tb3_2_picam`
- model status available in the service health response

### 3. ROS / Vision gateway preflight

ROS source check:

```bash
source /opt/ros/jazzy/setup.bash
ros2 pkg list | grep -E '^(cv_bridge|image_transport|rclpy)$'
```

Confirmed packages:

```text
cv_bridge
image_transport
rclpy
```

Gateway preflight command:

```bash
VISION_MODEL_WORKER_ENABLED=false \
./scripts/vision/run_d1_vision_multi_source_gateway_bundle.sh --check
```

Result: preflight passed and printed Main-facing hostname-first URLs plus fallback IP evidence:

```text
detected_lan_ip=192.168.30.3
VISION_API_FALLBACK_BASE_URL=http://192.168.30.3:8100
VISION_STREAM_FALLBACK_BASE_URL=http://192.168.30.3:8090
LMS_VISION_STREAM_FALLBACK_BASE_URL=http://192.168.30.3:8090
```

### 4. Lab Vision profile preflight

Command:

```bash
./scripts/vision/sf_lab.sh check
```

Result:

```text
source model config check: ok
local ROS module check: ok
[webrtc-sidecar] check ok
[sf-vision] check ok: lab-gopro-tb3-ffmpeg-first
```

Important note: this only validates preflight and configuration. It does not prove GoPro/Pi camera frames because hardware validation was intentionally skipped.

### 5. MediaMTX / WebRTC sidecar preflight

MediaMTX install check:

```bash
command -v mediamtx
mediamtx --version
```

Result:

```text
/usr/local/bin/mediamtx
v1.19.2
```

Repo sidecar check:

```bash
./scripts/vision/run_webrtc_sidecar_mediamtx.sh --check
```

Result:

```text
[webrtc-sidecar] check ok
```

### 6. mDNS hostname helper

The repo includes `scripts/vision/publish_vision_mdns_alias.py`, which temporarily publishes an Avahi/mDNS A record while the process is running. It does not permanently edit DNS, `/etc/hosts`, router DHCP, or the system hostname.

Verification command:

```bash
python3 scripts/vision/publish_vision_mdns_alias.py --address 192.168.30.3
getent hosts smartfactory-vision.local
```

Result while helper was active:

```text
published A smartfactory-vision.local -> 192.168.30.3 via Avahi D-Bus
192.168.30.3    smartfactory-vision.local
```

Before the helper is running, hostname resolution may point elsewhere or fail depending on the lab network. The live Vision profile is expected to run the mDNS helper when `SF_VISION_MDNS_ENABLED=true`.

## Requirements / lockfile decision

No tracked requirements update was needed for this laptop setup.

Observed repo behavior:

- `scripts/ai/setup_ai_server_env.sh` writes `services/ai-server/requirements.lock` as a generic pip freeze side effect.
- `scripts/setup/setup_ubuntu24_ai_vision_laptop.sh` writes `services/ai-server/requirements.local.lock` for local environment capture.
- Deployment validation expects the Dockerfile to use tracked `requirements.lock`.

Decision:

- Keep tracked `requirements.lock` unchanged unless doing an intentional dependency update.
- Keep `services/ai-server/requirements.local.lock` as a local setup artifact for this laptop.

Current git status after setup:

```text
?? services/ai-server/requirements.local.lock
```

No tracked source/config diffs remain.

## Current readiness matrix

| Area | Status | Notes |
| --- | --- | --- |
| AI Server venv | Ready | `.venv` created and tests pass |
| No-hardware API/monitor contract | Ready | `45 passed` smoke suite |
| ROS 2 Jazzy gateway preflight | Ready | ROS packages and gateway `--check` verified |
| CUDA/GPU visibility | Ready | MX450 detected; torch CUDA was verified during setup |
| Model weights | Ready | Present under `/home/hasam/yolo_test`; `/home/codelab/yolo_test` symlink added for lab profiles |
| MediaMTX/WebRTC sidecar | Ready for preflight | `mediamtx v1.19.2`; sidecar `--check` ok |
| mDNS hostname | Ready when helper/profile is running | Temporary Avahi record verified for `192.168.30.3` |
| UFW/firewall | Inactive | No allow rules needed while UFW remains inactive |
| GoPro/camera hardware | Not tested | Intentionally deferred |

## Operator notes

Recommended no-hardware/local check:

```bash
./scripts/vision/sf_lab.sh check
```

Recommended live lab entrypoint when hardware validation is allowed later:

```bash
./scripts/vision/sf_lab.sh all
```

Expected Main-facing hostname-first URLs when the mDNS helper/profile is active:

```text
http://smartfactory-vision.local:8100/api/v1/health
http://smartfactory-vision.local:8090/api/v1/vision/bridge/status
http://smartfactory-vision.local:8889/global_cam_01_full/
```

Fallback URLs for the current network if hostname resolution is unavailable:

```text
http://192.168.30.3:8100
http://192.168.30.3:8090
```

## Deferred / not performed

The following were intentionally not executed because they require live hardware or lab runtime conditions:

- GoPro USB/webcam read test.
- TurtleBot Pi camera live frame ingestion.
- End-to-end WebRTC browser playback with live camera frames.
- Main PC cross-machine curl/browser validation.
- Robot/Nav/Movement integration.

