# SmartFactory Vision WebRTC MediaMTX sidecar

This is the operator path for WebRTC video transport. It is **media-only**:
it does not publish robot commands, expose the whole ROS graph, mutate ROS
parameters, write DB state, or change evidence truth.

## One-command profile

Use the normal MJPEG-safe profile when WebRTC is not needed:

```bash
./scripts/vision/sf_vision.sh up lab-gopro-tb3
```

Use the WebRTC sidecar profile when Main/browser should prefer WebRTC and keep
MJPEG fallback:

```bash
./scripts/vision/sf_vision.sh check lab-gopro-tb3-webrtc
# live runs are guarded to tmux Smartfactory:3:Development.
./scripts/vision/sf_vision.sh up lab-gopro-tb3-webrtc
./scripts/vision/sf_vision.sh status
./scripts/vision/sf_vision.sh smoke
```

Stop all recorded processes:

```bash
./scripts/vision/sf_vision.sh down
```

Live/long-running processes for the current lab workflow must be kept in tmux
`Smartfactory:3:Development`.

## Prerequisites

The sidecar needs:

- `ffmpeg` / `ffprobe`
- `mediamtx` on `PATH`, or `MEDIAMTX_BIN=/absolute/path/to/mediamtx`

Check only the sidecar prerequisites:

```bash
./scripts/vision/run_webrtc_sidecar_mediamtx.sh --check
```

If MediaMTX is missing, download the Linux amd64 release from
<https://github.com/bluenviron/mediamtx/releases>, extract it, and either put
`mediamtx` on `PATH` or export `MEDIAMTX_BIN`.

## Ports

The profile intentionally avoids GoPro UDP `:8554`.

| Port | Purpose |
|---|---|
| `18554/tcp` | MediaMTX localhost-only RTSP publish/read |
| `8889/tcp` | MediaMTX WebRTC browser/WHEP HTTP |
| `8189/udp` | MediaMTX WebRTC ICE UDP |
| `19997/tcp` | MediaMTX localhost Control API |

## Stream mapping

Default profile streams:

| Source/view | MediaMTX path | Browser URL | WHEP URL |
|---|---|---|---|
| `global_cam_01/full` | `global_cam_01_full` | `http://smartfactory-vision.local:8889/global_cam_01_full` | `http://smartfactory-vision.local:8889/global_cam_01_full/whep` |
| `global_cam_01/lift_roi` | `global_cam_01_lift_roi` | `http://smartfactory-vision.local:8889/global_cam_01_lift_roi` | `http://smartfactory-vision.local:8889/global_cam_01_lift_roi/whep` |
| `tb3_1_picam/full` | `tb3_1_picam_full` | `http://smartfactory-vision.local:8889/tb3_1_picam_full` | `http://smartfactory-vision.local:8889/tb3_1_picam_full/whep` |
| `tb3_2_picam/full` | `tb3_2_picam_full` | `http://smartfactory-vision.local:8889/tb3_2_picam_full` | `http://smartfactory-vision.local:8889/tb3_2_picam_full/whep` |

The runner reads the already-proven MJPEG overlay stream and republishes it to
MediaMTX as low-latency H.264 RTSP via ffmpeg. Main/browser reads WebRTC from
MediaMTX.

## Main-facing contract

Main should discover stream transports from AI Server:

```bash
curl 'http://smartfactory-vision.local:8100/api/v1/vision/streams?source=global_cam_01'
```

For `lab-gopro-tb3-webrtc`, the WebRTC transport descriptor includes URL and health metadata:

```json
{
  "kind": "webrtc",
  "media_only": true,
  "fallback_kind": "mjpeg",
  "sidecar": {
    "status": "configured",
    "url_configured": true,
    "runtime_health_url": "http://127.0.0.1:8889/",
    "path_runtime_health": "online",
    "path_id": "global_cam_01_full",
    "whep_url": "http://smartfactory-vision.local:8889/global_cam_01_full/whep",
    "browser_url": "http://smartfactory-vision.local:8889/global_cam_01_full"
  }
}
```

Main should call the offer endpoint and use `sidecar.whep_url` only when the offer response returns `selected_transport=webrtc`. Selection requires both the MediaMTX WebRTC listener to be healthy and the requested MediaMTX path to be online. If the listener is unhealthy or the requested path is missing/offline, the offer response selects MJPEG fallback. `sidecar.browser_url` is for iframe/operator demo playback.

## Diagnostics

```bash
./scripts/vision/run_webrtc_sidecar_mediamtx.sh --print-config
./scripts/vision/run_webrtc_sidecar_mediamtx.sh --status
./scripts/vision/run_webrtc_sidecar_mediamtx.sh --smoke
./scripts/vision/sf_vision.sh logs webrtc-sidecar
```

`--status` distinguishes:

- `configured`
- `mediamtx_unreachable`
- `publisher_missing`
- `publisher_alive`

`--smoke` additionally uses `ffprobe` against the first RTSP path, so it needs
real frames from the gateway/GoPro stream.
