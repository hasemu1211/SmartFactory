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

## Install

If the repo is not cloned yet, bootstrap clone/pull + setup in one command:

```bash
curl -fsSL https://raw.githubusercontent.com/hasemu1211/SmartFactory/feature/ai-server-marker-detection/scripts/setup/bootstrap_ubuntu24_ai_vision_laptop.sh \
  -o /tmp/bootstrap_smartfactory_ai_vision.sh
bash /tmp/bootstrap_smartfactory_ai_vision.sh -- \
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
- GTX 1650-class GPUs should start with conservative settings:
  - `VISION_MODEL_IMGSZ=224` or `320`
  - `GOPRO_TARGET_FPS=5`
  - enable only the needed ROI path first (`lift_roi`).


## Lift transport evidence mode (B안)

권장 운영은 **전이 시점 고품질 증거 + 주행 중 낙하물 후보 감시**다.

- `LIFT_UP -> DRIVE`: full frame과 `lift_roi` crop을 짧게 저장하고 LiftRoiEvidence를 실행한다.
- `DRIVE`: 모든 부품 검증을 계속 돌리지 않고, `DROPPED_ITEM`/이탈 후보만 `3~5fps`로 감시한다.
- `DRIVE -> LIFT_DOWN`: lift-down 허용 직전에 full frame과 `lift_roi` crop을 다시 저장한다.
- 주행 중 GoPro 결과는 `CANDIDATE/ALERT`로 취급하고, 최종 task 전이는 WMS/robot state가 authoritative하다.

자세한 운영 명령은 `docs/setup/gopro-lift-transport-evidence-workflow.md`를 따른다.

## Run

Start the AI Server + public gateway bundle:

```bash
AI_SERVER_HOST=0.0.0.0 \
VISION_MODEL_WORKER_ENABLED=true \
VISION_MODEL_PATH=./yolov8n.pt \
VISION_MODEL_TASK=detect \
VISION_MODEL_DEVICE=0 \
VISION_MODEL_IMGSZ=224 \
./scripts/vision/run_d1_vision_multi_source_gateway_bundle.sh
```

Start the GoPro USB webcam stream headlessly and verify one OpenCV frame:

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
  --target-fps 5 \
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
  --target-fps 3 \
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

- 1080p live USB webcam is the baseline because OpenGoPro's webcam enum exposes
  1080/720/480 real-time webcam modes.
- Higher GoPro recording resolutions are still useful, but they are not assumed
  to be available as the low-latency live USB webcam stream. If true 4K/5.3K
  live input is later needed, add a capture-card/HDMI or verified stream path
  behind the same adapter boundary.
- Detection should crop before resize. A 4K or 1080p full frame resized directly
  to YOLO input can erase small lift/load details; crop-first keeps many more
  model-space pixels for the same object.
