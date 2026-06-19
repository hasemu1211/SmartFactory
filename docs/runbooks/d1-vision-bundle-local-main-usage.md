# D1 Vision Multi-source Bundle 사용법

Date: 2026-06-16 KST  
Scope: 로컬 Vision PC에서 두 로봇 카메라의 AI overlay stream을 만들고, Main Server가 단일 HTTP gateway로 받아가는 방법

---

## 1. 전체 구조

```text
Robot1 camera, ROS_DOMAIN_ID=2
Robot2 camera, ROS_DOMAIN_ID=5
        ↓
Local Vision PC
  - AI Server :8100
  - vision_frame_gateway x 2
  - internal overlay bridge :18090 / :18091
  - public Vision Stream Gateway :8090
        ↓
Main Server proxy
        ↓
HTML dashboard
```

Main Server는 ROS2/DDS/domain bridge를 직접 사용하지 않습니다.  
Main이 알아야 하는 것은 **단일 HTTP base URL** 하나입니다.

```text
LMS_VISION_STREAM_BASE_URL=http://smartfactory-vision.local:8090
```

`smartfactory-vision.local`은 hostname-first 권장값입니다. Main Server PC에서 이 이름이 mDNS/DNS/운영자 관리 host alias로 resolve되어야 합니다. 이 repo의 실행 스크립트는 IP, router reservation, `/etc/hosts`를 자동 변경하지 않습니다. 이름 해석이 아직 준비되지 않은 경우에만 `make vision-config`가 출력하는 detected LAN IP를 명시적 fallback env로 설정합니다.

카메라는 port가 아니라 `source` query parameter로 구분합니다.

```text
tb3_1_picam
tb3_2_picam
```

---

## 2. 안전 범위

이 bundle은 read-only vision/evidence 용도입니다.

하지 않는 것:

- `/cmd_vel` publish 없음
- Nav2 action call 없음
- teleop 없음
- ROS parameter mutation 없음
- robot-side persistent service 설치/변경 없음
- whole-graph rosbridge 노출 없음

Main-facing public gateway는 ROS-free로 유지합니다. 현재 ROS/domain 처리는 sidecar process에서 수행하지만, 안전 gate와 ADR을 통과한 ROS-aware Vision/AI 내부 구현 가능성은 닫지 않습니다.

---

## 3. 로컬 Vision PC 사용법

### 3.1 사전 조건

각 로봇에서는 카메라 launch가 이미 켜져 있어야 합니다.

예상 source/domain:

| Robot | Source ID | ROS_DOMAIN_ID | Camera topic |
|---|---|---:|---|
| Robot1 | `tb3_1_picam` | `2` | `/camera/image_raw/compressed` |
| Robot2 | `tb3_2_picam` | `5` | `/camera/image_raw/compressed` |

로컬 Vision PC에서는 이 repo에서 실행합니다.

```bash
cd /home/codelab/Desktop/Project/SmartFactory
```

장기 실행은 현재 운용 규칙상 tmux `Smartfactory:3` 안에서 실행합니다.

---

### 3.2 dry check

실행 전 의존성/설정 확인:

```bash
./scripts/vision/run_d1_vision_multi_source_gateway_bundle.sh --check
```

성공 시 이런 항목이 출력됩니다.

```text
ai_server: 0.0.0.0:8100
public_gateway: 0.0.0.0:8090
source1: tb3_1_picam, domain=2, internal_port=18090
source2: tb3_2_picam, domain=5, internal_port=18091
pipeline: async=true, inline_process=true, frame_process_path=/api/v1/vision/frame/process
```

---

### 3.3 bundle 실행

```bash
./scripts/vision/run_d1_vision_multi_source_gateway_bundle.sh
```

이 명령 하나가 local child process들을 함께 띄웁니다.

| Process | Bind / domain | 역할 |
|---|---|---|
| AI Server | `0.0.0.0:8100` | frame 저장, AI detection, overlay 생성 |
| `vision_frame_gateway:tb3_1_picam` | ROS_DOMAIN_ID `2` | Robot1 camera → AI Server → ROS overlay publish |
| `vision_frame_gateway:tb3_2_picam` | ROS_DOMAIN_ID `5` | Robot2 camera → AI Server → ROS overlay publish |
| internal stream bridge | `127.0.0.1:18090` | Robot1 overlay MJPEG 내부 bridge |
| internal stream bridge | `127.0.0.1:18091` | Robot2 overlay MJPEG 내부 bridge |
| public stream gateway | `0.0.0.0:8090` | Main이 접근하는 단일 source-mux gateway |

중지:

```text
Ctrl-C
```

bundle supervisor가 child process들을 같이 종료합니다.

---

## 4. 로컬 확인 URL

로컬 또는 같은 네트워크 PC에서 확인:

### 4.1 상태 확인

```bash
curl http://smartfactory-vision.local:8090/api/v1/vision/bridge/status
```

정상 출력 예:

```json
{
  "ok": true,
  "service": "vision-stream-bridge",
  "read_only": true,
  "motion_command_allowed": false,
  "source_count": 2,
  "sources": [
    {
      "source_id": "tb3_1_picam",
      "status": "online",
      "fps": 30.0,
      "latest_sequence_id": 123,
      "stream_path": "/api/v1/vision/overlay/stream?source=tb3_1_picam",
      "raw_stream_path": "/api/v1/vision/frame/stream?source=tb3_1_picam"
    }
  ]
}
```

### 4.2 browser 확인

```text
http://smartfactory-vision.local:8090/api/v1/vision/overlay/view?source=tb3_1_picam
http://smartfactory-vision.local:8090/api/v1/vision/overlay/view?source=tb3_2_picam
```

### 4.3 stream 직접 확인

AI overlay MJPEG:

```text
http://smartfactory-vision.local:8090/api/v1/vision/overlay/stream?source=tb3_1_picam&max_fps=30
http://smartfactory-vision.local:8090/api/v1/vision/overlay/stream?source=tb3_2_picam&max_fps=30
```

Raw/latest frame MJPEG:

```text
http://smartfactory-vision.local:8090/api/v1/vision/frame/stream?source=tb3_1_picam&max_fps=30
http://smartfactory-vision.local:8090/api/v1/vision/frame/stream?source=tb3_2_picam&max_fps=30
```

### 4.4 AI Server 상태

```bash
curl http://smartfactory-vision.local:8100/api/v1/health
```

### 4.5 최신 semantic tags 확인

```text
http://smartfactory-vision.local:8100/api/v1/detections/latest?source=tb3_1_picam&limit=10
http://smartfactory-vision.local:8100/api/v1/detections/latest?source=tb3_2_picam&limit=10
```

---

## 5. 주요 환경변수

대부분 기본값으로 사용하면 됩니다.

| Env | Default | 설명 |
|---|---:|---|
| `AI_SERVER_HOST` | `0.0.0.0` | AI Server bind host |
| `AI_SERVER_PORT` | `8100` | AI Server port |
| `AI_SERVER_URL` | `http://127.0.0.1:8100` | sidecar가 내부 호출하는 AI Server URL |
| `VISION_PUBLIC_HOST` | `smartfactory-vision.local` | Main-facing hostname-first 권장값 |
| `VISION_STREAM_GATEWAY_HOST` | `0.0.0.0` | Main-facing gateway host |
| `VISION_STREAM_GATEWAY_PORT` | `8090` | Main-facing gateway port |
| `VISION_SOURCE_1_ID` | `tb3_1_picam` | Robot1 source id |
| `VISION_SOURCE_1_DOMAIN` | `2` | Robot1 ROS domain |
| `VISION_SOURCE_1_TOPIC` | `/camera/image_raw/compressed` | Robot1 camera topic |
| `VISION_SOURCE_2_ID` | `tb3_2_picam` | Robot2 source id |
| `VISION_SOURCE_2_DOMAIN` | `5` | Robot2 ROS domain |
| `VISION_SOURCE_2_TOPIC` | `/camera/image_raw/compressed` | Robot2 camera topic |
| `VISION_GATEWAY_PERIOD_SEC` | `0.033333` | gateway target processing cadence |
| `VISION_GATEWAY_ASYNC_PIPELINE` | `true` | latest-only async pipeline |
| `VISION_GATEWAY_PROCESS_FRAME_INLINE` | `true` | `/frame/process` hot path 사용 |
| `VISION_GATEWAY_FRAME_PROCESS_PATH` | `/api/v1/vision/frame/process` | AI Server hot path |
| `VISION_GATEWAY_IMAGE_QOS_RELIABILITY` | `reliable` | camera subscribe QoS |
| `VISION_GATEWAY_OVERLAY_PUB_QOS_RELIABILITY` | `reliable` | overlay publish QoS |
| `VISION_STREAM_OVERLAY_SUB_QOS_RELIABILITY` | `reliable` | bridge subscribe QoS |
| `VISION_MODEL_PATH` | `./yolov8n.pt` | 기본 pretrained YOLO model |
| `VISION_MODEL_IMGSZ` | `224` | high-FPS smoke image size |
| `VISION_MODEL_CONF` | `0.35` | model confidence threshold |

QoS 주의:

- camera publisher가 reliable이면 기본값 그대로 사용
- camera publisher가 best-effort이면 아래처럼 바꿔야 연결됩니다.

```bash
VISION_GATEWAY_IMAGE_QOS_RELIABILITY=sensor_data \
./scripts/vision/run_d1_vision_multi_source_gateway_bundle.sh
```

---

## 6. Main Server 사용법

### 6.1 환경변수

Main Server는 Vision PC gateway base URL만 알면 됩니다.

```bash
LMS_VISION_STREAM_BASE_URL=http://smartfactory-vision.local:8090
```

권장 Main 설정:

```bash
VISION_API_BASE_URL=http://smartfactory-vision.local:8100
VISION_STREAM_BASE_URL=http://smartfactory-vision.local:8090
LMS_VISION_STREAM_BASE_URL=http://smartfactory-vision.local:8090
```

명시적 fallback은 hostname resolution 또는 health check 실패 때만 사용합니다. Main이 임의 IP를 추측하면 안 됩니다.

```bash
VISION_API_FALLBACK_BASE_URL=http://<detected-vision-lan-ip>:8100
VISION_STREAM_FALLBACK_BASE_URL=http://<detected-vision-lan-ip>:8090
```

Main Server PC에는 ROS2, DDS, domain bridge 설정이 필요 없습니다.

---

### 6.2 DB source 등록

Main은 등록된 source만 proxy해야 합니다.

예시:

| camera_sources.source_id | 설명 |
|---|---|
| `tb3_1_picam` | Robot1 PiCam |
| `tb3_2_picam` | Robot2 PiCam |

source가 DB에 없으면 Main이 upstream 호출 전에 차단하는 것이 좋습니다.

---

### 6.3 Main proxy endpoints

HTML은 gateway IP를 직접 알지 않고 Main만 호출합니다.

HTML 요청:

```text
GET /api/v1/vision/overlay/stream?source=tb3_1_picam&max_fps=30
```

Main upstream 요청:

```text
GET ${LMS_VISION_STREAM_BASE_URL}/api/v1/vision/overlay/stream?source=tb3_1_picam&max_fps=30
```

응답은 그대로 streaming proxy합니다.

```text
Content-Type: multipart/x-mixed-replace; boundary=...
```

권장 Main proxy 목록:

```text
GET /api/v1/vision/overlay/stream?source={source_id}&max_fps=30
GET /api/v1/vision/frame/stream?source={source_id}&max_fps=30
GET /api/v1/vision/bridge/status
```

---

### 6.4 Main dashboard 권장 동작

권장:

1. 기본 UI는 선택된 camera 1개를 크게 표시
2. camera selector로 `tb3_1_picam`, `tb3_2_picam` 전환
3. 필요할 때만 2개 stream 동시 표시
4. `max_fps`는 30까지 허용하되, UI 옵션으로 10/15/30 선택 가능하게 두기

이유:

- 여러 MJPEG stream을 동시에 열면 Wi-Fi, frame size, browser decode 부하로 per-stream FPS가 떨어질 수 있습니다.
- 영상은 DB에 저장하지 않습니다.

---

## 7. Semantic evidence/tag 사용법

영상 stream과 semantic evidence는 분리해서 다룹니다.

### 7.1 polling fallback

Main이 아직 push ingest를 구현하지 않았다면 controlled polling 가능:

```text
GET http://smartfactory-vision.local:8100/api/v1/detections/latest?source=tb3_1_picam&limit=10
```

설명: 최신 `VisionEvent v1` 후보를 조회합니다.

출력 예:

```json
{
  "generated_at": "2026-06-16T15:52:13+09:00",
  "events": [
    {
      "schema_version": "vision-event.v1",
      "source": "tb3_1_picam",
      "event_kind": "CANDIDATE",
      "class_name": "person",
      "robot_id": "tb3_1"
    }
  ]
}
```

권장 polling cadence:

```text
1~2초 단위 / source별 / 필요 화면에서만
```

### 7.2 target canonical push

최종 권장 Main API:

```text
POST /api/v1/vision/events
```

요청: full `VisionEvent v1` JSON 1건

Main 응답 예:

```json
{
  "accepted": true,
  "duplicate": false,
  "event_id": "11111111-1111-4111-8111-111111111111",
  "wms_processing_status": "queued"
}
```

Main 저장 권장:

- `event_id` 기준 dedup
- event metadata 저장
- image bytes는 저장하지 않음
- 필요한 순간의 overlay snapshot URL 또는 object-storage key만 저장

---

## 8. 내부 hot path 설명

로컬 bundle 내부에서는 아래 API를 씁니다.

```text
POST http://127.0.0.1:8100/api/v1/vision/frame/process
```

설명: frame 저장 + AI detection + overlay cache 갱신을 한 번에 수행합니다.

Main이 직접 호출하지 않아도 됩니다.

요청:

```text
multipart/form-data
source=tb3_1_picam
image=@frame.jpg
force=true
stale=false
```

출력 핵심:

```json
{
  "source": "tb3_1_picam",
  "processed": true,
  "status": "processed",
  "frame_seq": 42,
  "event_count": 2,
  "frame": {...},
  "overlay": {...},
  "ingest_context": {
    "processed_inline": true
  }
}
```

---

## 9. FPS / 성능 메모

현재 구조는 고정된 모든 frame을 queue에 쌓지 않고 latest-only로 처리합니다.

장점:

- latency가 누적되지 않음
- memory가 안정적
- 오래된 frame 처리로 밀리지 않음

주의:

- browser-visible 30fps는 Wi-Fi 품질, JPEG frame size, 동시 viewer 수에 따라 흔들릴 수 있음
- strict 30fps가 필요하면 먼저 camera resolution/JPEG quality를 낮추는 것이 좋음
- 그래도 부족하면 MJPEG보다 WebRTC/H.264 같은 video-native transport를 별도 계획하는 것이 좋음

---

## 10. 장애 확인 순서

### 10.1 public gateway 상태

```bash
curl http://smartfactory-vision.local:8090/api/v1/vision/bridge/status
```

이름 해석부터 확인하려면:

```bash
getent hosts smartfactory-vision.local
```

source `status`가 `online`인지 확인합니다.

### 10.2 AI Server 상태

```bash
curl http://smartfactory-vision.local:8100/api/v1/health
```

`model_status=loaded`, `source_summary.online` 값을 확인합니다.

### 10.3 port listener 확인

```bash
ss -ltnp '( sport = :8090 or sport = :8100 or sport = :18090 or sport = :18091 )'
```

### 10.4 process 확인

```bash
pgrep -af 'run_d1_vision_multi_source_gateway_bundle|vision_frame_gateway|vision_overlay_stream_bridge|uvicorn|run_d1_vision_stream_gateway'
```

### 10.5 흔한 원인

| 증상 | 가능 원인 | 조치 |
|---|---|---|
| source가 stale | robot camera launch 중단, Wi-Fi 끊김 | robot camera 재확인 |
| frame이 안 들어옴 | QoS mismatch | `VISION_GATEWAY_IMAGE_QOS_RELIABILITY=sensor_data` 시도 |
| AI box가 안 보임 | model env/path 문제 | `AI_SERVER_EXTRA_PYTHONPATH`, `VISION_MODEL_PATH` 확인 |
| FPS 낮음 | Wi-Fi/frame size/동시 stream | viewer 수 줄이기, 해상도/JPEG quality 낮추기 |
| Main에서 400 | source 미등록 | Main DB `camera_sources.source_id` 확인 |

---

## 11. Main에 전달할 최소 스펙

```text
Base URL:
  http://smartfactory-vision.local:8090

Overlay MJPEG:
  GET /api/v1/vision/overlay/stream?source={source_id}&max_fps={1..30}

Raw MJPEG:
  GET /api/v1/vision/frame/stream?source={source_id}&max_fps={1..30}

Status:
  GET /api/v1/vision/bridge/status

Type:
  multipart/x-mixed-replace MJPEG

Source IDs:
  tb3_1_picam
  tb3_2_picam

Main DB:
  source_id must match camera_sources.source_id

Network:
  Vision PC binds 0.0.0.0:8090 and Main Server must be able to reach it.
```
