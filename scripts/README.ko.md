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

## 권장 실행: operator bundle

사용자 부담을 줄이기 위해 장시간 실행 프로세스는 이제 profile 기반
operator script로 묶습니다. 일반 데모에서는 아래 4개 명령만 기억하면 됩니다.

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

Makefile alias도 같습니다.

```bash
make vision-profiles
make vision-up PROFILE=lab-gopro-tb3
make vision-status
make vision-smoke-local
make vision-down
```

### WebRTC sidecar까지 켜는 가장 쉬운 경로

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
같은 bundle을 쓰되 가벼운 smoke profile로 모델 처리를 켭니다.

```bash
VISION_MODEL_WORKER_ENABLED=true \
VISION_MODEL_PATH="$PWD/yolov8n.pt" \
VISION_MODEL_TASK=detect \
VISION_MODEL_IMGSZ=224 \
VISION_GATEWAY_PUBLISH_EVIDENCE=false \
WMS_EMIT_ENABLED=false \
./scripts/vision/run_d1_vision_multi_source_gateway_bundle.sh
```

GoPro segment-overlay proof는 위의 가벼운 기본값에 의존하지 말고, 명시적으로
segment proof profile을 사용하세요.

```bash
VISION_MODEL_WORKER_ENABLED=true \
VISION_MODEL_PATH=/home/codelab/yolo_test/runs/segment/bottle_detection_yolov8s_seg/weights/best.pt \
VISION_MODEL_TASK=segment \
VISION_MODEL_IMGSZ=640 \
VISION_GATEWAY_PUBLISH_EVIDENCE=false \
WMS_EMIT_ENABLED=false \
./scripts/vision/run_d1_vision_multi_source_gateway_bundle.sh
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
