# Ubuntu 24.04 AI/Vision Laptop Setup

Purpose: reproduce the map-side AI Server environment on a personal Ubuntu
24.04 laptop that receives a USB GoPro/global camera feed and serves the
SmartFactory Vision API/stream gateway.

## Hardware placement

- The GoPro/global camera must be physically connected to the same machine that
  captures frames, unless a separate capture/stream source forwards frames over
  the LAN.
- For the current GoPro USB path, treat the map-side laptop/PC as the
  **AI/Vision host**:
  - USB-C/USB3 cable to GoPro.
  - AI Server on `:8100`.
  - public Vision Stream Gateway on `:8090`.
  - Main/GUI points at `http://smartfactory-vision.local:8090` for streams and
    `http://smartfactory-vision.local:8100` for API.

## Network model: WiFi is OK

The AI/Vision laptop does **not** need a wired Ethernet cable for MVP/lab smoke.
Using the same WiFi as the Main PC is acceptable when the network allows devices
to talk to each other.

Required WiFi conditions:

- Main PC and AI/Vision laptop are on the same LAN/subnet or have routable paths.
- The WiFi/router does not enable AP isolation, guest isolation, or client
  isolation.
- The laptop firewall allows the required ports.
- The laptop keeps a stable enough WiFi connection for the stream test. If
  WebRTC/video is unstable, first verify the API on `:8100`, then reduce stream
  FPS/bitrate or move closer to the access point.

Address rule:

- `127.0.0.1` means **this laptop only**. Use it only from a terminal/browser on
  the AI/Vision laptop itself.
- Main PC must use the laptop's WiFi IP or a hostname that resolves to it:
  - `http://<laptop_wifi_ip>:8100` for API.
  - `http://<laptop_wifi_ip>:8090` for MJPEG fallback stream gateway.
  - `http://smartfactory-vision.local:8100` / `:8090` or
    `http://smartfactory-ai:8100` / `:8090` when DNS/mDNS/hosts is configured.

Find the laptop WiFi IP:

```bash
hostname -I
ip route get 1.1.1.1 | awk '{print $7; exit}'
```

The second command usually prints the active outbound WiFi/LAN IP. Use that as
`<laptop_wifi_ip>` for Main-side smoke tests.

If Ubuntu firewall is enabled, allow the MVP ports:

```bash
sudo ufw allow 8100/tcp   # AI Server API
sudo ufw allow 8090/tcp   # public MJPEG fallback gateway
sudo ufw allow 8889/tcp   # MediaMTX/WHEP
sudo ufw allow 8189/udp   # WebRTC ICE UDP
sudo ufw status
```

If hostname lookup is not ready, use IP first. For a temporary manual hostname
mapping on the Main PC, add a hosts entry that points to the laptop WiFi IP:

```text
<laptop_wifi_ip> smartfactory-vision.local smartfactory-ai
```

## Install

If the repo is not cloned yet, bootstrap clone/pull + setup in one command. Replace `<handoff-git-ref>` with the branch or commit SHA recorded in the implementation handoff; do not rely on stale classroom branch names:

```bash
curl -fsSL https://raw.githubusercontent.com/hasemu1211/SmartFactory/<handoff-git-ref>/scripts/setup/bootstrap_ubuntu24_ai_vision_laptop.sh \
  -o /tmp/bootstrap_smartfactory_ai_vision.sh
bash /tmp/bootstrap_smartfactory_ai_vision.sh \
  --git-ref <handoff-git-ref> -- \
  --with-gopro \
  --with-model
```

If the repo already exists, project-local setup:

```bash
./scripts/setup/setup_ubuntu24_ai_vision_laptop.sh --with-gopro --with-model
```

Full fresh laptop setup after installing Ubuntu 24.04:

```bash
./scripts/setup/setup_ubuntu24_ai_vision_laptop.sh \
  --git-pull \
  --install-system \
  --with-ros \
  --with-cuda \
  --with-gopro \
  --with-model
```

Notes:

- ROS 2 distro is `jazzy` by default (`ROS_DISTRO=jazzy`).
- CUDA/driver installation is intentionally opt-in because it changes system
  packages and may require reboot.
- The setup script recreates `.venv` from requirements and writes
  `services/ai-server/requirements.local.lock`. Copying `.venv` between
  machines is not the primary path because paths and compiled wheels can be
  machine-specific. If an emergency same-OS transfer is needed, run
  `--pack-venv` to create a best-effort archive under `dist/`.
- MX450/2GB-VRAM class laptops should start with conservative settings:
  - `VISION_MODEL_IMGSZ=224` or `320` for continuous monitors.
  - `GOPRO_AI_MONITOR_FPS=1~3` until thermal/VRAM measurements are known.
  - `GOPRO_STREAM_TARGET_FPS=30` only as a media/browser target when healthy.
  - enable only the needed ROI path first (`lift_roi`) and keep high-quality evidence capture burst-based.
- Naming boundary: "GoPro webcam" in this document means OpenGoPro's USB
  webcam-mode transport. In SmartFactory source contracts the camera is still
  `global_cam_01` / global camera, not a generic webcam source.


## Lift transport evidence mode (B안)

권장 운영은 **전이 시점 고품질 증거 + 주행 중 낙하물 후보 감시**다.

- `LIFT_UP -> DRIVE`: full frame과 `lift_roi` crop을 짧게 저장하고 LiftRoiEvidence를 실행한다.
- `DRIVE`: 모든 부품 검증을 계속 돌리지 않고, `DROPPED_ITEM`/이탈 후보만 `3~5fps`로 감시한다.
- `DRIVE -> LIFT_DOWN`: lift-down 허용 직전에 full frame과 `lift_roi` crop을 다시 저장한다.
- 주행 중 GoPro 결과는 `ADVISORY/CANDIDATE`로 취급하고, 최종 task 전이/HOLD 여부는 Main/WMS/robot state가 authoritative하다.

자세한 운영 명령은 `docs/setup/gopro-lift-transport-evidence-workflow.md`를 따른다.


## No-hardware monitor/API smoke

This smoke path needs no robot, no GoPro, and no model tuning. It validates the
REST contract, monitor state API, person hazard read model, pure dropped-item
policy, lift-load aggregation policy, and Main DB adapter shape tests.

```bash
cd /path/to/SmartFactory
./scripts/ai/setup_ai_server_env.sh
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

Optional local-only API smoke in another terminal. This proves the laptop
process is alive, but it does **not** prove Main can reach it because
`127.0.0.1` is loopback-local to this laptop:

```bash
AI_SERVER_HOST=127.0.0.1 \
VISION_MODEL_WORKER_ENABLED=false \
./scripts/ai/run_ai_server.sh

curl http://127.0.0.1:8100/api/v1/health
curl http://127.0.0.1:8100/api/v1/vision/monitors
curl -X PUT http://127.0.0.1:8100/api/v1/vision/monitors/person_drive/state \
  -H 'Content-Type: application/json' \
  -d '{"enabled":true,"source":"tb3_1_picam","operation_state":"DRIVE","task_id":101}'
curl -X PUT http://127.0.0.1:8100/api/v1/vision/monitors/person_drive/state \
  -H 'Content-Type: application/json' \
  -d '{"enabled":true,"source":"tb3_2_picam","operation_state":"DRIVE","task_id":102}'
curl 'http://127.0.0.1:8100/api/v1/vision/monitors/person_drive/state?robot_id=tb3_1'
curl 'http://127.0.0.1:8100/api/v1/vision/monitors/person_drive/state?robot_id=tb3_2'
curl 'http://127.0.0.1:8100/api/v1/vision/hazards/person/latest?robot_id=tb3_1'
curl 'http://127.0.0.1:8100/api/v1/vision/hazards/person/latest?robot_id=tb3_2'
```

The monitor state API is **process-local/ephemeral** by design in this
no-hardware scaffold. Main should reassert the desired monitor state after every
AI Server restart; the returned `revision` is a per-process monotonic smoke
counter, not a durable DB version.

For Main/WiFi-LAN smoke on the target laptop, set `AI_SERVER_HOST=0.0.0.0` so
the API listens on the laptop WiFi interface, then test from both sides:

```bash
AI_SERVER_HOST=0.0.0.0 \
VISION_MODEL_WORKER_ENABLED=false \
./scripts/ai/run_ai_server.sh
```

Laptop-local check:

```bash
curl http://127.0.0.1:8100/api/v1/health
```

Main PC check, replacing `<laptop_wifi_ip>` with `hostname -I` / `ip route get`
output from the laptop:

```bash
curl http://<laptop_wifi_ip>:8100/api/v1/health
curl http://<laptop_wifi_ip>:8100/api/v1/vision/monitors
```

After hostname/DNS/mDNS/hosts is configured, the same Main-side check should work
with hostname-first endpoints such as `http://smartfactory-vision.local:8100` or
an operator-managed `http://smartfactory-ai:8100` alias. If the lab subnet
changes to `192.168.30.x`, update only DNS/mDNS/hosts or explicit fallback envs;
do not hard-code the new subnet in tracked defaults.

## Operator PC remote low-load refresh/restart

The lab-only runtime-control API lets an operator PC ask the AI/Vision laptop to
restart its local `low-load` runtime with a small allowlist of tuning parameters.
This is for laptop runtime operation only; it is not a Main-facing robot-control
API and it never publishes `/cmd_vel`, mutates Main DB rows, or runs arbitrary
shell commands.

Safety rules:

- Disabled by default. Enable it only on the lab laptop with
  `SF_RUNTIME_CONTROL_ENABLED=true`.
- Optional but recommended token: set `SF_RUNTIME_CONTROL_TOKEN` on the laptop
  and on the operator PC. Requests then need `X-SF-Operator-Token`.
- Git update is limited to the laptop's current branch with `git pull --ff-only`.
  The helper refuses to pull/restart if the laptop working tree is dirty.
- Runtime params are allowlisted, for example
  `GOPRO_AI_MONITOR_FPS`, `GOPRO_AI_MONITOR_IMGSZ`,
  `GOPRO_WEBRTC_FULL_OUTPUT_WIDTH`, `GOPRO_WEBRTC_BITRATE`,
  `PICAM_WEBRTC_AI_FPS`, `GOPRO_ROI_HINT_NORMALIZED`, and the diagnostic
  `VISION_MAP_ROI_*` overlay-tuning values.

First time after pulling this feature, start low-load once on the laptop with the
operator endpoint enabled:

```bash
cd ~/SmartFactory
export SF_RUNTIME_CONTROL_ENABLED=true
# Optional shared secret for the lab network:
# export SF_RUNTIME_CONTROL_TOKEN='<lab-token>'
./scripts/vision/sf_lab.sh low-load
```

Operator PC aliases, assuming this repo is also available locally:

```bash
export SF_VISION_LAPTOP_URL=http://smartfactory-vision.local:8100
# If a token was set on the laptop, set the same value here:
# export SF_RUNTIME_CONTROL_TOKEN='<lab-token>'
alias sfvisionctl='cd ~/SmartFactory && AI_SERVER_URL=${SF_VISION_LAPTOP_URL:-http://smartfactory-vision.local:8100} ./scripts/vision/sf_lab.sh api'
alias sflowrefresh='sfvisionctl restart-low-load --git-pull'
alias sflowdry='sfvisionctl restart-low-load --dry-run'
```

Examples from the operator PC:

```bash
# Check whether the laptop endpoint is enabled and see the allowlist.
sfvisionctl runtime-status

# Dry-run: writes no restart, but validates the payload shape.
sflowdry GOPRO_AI_MONITOR_FPS=3 GOPRO_AI_MONITOR_IMGSZ=512

# Pull latest current-branch code on the laptop, then restart low-load with params.
sflowrefresh \
  GOPRO_AI_MONITOR_FPS=3 \
  GOPRO_AI_MONITOR_IMGSZ=512 \
  GOPRO_WEBRTC_FULL_OUTPUT_WIDTH=960 \
  GOPRO_WEBRTC_FULL_OUTPUT_HEIGHT=540 \
  GOPRO_WEBRTC_BITRATE=1200k \
  PICAM_WEBRTC_AI_FPS=5

# Static ROI hint tuning for the legacy lift_roi crop.
sflowrefresh GOPRO_ROI_HINT_NORMALIZED=0.10,0.20,0.50,0.55

# Diagnostic global MapROI overlay.
# This draws only on the AI/WebRTC overlay; it is not a Main-facing dropped-item
# or lift evidence contract and does not mutate Main DB/control state.
# Quote the polygon because semicolons are shell separators.
sflowrefresh \
  VISION_MAP_ROI_ENABLED=true \
  VISION_MAP_ROI_SOURCE=global_cam_01 \
  VISION_MAP_ROI_MARKER_IDS=11,12 \
  VISION_MAP_ROI_FREEZE_MARKER_IDS=12 \
  VISION_MAP_ROI_MIN_MARKERS=1 \
  VISION_MAP_ROI_STALE_USABLE_S=180 \
  'VISION_MAP_ROI_POLYGON_NORMALIZED=0.18,0.01;0.90,0.01;0.82,0.98;0.26,0.98'
```

If `--git-pull` fails because the laptop has local changes, the helper exits
before stopping the current runtime. Inspect the laptop log under
`.run/vision/runtime-control/<run_id>.log`, clean/commit/stash intentionally,
and retry.

## Run

Start the AI Server + public gateway bundle. The following is the lightweight
smoke/comparator profile for laptop/TurtleBot checks:

```bash
AI_SERVER_HOST=0.0.0.0 \
VISION_MODEL_WORKER_ENABLED=true \
VISION_MODEL_PATH=./yolov8n.pt \
VISION_MODEL_TASK=detect \
VISION_MODEL_DEVICE=0 \
VISION_MODEL_IMGSZ=224 \
./scripts/vision/run_d1_vision_multi_source_gateway_bundle.sh
```

For the GoPro segment-overlay proof profile, override the model settings
explicitly instead of relying on the lightweight defaults:

```bash
AI_SERVER_HOST=0.0.0.0 \
VISION_MODEL_WORKER_ENABLED=true \
VISION_MODEL_PATH=/home/codelab/yolo_test/runs/segment/bottle_detection_yolov8s_seg/weights/best.pt \
VISION_MODEL_TASK=segment \
VISION_MODEL_DEVICE=0 \
VISION_MODEL_IMGSZ=640 \
./scripts/vision/run_d1_vision_multi_source_gateway_bundle.sh
```

Start the GoPro USB webcam-mode transport headlessly and verify one OpenCV
frame:

```bash
./scripts/vision/start_gopro_webcam_stream.py --test-read
```

It should print an `opencv_input=...` URL similar to:

```text
udp://0.0.0.0:8554?overrun_nonfatal=1&fifo_size=50000000
```

In another terminal, start GoPro/global camera ingest from that OpenCV-readable
source:

```bash
./scripts/vision/run_gopro_smart_roi_adapter.py \
  --input 'udp://0.0.0.0:8554?overrun_nonfatal=1&fifo_size=50000000' \
  --source global_cam_01 \
  --roi-view lift_roi \
  --target-fps "${GOPRO_AI_MONITOR_FPS:-5}" \
  --bufferless
```

If the GoPro appears as a real UVC `/dev/video*` node on a different laptop,
`--input /dev/video0` is also valid. The current verified path on this PC is
USB-NCM + OpenGoPro TS stream, not `/dev/video*`.

Optional model-backed lift ROI check:

```bash
./scripts/vision/run_gopro_smart_roi_adapter.py \
  --input /dev/video0 \
  --source global_cam_01 \
  --roi-view lift_roi \
  --target-fps "${GOPRO_AI_MONITOR_FPS:-5}" \
  --evaluate-lift-roi \
  --operation MONITOR \
  --bufferless
```

## View

```text
Full overlay:
http://smartfactory-vision.local:8090/api/v1/vision/overlay/stream?source=global_cam_01&view=full

Lift ROI overlay:
http://smartfactory-vision.local:8090/api/v1/vision/overlay/stream?source=global_cam_01&view=lift_roi

Pallet crop overlay:
http://smartfactory-vision.local:8090/api/v1/vision/overlay/stream?source=global_cam_01&view=pallet_zoom
```

## Verification

```bash
./scripts/vision/run_gopro_smart_roi_adapter.py --check
./scripts/vision/start_gopro_webcam_stream.py --test-read --exit-after-test
VISION_MODEL_WORKER_ENABLED=false ./scripts/vision/run_d1_vision_multi_source_gateway_bundle.sh --check
services/ai-server/.venv/bin/python - <<'PY'
import cv2
print('opencv', cv2.__version__)
try:
    import torch
    print('torch', torch.__version__, 'cuda_available', torch.cuda.is_available())
except Exception as exc:
    print('torch check skipped/error:', exc)
PY
```

## Design constraints

- 1080p live USB webcam-mode transport is the baseline because OpenGoPro's
  transport enum exposes 1080/720/480 real-time modes.
- Higher GoPro recording resolutions are still useful, but they are not assumed
  to be available as the low-latency live USB webcam stream. If true 4K/5.3K
  live input is later needed, add a capture-card/HDMI or verified stream path
  behind the same adapter boundary.
- Detection should crop before resize. A 4K or 1080p full frame resized directly
  to YOLO input can erase small lift/load details; crop-first keeps many more
  model-space pixels for the same object.
- Media FPS, continuous AI FPS, and transition-proof quality are separate
  knobs. Start with low continuous AI load and use short high-quality proof
  capture at PICKUP/DROPOFF boundaries once the hardware-gated live transition
  capture story is enabled. In this no-hardware implementation,
  `GOPRO_EVIDENCE_RUNTIME_SCOPE=plan_mock_no_hardware` makes that boundary
  explicit. If 4 cm dropped items are below pixel budget, return
  `LOW_PIXEL_BUDGET`/`LOW_QUALITY_EVIDENCE` for review before increasing
  continuous load.
