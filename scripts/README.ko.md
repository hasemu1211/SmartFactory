# SmartFactory scripts 안내서 (한국어)

이 디렉토리는 SmartFactory 로컬 개발/운영 보조 스크립트의 진입점입니다. 특히 Main/Vision 연동은 임의 명령보다 이 디렉토리의 스크립트를 우선 사용하세요.
파일시스템 ownership / 용도별 배치 기준: [`../docs/technical/project-filesystem-ownership.md`](../docs/technical/project-filesystem-ownership.md).

## 현재 결론: `smartfactory-vision.local`은 자동 영구 설정이 아님

현재 `smartfactory-vision.local`은 다음 helper 프로세스가 살아있는 동안만 임시로 mDNS 방송됩니다.

```bash
./scripts/vision/publish_vision_mdns_alias.py
```

이 helper는 다음을 하지 않습니다.

- `/etc/hosts` 수정 안 함
- OS hostname 변경 안 함
- 라우터 DHCP reservation 설정 안 함
- 영구 DNS 설정 안 함

따라서 “사용자가 신경 쓰지 않아도 되는 운영 상태”를 만들려면 라우터/DNS 쪽에서 고정해야 합니다.

날짜가 박힌 lab DHCP/DNS handoff 세부값은
[`docs/requests/main-vision-runtime-config-request-2026-06-19.md`](../docs/requests/main-vision-runtime-config-request-2026-06-19.md)를 보세요.
MAC/IP 값은 외부 공개 또는 DHCP/router 변경 후 사용 전에 반드시 재확인하세요.

## 가장 쉬운 실행: `sf_lab.sh`

운영자는 환경변수/profile 이름을 몰라도 아래 wrapper만 쓰면 됩니다.
장시간 live 프로세스는 안전상 tmux `Smartfactory:3:Development` 안에서만 켜세요.

```bash
# 통합 실행: GoPro global camera + TurtleBot Pi camera WebRTC, AI Server API, MJPEG fallback
./scripts/vision/sf_lab.sh all
# 또는 make vision-lab-all

# 상태/URL 확인
./scripts/vision/sf_lab.sh status
./scripts/vision/sf_lab.sh urls

# 종료
./scripts/vision/sf_lab.sh down
```

분리해서 확인하고 싶을 때도 같은 wrapper를 씁니다.

```bash
# WebRTC/direct-media 후보 읽기 전용 진단
./scripts/vision/sf_lab.sh probe

# Main/connector가 받을 JSON API 표면 확인
./scripts/vision/sf_lab.sh api health
./scripts/vision/sf_lab.sh api streams
./scripts/vision/sf_lab.sh api worker-status global_cam_01
./scripts/vision/sf_lab.sh api evidence-plan PICKUP
./scripts/vision/sf_lab.sh api evidence-mock DROPOFF
./scripts/vision/sf_lab.sh api evaluate-no-frame global_cam_01 lift_roi PICKUP
./scripts/vision/sf_lab.sh api evaluate-quality global_cam_01 full
```

역할 구분은 다음처럼 보면 됩니다.

| 원하는 것 | 명령 | 비고 |
|---|---|---|
| 전부 한 번에 켜기 | `./scripts/vision/sf_lab.sh all` | WebRTC + AI Server API + MJPEG fallback + mDNS |
| 스트리밍만 operator 관점에서 켜기 | `./scripts/vision/sf_lab.sh stream` | 현재는 `all`과 같은 안전 bundle |
| Main이 받을 stream/API URL 보기 | `./scripts/vision/sf_lab.sh urls` | 전달/브라우저 확인용 |
| 증거 판단 JSON 계약 보기 | `./scripts/vision/sf_lab.sh api evidence-plan` | 하드웨어 없이 plan JSON |
| 증거 판단 mock JSON 보기 | `./scripts/vision/sf_lab.sh api evidence-mock` | Main DB 변경 없음 |
| 실제 실행 중 AI Server에 평가 요청 | `./scripts/vision/sf_lab.sh api evaluate-no-frame` / `evaluate-quality` | 응답은 `/api/v1/evidence/evaluate` 계약 |

`sf_lab.sh`는 내부적으로 기본 profile `lab-gopro-tb3-webrtc`와 기존
`sf_vision.sh` bundle을 사용합니다. 따라서 복잡한 환경변수는 기본값으로 숨기되,
디버깅이 필요하면 아래의 `sf_vision.sh`/sidecar 스크립트를 직접 사용할 수 있습니다.

## 기존 profile 직접 실행: `sf_vision.sh`

`sf_lab.sh`보다 낮은 수준의 profile 기반 operator script입니다.
디버깅이나 profile 전환이 필요할 때 사용하세요.

```bash
./scripts/vision/sf_vision.sh profiles
./scripts/vision/sf_vision.sh up lab-gopro-tb3
./scripts/vision/sf_vision.sh status
./scripts/vision/sf_vision.sh smoke
```

종료:

```bash
./scripts/vision/sf_vision.sh down
```

로그 확인:

```bash
./scripts/vision/sf_vision.sh logs
./scripts/vision/sf_vision.sh logs vision-bundle
./scripts/vision/sf_vision.sh logs gopro-adapter
```

Makefile alias도 있습니다. `sf_lab.sh`에 대응하는 쉬운 alias는 다음입니다.

```bash
make vision-lab-all
make vision-lab-status
make vision-lab-urls
make vision-lab-api-plan OPERATION=PICKUP
make vision-lab-down
```

하위 `sf_vision.sh` profile을 직접 쓸 때는 기존 alias를 사용하세요.

```bash
make vision-profiles
make vision-up PROFILE=lab-gopro-tb3
make vision-status
make vision-smoke-local
make vision-down
```

### WebRTC sidecar profile 직접 실행

기본 안정 경로는 여전히 `lab-gopro-tb3`입니다. Main/browser가 WebRTC를 우선
받아보고 MJPEG fallback도 유지해야 하면 `lab-gopro-tb3-webrtc`를 사용합니다.

```bash
./scripts/vision/sf_vision.sh check lab-gopro-tb3-webrtc
# live 실행은 tmux Smartfactory:3:Development 안에서만 허용됩니다.
./scripts/vision/sf_vision.sh up lab-gopro-tb3-webrtc
./scripts/vision/sf_vision.sh status
./scripts/vision/sf_vision.sh smoke
```

WebRTC sidecar는 `mediamtx`와 `ffmpeg`가 필요합니다. 이 PC에서 `mediamtx`가
없으면 `check`가 실패하면서 설치/경로 지정 방법을 출력합니다. 설치 후에는
`mediamtx`를 PATH에 두거나 다음처럼 지정하세요.

```bash
export MEDIAMTX_BIN=/absolute/path/to/mediamtx
```

Sidecar 단독 확인:

```bash
./scripts/vision/run_webrtc_sidecar_mediamtx.sh --check
./scripts/vision/run_webrtc_sidecar_mediamtx.sh --print-config
./scripts/vision/run_webrtc_sidecar_mediamtx.sh --status
```

### WebRTC/direct-media 상태를 안전하게 판별하는 probe

`lab-gopro-tb3-webrtc`를 켠 뒤 “지금 WebRTC가 실제로 쓸 만한 direct media
경로인지, 아니면 MJPEG를 다시 H264로 바꾼 호환 경로인지”를 확인하려면 다음
probe를 실행하세요.

```bash
python3 scripts/vision/probe_direct_media_candidates.py
```

JSON으로 남기려면:

```bash
python3 scripts/vision/probe_direct_media_candidates.py \
  --json \
  --output /tmp/sf_direct_media_probe.json
```

이 probe는 **안전한 읽기 전용 진단**입니다.

- ROS2 bringup을 시작하지 않음
- robot motion / Nav2 / `/cmd_vel`을 건드리지 않음
- MediaMTX/ffmpeg/GoPro stream 같은 live process를 새로 띄우지 않음
- map 세팅이 없어도 실행 가능
- Main `:8090` MJPEG fallback과 ROS no-control 계약을 확인 대상으로만 봄

판정 순서는 다음입니다.

| 후보 | 의미 | 기대 상태 |
|---|---|---|
| `direct_clean_media_webrtc` | GoPro/PiCam 원본 media가 직접 WebRTC로 가는 최선 경로 | 최종 목표 |
| `camera_input_h264_transcode_webrtc` | `/dev/videoN` 또는 camera input을 바로 H264/WebRTC로 변환 | 차선 목표 |
| `mjpeg_overlay_h264_transcode_webrtc` | 현재 호환 baseline: MJPEG/overlay를 다시 H264/WebRTC로 변환 | 지금 실험 가능, 지연은 MJPEG와 비슷할 수 있음 |
| `http_mjpeg_gateway` | 기존 Main 호환 `:8090` MJPEG fallback | 항상 유지해야 함 |

현재처럼 GoPro가 `/dev/video*`로 보이지 않고 direct RTSP/UDP/TCP URL도 없으면
`direct_clean_media_webrtc`와 `camera_input_h264_transcode_webrtc`는 `blocked`로
나오는 것이 정상입니다. 이때 `tb3_1_picam_full` 같은 MediaMTX path가 online이면
`mjpeg_overlay_h264_transcode_webrtc`는 `available`로 나옵니다.

direct media 후보를 따로 검증해야 할 때는 HTTP/HTTPS URL이 아니라 redirect 안전
문제 때문에 다음처럼 RTSP/UDP/TCP 또는 local device 경로를 쓰세요.

```bash
DIRECT_CLEAN_MEDIA_URL='rtsp://127.0.0.1:18554/global_cam_01_full' \
python3 scripts/vision/probe_direct_media_candidates.py

CAMERA_INPUT_URL='/dev/video0' \
python3 scripts/vision/probe_direct_media_candidates.py
```

요약하면, operator 입장에서는 다음 순서로 보면 됩니다.

```bash
# 1) live 실행은 tmux Smartfactory:3:Development 안에서만
./scripts/vision/sf_vision.sh up lab-gopro-tb3-webrtc

# 2) 다른 터미널에서 읽기 전용 상태 확인 가능
./scripts/vision/sf_vision.sh status
python3 scripts/vision/probe_direct_media_candidates.py
```

GoPro/global camera는 **미디어 스트리밍 FPS**와 **AI 추론 FPS**를 분리합니다.
`lab-gopro-tb3-webrtc`의 기본 의도는 브라우저/WebRTC는 30 FPS target,
낙하물/overlay AI는 `GOPRO_AI_MONITOR_FPS=5`, 전이 시점 증거는
`GOPRO_EVIDENCE_IMGSZ=960`입니다. 4cm급 작은 낙하물이 픽셀 예산 부족이면
연속 AI 부하를 바로 올리지 말고 `LOW_PIXEL_BUDGET`/`LOW_QUALITY_EVIDENCE`
판정과 sparse alert-window metadata로 리뷰 대상으로 남깁니다.

기본 WebRTC URL은 다음입니다.

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

운영자가 확인할 때는 browser URL을 직접 열거나 `--status`/`smoke`로 path readiness를
확인하면 됩니다. Main 팀에 전달할 WebRTC/MJPEG 연동 요구사항은 README가 아니라
별도 전달본 [`../docs/requests/main-webrtc-vision-integration-handoff-2026-06-25.ko.md`](../docs/requests/main-webrtc-vision-integration-handoff-2026-06-25.ko.md)를 사용하세요.
sidecar 상세 문서는 [`../docs/setup/webrtc-mediamtx-sidecar.md`](../docs/setup/webrtc-mediamtx-sidecar.md)를 보세요.

### 주요 profile

| profile | 용도 | 하드웨어 |
|---|---|---|
| `local-smoke` | AI Server/gateway/API/WebRTC fallback smoke | 없음 |
| `tb3-live` | TurtleBot 1대 Pi camera overlay | 로봇 카메라 |
| `gopro-segment` | GoPro `global_cam_01` segment overlay proof | GoPro |
| `lab-gopro-tb3` | GoPro + TurtleBot 1대 통합 데모, MJPEG 안정 경로 | GoPro + 로봇 카메라 |
| `lab-gopro-tb3-webrtc` | 위 구성 + MediaMTX WebRTC sidecar | GoPro + 로봇 카메라 + `mediamtx` |

`lab-gopro-tb3`는 내부적으로 다음을 한 번에 띄웁니다.

- `smartfactory-vision.local` mDNS 임시 방송
- AI Server `:8100`
- public MJPEG stream gateway `:8090`
- `tb3_1_picam` ROS2 camera sidecar
- GoPro OpenGoPro stream
- GoPro smart ROI adapter
- WebRTC discovery/offer fallback endpoint

`lab-gopro-tb3-webrtc`는 여기에 MediaMTX sidecar를 추가합니다. 현재 사용 가능한
하드웨어가 GoPro + `tb3_1_picam` 한 대뿐이면 `global_cam_01/*`와
`tb3_1_picam/full`은 WebRTC online이 되고, `tb3_2_picam/full`은 같은 설정으로
대기하다가 두 번째 로봇 카메라가 같은 domain/topic으로 올라오면 online이 됩니다.

WebRTC는 현재 additive/candidate입니다. 실제 media sidecar가 설정되지 않았으면
offer는 의도적으로 MJPEG fallback을 선택합니다. Main은 WebRTC 우선 시도 후
MJPEG fallback을 유지해야 합니다.

로봇 쪽 camera bringup은 안전상 operator bundle이 자동으로 SSH 실행하지 않습니다.
TurtleBot 쪽에서는 별도로 다음을 실행하세요.

```bash
ROS_DOMAIN_ID=2 ros2 launch turtlebot3_bringup camera_low_bandwidth.launch.py
```

## 하위 스크립트 직접 실행 순서 (디버깅용)

### 1. 임시 hostname 방송

현재 lab live 프로세스는 tmux `Smartfactory:3:Development`에서만 시작되도록 guard됩니다. 다른 장비에서 다른 tmux 이름을 쓰면 `SF_VISION_TMUX_REQUIRED_CONTEXT`를 맞춘 뒤 실행하세요.

```bash
./scripts/vision/publish_vision_mdns_alias.py
```

동작 확인만 하고 싶으면:

```bash
./scripts/vision/publish_vision_mdns_alias.py --print-only
```

### 2. Main-compatible Vision bundle 실행

```bash
VISION_MODEL_WORKER_ENABLED=false ./scripts/vision/run_d1_vision_multi_source_gateway_bundle.sh
```

이 bundle은 다음을 띄웁니다.

```text
0.0.0.0:8100   AI Server
0.0.0.0:8090   public HTTP/MJPEG Vision Stream Gateway
127.0.0.1:18090 internal tb3_1 overlay bridge
127.0.0.1:18091 internal tb3_2 overlay bridge
```

기본 Main callback 설정은 다음입니다.

```env
MAIN_SERVER_URL=http://smartfactory-main.local:8088
WMS_VISION_EVENTS_PATH=/api/v1/vision/events
WMS_EMIT_ENABLED=false
```

`WMS_EMIT_ENABLED=false`는 안전 기본값입니다. 실제로 VisionEvent를 Main에 POST하려는 경우에만 명시적으로 `true`로 바꾸세요.

TurtleBot Pi camera comparator 검증처럼 실제 카메라/AI overlay까지 볼 때는
같은 bundle을 쓰되 가벼운 detect 모델 처리를 켭니다.

```bash
VISION_MODEL_WORKER_ENABLED=true \
VISION_MODEL_PATH=/home/codelab/yolo_test/yolov8n.pt \
VISION_MODEL_TASK=detect \
VISION_MODEL_IMGSZ=320 \
VISION_GATEWAY_PUBLISH_EVIDENCE=false \
WMS_EMIT_ENABLED=false \
./scripts/vision/run_d1_vision_multi_source_gateway_bundle.sh
```

GoPro + PiCam 통합 실험은 source별 모델 분기를 쓰는 profile을 사용하세요.
현재 기본 의도는 `global_cam_01=비튜닝 yolov8s-seg segment`,
`tb3_*_picam=비튜닝 yolov8n detect`입니다. GoPro 전역 스트리밍은 리프트로
들어올린 파레트/ROI를 segment overlay로 잡고, crop 이후 부품 인식 결과를
증거 생성/전달에 쓰는 구조입니다. 단, 현재 GoPro segment는 파이프라인 증명용이며,
실제 파레트/부품 안정 인식은 이후 튜닝 모델로 교체해야 합니다.

```bash
./scripts/vision/sf_vision.sh up lab-gopro-tb3-webrtc
```

이 multi-source bundle은 Main 호환성을 위해 여전히 MJPEG 우선입니다. 동시에 AI Server discovery에서 WebRTC 후보 descriptor를 제공합니다.

```bash
curl 'http://smartfactory-vision.local:8100/api/v1/vision/streams?source=global_cam_01'
curl 'http://smartfactory-vision.local:8100/api/v1/vision/streams?source=tb3_1_picam'
curl 'http://smartfactory-vision.local:8100/api/v1/vision/webrtc/demo?source=global_cam_01&view=full'
```

Main 쪽 WebRTC 적용 요청서는 다음 문서를 전달하세요.
[`docs/requests/main-webrtc-vision-integration-request-2026-06-25.md`](../docs/requests/main-webrtc-vision-integration-request-2026-06-25.md)

## 로봇 카메라 bringup / namespace 기준

각 TurtleBot/Raspberry Pi에서는 저대역폭 카메라 launch를 실행합니다.

```bash
ros2 launch turtlebot3_bringup camera_low_bandwidth.launch.py
```

각 로봇이 서로 다른 ROS domain으로 분리되어 있으면 namespace 지정은 **필수 아님**입니다.
현재 권장 lab 구성은 다음입니다.

```text
tb3_1_picam: ROS_DOMAIN_ID=2, topic=/camera/image_raw/compressed, internal port 18090
tb3_2_picam: ROS_DOMAIN_ID=5, topic=/camera/image_raw/compressed, internal port 18091
```

즉 로봇 안에서는 unnamespaced `/camera/image_raw/compressed`를 publish해도 되고,
Vision sidecar가 domain/source mapping으로 `tb3_1_picam`, `tb3_2_picam` source id를 붙입니다.

반대로 여러 로봇을 의도적으로 같은 ROS domain에 넣는다면 topic 충돌을 피하려고 namespace/remap이 필요합니다. 그 경우 bundle 실행 시 topic을 명시하세요.

```bash
VISION_SOURCE_1_TOPIC=/tb3_1/camera/image_raw/compressed \
VISION_SOURCE_2_TOPIC=/tb3_2/camera/image_raw/compressed \
./scripts/vision/run_d1_vision_multi_source_gateway_bundle.sh
```

## GoPro global camera 기준

GoPro는 generic webcam source가 아니라 `global_cam_01` global camera입니다.
multi-source bundle은 `global_cam_01`을 AI Server upstream으로 노출하지만, GoPro USB/OpenGoPro capture 프로세스를 자동으로 시작하지는 않습니다.
GoPro proof run에서는 AI Server/bundle을 유지한 채 별도 터미널에서 GoPro stream + adapter를 실행하세요.

```bash
services/ai-server/.venv/bin/python scripts/vision/start_gopro_webcam_stream.py \
  --protocol TS --resolution 1080 --fov WIDE --port 8554 --test-read

services/ai-server/.venv/bin/python scripts/vision/run_gopro_smart_roi_adapter.py \
  --input 'udp://0.0.0.0:8554?overrun_nonfatal=1&fifo_size=50000000' \
  --source global_cam_01 \
  --ai-server-url http://127.0.0.1:8100 \
  --bufferless
```

WebRTC는 아직 additive/candidate입니다. MediaMTX/GStreamer 같은 실제 media sidecar가 설정·검증되기 전까지 Main 호환 MJPEG는 필수 fallback으로 유지합니다.

### 3. 확인 URL

```bash
curl http://smartfactory-vision.local:8100/api/v1/health
curl http://smartfactory-vision.local:8090/api/v1/vision/bridge/status
curl http://smartfactory-main.local:8088/api/v1/vision/bridge/status
```

로봇/카메라가 없을 때는 서비스가 `200`이어도 source 상태가 `no_frame`, `offline`, `stale`일 수 있습니다. 이것은 정상입니다.

## 스크립트 그룹과 실제 배치

이제 루트 `scripts/`에는 문서만 남깁니다. 실행 가능한 스크립트는 용도별
하위 폴더에 직접 배치되어 있고, 현재 문서/Makefile/systemd 참조도 실제 경로를 직접 가리킵니다.

| 그룹 | 실행 위치 | 예시 |
|---|---|---|
| AI Server | `scripts/ai/` | `run_ai_server.sh`, `setup_ai_server_env.sh`, `setup_ai_server_model_env.sh`, `test_ai_server.sh` |
| D1 Vision / Main 연동 | `scripts/vision/` | `sf_vision.sh`, `publish_vision_mdns_alias.py`, `run_d1_vision_multi_source_gateway_bundle.sh`, `run_d1_vision_stream_gateway.py`, `smoke_main_dashboard_gateway.sh` |
| 계약/검증 | `scripts/validate/` | `validate_contracts.py`, `validate_deployment_assets.py` |
| 계약 산출물 생성 | `scripts/generate/` | `generate_source_registry_surfaces.py` |
| 보고서/Confluence 산출물 | `scripts/reports/` | `create_sprint3_presentation_pptx.py`, `generate-drawio-architectures.py`, `render-scenario-sequence-diagrams.py` |
| 운영 확인 | `scripts/ops/` | `check-confluence-env.sh` |
| 공용 shell helper | `scripts/lib/` | `vision_bundle_common.sh` |

배치 규칙:

- 새 문서와 자동화에는 용도별 실제 경로를 직접 사용합니다.
- 외부 배포 호환 전환이 필요한 경우가 아니면 루트 실행 shim을 만들지 않습니다.
- 구현 변경은 용도에 맞는 하위 폴더에서 합니다.

## 안전 경계

이 Vision script 세트는 다음을 하지 않아야 합니다.

- `/cmd_vel` publish
- Nav2 action 호출
- teleop 실행
- ROS parameter mutation
- robot-side persistent service 변경
- 전체 DDS/rosbridge graph 노출

Vision은 evidence/advisory만 제공하고, Main/WMS와 Movement/Safety가 최종 상태와 제어를 소유합니다.
