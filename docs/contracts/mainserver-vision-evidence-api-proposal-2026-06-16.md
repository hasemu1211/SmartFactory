# Mainserver 연동용 Vision Evidence API 제안서

- 작성일: 2026-06-16 Asia/Seoul
- 범위: Robot camera → `vision_frame_gateway` → AI Server → **이미 구현 중인 Mainserver API와 연결**
- 상태: 제안 문서. Mainserver 내부 구현 요구서가 아니라, AI Server/Lane C 쪽에서 Main API에 맞춰 연결하기 위한 계약 정리다.
- 안전 경계: evidence/image 조회만 다룬다. Mainserver/WMS가 task, inventory, DB-persisted truth의 최종 소유자이며 AI Server/Lane C는 이를 직접 생성·완료·실패·수정하지 않는다. `/cmd_vel`, Nav2 action, teleop, ROS parameter mutation, 로봇 파일/네트워크/캘리브레이션 변경은 범위 밖이다.

## 1. 구성 요소 간단 설명

| 요소 | 설명 |
|---|---|
| Robot camera | TurtleBot3 Pi camera가 ROS2 topic으로 내보내는 실제 영상 입력이다. Robot1 예시는 `/camera/image_raw/compressed` (`sensor_msgs/msg/CompressedImage`)이다. |
| `vision_frame_gateway` | ROS2 sidecar 노드다. 카메라 topic을 구독해 AI Server의 frame ingest API로 전달한다. 선택적으로 worker tick 호출, overlay/evidence ROS publish를 한다. 로봇 제어자는 아니다. |
| AI Server live frame 저장 | source별 최신 frame 1개를 메모리에 저장한다. 히스토리 저장소가 아니라 latest cache다. |
| `POST /api/v1/vision/worker/tick` | 최신 frame을 1회 처리해 overlay/evidence를 갱신하는 debug/control API다. 로봇 motion은 발생시키지 않는다. |
| raw frame image 조회 | `GET /api/v1/vision/frame/latest/image?source=tb3_1_picam`로 AI Server의 최신 원본 frame image를 binary로 조회한다. |
| overlay image 조회 | `GET /api/v1/vision/overlay/latest/image?source=tb3_1_picam`로 AI Server의 최신 overlay image를 binary로 조회한다. |
| ROS overlay topic | `/sf/vision/sources/tb3_1_picam/overlay/compressed`: overlay JPEG를 ROS `sensor_msgs/msg/CompressedImage`로 publish하는 안전 topic이다. |
| ROS evidence topic | `/sf/vision/events`: evidence metadata JSON을 ROS `std_msgs/msg/String`으로 publish하는 안전 topic이다. 이미지 bytes는 포함하지 않는다. |

## 2. Mainserver 담당자와 맞출 연결 포인트

Mainserver는 이미 다른 작업자가 구현 중이므로, 여기서는 “Main 내부를 어떻게 만들라”가 아니라 **AI Server가 어떤 API 모양에 연결 가능한지**만 정의한다.

| 연결 포인트 | AI Server/Lane C 현재 상태 | Main 담당자와 합의할 것 |
|---|---|---|
| VisionEvent metadata ingest | AI Server에 outbound client가 있음 | Main의 `POST /api/v1/vision/events` 경로, 성공 status code `200` 또는 `202` |
| raw/latest frame image | AI Server에서 조회 가능 | Main/GUI가 필요 시 AI Server URL을 pull할지 여부 |
| overlay/latest image | AI Server에서 조회 가능 | Main/GUI가 evidence 상세 화면에서 overlay를 pull할지 여부 |
| live camera frame ingest | Lane C sidecar가 AI Server로 전달 가능 | Main이 frame bytes를 직접 받을 필요가 있는지 여부. 기본 제안은 직접 받지 않음 |
| ROS safe topics | sidecar publish 가능 | Main이 ROS2를 직접 구독할지, HTTP POST만 받을지 결정. 기본 제안은 HTTP POST |

## 3. 권장 연결 방식

### 추천: HTTP metadata push + image pull

1. AI Server가 `VisionEvent v1` metadata를 Main의 `POST /api/v1/vision/events`로 POST한다.
2. Main/GUI가 이미지가 필요할 때만 AI Server의 raw/overlay image endpoint를 pull한다.
3. Main은 모든 frame을 저장하지 않고, 필요한 evidence snapshot만 선택적으로 저장한다.

이 방식의 장점:

- Mainserver가 ROS2를 직접 알 필요가 없다.
- image bytes와 semantic metadata가 분리된다.
- 네트워크/DB 부하가 작다.
- AI Server/Lane C가 robot motion authority를 갖지 않는다.


## 3.5. Camera bringup 책임 경계

**API가 로봇 카메라 launch를 대신 실행하지 않는다.**

- Robot camera bringup은 로봇/운영 쪽 ROS launch 책임이다.
- `vision_frame_gateway`는 이미 publish 중인 camera topic을 구독하는 sidecar다.
- AI Server API는 gateway가 POST한 frame을 저장/처리/조회한다.
- camera topic이 없으면 gateway는 받을 frame이 없고, AI Server latest frame/overlay API는 `404` 또는 worker `no_frame` 상태가 된다.
- 다른 컴퓨터가 robot bringup/camera launch를 계속 유지 중이면, 이 로컬 PC에서 같은 camera launch를 중복 실행할 필요가 없다.

로컬 PC에서 필요한 것은 보통 아래 3가지다.

1. AI Server 실행: `http://127.0.0.1:8100` 등.
2. ROS2에서 camera topic이 보이는지 확인: 직접 robot domain을 보거나 domain bridge/remap topic을 사용.
3. `vision_frame_gateway` 실행: visible camera topic을 구독해서 AI Server로 frame을 POST.

예시 흐름:

```bash
# 1) AI Server 확인
curl http://127.0.0.1:8100/api/v1/health

# 2) 카메라 topic 확인: direct Robot1 domain이면 /camera/... 일 수 있음
ros2 topic hz /camera/image_raw/compressed

# 3) direct topic을 쓰는 Lane C gateway 예시
ros2 launch smartfactory_perception_ros vision_frame_gateway.launch.py \
  use_vision_frame_gateway:=true \
  use_tb3_1_picam:=true \
  tb3_1_picam_image_topic:=/camera/image_raw/compressed \
  ai_server_url:=http://127.0.0.1:8100 \
  process_with_worker_tick:=true \
  publish_overlay:=true \
  publish_evidence:=true
```

만약 domain bridge가 `/tb3_1/camera/image_raw/compressed`로 remap해주고 있다면 `tb3_1_picam_image_topic` override 없이 기본값을 써도 된다.


## 3.6. 현재 로컬 PC runtime 상태 스냅샷

> 스냅샷 시각: 2026-06-16 11:07 KST. 이 상태는 임시 runtime 상태이며, 프로세스가 재시작/종료되면 다시 확인해야 한다.

현재 로컬 PC와 Robot1은 Main 담당자가 연동 smoke를 보기 좋은 상태로 올라와 있다.

| 항목 | 현재 상태 | Main 담당자에게 의미 있는 점 |
|---|---|---|
| Robot1 camera launch | `Smartfactory:3.2` SSH pane에서 실행 중 | Robot1 Pi camera가 ROS2 topic을 publish 중이다. |
| ROS domain | `ROS_DOMAIN_ID=2` | local gateway가 Robot1 camera topic을 직접 본다. |
| Camera topic | `/camera/image_raw/compressed` | local에서 topic이 보이며 gateway input으로 사용 중이다. |
| AI Server | `Smartfactory:3.3` local pane에서 실행 중 | API base: `http://127.0.0.1:8100`, LAN base: `http://192.168.10.63:8100` |
| AI Server bind | `0.0.0.0:8100` | 같은 로컬 PC는 `127.0.0.1:8100`, 같은 LAN의 Main/GUI는 `192.168.10.63:8100`으로 접근 가능하다. 신뢰 네트워크 안에서만 사용한다. |
| Gateway | `Smartfactory:3.5` local pane에서 실행 중 | source `tb3_1_picam`으로 camera frame을 AI Server에 POST 중이다. |
| Gateway input | `/camera/image_raw/compressed` | domain bridge/remap 없이 direct Robot1 topic override를 사용 중이다. |
| Gateway output | `/sf/vision/sources/tb3_1_picam/overlay/compressed`, `/sf/vision/events` | safe ROS topic만 publish한다. motion/control topic 없음. |
| Main outbound | 현재 자동 Main POST는 켜지지 않은 상태 | `worker/tick`은 AI Server cache/overlay/evidence를 갱신한다. Main HTTP push는 `MAIN_SERVER_URL`, `WMS_EMIT_ENABLED=true` 설정 또는 별도 auto-emitter slice가 필요하다. Main/GUI가 이미지 pull만 한다면 `http://192.168.10.63:8100`을 쓰면 된다. |

현재 확인된 API 상태:

```json
{
  "health": {
    "status": "ok",
    "main_server_url": "http://127.0.0.1:8000",
    "ai_server_bind": "0.0.0.0:8100",
    "ai_server_lan_base": "http://192.168.10.63:8100",
    "source_summary": {
      "configured": 3,
      "online": 1,
      "stale": 0,
      "disabled": 0,
      "offline": 2
    }
  },
  "tb3_1_picam_latest_frame": {
    "frame_seq": 677,
    "width": 640,
    "height": 480,
    "content_type": "image/jpeg",
    "size_bytes": 84710
  },
  "tb3_1_picam_overlay_sync": {
    "latest_frame_seq": 678,
    "latest_overlay_frame_seq": 678,
    "overlay_lag_frames": 0,
    "overlay_visual_state": "fresh",
    "overlay_event_count": 0
  }
}
```

현재 Main/GUI가 같은 로컬 PC에서 바로 확인 가능한 URL:

```text
GET http://127.0.0.1:8100/api/v1/health
GET http://127.0.0.1:8100/api/v1/vision/frame/latest?source=tb3_1_picam
GET http://127.0.0.1:8100/api/v1/vision/frame/latest/image?source=tb3_1_picam
GET http://127.0.0.1:8100/api/v1/vision/overlay/latest?source=tb3_1_picam
GET http://127.0.0.1:8100/api/v1/vision/overlay/latest/image?source=tb3_1_picam

# 같은 LAN의 Main/GUI는 현재 아래 base를 사용한다.
GET http://192.168.10.63:8100/api/v1/health
GET http://192.168.10.63:8100/api/v1/vision/overlay/latest/image?source=tb3_1_picam
```

현재 실행 중인 명령 요약:

```bash
# Robot1 SSH pane: Smartfactory:3.2
export ROS_DOMAIN_ID=2
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
export QT_QPA_PLATFORM=offscreen
source /opt/ros/jazzy/setup.bash
ros2 launch turtlebot3_bringup camera.launch.py

# Local AI Server pane: Smartfactory:3.3
AI_SERVER_HOST=0.0.0.0 AI_SERVER_PORT=8100 ./scripts/run_ai_server.sh

# Local gateway pane: Smartfactory:3.5
export ROS_DOMAIN_ID=2
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
source /opt/ros/jazzy/setup.bash
source /home/codelab/turtlebot3_ws/install/setup.bash
ros2 launch smartfactory_perception_ros vision_frame_gateway.launch.py \
  use_vision_frame_gateway:=true \
  use_tb3_1_picam:=true \
  tb3_1_picam_image_topic:=/camera/image_raw/compressed \
  ai_server_url:=http://127.0.0.1:8100 \
  process_with_worker_tick:=true \
  publish_overlay:=true \
  publish_evidence:=true
```

중지해야 할 때는 각각 `Smartfactory:3.2`, `Smartfactory:3.3`, `Smartfactory:3.5` pane에서 Ctrl-C를 누른다.

## 4. AI Server → Mainserver outbound 설정

AI Server에는 Main/WMS-style outbound client가 이미 있다.

| 환경변수 | 기본값 | 설명 |
|---|---|---|
| `MAIN_SERVER_URL` | `http://127.0.0.1:8000` | Mainserver base URL |
| `WMS_VISION_EVENTS_PATH` | `/api/v1/vision/events` | Mainserver VisionEvent ingest path |
| `WMS_EMIT_ENABLED` | `false` | `true`일 때만 outbound POST 시도 |
| `WMS_EMIT_TIMEOUT_S` | `2.0` | Mainserver POST timeout |
| `WMS_EMIT_RETRIES` | `0` | 실패 시 추가 retry 횟수 |

예시:

```bash
export MAIN_SERVER_URL="http://<mainserver-host>:<port>"
export WMS_VISION_EVENTS_PATH="/api/v1/vision/events"
export WMS_EMIT_ENABLED="true"
export WMS_EMIT_TIMEOUT_S="2.0"
export WMS_EMIT_RETRIES="0"
```

AI Server outbound URL 계산식:

```text
{MAIN_SERVER_URL.rstrip('/')}/{WMS_VISION_EVENTS_PATH.lstrip('/')}
```

예:

```text
http://mainserver:8080/api/v1/vision/events
```

## 5. Mainserver가 받아주면 되는 최소 HTTP 계약

### `POST /api/v1/vision/events`

**설명**: AI Server가 생성한 schema-valid `VisionEvent v1` metadata를 Mainserver에 전달한다.

**요청 body**: `docs/contracts/vision-event.schema.json` 형식.

```json
{
  "schema_version": "vision-event.v1",
  "event_id": "11111111-1111-4111-8111-111111111111",
  "timestamp": "2026-06-16T10:30:00+09:00",
  "source": "tb3_1_picam",
  "robot_id": "tb3_1",
  "frame_id": "tb3_1_pi_camera_optical_frame",
  "event_kind": "CANDIDATE",
  "class_name": "aruco_marker",
  "confidence": 0.92,
  "bbox_xyxy": [120, 90, 210, 180],
  "track_id": null,
  "marker_id": "7",
  "zone": null,
  "roi_id": null,
  "pose_estimate": null,
  "depth_median_m": null,
  "wms_hint": "TAG_DETECTED",
  "metadata": {
    "n_frame_count": 1,
    "policy_version": "mvp1",
    "model": "opencv-marker-detector",
    "image_width": 640,
    "image_height": 480,
    "latency_ms": 38.5
  }
}
```

**AI Server가 성공으로 보는 응답**:

- HTTP `200` 또는 `202`
- Response JSON 필드는 엄격하지 않다. AI Server는 response JSON을 `emit_results[].response`에 기록만 한다.

권장 응답 예시:

```json
{
  "accepted": true,
  "duplicate": false,
  "event_id": "11111111-1111-4111-8111-111111111111",
  "processing_status": "queued"
}
```

중복 event 권장 응답 예시:

```json
{
  "accepted": true,
  "duplicate": true,
  "event_id": "11111111-1111-4111-8111-111111111111",
  "processing_status": "already_seen"
}
```

**Main 담당자에게 전달할 최소 요구사항**:

- `200` 또는 `202`를 성공으로 반환한다.
- 같은 `event_id`가 재전송되어도 중복 row/상태전이를 만들지 않는다.
- validation 실패는 `4xx`로 반환한다.
- Main 최종 상태전이는 Main/WMS 정책이 결정한다. Task 생성/완료/실패, inventory count/location 변경, DB row persistence는 Main/WMS만 수행하며 AI Server event는 evidence일 뿐이다.

## 6. 현재 AI Server에서 바로 연결 smoke 가능한 API

현재 outbound emit은 아래 debug/offline detector API에서 이미 연결 smoke가 가능하다.

### 6.1 `POST /api/v1/vision/synthetic/frame`

**설명**: synthetic ArUco frame을 생성/처리하고, `emit=true`이면 Mainserver로 VisionEvent POST를 시도한다. 실제 로봇/카메라 없이 Main 연결 smoke에 적합하다.

**요청**:

```json
{
  "source": "tb3_1_picam",
  "marker_id": 7,
  "marker_size": 96,
  "padding": 32,
  "stale": false,
  "emit": true
}
```

**응답 핵심 필드**:

```json
{
  "source": "tb3_1_picam",
  "emitted": true,
  "emit_disabled": false,
  "emit_results": [
    {
      "event_id": "11111111-1111-4111-8111-111111111111",
      "attempted": true,
      "ok": true,
      "status_code": 202,
      "error": null,
      "response": {
        "accepted": true,
        "duplicate": false,
        "processing_status": "queued"
      }
    }
  ],
  "events": [
    { "schema_version": "vision-event.v1", "source": "tb3_1_picam" }
  ]
}
```

**판정**:

- `emitted=true`: Mainserver POST까지 성공.
- `emit_disabled=true`: AI Server 환경변수 `WMS_EMIT_ENABLED=true`가 아님.
- `emit_results[].ok=false`: Mainserver timeout, transport error, 또는 non-200/202.

### 6.2 `POST /api/v1/detect/image`

**설명**: 업로드한 image를 detection하고, `emit=true`이면 Mainserver로 VisionEvent POST를 시도한다.

**요청 예시**:

```bash
curl -X POST "http://ai-server:8100/api/v1/detect/image" \
  -F source=tb3_1_picam \
  -F emit=true \
  -F image=@sample.jpg
```

**응답 핵심 필드**:

```json
{
  "source": "tb3_1_picam",
  "emitted": true,
  "emit_disabled": false,
  "emit_results": [
    {
      "attempted": true,
      "ok": true,
      "status_code": 202,
      "error": null
    }
  ],
  "events": []
}
```

## 7. Live Robot camera 경로와 Main 연결 시 주의점

현재 live camera 경로는 다음과 같다.

```text
Robot camera
  → ROS2 /camera/image_raw/compressed
  → vision_frame_gateway
  → POST /api/v1/vision/frame
  → POST /api/v1/vision/worker/tick
  → AI Server latest frame/overlay/evidence cache
```

주의:

- `worker/tick`은 현재 frame 처리/overlay 갱신용 debug/control API다.
- 현재 outbound Main POST smoke는 `synthetic/frame` 또는 `detect/image`의 `emit=true` 경로로 검증하는 것이 가장 안전하다.
- live camera에서 생성된 evidence를 Main으로 자동 전송하려면 다음 중 하나를 Main 담당자와 선택해야 한다.

| 선택지 | 설명 | 추천도 |
|---|---|---:|
| A. AI Server HTTP auto-emitter 추가 | worker tick 결과 중 새 event를 `POST /api/v1/vision/events`로 전송 | 높음 |
| B. Main이 AI Server events/latest를 pull | Main이 주기적으로 AI Server evidence를 조회 | 중간 |
| C. Main이 `/sf/vision/events` ROS topic 구독 | Main이 ROS2 환경을 직접 가져야 함 | 낮음, Main이 ROS-aware일 때만 |

추천은 **A: AI Server HTTP auto-emitter**다. Mainserver는 HTTP API만 열면 되고 ROS2 의존성이 생기지 않는다.

## 8. Main/GUI가 이미지를 확인하는 방법

### raw latest image

```http
GET http://ai-server:8100/api/v1/vision/frame/latest/image?source=tb3_1_picam
```

응답:

- `200` + binary image, 보통 `image/jpeg`
- `400` unknown source
- `404` 아직 frame 없음

### overlay latest image

```http
GET http://ai-server:8100/api/v1/vision/overlay/latest/image?source=tb3_1_picam
```

응답:

- `200` + overlay JPEG binary
- `400` unknown source
- `404` 아직 overlay 없음

### overlay metadata

```http
GET http://ai-server:8100/api/v1/vision/overlay/latest?source=tb3_1_picam
```

응답 예시:

```json
{
  "requested_source": "tb3_1_picam",
  "sync": {
    "has_frame": true,
    "has_overlay": true,
    "latest_frame_seq": 15,
    "latest_overlay_frame_seq": 15,
    "overlay_lag_frames": 0,
    "visual_state": "fresh"
  },
  "overlay": {
    "source": "tb3_1_picam",
    "frame_seq": 15,
    "event_count": 0,
    "stale": false,
    "visual_state": "fresh",
    "content_type": "image/jpeg"
  }
}
```

## 9. Main 담당자에게 넘길 짧은 요청 문구

> AI Server는 `VisionEvent v1` JSON을 `POST /api/v1/vision/events`로 보낼 수 있습니다. `MAIN_SERVER_URL`, `WMS_VISION_EVENTS_PATH`, `WMS_EMIT_ENABLED=true`로 대상 URL을 설정합니다. AI Server는 HTTP `200` 또는 `202`를 성공으로 처리하고, response JSON은 그대로 기록합니다. 이미지 bytes는 event JSON에 넣지 않고, 필요 시 Main/GUI가 AI Server의 `/api/v1/vision/frame/latest/image` 또는 `/api/v1/vision/overlay/latest/image`를 pull하는 방식을 권장합니다. 같은 `event_id`는 중복 처리하지 않는 idempotent ingest로 맞춰주세요.

## 10. 연결 검증 순서

1. Mainserver 담당자에게 `POST /api/v1/vision/events` URL과 성공 status code를 확인한다.
2. AI Server 환경변수를 설정한다.
3. 실제 로봇 없이 `POST /api/v1/vision/synthetic/frame` + `emit=true`로 Main POST smoke를 먼저 한다.
4. Main log/DB에서 `event_id`, `source`, `robot_id`, `event_kind`, `class_name` 저장 여부를 확인한다.
5. duplicate smoke: 같은 event를 재전송했을 때 Main이 중복 상태전이를 만들지 않는지 확인한다.
6. 그 다음 live Robot camera → `vision_frame_gateway` → AI Server raw/overlay image 조회를 붙인다.
7. live evidence 자동 POST는 Main 담당자와 A/B/C 선택 후 별도 작은 slice로 켠다.


## 11. Lane D1 safe ultragoal connection plan

Lane D1 should be run as a safe Main/GUI/stream integration ultragoal, not as an active robot-control lane.

Recommended split for Main implementers:

| Plane | Recommended path | Notes |
|---|---|---|
| Main semantic evidence | `AI Server -> Main POST /api/v1/vision/events` | Canonical DB/task evidence path. Main deduplicates by `event_id`. |
| Evidence image display | `Main/GUI -> AI Server GET /api/v1/vision/*/image` | Pull images by URL. Do not put image bytes in `VisionEvent`. |
| High-FPS browser stream | Movement rosbridge/WebSocket `9090` or another allowlisted read-only bridge | Do not use repeated HTTP snapshot polling as production stream. |
| ROS debug/overlay topics | `/sf/vision/sources/tb3_1_picam/overlay/compressed`, `/sf/vision/events` | Safe/read-only visualization and debug topics only. |
| Robot control | `Main -> Movement /movement-api/v1/commands` | Vision/AI does not own `/cmd_vel`, Nav2, or teleop. |

D1 execution order should be:

1. Confirm Main `/api/v1/vision/events` behavior with synthetic/offline AI events.
2. Confirm Main/GUI can pull images from `http://192.168.10.63:8100`.
3. Design or attach the read-only high-FPS stream plane through Movement rosbridge or an allowlisted bridge.
4. Only after Main ingest and idempotency are confirmed, add live camera evidence auto-emission if needed.

AI model note:

- The first D1 ultragoal should not silently add a new heavyweight AI model.
- Current marker evidence uses OpenCV ArUco.
- Optional Lift ROI model integration needs a separate model subgoal with weights, classes, sample images, runtime install method, latency target, and fail-closed validation.

Critic/design gate:

- Reject any D1 design that exposes `/cmd_vel`, teleop, Nav2, parameter mutation, or whole-graph rosbridge access.
- Reject any design that makes rosbridge the canonical Main DB/evidence path.
- Reject any design that uses HTTP snapshot polling as the production high-FPS stream.


## 12. AI-included Vision delivery prerequisites

If D1 includes YOLO/AI model results, Main should not receive raw model labels blindly. Current local YOLO candidates were trained with classes `bottle1`, `bottle2`, and `bottle3`, while public project contracts currently use normalized classes such as `box`, `pallet`, `unknown`, `person`, `obstacle`, and marker classes.

Recommended delivery rule:

1. AI Server runs model inference in a project-managed model environment, not by copying an external venv blindly.
2. AI Server normalizes model labels to public contract classes before Main delivery.
3. Main receives only normalized `VisionEvent` or a future agreed `LiftRoiEvidence` payload.
4. Main must not rely on `bottle1`, `bottle2`, `bottle3` unless the shared API contract is explicitly changed.

Current local model runtime facts:

- `~/venv/venv`: YOLO runtime OK (`ultralytics 8.4.63`, `torch 2.12.0+cu130`, CUDA available, RTX 5060), but missing FastAPI service dependencies.
- `services/ai-server/.venv`: AI Server runtime OK, but missing YOLO/Torch.
- First candidate model: `/home/codelab/yolo_test/runs/segment/bottle_detection_yolov8s_seg/weights/best.pt`.

Therefore D1-AI needs a small environment/setup slice before live Main delivery.

## 13. Architect-Critic gate for D1/D1-AI

The D1 plan was reviewed in Architect -> Critic order on 2026-06-16.

Result: D1 is safe only as a gate-first evidence/GUI/read-only stream lane. It should not be executed as one broad ultragoal that mixes Main ingest, high-FPS streaming, and new YOLO model semantics at once.

Fixed Main-facing gates:

1. **G0 runtime snapshot**: refresh current AI Server/gateway/camera status before live claims. At 2026-06-16 12:25 KST, `127.0.0.1:8100` and `192.168.10.63:8100` were not reachable and no `:8100` listener was present; Main should treat previous live URLs as a prior snapshot until restarted and revalidated.
2. **G1 Main HTTP handshake**: confirm `POST /api/v1/vision/events`, success status `200` or `202`, duplicate `event_id` behavior, no image bytes, and retry/failure behavior.
3. **G3 stream allowlist**: if using rosbridge/WebSocket, expose only read-only image/evidence/status topics. Do not expose `/cmd_vel`, Nav2, teleop, parameter mutation, or whole-graph ROS access.
4. **D1-AI model gate**: do not send raw `bottle1`, `bottle2`, or `bottle3` labels to Main. Agree on `box`, `unknown`, or a contract expansion first.
5. **G5 documentation**: update local docs in each implementation cycle; publish Confluence only after verified behavior or explicit draft-publish approval.

Main owner decisions needed:

- Confirm the Main base URL and whether `/api/v1/vision/events` is ready.
- Confirm idempotent ingest semantics keyed by `event_id`.
- Confirm the class mapping for current YOLO bottle classes.
- Confirm the approved high-FPS stream path if GUI needs more than snapshot/debug images.

## 14. D1-AI ROS overlay stream correction

The high-FPS AI-included video path should not be repeated HTTP image pulls. The agreed primary path is the ROS overlay topic through a read-only bridge:

```text
AI Server worker/tick creates AI overlay
vision_frame_gateway republishes overlay JPEG
/sf/vision/sources/tb3_1_picam/overlay/compressed
read-only rosbridge or stream bridge
Main/GUI video view
```

HTTP endpoints remain useful for smoke/debug only:

- `GET /api/v1/vision/frame/latest/image?source=tb3_1_picam`
- `GET /api/v1/vision/overlay/latest/image?source=tb3_1_picam`
- `GET /api/v1/vision/stream/tb3_1_picam.mjpeg?max_fps=10`

Main PC verification checklist:

1. Confirm the Main/GUI PC can connect to the approved bridge endpoint.
2. Subscribe only to allowlisted read-only topics, especially `/sf/vision/sources/tb3_1_picam/overlay/compressed` for AI overlay view.
3. Confirm no client publish permissions and no `/cmd_vel`, Nav2, teleop, params, `/tf`, `/tf_static`, `/rosout`, or whole-graph exposure.
4. Confirm GUI frame rate from the bridge path, not from repeated HTTP snapshot calls.
5. Keep semantic evidence ingest on `POST /api/v1/vision/events`; do not send high-FPS image bytes to Main DB.

AI model note:

- The local D1-AI path now supports optional pretrained YOLO worker candidates using `VISION_MODEL_WORKER_ENABLED=true` and `VISION_MODEL_PATH=yolov8n.pt`.
- Public class normalization is required before Main-facing evidence: `bottle -> box`, `person -> person`, unmapped classes -> `unknown`.

## 15. Implemented D1 read-only overlay stream bridge

Because high-FPS AI video should not be delivered by repeated HTTP image pulls,
this repo now includes a dedicated read-only ROS overlay stream bridge in
`smartfactory_perception_ros`.

Primary path:

```text
Robot camera
  -> vision_frame_gateway
  -> AI Server worker/tick + overlay render
  -> /sf/vision/sources/tb3_1_picam/overlay/compressed
  -> vision_overlay_stream_bridge
  -> Main/GUI browser MJPEG view
```

Bridge launch example on the local ROS PC:

```bash
source /opt/ros/jazzy/setup.bash
source /home/codelab/Desktop/Project/SmartFactory/install/setup.bash
ros2 launch smartfactory_perception_ros vision_overlay_stream_bridge.launch.py \
  use_vision_overlay_stream_bridge:=true \
  host:=0.0.0.0 \
  port:=8090 \
  sources:=tb3_1_picam \
  max_fps:=30
```

Bridge APIs for Main/GUI smoke:

| API | Request | Output | Purpose |
|---|---|---|---|
| `GET /api/v1/vision/bridge/status` | none | JSON status, enabled sources, overlay topics, frame age, stream/view paths | Health/status for the read-only stream bridge. |
| `GET /api/v1/vision/overlay/view?source=tb3_1_picam` | `source` query | HTML page with embedded stream | Human/browser verification. |
| `GET /api/v1/vision/overlay/stream?source=tb3_1_picam&max_fps=30` | `source`, optional `max_fps` | MJPEG `multipart/x-mixed-replace` | Main/GUI AI overlay video stream. |
| `GET /view/tb3_1_picam` | path source | HTML alias | Simple operator URL. |
| `GET /stream/tb3_1_picam.mjpeg?max_fps=30` | path source, optional `max_fps` | MJPEG alias | Simple stream URL. |

Safety contract:

- Bridge subscribes only to allowlisted `/sf/vision/sources/<source>/overlay/compressed` topics.
- Bridge exposes only `GET`/`OPTIONS`; mutation methods return `405`.
- Bridge creates no ROS publishers and no ROS service/action clients.
- Forbidden surfaces remain `/cmd_vel`, Nav2, teleop, parameter mutation, `/rosout`, `/tf`, `/tf_static`, and whole-graph ROS access.
- Main semantic evidence remains `POST /api/v1/vision/events`; high-FPS image bytes must not be inserted into the Main DB event JSON.

Local validation completed:

```bash
source /opt/ros/jazzy/setup.bash
cd ros2/smartfactory_perception_ros
pytest -q
# 34 passed

source /opt/ros/jazzy/setup.bash
colcon build --symlink-install --packages-select smartfactory_perception_ros
colcon test --packages-select smartfactory_perception_ros --event-handlers console_direct+
# 34 passed
```

## 16. Current local live runtime for Main/GUI smoke

Captured on 2026-06-16 14:18 KST.

All runtime/process work is in `Smartfactory:3:Development`.

| Pane | Role | Status |
|---|---|---|
| `Smartfactory:3.3` | Robot1 camera SSH | Running temporary camera launch; publishes `/camera/image_raw/compressed`. |
| `Smartfactory:3.4` | AI Server | Running on `0.0.0.0:8100`; model worker active with pretrained `yolov8n.pt`. |
| `Smartfactory:3.6` | `vision_frame_gateway` | Running; posts frames to AI Server, ticks worker, publishes overlay/evidence topics. |
| `Smartfactory:3.2` | `vision_overlay_stream_bridge` | Running on `0.0.0.0:8090`; serves ROS overlay topic as MJPEG. |

Main/GUI browser check URL:

```text
http://192.168.10.63:8090/api/v1/vision/overlay/view?source=tb3_1_picam
```

Status APIs currently reachable from this PC/LAN:

```text
GET http://192.168.10.63:8100/api/v1/health
GET http://192.168.10.63:8090/api/v1/vision/bridge/status
```

Observed runtime state:

- AI Server health OK, `source_summary.online=1`, model worker active.
- AI overlay metadata fresh with `overlay_lag_frames=0`, `640x480`, `image/jpeg`.
- Read-only stream bridge status OK: `read_only=true`, `motion_command_allowed=false`, `has_frame=true`, `stale=false`.
- Bridge stream returns `multipart/x-mixed-replace` MJPEG.
- ROS overlay topic `/sf/vision/sources/tb3_1_picam/overlay/compressed` observed around `4.9-5.0 Hz`.
- Topic list on this path showed only camera/vision topics and no `/cmd_vel`, Nav2, teleop, or parameter mutation topic.

Temporary runtime caveat:

- For this smoke, AI Server reused the known YOLO/Torch environment via `PYTHONPATH=/home/codelab/venv/venv/lib/python3.12/site-packages` while running the service `.venv`.
- For reproducible project runs, use `./scripts/setup_ai_server_model_env.sh` and `AI_SERVER_VENV_DIR=services/ai-server/.venv-yolo`.

## 17. Detection overlay runtime correction

Captured on 2026-06-16 14:23 KST.

Issue observed: browser video was visible, but detection boxes were not visible.

Root cause: `scripts/run_ai_server.sh` clears inherited `PYTHONPATH` to keep the
AI Server isolated from ROS2. The temporary YOLO/Torch environment path was
therefore not visible to uvicorn, and model inference failed closed with zero
model candidates.

Fix applied:

```text
AI_SERVER_EXTRA_PYTHONPATH=/home/codelab/venv/venv/lib/python3.12/site-packages
```

The runner now applies this explicit model-only path after clearing inherited
`PYTHONPATH`. This keeps the default ROS isolation boundary intact.

Current validation after restart:

- `GET /api/v1/vision/overlay/latest?source=tb3_1_picam` returned fresh overlay with `event_count=5` and `overlay_lag_frames=0`.
- `GET /api/v1/detections/latest?source=tb3_1_picam&limit=10` returned `VisionEvent v1` `CANDIDATE` events.
- Confirmed class normalization: YOLO `bottle -> box`, YOLO `person -> person`, unmapped COCO classes such as `tv`/`keyboard -> unknown`.
- Browser URL remains:

```text
http://192.168.10.63:8090/api/v1/vision/overlay/view?source=tb3_1_picam
```

## 18. D1 bundled local vision process for Main handoff

Added on 2026-06-16 KST.

`./scripts/run_d1_vision_bundle.sh` is the recommended local supervisor for Main/GUI smoke. It starts AI Server, `vision_frame_gateway`, and `vision_overlay_stream_bridge` together while preserving the ROS/FastAPI safety boundary.

Main should consume this bundle through:

```text
GET http://<vision-pc>:8090/api/v1/vision/overlay/stream?source=tb3_1_picam&max_fps=30
GET http://<vision-pc>:8090/api/v1/vision/bridge/status
GET http://<vision-pc>:8100/api/v1/detections/latest?source=tb3_1_picam&limit=10
```

The operator HTML check URL is:

```text
GET http://<vision-pc>:8090/api/v1/vision/overlay/view?source=tb3_1_picam
```

Recommended Main contract remains:

```text
POST /api/v1/vision/events
```

for semantic `VisionEvent v1` ingestion. Until a continuous live auto-emitter/relay is enabled, Main can poll `GET /api/v1/detections/latest` at a controlled cadence and deduplicate by `event_id`.

Runbook: `docs/runbooks/d1-vision-bundle-main-handoff.md`.

## 19. Two-robot D1 stream handoff smoke

Added on 2026-06-16 KST.

Current simultaneous stream layout:

```text
tb3_1_picam / ROS_DOMAIN_ID=2 -> vision bundle -> http://<vision-pc>:8090
tb3_2_picam / ROS_DOMAIN_ID=5 -> domain sidecar -> http://<vision-pc>:8091
```

Main/GUI receive URLs:

```text
GET http://<vision-pc>:8090/api/v1/vision/overlay/stream?source=tb3_1_picam&max_fps=30.0
GET http://<vision-pc>:8091/api/v1/vision/overlay/stream?source=tb3_2_picam&max_fps=30.0
GET http://<vision-pc>:8090/api/v1/vision/bridge/status
GET http://<vision-pc>:8091/api/v1/vision/bridge/status
GET http://<vision-pc>:8100/api/v1/detections/latest?source=tb3_1_picam&limit=10
GET http://<vision-pc>:8100/api/v1/detections/latest?source=tb3_2_picam&limit=10
```

This does not change the canonical semantic push target: Main should still implement/accept `POST /api/v1/vision/events` for `VisionEvent v1` when push/relay is enabled.

## 20. Main-compatible single-port Vision Stream Gateway

Added on 2026-06-16 KST after Main clarified that it wants one upstream gateway.

Public base URL:

```text
LMS_VISION_STREAM_BASE_URL=http://192.168.10.63:8090
```

Public endpoints:

```text
GET /api/v1/vision/overlay/stream?source=tb3_1_picam&max_fps=30
GET /api/v1/vision/overlay/stream?source=tb3_2_picam&max_fps=30
GET /api/v1/vision/frame/stream?source=tb3_1_picam&max_fps=30
GET /api/v1/vision/frame/stream?source=tb3_2_picam&max_fps=30
GET /api/v1/vision/overlay/view?source=tb3_1_picam
GET /api/v1/vision/bridge/status
```

Response type for stream endpoints:

```text
Content-Type: multipart/x-mixed-replace; boundary=...
```

Runtime implementation:

```text
0.0.0.0:8090 public ROS-free Vision Stream Gateway
  -> 127.0.0.1:18090 internal tb3_1_picam bridge, ROS_DOMAIN_ID=2
  -> 127.0.0.1:18091 internal tb3_2_picam bridge, ROS_DOMAIN_ID=5
```

Main should not know the internal ports. Main should validate that `source` exists in `camera_sources.source_id`, then proxy to the public `:8090` gateway with the same `source` query parameter.

## 21. Async AI overlay hot path and Main-facing contract

Added on 2026-06-16 KST.

The Vision PC now has an internal hot path for higher-FPS AI overlay generation:

```text
vision_frame_gateway -> AI Server POST /api/v1/vision/frame/process
```

This endpoint is **not** a Main Server dependency. It is used by the local ROS sidecar to store one frame and update the AI overlay cache in a single request before publishing the overlay image back onto the safe ROS vision topic.

Main Server should continue to consume only the public single-port gateway:

```text
Base URL: LMS_VISION_STREAM_BASE_URL=http://192.168.10.63:8090
GET /api/v1/vision/overlay/stream?source=tb3_1_picam&max_fps=30
GET /api/v1/vision/overlay/stream?source=tb3_2_picam&max_fps=30
GET /api/v1/vision/frame/stream?source=tb3_1_picam&max_fps=30
GET /api/v1/vision/frame/stream?source=tb3_2_picam&max_fps=30
GET /api/v1/vision/bridge/status
```

Main-side requirements remain:

1. Validate `source` against `camera_sources.source_id` before proxying.
2. Proxy MJPEG as `multipart/x-mixed-replace`; do not store high-FPS image bytes in DB.
3. Use one selected stream by default in the HTML dashboard; opening many streams at once can reduce per-stream FPS.
4. For semantic tags/evidence, poll `GET http://192.168.10.63:8100/api/v1/detections/latest?source={source_id}&limit=10` at a controlled cadence or implement `POST /api/v1/vision/events` for push ingestion.
5. Deduplicate semantic events by `event_id`; store metadata and selected snapshot URLs/object-storage keys only when needed.

Current local bundle defaults use configurable reliable QoS for the live robots:

```text
VISION_GATEWAY_IMAGE_QOS_RELIABILITY=reliable
VISION_GATEWAY_OVERLAY_PUB_QOS_RELIABILITY=reliable
VISION_STREAM_OVERLAY_SUB_QOS_RELIABILITY=reliable
VISION_GATEWAY_ASYNC_PIPELINE=true
VISION_GATEWAY_PROCESS_FRAME_INLINE=true
VISION_GATEWAY_FRAME_PROCESS_PATH=/api/v1/vision/frame/process
```

If a robot camera publisher is best-effort, set `VISION_GATEWAY_IMAGE_QOS_RELIABILITY=sensor_data` or `best_effort`; a reliable subscriber is not compatible with a best-effort publisher.
