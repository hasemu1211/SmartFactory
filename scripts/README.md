# SmartFactory scripts guide

Korean version: [`README.ko.md`](README.ko.md).

This is the short operator guide: what to run, when to run it, and what each command does.
Detailed architecture notes live under `docs/`.

## Basic rules

- Start long-running Vision live processes only inside tmux `Smartfactory:3:Development`.
- Use `sf_lab.sh` for normal operation.
- Use `sf_vision.sh` only for lower-level profile debugging.

## Most-used commands

```bash
# Start all lab Vision services: AI Server + GoPro global cam + PiCam WebRTC/MJPEG fallback + mDNS
./scripts/vision/sf_lab.sh all

# Check status
./scripts/vision/sf_lab.sh status

# Print Main/browser URLs
./scripts/vision/sf_lab.sh urls

# Stop
./scripts/vision/sf_lab.sh down
```

## What to run for each task

| Task | Command | What it does |
|---|---|---|
| Start the full lab Vision bundle | `./scripts/vision/sf_lab.sh all` | Starts GoPro, PiCam, AI Server, WebRTC, MJPEG fallback, and mDNS helper. |
| Check runtime status | `./scripts/vision/sf_lab.sh status` | Shows live processes and stream health. |
| Print URLs | `./scripts/vision/sf_lab.sh urls` | Shows Main dashboard, AI API, WebRTC, and MJPEG fallback URLs. |
| Stop Vision processes | `./scripts/vision/sf_lab.sh down` | Stops the Vision live bundle. |
| Check AI health | `./scripts/vision/sf_lab.sh api health` | Calls AI Server health. |
| Check stream discovery | `./scripts/vision/sf_lab.sh api streams` | Prints the JSON Main should read. |
| Show evidence request plan | `./scripts/vision/sf_lab.sh api evidence-plan PICKUP` | No hardware required. |
| Show evidence mock response | `./scripts/vision/sf_lab.sh api evidence-mock DROPOFF` | No Main DB mutation. |
| Call evaluation without a frame | `./scripts/vision/sf_lab.sh api evaluate-no-frame global_cam_01 lift_roi PICKUP` | Checks API response shape. |
| Call quality evaluation | `./scripts/vision/sf_lab.sh api evaluate-quality global_cam_01 full` | Checks current quality/evaluation response. |

## Robot Pi camera bringup

Before running `sf_lab.sh all` on the Vision PC, start camera bringup on the robot SSH terminal you are using.

```bash
# tb3_1 camera
ROS_DOMAIN_ID=2 ros2 launch turtlebot3_bringup camera_low_bandwidth.launch.py

# tb3_2 camera when needed
ROS_DOMAIN_ID=5 ros2 launch turtlebot3_bringup camera_low_bandwidth.launch.py
```

The robot Pi should only run camera bringup. WebRTC/AI work runs on the Vision PC.

## Main dashboard

```text
http://smartfactory-main.local:8088/operate/control
```

Use these commands to see what Main should consume:

```bash
./scripts/vision/sf_lab.sh urls
./scripts/vision/sf_lab.sh api streams
```

If Main shows `MJPEG·poll`, check only these first:

```bash
./scripts/vision/sf_lab.sh status
./scripts/vision/sf_lab.sh urls
./scripts/vision/sf_vision.sh logs gopro-adapter
./scripts/vision/sf_vision.sh logs webrtc-sidecar
```

## Lower-level profile commands

Normally not needed. Use these for profile checks/debugging.

```bash
# List profiles
./scripts/vision/sf_vision.sh profiles

# Check recommended WebRTC profile
./scripts/vision/sf_vision.sh check lab-gopro-tb3-ffmpeg-first

# Start recommended WebRTC profile directly
./scripts/vision/sf_vision.sh up lab-gopro-tb3-ffmpeg-first

# Status/smoke/logs/stop
./scripts/vision/sf_vision.sh status
./scripts/vision/sf_vision.sh smoke
./scripts/vision/sf_vision.sh logs
./scripts/vision/sf_vision.sh down
```

## Make aliases

```bash
make vision-lab-all
make vision-lab-status
make vision-lab-urls
make vision-lab-api-plan OPERATION=PICKUP
make vision-lab-down
```

## Default profiles

| Profile | When to use |
|---|---|
| `lab-gopro-tb3-ffmpeg-first` | Recommended default. GoPro full uses 720p WebRTC primary, lift ROI uses 640x480 WebRTC, with MJPEG fallback. |
| `lab-gopro-tb3` | Use when checking the older MJPEG-stable path. |
| `tb3-live-webrtc` | Use when testing only tb3_1 PiCam WebRTC without GoPro. |
| `local-smoke` | Use when no hardware is available. |

## Default WebRTC URLs

```text
http://smartfactory-vision.local:8889/global_cam_01_full/
http://smartfactory-vision.local:8889/global_cam_01_lift_roi/
http://smartfactory-vision.local:8889/tb3_1_picam_full/
http://smartfactory-vision.local:8889/tb3_2_picam_full/
```

## Default MJPEG fallback URLs

```text
http://smartfactory-vision.local:8090/api/v1/vision/overlay/stream?source=global_cam_01&view=full&max_fps=30
http://smartfactory-vision.local:8090/api/v1/vision/overlay/stream?source=global_cam_01&view=lift_roi&max_fps=30
http://smartfactory-vision.local:8090/api/v1/vision/overlay/stream?source=tb3_1_picam&view=full&max_fps=30
http://smartfactory-vision.local:8090/api/v1/vision/overlay/stream?source=tb3_2_picam&view=full&max_fps=30
```

## mediamtx / ffmpeg checks

```bash
./scripts/vision/run_webrtc_sidecar_mediamtx.sh --check
./scripts/vision/run_webrtc_sidecar_mediamtx.sh --status
```

If `mediamtx` is not on PATH, set it explicitly:

```bash
export MEDIAMTX_BIN=/absolute/path/to/mediamtx
```
