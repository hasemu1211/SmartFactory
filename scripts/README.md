# SmartFactory scripts guide

Korean version: [`README.ko.md`](README.ko.md).
Filesystem ownership / placement rules: [`../docs/technical/project-filesystem-ownership.md`](../docs/technical/project-filesystem-ownership.md).

This directory contains local operator/developer entrypoints. Prefer these
scripts over ad-hoc commands so Main/Vision integration stays reproducible.

## Easiest operator path: `sf_lab.sh`

Operators do not need to remember profile names or environment variables for the
current lab setup. Start long-running live processes only inside tmux
`Smartfactory:3:Development`.

```bash
# all-in-one: GoPro global camera + TurtleBot Pi camera WebRTC, AI Server API, MJPEG fallback
./scripts/vision/sf_lab.sh all
# or: make vision-lab-all

# inspect status/URLs
./scripts/vision/sf_lab.sh status
./scripts/vision/sf_lab.sh urls

# stop
./scripts/vision/sf_lab.sh down
```

Separated helper commands use the same wrapper:

```bash
./scripts/vision/sf_lab.sh probe
./scripts/vision/sf_lab.sh api health
./scripts/vision/sf_lab.sh api streams
./scripts/vision/sf_lab.sh api worker-status global_cam_01
./scripts/vision/sf_lab.sh api evidence-plan PICKUP
./scripts/vision/sf_lab.sh api evidence-mock DROPOFF
./scripts/vision/sf_lab.sh api evaluate-no-frame global_cam_01 lift_roi PICKUP
./scripts/vision/sf_lab.sh api evaluate-quality global_cam_01 full
```

| Goal | Command | Notes |
|---|---|---|
| Start everything | `./scripts/vision/sf_lab.sh all` | WebRTC + AI Server API + MJPEG fallback + mDNS |
| Operator stream alias | `./scripts/vision/sf_lab.sh stream` | currently the same safe bundle as `all` |
| Print Main-facing URLs | `./scripts/vision/sf_lab.sh urls` | browser/handoff checks |
| Print evidence-plan JSON | `./scripts/vision/sf_lab.sh api evidence-plan` | no hardware required |
| Print evidence mock JSON | `./scripts/vision/sf_lab.sh api evidence-mock` | no Main DB mutation |
| Call the running AI Server evidence API | `evaluate-no-frame` / `evaluate-quality` | `/api/v1/evidence/evaluate` contract |

`sf_lab.sh` defaults to profile `lab-gopro-tb3-webrtc` and delegates to the
existing `sf_vision.sh` bundle. Use the lower-level scripts below only for
debugging or profile changes.

## Lower-level profile entrypoint: `sf_vision.sh`

Use this profile-based operator script when you need lower-level debugging or profile changes.

```bash
./scripts/vision/sf_vision.sh profiles
./scripts/vision/sf_vision.sh up lab-gopro-tb3
./scripts/vision/sf_vision.sh status
./scripts/vision/sf_vision.sh smoke
```

Stop everything:

```bash
./scripts/vision/sf_vision.sh down
```

Inspect logs:

```bash
./scripts/vision/sf_vision.sh logs
./scripts/vision/sf_vision.sh logs vision-bundle
./scripts/vision/sf_vision.sh logs gopro-adapter
```

Make aliases are also available. Easy `sf_lab.sh` aliases:

```bash
make vision-lab-all
make vision-lab-status
make vision-lab-urls
make vision-lab-api-plan OPERATION=PICKUP
make vision-lab-down
```

Lower-level `sf_vision.sh` profile aliases:

```bash
make vision-profiles
make vision-up PROFILE=lab-gopro-tb3
make vision-status
make vision-smoke-local
make vision-down
```

### Lower-level WebRTC sidecar profile

The stable default remains `lab-gopro-tb3`. Use `lab-gopro-tb3-webrtc` when
Main/browser should prefer WebRTC while retaining MJPEG fallback.

```bash
./scripts/vision/sf_vision.sh check lab-gopro-tb3-webrtc
# live runs are guarded to tmux Smartfactory:3:Development.
./scripts/vision/sf_vision.sh up lab-gopro-tb3-webrtc
./scripts/vision/sf_vision.sh status
./scripts/vision/sf_vision.sh smoke
```

The WebRTC sidecar requires `mediamtx` and `ffmpeg`. If `mediamtx` is missing,
`check` fails with install/path guidance. After installing, put `mediamtx` on
PATH or set:

```bash
export MEDIAMTX_BIN=/absolute/path/to/mediamtx
```

Sidecar-only checks:

```bash
./scripts/vision/run_webrtc_sidecar_mediamtx.sh --check
./scripts/vision/run_webrtc_sidecar_mediamtx.sh --print-config
./scripts/vision/run_webrtc_sidecar_mediamtx.sh --status
```

GoPro/global-camera media FPS and AI inference FPS are separate. The
`lab-gopro-tb3-webrtc` intent is 30 FPS WebRTC/browser media when healthy,
`GOPRO_AI_MONITOR_FPS=5` for continuous dropped-item/overlay inference, and
`GOPRO_EVIDENCE_IMGSZ=960` for short transition-proof evaluation. If a 4 cm
dropped item is below pixel budget, return
`LOW_PIXEL_BUDGET`/`LOW_QUALITY_EVIDENCE` plus sparse alert-window metadata
before increasing continuous AI load.

Default WebRTC URLs:

```text
browser: http://smartfactory-vision.local:8889/global_cam_01_full
WHEP:    http://smartfactory-vision.local:8889/global_cam_01_full/whep
browser: http://smartfactory-vision.local:8889/global_cam_01_lift_roi
WHEP:    http://smartfactory-vision.local:8889/global_cam_01_lift_roi/whep
browser: http://smartfactory-vision.local:8889/tb3_1_picam_full
WHEP:    http://smartfactory-vision.local:8889/tb3_1_picam_full/whep
browser: http://smartfactory-vision.local:8889/tb3_2_picam_full
WHEP:    http://smartfactory-vision.local:8889/tb3_2_picam_full/whep
```

For operator checks, open the browser URLs directly or use `--status`/`smoke`
to verify path readiness. Main-team WebRTC/MJPEG integration requirements live
in the separate handoff document
[`../docs/requests/main-webrtc-vision-integration-handoff-2026-06-25.ko.md`](../docs/requests/main-webrtc-vision-integration-handoff-2026-06-25.ko.md).
Sidecar details are in [`../docs/setup/webrtc-mediamtx-sidecar.md`](../docs/setup/webrtc-mediamtx-sidecar.md).

### Profiles

| Profile | Purpose | Hardware |
|---|---|---|
| `local-smoke` | AI Server/gateway/API/WebRTC fallback smoke | none |
| `tb3-live` | one TurtleBot Pi camera overlay | robot camera |
| `gopro-segment` | GoPro `global_cam_01` segment overlay proof | GoPro |
| `lab-gopro-tb3` | integrated GoPro + one TurtleBot lab demo, MJPEG stable path | GoPro + robot camera |
| `lab-gopro-tb3-webrtc` | same demo plus MediaMTX WebRTC sidecar | GoPro + robot camera + `mediamtx` |

`lab-gopro-tb3` starts:

- temporary `smartfactory-vision.local` mDNS publishing
- AI Server on `:8100`
- public MJPEG stream gateway on `:8090`
- `tb3_1_picam` ROS2 camera sidecar
- GoPro OpenGoPro stream
- GoPro smart ROI adapter
- WebRTC discovery/offer fallback endpoint

`lab-gopro-tb3-webrtc` adds the MediaMTX sidecar. If the currently available
hardware is GoPro + one `tb3_1_picam`, `global_cam_01/*` and
`tb3_1_picam/full` can be WebRTC-online now, while `tb3_2_picam/full` uses the
same configuration and becomes online when the second robot camera is brought
up with the matching domain/topic.

WebRTC is still additive/candidate. Without a configured media sidecar, the
offer endpoint intentionally selects MJPEG fallback. Main should prefer WebRTC
when healthy/configured and keep MJPEG fallback.

Robot-side camera bringup remains safety-owned and is not launched over SSH by
the operator bundle. On the TurtleBot, run:

```bash
ROS_DOMAIN_ID=2 ros2 launch turtlebot3_bringup camera_low_bandwidth.launch.py
```

## Lower-level Main/Vision scripts for debugging

### 1. Publish the temporary Vision hostname for a lab session

```bash
./scripts/vision/publish_vision_mdns_alias.py
```

Default behavior:

- publishes `smartfactory-vision.local -> <first LAN IPv4>` via Avahi/mDNS
- runs in the foreground
- withdraws the record when stopped with `Ctrl-C`
- does **not** change `/etc/hosts`, hostname, router DHCP, or DNS

Use this only for local/lab validation. Production should use router DHCP
reservation plus DNS/mDNS hostname configuration:

For dated lab DHCP/DNS handoff details, see
[`docs/requests/main-vision-runtime-config-request-2026-06-19.md`](../docs/requests/main-vision-runtime-config-request-2026-06-19.md).
Verify MAC/IP values before publishing externally or after DHCP/router changes.

Dry check:

```bash
./scripts/vision/publish_vision_mdns_alias.py --print-only
```

### 2. Start the Main-compatible Vision bundle

```bash
VISION_MODEL_WORKER_ENABLED=false ./scripts/vision/run_d1_vision_multi_source_gateway_bundle.sh
```

The bundle starts:

```text
0.0.0.0:8100   AI Server
0.0.0.0:8090   public HTTP/MJPEG Vision Stream Gateway
127.0.0.1:18090 internal tb3_1 overlay bridge
127.0.0.1:18091 internal tb3_2 overlay bridge
```

Current default callback settings:

```env
MAIN_SERVER_URL=http://smartfactory-main.local:8088
WMS_VISION_EVENTS_PATH=/api/v1/vision/events
WMS_EMIT_ENABLED=false
```

`WMS_EMIT_ENABLED=false` is intentional for safe default operation. Set it to
`true` only when you explicitly want Vision to POST evidence events into Main.

For TurtleBot Pi camera comparator validation, use the same bundle with model
processing enabled but keep the lightweight detect profile:

```bash
VISION_MODEL_WORKER_ENABLED=true \
VISION_MODEL_PATH=/home/codelab/yolo_test/yolov8n.pt \
VISION_MODEL_TASK=detect \
VISION_MODEL_IMGSZ=320 \
VISION_GATEWAY_PUBLISH_EVIDENCE=false \
WMS_EMIT_ENABLED=false \
./scripts/vision/run_d1_vision_multi_source_gateway_bundle.sh
```

For the integrated GoPro + PiCam lab path, use the source-specific model
profile. The current default intent is `global_cam_01=untuned yolov8s-seg
segment` and `tb3_*_picam=untuned yolov8n detect`. The GoPro global stream is
intended to segment the lifted pallet/ROI, then crop-first part recognition can
produce and deliver evidence. The current GoPro segment path is a pipeline
proof; reliable pallet/part recognition still requires a tuned model later.

```bash
./scripts/vision/sf_vision.sh up lab-gopro-tb3-webrtc
```

The multi-source bundle is still MJPEG-first for Main compatibility. It also
exposes WebRTC candidate descriptors from AI Server discovery:

```bash
curl 'http://smartfactory-vision.local:8100/api/v1/vision/streams?source=global_cam_01'
curl 'http://smartfactory-vision.local:8100/api/v1/vision/streams?source=tb3_1_picam'
curl 'http://smartfactory-vision.local:8100/api/v1/vision/webrtc/demo?source=global_cam_01&view=full'
```

Main-side WebRTC adoption request:
[`docs/requests/main-webrtc-vision-integration-request-2026-06-25.md`](../docs/requests/main-webrtc-vision-integration-request-2026-06-25.md).

### Robot camera bringup and namespace/domain rule

On each TurtleBot/Raspberry Pi, start the low-bandwidth camera driver:

```bash
ros2 launch turtlebot3_bringup camera_low_bandwidth.launch.py
```

Namespace is **not required** when each robot is isolated by ROS domain and the
Vision bundle maps each domain to a source id:

```text
tb3_1_picam: ROS_DOMAIN_ID=2, topic=/camera/image_raw/compressed, internal port 18090
tb3_2_picam: ROS_DOMAIN_ID=5, topic=/camera/image_raw/compressed, internal port 18091
```

This is the current recommended lab setup. The source id (`tb3_1_picam`) is
assigned by the Vision sidecar even though the robot camera topic inside that
domain is the unnamespaced `/camera/image_raw/compressed`.

Only use namespaced topics such as `/tb3_1/camera/image_raw/compressed` when
multiple robots intentionally share one ROS domain. In that case override the
bundle topic(s):

```bash
VISION_SOURCE_1_TOPIC=/tb3_1/camera/image_raw/compressed \
VISION_SOURCE_2_TOPIC=/tb3_2/camera/image_raw/compressed \
./scripts/vision/run_d1_vision_multi_source_gateway_bundle.sh
```

### GoPro global camera notes

GoPro is the global camera source `global_cam_01`, not a generic webcam source.
The multi-source bundle exposes `global_cam_01` through the AI Server upstream,
but it does not by itself start the GoPro USB/OpenGoPro capture process. For a
GoPro proof run, keep the AI Server/bundle running and start the GoPro stream +
adapter in separate terminals:

```bash
services/ai-server/.venv/bin/python scripts/vision/start_gopro_webcam_stream.py \
  --protocol TS --resolution 1080 --fov WIDE --port 8554 --test-read

services/ai-server/.venv/bin/python scripts/vision/run_gopro_smart_roi_adapter.py \
  --input 'udp://0.0.0.0:8554?overrun_nonfatal=1&fifo_size=50000000' \
  --source global_cam_01 \
  --ai-server-url http://127.0.0.1:8100 \
  --bufferless
```

WebRTC remains additive/candidate. MJPEG remains the required fallback until a
real media sidecar such as MediaMTX/GStreamer is configured and validated.

### 3. Smoke checks

```bash
curl http://smartfactory-vision.local:8100/api/v1/health
curl http://smartfactory-vision.local:8090/api/v1/vision/bridge/status
curl http://smartfactory-main.local:8088/api/v1/vision/bridge/status
```

Expected while robots/cameras are absent:

- services return HTTP `200`
- `motion_command_allowed=false`
- sources may show `no_frame` or offline/stale state until camera frames arrive

## Script groups and physical layout

Root `scripts/` now contains documentation only. Runnable scripts live directly
in purpose-specific subdirectories, and current docs/Makefile/systemd references
point to those real paths directly.

| Group | Runnable location | Examples |
|---|---|---|
| AI Server | `scripts/ai/` | `run_ai_server.sh`, `setup_ai_server_env.sh`, `setup_ai_server_model_env.sh`, `test_ai_server.sh` |
| D1 Vision / Main integration | `scripts/vision/` | `sf_vision.sh`, `publish_vision_mdns_alias.py`, `run_d1_vision_multi_source_gateway_bundle.sh`, `run_d1_vision_stream_gateway.py`, `smoke_main_dashboard_gateway.sh` |
| Contracts / validation | `scripts/validate/` | `validate_contracts.py`, `validate_deployment_assets.py` |
| Generated contract surfaces | `scripts/generate/` | `generate_source_registry_surfaces.py` |
| Reports / Confluence assets | `scripts/reports/` | `create_sprint3_presentation_pptx.py`, `generate-drawio-architectures.py`, `render-scenario-sequence-diagrams.py` |
| Ops checks | `scripts/ops/` | `check-confluence-env.sh` |
| Shared shell helpers | `scripts/lib/` | `vision_bundle_common.sh` |

Placement rule:

- Use the grouped script paths directly in new docs and automation.
- Do not add root-level executable shims unless an external deployment requires a documented transition.
- Keep implementation changes in the matching purpose directory.

## Notes

- Current lab live processes are guarded to tmux `Smartfactory:3:Development`.
  On another machine, set `SF_VISION_TMUX_REQUIRED_CONTEXT` before live `up` if the tmux name differs.
- Keep robot motion, Nav2, teleop, and `/cmd_vel` outside these Vision scripts.
- Do not commit generated `__pycache__` directories; they are local runtime cache.
