# Main dashboard request — Vision WebRTC candidate + MJPEG fallback

- Date: 2026-06-25 KST
- Main page discussed: `http://smartfactory-main.local:8088/operate/control`
- Vision host: `smartfactory-vision.local`
- Scope requested from Main team: dashboard/media integration only. Do not make Main own AI evidence truth or robot motion control through Vision media APIs.

## Summary

The Vision side now exposes:

1. Existing HTTP/MJPEG stream paths for `global_cam_01`, `tb3_1_picam`, and `tb3_2_picam`.
2. Additive WebRTC candidate descriptors/signaling metadata through AI Server discovery.
3. Separate evidence/evaluation REST endpoints.

Existing MJPEG usage can continue. To actually use WebRTC from Main, the Main dashboard needs a small transport-selection update: discover available stream transports, prefer WebRTC when healthy/configured, and fall back to MJPEG without writing DB state for live video transport.

## Required Main runtime config

Keep hostname-first Vision config:

```bash
VISION_API_BASE_URL=http://smartfactory-vision.local:8100
VISION_STREAM_BASE_URL=http://smartfactory-vision.local:8090
LMS_VISION_STREAM_BASE_URL=http://smartfactory-vision.local:8090
```

Optional explicit fallback values:

```bash
VISION_API_FALLBACK_BASE_URL=http://192.168.10.59:8100
VISION_STREAM_FALLBACK_BASE_URL=http://192.168.10.59:8090
LMS_VISION_STREAM_FALLBACK_BASE_URL=http://192.168.10.59:8090
```

Do not replace live video with DB writes. DB/evidence records should be created only by explicit evidence/evaluation flows.

## Main dashboard transport selection

For each camera tile on `/operate/control`, Main should call:

```http
GET {VISION_API_BASE_URL}/api/v1/vision/streams?source={source_id}
```

Initial source/view set:

```text
global_cam_01/full
global_cam_01/lift_roi
tb3_1_picam/full
tb3_2_picam/full
```

Expected behavior:

1. Read `sources[0].stream_transports`.
2. Prefer WebRTC only after the offer endpoint returns `selected_transport == "webrtc"`; discovery URL templates alone are not enough.
3. If WebRTC offer/sidecar health is unavailable, unknown, or unhealthy, use the `kind == "mjpeg"` transport.
4. Keep the existing MJPEG stream path working:

```http
GET {VISION_STREAM_BASE_URL}/api/v1/vision/overlay/stream?source={source_id}&view={view}&max_fps=30
```

Candidate WebRTC path from AI Server:

```http
POST {VISION_API_BASE_URL}/api/v1/vision/streams/{source_id}/webrtc/offer?view={view}
```

When Vision is started with `lab-gopro-tb3-webrtc`, the descriptor includes sidecar URLs like:

```json
{
  "sidecar": {
    "status": "configured",
    "url_configured": true,
    "runtime_health_url": "http://127.0.0.1:8889/",
    "whep_url": "http://smartfactory-vision.local:8889/global_cam_01_full/whep",
    "browser_url": "http://smartfactory-vision.local:8889/global_cam_01_full"
  },
  "fallback_path": "/api/v1/vision/overlay/stream?source=global_cam_01&view=full&max_fps=30"
}
```

Use `whep_url` for WHEP-capable player integration only when the offer response selects WebRTC. `browser_url` is suitable for operator/browser demo embedding. Keep `fallback_path` as MJPEG fallback.

Debug/demo page exposed by Vision:

```http
GET {VISION_API_BASE_URL}/api/v1/vision/webrtc/demo?source=global_cam_01&view=full
```

If Main cannot make browser-direct requests to `smartfactory-vision.local` because of network/CORS constraints, add Main proxy endpoints for:

```http
GET  /api/v1/vision/streams?source={source_id}
POST /api/v1/vision/streams/{source_id}/webrtc/offer?view={view}
GET  /api/v1/vision/overlay/stream?source={source_id}&view={view}&max_fps=30
```

The proxy must remain read-only for media.

## Safety and ownership boundaries

Main must treat the Vision WebRTC/MJPEG APIs as media-only:

- no `/cmd_vel` publish
- no Nav2 action call
- no ROS parameter mutation
- no full rosbridge graph exposure
- no DB write from live video transport selection
- no evidence-truth mutation from WebRTC signaling

The Vision WebRTC offer response explicitly reports:

```json
{
  "media_only": true,
  "motion_command_allowed": false,
  "control_topics_published": [],
  "side_effects": {
    "db_writes": false,
    "evidence_truth_mutated": false,
    "ros_control_published": false,
    "ros_topics_started_by_http_request": false
  }
}
```

## Evidence/evaluation REST remains separate

Main should call evidence APIs only when it needs a task/evidence decision, not for live video rendering:

```http
POST {VISION_API_BASE_URL}/api/v1/evidence/evaluate
POST {VISION_API_BASE_URL}/api/v1/lift-roi/evaluate
POST {VISION_API_BASE_URL}/api/v1/lift-roi/evaluate-image
```

The returned payload includes judgment fields such as PASS / FAIL / UNCERTAIN and reason fields suitable for DB storage. Main remains owner of task IDs, DB writes, inventory truth, and UI state transitions.

## Acceptance checks for Main team

Run after Main config/code update:

```bash
curl http://smartfactory-vision.local:8100/api/v1/health
curl 'http://smartfactory-vision.local:8100/api/v1/vision/streams?source=global_cam_01'
curl 'http://smartfactory-vision.local:8100/api/v1/vision/streams?source=tb3_1_picam'
curl http://smartfactory-vision.local:8090/api/v1/vision/bridge/status
curl http://smartfactory-main.local:8088/api/v1/system/external-config
curl 'http://smartfactory-main.local:8088/api/v1/vision/streams?source=global_cam_01'
curl 'http://smartfactory-main.local:8088/api/v1/vision/bridge/status'
```

Expected:

- Main external config does not contain `<vision-host-or-name>`.
- `/operate/control` can show MJPEG fallback without WebRTC sidecar.
- When WebRTC is configured healthy, Main chooses WebRTC first.
- When WebRTC offer fails/unconfigured, Main falls back to MJPEG.
- Main does not expose robot control topics through the video component.

## Notes for today’s validation state

- GoPro `global_cam_01` MJPEG/overlay was proven.
- `tb3_1_picam` camera health and metrics were proven with a read-only subscriber.
- Vision now has an optional `lab-gopro-tb3-webrtc` MediaMTX sidecar profile. If `mediamtx` is not installed or the profile is not used, MJPEG fallback remains the stable path.
- `dist/SmartFactory_MVP` was intentionally not modified by Vision-side work.
