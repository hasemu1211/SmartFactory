# GoPro Lift→Transport Evidence Workflow

Purpose: use the wall-mounted GoPro/global camera as a smart-factory evidence
and anomaly sensor without making it the robot-control authority.

## Decision: B안

Adopt **state-boundary evidence + lightweight transit monitoring**:

1. `LIFT_UP -> DRIVE` 전이 직후: 고품질 full-frame + lift ROI 증거를 남긴다.
2. `DRIVE` 중: 모든 부품 확인을 계속 돌리지 않고, 낙하물/이탈 후보만 저율로 감시한다.
3. `DRIVE -> LIFT_DOWN` 전이 직전: 고품질 full-frame + lift ROI 증거를 다시 남긴다.
4. `LIFT_DOWN` 이후: 기존 LiftRoiEvidence/WMS 결과와 결합해 최종 검증한다.

GoPro 결과는 기본적으로 `PROOF`, `CANDIDATE`, `ALERT`다. 주행 중 단일
프레임 탐지는 `CONFIRMED`로 승격하지 않는다. 최종 task state 전이는 WMS/로봇
상태기계가 계속 authoritative하다.

## Why this fits the project

- 전역 카메라는 리프트 주변과 맵 전체 문맥을 동시에 보는 데 유리하다.
- GoPro/OpenGoPro live webcam baseline은 1080p라서, 주행 내내 고해상도 정밀
  부품 검사를 실시간으로 돌리는 것보다 transition proof에 쓰는 편이 안전하다.
- GTX 1650급 노트북에서는 `1080p ingest + crop-first ROI + YOLO imgsz 224~320 + 3~5fps`
  부터 시작하는 것이 현실적이다.
- 중간 주행에서는 “부품이 온전히 맞는지”보다 “떨어진 물체 후보가 생겼는지”가
  더 잘 맞는 전역 카메라 역할이다.

## Runtime shape

```text
GoPro HERO11 USB/OpenGoPro TS stream
  -> run_gopro_smart_roi_adapter.py --bufferless
    -> full frame POST: /api/v1/vision/frame/process source=global_cam_01
    -> smart lift ROI crop
    -> optional LiftRoiEvidence image POST
    -> evidence jpg: full + ROI
  -> stream gateway: :8090 overlay URLs with view=full|lift_roi|pallet_zoom
```

The adapter captures in a background thread and processes only the latest frame
when `--bufferless` is enabled. This prevents stale OpenCV/FFMPEG queue frames
from turning a 3~5 FPS AI loop into delayed evidence.

## Commands

Start AI Server + gateway:

```bash
AI_SERVER_HOST=0.0.0.0 \
VISION_MODEL_WORKER_ENABLED=true \
VISION_MODEL_PATH=./yolov8n.pt \
VISION_MODEL_TASK=detect \
VISION_MODEL_DEVICE=0 \
VISION_MODEL_IMGSZ=224 \
./scripts/vision/run_d1_vision_multi_source_gateway_bundle.sh
```

Start GoPro stream and copy the printed `opencv_input` URL:

```bash
./scripts/vision/start_gopro_webcam_stream.py --test-read
```

Example URL used below:

```bash
GOPRO_INPUT='udp://0.0.0.0:8554?overrun_nonfatal=1&fifo_size=50000000'
```

### 1) LIFT_UP -> DRIVE proof

Run for a short burst at transition time:

```bash
mkdir -p evidence/lift_up
./scripts/vision/run_gopro_smart_roi_adapter.py \
  --input "$GOPRO_INPUT" \
  --source global_cam_01 \
  --roi-view lift_roi \
  --target-fps 3 \
  --max-frames 5 \
  --bufferless \
  --evaluate-lift-roi \
  --operation PICKUP \
  --save-full-dir evidence/lift_up \
  --save-full-every 1 \
  --save-roi-dir evidence/lift_up \
  --save-every 1 \
  --evidence-label lift_up_proof
```

### 2) DRIVE transit dropped-object watch

Keep this running during drive state. Save sparse ROI evidence only when needed
or every N frames for audit sampling:

```bash
mkdir -p evidence/transit_roi
./scripts/vision/run_gopro_smart_roi_adapter.py \
  --input "$GOPRO_INPUT" \
  --source global_cam_01 \
  --roi-view lift_roi \
  --target-fps 5 \
  --bufferless \
  --evaluate-lift-roi \
  --operation MONITOR \
  --roi-kind DROPPED_ITEM \
  --save-roi-dir evidence/transit_roi \
  --save-every 15 \
  --evidence-label transit_drop_watch
```

### 3) DRIVE -> LIFT_DOWN proof

Run another short burst right before allowing lift-down:

```bash
mkdir -p evidence/pre_dropoff
./scripts/vision/run_gopro_smart_roi_adapter.py \
  --input "$GOPRO_INPUT" \
  --source global_cam_01 \
  --roi-view lift_roi \
  --target-fps 3 \
  --max-frames 5 \
  --bufferless \
  --evaluate-lift-roi \
  --operation DROPOFF \
  --save-full-dir evidence/pre_dropoff \
  --save-full-every 1 \
  --save-roi-dir evidence/pre_dropoff \
  --save-every 1 \
  --evidence-label pre_dropoff_proof
```

## Acceptance checks

- `start_gopro_webcam_stream.py --test-read --exit-after-test` reads one
  `1920x1080` frame from the GoPro stream on this PC.
- Adapter summaries include `capture_seq` and low `capture_age_ms` when
  `--bufferless` is used.
- Evidence directories contain both full-frame and ROI images for transition
  proof runs.
- Main/GUI can view:
  - `...?source=global_cam_01&view=full`
  - `...?source=global_cam_01&view=lift_roi`
