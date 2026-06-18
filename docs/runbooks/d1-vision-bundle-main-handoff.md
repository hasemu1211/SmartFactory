# D1 Vision Bundle and Main Handoff Runbook

Date: 2026-06-16 KST

## Purpose

`./scripts/run_d1_vision_bundle.sh` is the local one-command supervisor for the AI-included vision path. It keeps the ROS/FastAPI safety boundary intact while making the runtime easier to operate.

It is a **single supervisor process** that starts and stops these child processes together:

1. **AI Server** (`:8100`) — stores latest frames, runs worker tick/model detection, produces overlay images and `VisionEvent v1` candidates.
2. **`vision_frame_gateway`** — ROS2 sidecar that subscribes to the robot camera topic, posts frames to AI Server, triggers worker ticks, and publishes safe vision topics.
3. **`vision_overlay_stream_bridge`** (`:8090`) — read-only HTTP/MJPEG bridge that serves the AI overlay ROS topic to Main/GUI.

It intentionally does **not** start robot motion, Nav2, teleop, `/cmd_vel`, safety stop/slow execution, or robot-side persistent services. Nav/Movement owns motion and safety execution truth; this bundle only supplies vision evidence and read-only streams.

## Recommended process grouping

```text
Robot camera/domain bridge (already running)
  -> local ROS camera topic: /camera/image_raw/compressed
  -> D1 vision bundle supervisor
       1. AI Server :8100
       2. vision_frame_gateway
            publishes /sf/vision/sources/tb3_1_picam/overlay/compressed
            publishes /sf/vision/events
       3. vision_overlay_stream_bridge :8090
  -> Main/GUI consumes HTTP video/status/tags
```

This is preferable to merging all code into one Python process because AI Server must remain ROS-free. ROS code stays in sidecar processes; the bundle only supervises them.

## Run

Current demo/default profile:

```bash
cd /home/codelab/Desktop/Project/SmartFactory
./scripts/run_d1_vision_bundle.sh
```

Dry check without starting processes:

```bash
./scripts/run_d1_vision_bundle.sh --check
```

Help:

```bash
./scripts/run_d1_vision_bundle.sh --help
```

If replacing the currently running separate panes, stop only these local panes first: AI Server, `vision_frame_gateway`, and `vision_overlay_stream_bridge`. Keep the robot camera pane running unless the operator wants to stop the camera.

## Key environment knobs

| Env | Default | Meaning |
|---|---:|---|
| `ROS_DOMAIN_ID` | `2` | ROS domain used by local sidecars. |
| `AI_SERVER_HOST` | `0.0.0.0` | AI Server bind address. |
| `AI_SERVER_PORT` | `8100` | AI Server port. |
| `AI_SERVER_VENV_DIR` | `services/ai-server/.venv` | FastAPI runtime venv. |
| `AI_SERVER_EXTRA_PYTHONPATH` | `/home/codelab/venv/venv/...` if present | Temporary YOLO/Torch import path for current PC. Prefer project `.venv-yolo` later. |
| `VISION_MODEL_PATH` | `./yolov8n.pt` | Pretrained model file. |
| `VISION_MODEL_IMGSZ` | `224` | High-FPS smoke model image size. |
| `VISION_SOURCE_ID` | `tb3_1_picam` | Source id exposed to AI/Main. |
| `VISION_IMAGE_TOPIC` | `/camera/image_raw/compressed` | Camera topic the gateway subscribes to. |
| `VISION_GATEWAY_PERIOD_SEC` | `0.05` | Gateway processing cadence. |
| `VISION_STREAM_PORT` | `8090` | Read-only stream bridge port. |
| `VISION_STREAM_MAX_FPS` | `30` | Bridge max stream FPS cap. |

## Main/GUI receive surfaces

Assuming this PC is `192.168.10.63`:

| Purpose | Method / URL | Output |
|---|---|---|
| Operator view | `GET http://192.168.10.63:8090/api/v1/vision/overlay/view?source=tb3_1_picam` | HTML page with AI overlay video. |
| Main video stream | `GET http://192.168.10.63:8090/api/v1/vision/overlay/stream?source=tb3_1_picam&max_fps=30` | `multipart/x-mixed-replace` MJPEG stream. |
| Bridge status | `GET http://192.168.10.63:8090/api/v1/vision/bridge/status` | JSON read-only status, source paths, stale/has-frame state. |
| AI health | `GET http://192.168.10.63:8100/api/v1/health` | JSON service health, source/model summary. |
| Latest semantic tags | `GET http://192.168.10.63:8100/api/v1/detections/latest?source=tb3_1_picam&limit=10` | Latest `VisionEvent v1` candidates such as `box`, `person`, `unknown`. |
| Latest overlay metadata | `GET http://192.168.10.63:8100/api/v1/vision/overlay/latest?source=tb3_1_picam` | Overlay freshness, frame seq, event count. |

## Main server integration recommendation

Main should treat video and semantic evidence separately:

1. **Video:** pull MJPEG from `:8090`; do not request individual images at high FPS.
2. **Semantic tags:** either poll `GET /api/v1/detections/latest` at a controlled cadence or accept pushed events on `POST /api/v1/vision/events` once the live auto-emitter/relay is enabled.
3. **DB storage:** deduplicate by `event_id`, store semantic event metadata at a controlled cadence, and store images only as snapshot URLs or object-storage keys when needed.

Existing AI Server outbound client support already exists for `POST {MAIN_SERVER_URL}{WMS_VISION_EVENTS_PATH}` with defaults:

```text
MAIN_SERVER_URL=http://<main-host>:<main-port>
WMS_VISION_EVENTS_PATH=/api/v1/vision/events
WMS_EMIT_ENABLED=true
```

Current continuous live camera path publishes semantic snapshots to ROS `/sf/vision/events` and keeps AI cache updated. Continuous HTTP auto-post from worker tick to Main is not part of this bundle yet; it should be a small follow-up relay/emitter slice if Main wants push instead of polling.

## Safety guarantees

- No `/cmd_vel`, Nav2, teleop, ROS parameters, or whole-graph rosbridge exposure.
- No safety stop/slow execution authority; Vision may produce evidence/alerts, but Nav/Movement executes motion and safety outcomes.
- Stream bridge is read-only: GET/OPTIONS only; mutation methods are rejected.
- The public Main-facing gateway remains ROS-free. Current ROS/domain handling runs in sidecars, but ROS-aware Vision/AI internals remain valid future implementation options when approved by ADR and safety gates.
- Ctrl-C on the bundle supervisor sends shutdown signals to all local child processes.

## Dual robot/domain runtime

Current two-robot smoke keeps domain separation instead of forcing one ROS domain:

| Robot/source | Robot domain | Local process group | HTTP port | Main stream |
|---|---:|---|---:|---|
| `tb3_1_picam` | `2` | `run_d1_vision_bundle.sh` includes AI + Robot1 gateway + bridge | `8090` | `/api/v1/vision/overlay/stream?source=tb3_1_picam&max_fps=30.0` |
| `tb3_2_picam` | `5` | `run_d1_vision_domain_sidecar.sh` adds Robot2 gateway + bridge against the already-running AI Server | `8091` | `/api/v1/vision/overlay/stream?source=tb3_2_picam&max_fps=30.0` |

Robot2/domain5 sidecar command:

```bash
cd /home/codelab/Desktop/Project/SmartFactory
ROS_DOMAIN_ID=5 \
VISION_SOURCE_ID=tb3_2_picam \
VISION_IMAGE_TOPIC=/camera/image_raw/compressed \
VISION_STREAM_PORT=8091 \
./scripts/run_d1_vision_domain_sidecar.sh
```

Robot2 Main/GUI receive surfaces on the current LAN candidate:

```text
GET http://192.168.10.63:8091/api/v1/vision/overlay/view?source=tb3_2_picam
GET http://192.168.10.63:8091/api/v1/vision/overlay/stream?source=tb3_2_picam&max_fps=30.0
GET http://192.168.10.63:8091/api/v1/vision/bridge/status
GET http://192.168.10.63:8100/api/v1/detections/latest?source=tb3_2_picam&limit=10
```

Historical smoke note: the first two-robot smoke exposed separate read-only ports while domain-bridge risk was being isolated. Current Main integration supersedes that public `8090/8091` split with a single source-selected public `:8090` gateway; any `8091` bridge is internal/operator-only and not a Main contract.

## Main-compatible single public gateway mode

Current recommended Main integration mode supersedes the earlier temporary public `8090/8091` split.

Public base URL for Main:

```text
LMS_VISION_STREAM_BASE_URL=http://192.168.10.63:8090
```

Public endpoints:

```text
GET /api/v1/vision/overlay/stream?source={source_id}&max_fps={1..30}
GET /api/v1/vision/frame/stream?source={source_id}&max_fps={1..30}
GET /api/v1/vision/overlay/view?source={source_id}
GET /api/v1/vision/bridge/status
```

Internal implementation:

```text
public 0.0.0.0:8090 -> ROS-free Vision Stream Gateway
  tb3_1_picam -> internal 127.0.0.1:18090 -> ROS_DOMAIN_ID=2 overlay bridge
  tb3_2_picam -> internal 127.0.0.1:18091 -> ROS_DOMAIN_ID=5 overlay bridge
```

The internal ports are not Main contract. Main should know only `:8090` and `source`.

Run command, inside tmux `Smartfactory:3` only:

```bash
./scripts/run_d1_vision_multi_source_gateway_bundle.sh
```

Current 2026-06-16 runtime note: Robot1 is updating through the single gateway. Robot2 delivered initial frames but then became stale after `192.168.10.89` stopped responding to ping/SSH; restart Robot2 camera once that host is reachable again.

## Async high-FPS AI overlay mode

Added on 2026-06-16 KST.

The current recommended multi-source bundle uses a latest-only asynchronous gateway pipeline:

```text
Robot camera compressed topic
  -> vision_frame_gateway latest-only async slot
  -> AI Server POST /api/v1/vision/frame/process
  -> /sf/vision/sources/{source}/overlay/compressed
  -> internal source bridge 127.0.0.1:18090/18091
  -> public Vision Stream Gateway 0.0.0.0:8090
  -> Main proxy / HTML dashboard
```

Key defaults in `./scripts/run_d1_vision_multi_source_gateway_bundle.sh`:

| Env | Default | Meaning |
|---|---:|---|
| `VISION_GATEWAY_PERIOD_SEC` | `0.033333` | Gateway target processing cadence. |
| `VISION_GATEWAY_FRAME_PROCESS_PATH` | `/api/v1/vision/frame/process` | Single-request AI ingest+overlay hot path. |
| `VISION_GATEWAY_ASYNC_PIPELINE` | `true` | Enables bounded latest-only worker thread per source. |
| `VISION_GATEWAY_PROCESS_FRAME_INLINE` | `true` | Uses `/frame/process` instead of separate `/frame` + `/worker/tick`. |
| `VISION_GATEWAY_IMAGE_QOS_RELIABILITY` | `reliable` | Current robot camera subscription reliability. Change to `sensor_data`/`best_effort` if the publisher is best-effort. |
| `VISION_GATEWAY_OVERLAY_PUB_QOS_RELIABILITY` | `reliable` | Overlay topic publisher reliability. |
| `VISION_STREAM_OVERLAY_SUB_QOS_RELIABILITY` | `reliable` | Internal HTTP bridge overlay subscriber reliability. |
| `VISION_GATEWAY_PUBLISH_LAGGING_OVERLAY` | `false` | Do not publish overlay if it is behind the latest processed frame. |

Backpressure rule: at most one pending frame per source is retained. If AI/HTTP is slower than camera input, the pending frame is replaced by the newest frame. This protects latency and memory; it intentionally drops stale work instead of trying to process every frame.

Current Main contract is unchanged:

```text
LMS_VISION_STREAM_BASE_URL=http://192.168.10.63:8090
GET /api/v1/vision/overlay/stream?source={source_id}&max_fps=30
GET /api/v1/vision/frame/stream?source={source_id}&max_fps=30
GET /api/v1/vision/bridge/status
```

Main should not call `/api/v1/vision/frame/process`; that endpoint is an internal hot path between the ROS sidecar and AI Server.

Validation snapshot from the 2026-06-16 restart in tmux `Smartfactory:3.3`:

- Public listeners: `0.0.0.0:8100`, `0.0.0.0:8090`, internal `127.0.0.1:18090`, `127.0.0.1:18091`.
- Both `tb3_1_picam` and `tb3_2_picam` were online from `GET /api/v1/vision/bridge/status`.
- Status sequence deltas over a short sample were about 29-30 frames/s per source.
- Direct internal MJPEG samples were about 20-24 fps depending on frame size; public/browser FPS can vary with Wi-Fi, frame byte size, and number of simultaneous viewers.

If strict browser-visible 30fps is required, first reduce camera resolution/JPEG quality or model overlay frame size. If that is still insufficient, plan a future WebRTC/H.264 stream plane; do not revert to per-frame HTTP snapshot polling.
