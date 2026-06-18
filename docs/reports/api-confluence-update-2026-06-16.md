# SmartFactory API 계약 문서

**상태:** 2026-06-16 Asia/Seoul 기준 Lane A source registry + Lane B robot-free Vision Gateway API 반영본  
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
| Main interim event | `/api/v1/camera/events`는 audit/business interim |
| Main target event | `/api/v1/vision/events`가 canonical VisionEvent ingest target |
| Safety | direct Movement safety alert는 별도 승인 전 금지. Vision은 motion 제어 권한 없음 |

Source registry 생성/검증 산출물:

```bash
python3 scripts/generate_source_registry_surfaces.py
```

생성/갱신 대상: `vision-event.schema.json`, `lift-roi-evidence.schema.json`, `docs/contracts/generated/source-registry.snapshot.json`, `docs/contracts/fixtures/source-registry.valid.json`, `ai-server-openapi.json`.

---

## 1. Vision/AI Server API

### `GET /api/v1/health`

설명: 서비스 readiness. 모든 카메라 online을 요구하지 않습니다.

요청: 없음

출력:

```json
{
  "service": "ai-server",
  "status": "ok",
  "service_version": "0.1.0",
  "contract_version": "vision-event.v1",
  "model_status": "loaded",
  "models": {
    "marker": {"status": "loaded", "name": "opencv-marker-detector"},
    "lift_roi": {"status": "disabled | loaded | error", "task": "segment | detect", "path_configured": false, "device": "cpu"}
  },
  "source_summary": {"configured": 3, "online": 0, "stale": 0, "disabled": 0, "offline": 3},
  "event_retention": {"max_size": 200, "current_size": 0}
}
```

### `GET /api/v1/sources`

설명: source registry 기반 카메라 목록과 health를 반환합니다.

요청: 없음

출력:

```json
{
  "sources": [
    {
      "source": "tb3_1_picam",
      "source_id": "tb3_1_picam",
      "kind": "robot_pi_camera",
      "robot_id": "tb3_1",
      "enabled": true,
      "status": "online | stale | offline | disabled",
      "frame_id": "tb3_1_pi_camera_optical_frame",
      "last_frame_at": null,
      "last_frame_age_s": null,
      "last_event_at": null,
      "last_event_kind": null,
      "last_event_id": null,
      "last_marker_id": null,
      "frame_count": 0,
      "event_count": 0,
      "target_fps": 10.0,
      "notes": "front marker/dock/local item evidence",
      "ros_topic": "/tb3_1/camera/image_raw/compressed",
      "ros_message_type": "sensor_msgs/msg/CompressedImage",
      "ros_content_type": "image/jpeg"
    }
  ]
}
```

### `GET /api/v1/detections/latest?source={source}&limit={1..50}`

설명: AI Server local/debug 최신 detection feed입니다. Main 상태 판단 source of truth가 아닙니다.

요청: query `source` optional, `limit` optional.

출력:

```json
{
  "generated_at": "2026-06-16T09:00:03+09:00",
  "events": [
    {
      "schema_version": "vision-event.v1",
      "event_id": "11111111-1111-4111-8111-111111111111",
      "timestamp": "2026-06-16T09:00:03+09:00",
      "source": "tb3_1_picam",
      "event_kind": "CONFIRMED",
      "class_name": "aruco_marker",
      "confidence": 1.0,
      "robot_id": "tb3_1",
      "frame_id": "tb3_1_pi_camera_optical_frame",
      "metadata": {"policy_version": "mvp1"}
    }
  ]
}
```

### `GET /api/v1/metrics?source={source}`

설명: AI Server local observability입니다. WMS 상태 API가 아닙니다.

요청: query `source` optional.

출력:

```json
{
  "generated_at": "2026-06-16T09:00:06+09:00",
  "requested_source": "tb3_1_picam",
  "metrics": {
    "stream": {"clients_total": 0, "active_clients_total": 0, "frames_sent_total": 0, "stale_polls_total": 0, "by_source": {"tb3_1_picam": {"approx_fps": 0.0}}},
    "worker": {"tick_total": {"processed": 1}, "by_source": {"tb3_1_picam": {"processed": 1}}}
  },
  "event_store": {"max_size": 200, "current_size": 1},
  "frame_store": {"sources_with_frames": 1, "frame_seq_by_source": {"tb3_1_picam": 1}, "dropped_frames_by_source": {}, "dropped_frames_total": 0}
}
```

### `GET /api/v1/vision/streams?source={source}`

설명: stream discovery API입니다. Production browser stream은 rosbridge이고, HTTP/MJPEG는 debug/fallback입니다.

요청: query `source` optional.

출력:

```json
{
  "requested_source": "tb3_1_picam",
  "primary_stream_plane": "rosbridge",
  "rosbridge_url": "ws://<vision-host>:9090",
  "debug_only": true,
  "motion_command_allowed": false,
  "control_topics_published": [],
  "summary": {
    "sources_total": 1,
    "with_frame_count": 0,
    "with_overlay_count": 0,
    "ros_ingest_contract_ready_count": 1,
    "ros_ingest_runtime_subscriber_active_count": 0,
    "ros_publish_payload_available_count": 0,
    "evidence_event_publish_ready_count": 0
  },
  "sources": [
    {
      "source": "tb3_1_picam",
      "mjpeg_path": "/api/v1/vision/stream/tb3_1_picam.mjpeg",
      "frame_metadata_path": "/api/v1/vision/frame/latest?source=tb3_1_picam",
      "overlay_metadata_path": "/api/v1/vision/overlay/latest?source=tb3_1_picam",
      "ros_handoff_source_path": "/api/v1/vision/ros/topics?source=tb3_1_picam",
      "ros_ingest_readiness": {"readiness_state": "contract_ready", "physical_input_message_type": "sensor_msgs/msg/CompressedImage", "physical_input_content_type": "image/jpeg", "runtime_subscriber_active": false},
      "ros_publish_readiness": {"readiness_state": "no_frame", "overlay_ready": false}
    }
  ]
}
```

### `GET /api/v1/vision/debug/sources?source={source}`

설명: source별 frame/overlay/stream/ROS readiness debug snapshot입니다.

요청: query `source` optional.

출력:

```json
{
  "requested_source": "tb3_1_picam",
  "primary_stream_plane": "rosbridge",
  "debug_only": true,
  "summary": {"sources_total": 1, "with_frame_count": 1, "with_overlay_count": 1, "ros_publish_payload_available_count": 1},
  "sources": [
    {
      "source": "tb3_1_picam",
      "health": {"status": "online", "frame_count": 2, "event_count": 1},
      "latest_frame": {"frame_seq": 2, "size_bytes": 1234},
      "latest_overlay": {"frame_seq": 2, "event_count": 1, "visual_state": "fresh"},
      "debug_paths": {"frame_ingest": "/api/v1/vision/frame", "worker_tick": "/api/v1/vision/worker/tick", "ros_handoff": "/api/v1/vision/ros/topics?source=tb3_1_picam"}
    }
  ]
}
```

### `GET /api/v1/vision/ros/topics?source={source}`

설명: Lane C 전 ROS2/domain-bridge handoff matrix입니다. Read-only이며 ROS2를 시작하지 않습니다.

요청: query `source` optional.

출력:

```json
{
  "requested_source": "tb3_1_picam",
  "primary_stream_plane": "rosbridge",
  "debug_only": true,
  "motion_command_allowed": false,
  "control_topics_published": [],
  "topic_exposure_summary": {"sources_total": 1, "policy_status": "safe", "control_topic_allowed_count": 0, "client_publish_allowed_source_count": 0},
  "ingest_readiness_summary": {"sources_total": 1, "contract_ready_count": 1, "runtime_subscriber_active_count": 0},
  "sources": [
    {
      "source": "tb3_1_picam",
      "physical_input_topic": "/tb3_1/camera/image_raw/compressed",
      "physical_input_message_type": "sensor_msgs/msg/CompressedImage",
      "physical_input_content_type": "image/jpeg",
      "physical_input_transport": "compressed",
      "legacy_browser_topic": "/mission/tb3_1/camera/compressed",
      "normalized_image_topic": "/sf/vision/sources/tb3_1_picam/image/compressed",
      "normalized_overlay_topic": "/sf/vision/sources/tb3_1_picam/overlay/compressed",
      "evidence_event_topic": "/sf/vision/events",
      "ingest_readiness": {
        "readiness_state": "contract_ready",
        "runtime_subscriber_active": false,
        "runtime_plan": {
          "source_registry_path": "/home/codelab/Desktop/Project/SmartFactory/config/vision/sources.yaml",
          "subscription_callback": "registry_source_image_message_to_latest_frame_store_put",
          "ingest_adapter": "_store_latest_frame_from_bytes",
          "http_handler_role": "read_latest_state_only_never_spin_ros2"
        }
      },
      "publish_readiness": {"readiness_state": "no_frame", "overlay_ready": false}
    }
  ]
}
```

### `POST /api/v1/vision/frame`

설명: raw/latest frame ingest seam입니다. Frame만 저장하고 detection/overlay는 실행하지 않습니다.

요청: `multipart/form-data`

| field | required | 설명 |
| --- | --- | --- |
| `source` | yes | configured source ID |
| `image` | yes | decodable image file |

출력:

```json
{
  "source": "tb3_1_picam",
  "processed": false,
  "frame": {"source": "tb3_1_picam", "frame_seq": 1, "content_type": "image/png", "size_bytes": 1234},
  "overlay": null,
  "ingest_context": {"transport": "http_debug", "stored_in_latest_frame_cache": true, "processed_inline": false, "source_health_updated": true, "ros_callback_compatible": true},
  "worker_tick_path": "/api/v1/vision/worker/tick"
}
```

### `GET /api/v1/vision/frame/latest?source={source}`

설명: latest raw frame metadata입니다.

요청: query `source` required.

출력:

```json
{"generated_at": "2026-06-16T09:00:08+09:00", "frame": {"source": "tb3_1_picam", "frame_seq": 1, "image": {"width": 160, "height": 160}, "content_type": "image/jpeg", "size_bytes": 1234}}
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
{
  "requested_source": "tb3_1_picam",
  "sync": {"latest_frame_seq": 1, "latest_overlay_frame_seq": 1, "overlay_lag_frames": 0, "overlay_visual_state": "fresh"},
  "overlay": {"source": "tb3_1_picam", "frame_seq": 1, "event_count": 1, "stale": false, "visual_state": "fresh", "content_type": "image/jpeg"}
}
```

### `GET /api/v1/vision/overlay/latest/image?source={source}`

설명: latest overlay JPEG입니다. Stale overlay는 amber warning band를 포함합니다.

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
{"source": "tb3_1_picam", "marker_id": 7, "marker_size": 96, "padding": 32, "stale": false, "emit": false}
```

출력:

```json
{
  "source": "tb3_1_picam",
  "emitted": false,
  "emit_disabled": false,
  "emit_results": [],
  "events": [{"schema_version": "vision-event.v1", "marker_id": "ARUCO_4X4_50_7"}],
  "overlay": {"source": "tb3_1_picam", "frame_seq": 1, "event_count": 1, "stale": false, "visual_state": "fresh", "content_type": "image/jpeg"}
}
```

### `GET /api/v1/vision/worker/status?source={source}&max_frame_age_s=2.0`

설명: 다음 worker tick preview입니다. Read-only이며 detection/overlay를 실행하지 않습니다.

요청: query `source` optional, `max_frame_age_s` optional.

출력:

```json
{
  "requested_source": "tb3_1_picam",
  "max_frame_age_s": 2.0,
  "debug_only": true,
  "summary": {"sources_total": 1, "pending_count": 1, "would_create_new_evidence_count": 1, "status_counts": {"processed": 1}},
  "sources": [{"source": "tb3_1_picam", "has_frame": true, "pending": true, "next_tick_status": "processed", "evidence_action_if_ticked": "created"}]
}
```

### `POST /api/v1/vision/worker/tick`

설명: one-shot latest-frame processing tick입니다. Debug/control surface이며 ROS motion command를 내지 않습니다.

요청:

```json
{"source": "tb3_1_picam", "force": false, "stale": false, "max_frame_age_s": 2.0}
```

출력:

```json
{
  "requested_source": "tb3_1_picam",
  "force": false,
  "stale": false,
  "summary": {"sources_total": 1, "processed_count": 1, "skipped_count": 0, "new_event_count_total": 1, "reused_event_count_total": 0},
  "results": [{"source": "tb3_1_picam", "status": "processed", "frame_seq": 1, "event_count": 1, "new_event_count": 1, "evidence_action": "created", "overlay": {"frame_seq": 1, "visual_state": "fresh"}}]
}
```

### `POST /api/v1/detect/image`

설명: uploaded image marker detection/debug입니다. Optional WMS emit 가능.

요청: `multipart/form-data`

| field | required | 설명 |
| --- | --- | --- |
| `source` | yes | configured source ID |
| `image` | yes | image file |
| `emit` | no | default `false` |
| `pose_profile` or manual calibration fields | no | ArUco pose estimate optional |

출력:

```json
{"source": "tb3_1_picam", "emitted": false, "emit_disabled": false, "emit_results": [], "events": [{"schema_version": "vision-event.v1", "source": "tb3_1_picam", "event_kind": "CONFIRMED", "class_name": "aruco_marker"}]}
```

### `POST /api/v1/lift-roi/evaluate`

설명: caller-provided bbox/mask candidates를 ROI 기준으로 평가해 `LiftRoiEvidence v1`을 반환합니다.

요청:

```json
{
  "source": "tb3_1_picam",
  "operation": "PICKUP",
  "task_id": "TASK-IN-0001",
  "image": {"width": 640, "height": 480},
  "roi": {"roi_id": "TB3_1_LIFT_ROI", "kind": "LIFT", "polygon_xy": [[220,180],[420,180],[440,360],[200,360]]},
  "expected_count": 1,
  "stable_frames": 3,
  "count_stable": true,
  "lift_sensor": {"lift_up": true},
  "candidates": [{"class_name": "box", "bbox_xyxy": [240,210,310,290], "confidence": 0.91}]
}
```

출력:

```json
{
  "schema_version": "lift-roi-evidence.v1",
  "source": "tb3_1_picam",
  "robot_id": "tb3_1",
  "frame_id": "tb3_1_pi_camera_optical_frame",
  "operation": "PICKUP",
  "load": {"count": 1, "empty": false, "accepted_items": [], "rejected_items": []},
  "verification": {"status": "CONFIRMED | CANDIDATE | FAILED", "reason": "pickup_verified"}
}
```

### `POST /api/v1/lift-roi/evaluate-image`

설명: uploaded image를 optional detector/segmenter로 처리한 뒤 `LiftRoiEvidence v1`을 반환합니다. Model 미설정/불가 시 `503` fail-closed입니다.

요청: `multipart/form-data` with `source`, `operation`, `roi_json`, `image`, optional `task_id`, `expected_count`, `stable_frames`, `count_stable`, lift sensor fields, `dropped_item_count`, `policy_json`.

출력: `LiftRoiEvidence v1` JSON. Model path가 없으면 common error envelope로 `503`.

---

## 2. Main API 계약

### 현재 구현됨: `POST /api/v1/camera/events`

설명: generic camera audit/business event. 상태 전이 없음.

요청:

```json
{"event_id": "11111111-1111-4111-8111-111111111111", "event_type": "PERSON_INTRUSION", "robot_name": "tb3_1", "location": "STORAGE_A", "severity": "WARN", "payload": {"source": "tb3_1_picam"}}
```

출력:

```json
{"ok": true, "message": "camera event accepted"}
```

### Target canonical: `POST /api/v1/vision/events`

설명: Main target VisionEvent canonical ingest. Main 구현 필요.

요청: full `VisionEvent v1` JSON.

출력 accepted:

```json
{"accepted": true, "duplicate": false, "event_id": "11111111-1111-4111-8111-111111111111", "schema_version": "vision-event.v1", "wms_processing_status": "queued"}
```

출력 duplicate:

```json
{"accepted": true, "duplicate": true, "event_id": "11111111-1111-4111-8111-111111111111", "wms_processing_status": "already_seen"}
```

---

## 3. 공통 오류 응답

```json
{
  "error": {
    "code": "BAD_REQUEST | VALIDATION_ERROR | NOT_FOUND | SERVICE_UNAVAILABLE | INTERNAL_ERROR",
    "message": "unknown source: bad_cam",
    "details": [],
    "request_id": "..."
  }
}
```

---

## 4. 검증 상태

2026-06-16 구현 검증:

- `python3 scripts/generate_source_registry_surfaces.py`: OK
- `./scripts/test_ai_server.sh -q`: `129 passed, 1 warning`
- `python3 scripts/validate_contracts.py`: OK
- `python3 scripts/validate_deployment_assets.py`: `Deployment assets validated.`
- `make ros-build-bringup`: `smartfactory_perception_ros`, `smartfactory_bringup` build OK
- ROS app boundary guard: FastAPI app source에 `rclpy`, `sensor_msgs`, `cv_bridge` import/text 없음

실 로봇 탐사는 이번 Lane A/B source registry + ROS handoff prep 구현에는 필요하지 않았습니다. 실제 ROS subscriber/domain bridge runtime 검증은 Lane C passive window에서 진행합니다.
