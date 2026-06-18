# SmartFactory API 계약 문서

**상태:** 2026-06-16 Asia/Seoul 기준 Lane A source registry + Lane B robot-free Vision Gateway API + Lane C safe ROS sidecar smoke 반영본  
**목적:** Main / GUI / Movement / Vision 팀이 같은 API 이름, 요청, 출력 형태로 통합 논의하기 위한 압축 계약 문서  
**주의:** Vision Gateway는 evidence/stream만 제공하며 Main/WMS가 task·inventory·robot 상태의 최종 source of truth입니다. Vision Gateway는 `/cmd_vel` publish 또는 Nav2 action 호출을 하지 않습니다.

---

## 0. 핵심 결정

| 항목 | 결정 |
| --- | --- |
| Source registry | `config/vision/sources.yaml`이 source ID, robot ID, frame ID, ROS topic, schema/OpenAPI/fixture enum의 source of truth |
| MVP1 sources | `global_cam_01`, `tb3_1_picam`, `tb3_2_picam` |
| Robot PiCam physical input | `/tb3_1/camera/image_raw/compressed`, `/tb3_2/camera/image_raw/compressed` |
| Legacy browser topics | `/mission/tb3_1/camera/compressed`, `/mission/tb3_2/camera/compressed` 유지 |
| Normalized topics | `/sf/vision/sources/{source}/image/compressed`, `/sf/vision/sources/{source}/overlay/compressed` 병행 |
| Browser stream plane | rosbridge `ws://<vision-host>:9090` primary |
| HTTP/MJPEG APIs | debug/fallback only |
| Lane C sidecar | `smartfactory_perception_ros/vision_frame_gateway`; FastAPI 밖 ROS2 sidecar |
| Lane C safety | robot-side 영구 변경 없음, 임시 camera launch/read-only topic check만 허용, `/cmd_vel`/Nav2/teleop 금지 |
| Main interim event | `/api/v1/camera/events`는 audit/business interim |
| Main target event | `/api/v1/vision/events`가 canonical VisionEvent ingest target |

Source registry 생성/검증:

```shell
python3 scripts/generate_source_registry_surfaces.py
```

---

## 1. Vision/AI Server API

### `GET /api/v1/health`

설명: 서비스 readiness. 모든 카메라 online을 요구하지 않습니다.

요청: 없음

출력:

```json
{"service":"ai-server","status":"ok","service_version":"0.1.0","contract_version":"vision-event.v1","model_status":"loaded","source_summary":{"configured":3,"online":0,"offline":3}}
```

### `GET /api/v1/sources`

설명: source registry 기반 카메라 목록과 health를 반환합니다.

요청: 없음

출력:

```json
{"sources":[{"source":"tb3_1_picam","robot_id":"tb3_1","status":"online | stale | offline | disabled","frame_id":"tb3_1_pi_camera_optical_frame","ros_topic":"/tb3_1/camera/image_raw/compressed","ros_message_type":"sensor_msgs/msg/CompressedImage","ros_content_type":"image/jpeg"}]}
```

### `GET /api/v1/detections/latest?source={source}&limit={1..50}`

설명: local/debug 최신 detection feed입니다. Main 상태 판단 source of truth가 아닙니다.

요청: query `source` optional, `limit` optional.

출력:

```json
{"generated_at":"2026-06-16T09:00:03+09:00","events":[{"schema_version":"vision-event.v1","source":"tb3_1_picam","event_kind":"CONFIRMED","class_name":"aruco_marker","robot_id":"tb3_1"}]}
```

### `GET /api/v1/metrics?source={source}`

설명: AI Server local observability입니다. WMS 상태 API가 아닙니다.

요청: query `source` optional.

출력:

```json
{"generated_at":"2026-06-16T09:00:06+09:00","requested_source":"tb3_1_picam","metrics":{"stream":{"clients_total":0},"worker":{"tick_total":{"processed":1}}},"frame_store":{"sources_with_frames":1}}
```

### `GET /api/v1/vision/streams?source={source}`

설명: stream discovery API입니다. Production browser stream은 rosbridge이고, HTTP/MJPEG는 debug/fallback입니다.

요청: query `source` optional.

출력:

```json
{"requested_source":"tb3_1_picam","primary_stream_plane":"rosbridge","debug_only":true,"motion_command_allowed":false,"control_topics_published":[],"summary":{"sources_total":1,"ros_ingest_contract_ready_count":1},"sources":[{"source":"tb3_1_picam","mjpeg_path":"/api/v1/vision/stream/tb3_1_picam.mjpeg","ros_handoff_source_path":"/api/v1/vision/ros/topics?source=tb3_1_picam"}]}
```

### `GET /api/v1/vision/debug/sources?source={source}`

설명: source별 frame/overlay/stream/ROS readiness debug snapshot입니다.

요청: query `source` optional.

출력:

```json
{"requested_source":"tb3_1_picam","debug_only":true,"summary":{"sources_total":1,"with_frame_count":1,"with_overlay_count":1},"sources":[{"source":"tb3_1_picam","health":{"status":"online"},"latest_frame":{"frame_seq":2},"latest_overlay":{"frame_seq":2,"visual_state":"fresh"},"debug_paths":{"frame_ingest":"/api/v1/vision/frame","worker_tick":"/api/v1/vision/worker/tick"}}]}
```

### `GET /api/v1/vision/ros/topics?source={source}`

설명: Lane C ROS2/domain-bridge handoff matrix입니다. Read-only이며 HTTP 요청이 ROS2를 시작하지 않습니다.

요청: query `source` optional.

출력:

```json
{"requested_source":"tb3_1_picam","debug_only":true,"motion_command_allowed":false,"control_topics_published":[],"topic_exposure_summary":{"policy_status":"safe","control_topic_allowed_count":0},"sources":[{"source":"tb3_1_picam","physical_input_topic":"/tb3_1/camera/image_raw/compressed","normalized_overlay_topic":"/sf/vision/sources/tb3_1_picam/overlay/compressed","evidence_event_topic":"/sf/vision/events","ingest_readiness":{"readiness_state":"contract_ready","runtime_subscriber_active":false},"publish_readiness":{"readiness_state":"no_frame","overlay_ready":false}}]}
```

### `POST /api/v1/vision/frame`

설명: latest frame ingest seam입니다. Frame만 저장하고 detection/overlay는 실행하지 않습니다. Lane C `vision_frame_gateway`가 이 API를 사용합니다.

요청: `multipart/form-data`

| field | required | 설명 |
| --- | --- | --- |
| `source` | yes | configured source ID |
| `image` | yes | decodable image file |

출력:

```json
{"source":"tb3_1_picam","processed":false,"frame":{"source":"tb3_1_picam","frame_seq":1,"content_type":"image/jpeg","size_bytes":1234},"overlay":null,"ingest_context":{"transport":"http_debug","stored_in_latest_frame_cache":true,"processed_inline":false,"source_health_updated":true,"ros_callback_compatible":true},"worker_tick_path":"/api/v1/vision/worker/tick"}
```

Lane C 실로봇 smoke 출력 예:

```json
{"generated_at":"2026-06-16T10:28:18.741327+09:00","frame":{"source":"tb3_1_picam","frame_seq":15,"image":{"width":640,"height":480},"content_type":"image/jpeg","size_bytes":88311}}
```

### `GET /api/v1/vision/frame/latest?source={source}`

설명: latest raw frame metadata입니다.

요청: query `source` required.

출력:

```json
{"generated_at":"2026-06-16T09:00:08+09:00","frame":{"source":"tb3_1_picam","frame_seq":1,"image":{"width":160,"height":160},"content_type":"image/jpeg","size_bytes":1234}}
```

### `GET /api/v1/vision/frame/latest/image?source={source}`

설명: latest raw frame binary image입니다.

요청: query `source` required.

출력: `image/jpeg` 또는 ingest 당시 content type의 binary response. Frame이 없으면 `404`.

### `GET /api/v1/vision/overlay/latest?source={source}`

설명: latest overlay metadata입니다.

요청: query `source` required.

출력:

```json
{"requested_source":"tb3_1_picam","sync":{"latest_frame_seq":15,"latest_overlay_frame_seq":15,"overlay_lag_frames":0,"overlay_visual_state":"fresh"},"overlay":{"source":"tb3_1_picam","frame_seq":15,"event_count":0,"stale":false,"visual_state":"fresh","image":{"width":640,"height":480},"content_type":"image/jpeg"}}
```

### `GET /api/v1/vision/overlay/latest/image?source={source}`

설명: latest overlay JPEG입니다. Lane C sidecar가 이 출력을 `/sf/vision/sources/{source}/overlay/compressed`에 publish할 수 있습니다.

요청: query `source` required.

출력: `image/jpeg` binary response. Overlay가 없으면 `404`.

### `GET /api/v1/vision/stream/{source}.mjpeg?max_fps=10`

설명: local debug/fallback MJPEG overlay stream입니다. Production stream plane이 아닙니다.

요청: path `source`, query `max_fps` optional `1..30`.

출력: `multipart/x-mixed-replace` MJPEG stream. Overlay가 없으면 `404`.

### `POST /api/v1/vision/synthetic/frame`

설명: robot-free synthetic ArUco frame ingest입니다.

요청:

```json
{"source":"tb3_1_picam","marker_id":7,"marker_size":96,"padding":32,"stale":false,"emit":false}
```

출력:

```json
{"source":"tb3_1_picam","emitted":false,"events":[{"schema_version":"vision-event.v1","marker_id":"ARUCO_4X4_50_7"}],"overlay":{"source":"tb3_1_picam","frame_seq":1,"event_count":1,"visual_state":"fresh"}}
```

### `GET /api/v1/vision/worker/status?source={source}&max_frame_age_s=2.0`

설명: 다음 worker tick preview입니다. Read-only이며 detection/overlay를 실행하지 않습니다.

요청: query `source` optional, `max_frame_age_s` optional.

출력:

```json
{"requested_source":"tb3_1_picam","summary":{"sources_total":1,"pending_count":1},"sources":[{"source":"tb3_1_picam","has_frame":true,"pending":true,"next_tick_status":"processed"}]}
```

### `POST /api/v1/vision/worker/tick`

설명: one-shot latest-frame processing tick입니다. Debug/control surface이며 ROS motion command를 내지 않습니다. Lane C sidecar는 옵션으로 이 API를 호출한 뒤 overlay/evidence topic을 publish합니다.

요청:

```json
{"source":"tb3_1_picam","force":false,"stale":false,"max_frame_age_s":2.0}
```

출력:

```json
{"requested_source":"tb3_1_picam","summary":{"sources_total":1,"processed_count":1,"new_event_count_total":1},"results":[{"source":"tb3_1_picam","status":"processed","frame_seq":1,"event_count":1,"overlay":{"frame_seq":1,"visual_state":"fresh"}}]}
```

### `POST /api/v1/detect/image`

설명: uploaded image marker detection/debug입니다. Optional WMS emit 가능.

요청: `multipart/form-data` with `source`, `image`, optional `emit`, optional pose profile/calibration fields.

출력:

```json
{"source":"tb3_1_picam","emitted":false,"emit_results":[],"events":[{"schema_version":"vision-event.v1","source":"tb3_1_picam","event_kind":"CONFIRMED","class_name":"aruco_marker"}]}
```

### `POST /api/v1/lift-roi/evaluate`

설명: caller-provided bbox/mask candidates를 ROI 기준으로 평가해 `LiftRoiEvidence v1`을 반환합니다.

요청:

```json
{"source":"tb3_1_picam","operation":"PICKUP","task_id":"TASK-IN-0001","image":{"width":640,"height":480},"roi":{"roi_id":"TB3_1_LIFT_ROI","kind":"LIFT","polygon_xy":[[220,180],[420,180],[440,360],[200,360]]},"expected_count":1,"stable_frames":3,"count_stable":true,"lift_sensor":{"lift_up":true},"candidates":[{"class_name":"box","bbox_xyxy":[240,210,310,290],"confidence":0.91}]}
```

출력:

```json
{"schema_version":"lift-roi-evidence.v1","source":"tb3_1_picam","robot_id":"tb3_1","frame_id":"tb3_1_pi_camera_optical_frame","operation":"PICKUP","load":{"count":1,"empty":false,"accepted_items":[],"rejected_items":[]},"verification":{"status":"CONFIRMED | CANDIDATE | FAILED","reason":"pickup_verified"}}
```

### `POST /api/v1/lift-roi/evaluate-image`

설명: uploaded image를 optional detector/segmenter로 처리한 뒤 `LiftRoiEvidence v1`을 반환합니다. Model 미설정/불가 시 `503` fail-closed입니다.

요청: `multipart/form-data` with `source`, `operation`, `roi_json`, `image`, optional `task_id`, `expected_count`, `stable_frames`, `count_stable`, lift sensor fields, `dropped_item_count`, `policy_json`.

출력: `LiftRoiEvidence v1` JSON. Model path가 없으면 common error envelope로 `503`.

---

## 2. Lane C ROS sidecar / topic output

### `smartfactory_perception_ros vision_frame_gateway`

설명: FastAPI 밖에서 동작하는 ROS2 sidecar입니다. Compressed camera topic을 구독하고 기존 AI Server API를 호출한 뒤, 옵션으로 안전 topic만 publish합니다.

허용 publish:

```text
/sf/vision/sources/{source}/overlay/compressed  sensor_msgs/msg/CompressedImage
/sf/vision/events                              std_msgs/msg/String
```

금지: `/cmd_vel`, Nav2 action, teleop, robot launch/systemd/package/network/calibration 영구 변경, whole-graph bridge 노출.

실행 예:

```shell
ros2 launch smartfactory_perception_ros vision_frame_gateway.launch.py \
  use_vision_frame_gateway:=true \
  use_tb3_1_picam:=true \
  tb3_1_picam_image_topic:=/camera/image_raw/compressed \
  ai_server_url:=http://127.0.0.1:8100 \
  process_with_worker_tick:=true \
  force_worker_tick:=true \
  publish_overlay:=true \
  publish_evidence:=true
```

출력 evidence JSON topic payload 예:

```json
{"source":"tb3_1_picam","lane":"C","kind":"vision_gateway_evidence_snapshot","safe":true,"motion_control":false,"ai_server":{"processed":true,"events":[]}}
```

---

## 3. Main API 계약

### 현재 구현됨: `POST /api/v1/camera/events`

설명: generic camera audit/business event. 상태 전이 없음.

요청:

```json
{"event_id":"11111111-1111-4111-8111-111111111111","event_type":"PERSON_INTRUSION","robot_name":"tb3_1","location":"STORAGE_A","severity":"WARN","payload":{"source":"tb3_1_picam"}}
```

출력:

```json
{"ok":true,"message":"camera event accepted"}
```

### Target canonical: `POST /api/v1/vision/events`

설명: Main target VisionEvent canonical ingest. Main 구현 필요.

요청: full `VisionEvent v1` JSON.

출력 accepted:

```json
{"accepted":true,"duplicate":false,"event_id":"11111111-1111-4111-8111-111111111111","schema_version":"vision-event.v1","wms_processing_status":"queued"}
```

출력 duplicate:

```json
{"accepted":true,"duplicate":true,"event_id":"11111111-1111-4111-8111-111111111111","wms_processing_status":"already_seen"}
```

---

## 4. 공통 오류 응답

```json
{"error":{"code":"BAD_REQUEST | VALIDATION_ERROR | NOT_FOUND | SERVICE_UNAVAILABLE | INTERNAL_ERROR","message":"unknown source: bad_cam","details":[],"request_id":"..."}}
```

---

## 5. 검증 상태

2026-06-16 Lane C safe sidecar 구현 검증:

* ROS package pytest: `28 passed`
* live Robot1 passive camera check: `/camera/image_raw/compressed` 약 29~31Hz, `sensor_msgs/msg/CompressedImage`
* live Lane C sidecar smoke: `POST /api/v1/vision/frame`, `POST /api/v1/vision/worker/tick`, `GET /api/v1/vision/overlay/latest/image` 반복 성공
* AI Server latest frame: `tb3_1_picam`, `frame_seq=15`, `640x480`, `image/jpeg`
* AI Server overlay: `latest_frame_seq=15`, `latest_overlay_frame_seq=15`, `overlay_lag_frames=0`, `visual_state=fresh`
* `./scripts/test_ai_server.sh -q`: `129 passed, 1 warning`
* `python3 scripts/validate_contracts.py`: OK
* `python3 scripts/validate_deployment_assets.py`: `Deployment assets validated.`
* `make ros-build-bringup`: `smartfactory_perception_ros`, `smartfactory_bringup` build OK
* Static safety guards: FastAPI app source에 `rclpy`, `sensor_msgs`, `cv_bridge` import 없음; Lane C ROS package에 motion publisher/action 없음; allowlist allowed section에 motion/control topic 없음
* `git diff --check`: OK

실 로봇에서 수행한 것은 사용자 승인된 임시 camera launch와 read-only topic/hz 확인뿐이며, 로봇 내부 영구 환경은 변경하지 않았습니다.
