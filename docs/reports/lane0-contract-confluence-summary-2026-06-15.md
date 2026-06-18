# SmartFactory API 계약 문서 — Lane 0 Vision Gateway 정렬본

**상태:** 2026-06-15 Asia/Seoul 기준 Lane 0 계약 정렬본 + Lane B synthetic frame/worker tick/stream metrics/source snapshot/max_fps/ROS handoff topics/latest raw frame/raw frame ingest/stale worker guard/worker status summary/worker tick summary/ROS ingest policy seam/ROS publish readiness/source filter/stream source filter/metrics source filter/source-scoped discovery links/stream sync status/stream summary/ROS ingest readiness/source snapshot ROS ingest/publish readiness/summary breakdown/requested_source/overlay latest sync/ROS ingest+publish runtime plan/topic exposure policy/summary preflight + debug snapshot/stream discovery mirror/debug source rosbridge subscription hints/ROS ingest adapter contract/ROS debug evidence event readiness mirror/stream evidence event readiness mirror/stream ROS overlay publish readiness mirror/stream ROS ingest readiness mirror/stream runtime policy mirror/stream motion-control safety mirror/Lane B robot-free e2e consistency/multi-source isolation validation/API-served overlay visual QA/multi-source latest-only backpressure validation/worker tick idempotency validation/worker status idempotency preview/OpenAPI drift guard 반영  
**목적:** Main / GUI / Movement / Vision 팀이 같은 API 이름과 반환값을 기준으로 논의하기 위한 압축본  
**주의:** 구현 완료 문서가 아니라 **Lane 0 합의용 계약 문서**입니다. 현재 구현과 target 계약을 구분합니다. 2026-06-18 v2 contract supersedes stream-plane guidance below: Main-facing production video is the source-selected HTTP/MJPEG Vision Stream Gateway on `:8090`; ROS/rosbridge is internal allowlisted operator/prototype infrastructure unless a future ADR promotes it.

---

## 0. Lane 0 채택 결정

2026-06-15 추가 결정 반영:

| 항목 | 채택안 | 의미 |
| --- | --- | --- |
| Interim Main reporting | AI/Vision은 `/api/v1/camera/events`로 임시 보고 | Main의 `/vision/events` 구현 전까지 audit/business event로만 사용. 상태 전이/evidence canonical ingest로 오해 금지. |
| `task_id` | integer/null migration 방향 채택 | Main 표준에 맞춘다. 현재 AI schema/code는 string/null이므로 migration task 필요. |
| `/vision/events` | Main이 Lane A 직후 canonical ingest로 구현 | `/camera/events`는 임시 경로, `/vision/events`가 최종 VisionEvent ingest 경로. |
| dedup | Main에 `inbound_reports` 또는 동등 dedup 저장소 추가 | VisionEvent는 `event_id`, Lift ROI push는 `report_id` 기준 중복 제거. |
| source topic migration | `/mission/...` 회귀 없이 유지 + `/sf/...` 표준 병행 추가 | 기존 GUI/rosbridge topic을 깨지 않고 표준 topic으로 전환. |
| Movement safety | MVP는 Main 보고 우선, direct Movement alert는 별도 승인 후 | Vision은 `/cmd_vel`/Nav2 직접 제어 금지. |
| registry/schema | schema enum을 source registry에서 자동 생성 | `config/vision/sources.yaml`을 source of truth로 두고 schema/OpenAPI/fixture drift 방지. |

---

## 1. 책임 경계

- Vision Gateway(Camera/AI Server): 영상 수신, detection, Lift ROI evidence, overlay/evidence 생성.
- Main Server: task / inventory / robot / source 상태의 최종 판단 및 상태 전이.
- Movement/Safety Controller: stop/slow 등 motion safety 실행 권한.
- Vision Gateway는 Main DB 직접 접근, `/cmd_vel` publish, Nav2 action 호출을 하지 않습니다.

---

## 2. Base URL / Port

| Service | Base | 상태 |
| --- | --- | --- |
| Main API | `http://<main-host>:8080/api/v1` | 확정 |
| Vision/Camera API | `http://<vision-host>:8090/api/v1` | Lane 0 target |
| External env | `CAMERA_API_BASE=http://<vision-host>:8090/api/v1` | 통합용 canonical name |
| Internal alias | `VISION_API_BASE=http://<vision-host>:8090/api/v1` | optional alias only |
| rosbridge stream | `ws://<vision-host>:9090` | browser 영상/overlay 기본 경로 |
| Legacy AI local | `http://127.0.0.1:8100` | 개발/기존 호환 |

---

## 3. 현재 Vision/AI Server API

### `GET /api/v1/health`

서비스 readiness. 모든 카메라 online을 요구하지 않습니다.

```json
{
  "service": "ai-server",
  "status": "ok",
  "service_version": "0.1.0",
  "contract_version": "vision-event.v1",
  "model_status": "loaded",
  "models": {
    "marker": {"status": "loaded", "name": "opencv-marker-detector"},
    "lift_roi": {
      "status": "disabled | loaded | error",
      "task": "segment | detect",
      "path_configured": false,
      "device": "cpu"
    }
  },
  "source_summary": {"configured": 3, "online": 0, "stale": 0, "disabled": 0, "offline": 3},
  "event_retention": {"maxlen": 200, "size": 0}
}
```

### `GET /api/v1/sources`

카메라 source health/registry.

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
      "last_frame_at": "2026-06-15T09:00:00+09:00",
      "last_frame_age_s": 0.12,
      "last_event_at": null,
      "last_event_kind": null,
      "last_event_id": null,
      "last_marker_id": null,
      "frame_count": 10,
      "event_count": 0,
      "target_fps": 10,
      "ros_topic": "/tb3_1/pi_camera/image_raw"
    }
  ]
}
```

### `GET /api/v1/detections/latest?source={source}&limit={1..50}`

Vision Gateway local/debug feed. Main 상태 판단용 source of truth가 아닙니다.

```json
{
  "generated_at": "2026-06-15T09:00:03+09:00",
  "events": [
    {
      "schema_version": "vision-event.v1",
      "event_id": "11111111-1111-4111-8111-111111111111",
      "timestamp": "2026-06-15T09:00:03+09:00",
      "source": "tb3_1_picam",
      "event_kind": "CONFIRMED",
      "class_name": "aruco_marker",
      "confidence": 1.0,
      "robot_id": "tb3_1",
      "frame_id": "tb3_1_pi_camera_optical_frame",
      "metadata": {}
    }
  ]
}
```


### `GET /api/v1/vision/streams?source=tb3_1_picam`

Production/debug stream split discovery API입니다. Production browser stream plane은 `rosbridge 9090`이고, HTTP/MJPEG/frame APIs는 debug/fallback입니다. `topic_exposure_policy`, `topic_exposure_summary`, source별 `topic_exposure`, `rosbridge_subscription_hints`는 GUI가 안전한 rosbridge 구독 topic을 고를 수 있게 하는 read-only hint입니다. Top-level `debug_only`, `motion_command_allowed=false`, `control_topics_published=[]`는 `/api/v1/vision/ros/topics`와 같은 no-motion/no-control 경계입니다. Top-level `runtime_policy`는 `/api/v1/vision/ros/topics`와 같은 HTTP handler/ROS executor 분리 정책이며, stream discovery에서도 ROS2 start/spin/publish 금지 경계를 확인하게 합니다. `ros_ingest_readiness`는 `/api/v1/vision/ros/topics`의 future ROS image subscriber preflight를 stream discovery에도 mirror한 값이며, `summary.ros_ingest_contract_ready_count`, `summary.ros_ingest_runtime_subscriber_active_count`, `summary.ros_ingest_status_counts`는 반환된 source 기준 ingest 계약 준비 상태 집계입니다. `ros_publish_readiness`는 `/api/v1/vision/ros/topics`의 future overlay compressed-image publisher preflight를 stream discovery에도 mirror한 값이며, `summary.ros_publish_ready_count`, `summary.ros_publish_payload_available_count`, `summary.ros_publish_payload_blocked_count`, `summary.ros_publish_status_counts`는 반환된 source 기준 overlay publish 가능 상태 집계입니다. `evidence_event_publish_readiness`는 `/api/v1/vision/ros/topics`의 future `/sf/vision/events` publish preflight를 stream discovery에도 mirror한 값이며, `summary.evidence_event_publish_ready_count`는 반환된 source 중 최신 schema-valid `VisionEvent`가 있어 future publish 가능한 수입니다. Optional `source` query를 지정하면 해당 source만 반환하고, response-level `summary`도 반환된 source rows 기준으로만 집계합니다. Unknown source는 `400`입니다.

Response excerpt:

```json
{
  "generated_at": "2026-06-15T09:00:03+09:00",
  "requested_source": "tb3_1_picam",
  "primary_stream_plane": "rosbridge",
  "rosbridge_url": "ws://<vision-host>:9090",
  "debug_only": true,
  "motion_command_allowed": false,
  "control_topics_published": [],
  "topic_exposure_policy": {
    "policy": "explicit_allowlist_only",
    "rosbridge_exposes_all_topics": false,
    "client_publish_allowed": false,
    "server_publish_control_allowed": false
  },
  "topic_exposure_summary": {
    "sources_total": 1,
    "control_topic_allowed_count": 0,
    "client_publish_allowed_source_count": 0,
    "policy_status": "safe",
    "policy_violation_count": 0,
    "policy_violations": []
  },
  "runtime_policy": {
    "ros2_started_by_http_request": false,
    "recommended_executor": "MultiThreadedExecutor",
    "http_handlers_must_spin_ros2_executor": false,
    "threading_model": "ROS2 executor outside FastAPI request handlers with lock-protected latest-frame handoff"
  },
  "summary": {
    "sources_total": 1,
    "with_frame_count": 1,
    "with_overlay_count": 1,
    "overlay_lag_count": 1,
    "synced_overlay_count": 0,
    "stale_overlay_count": 0,
    "ros_ingest_contract_ready_count": 1,
    "ros_ingest_runtime_subscriber_active_count": 0,
    "ros_ingest_status_counts": {"contract_ready": 1},
    "ros_publish_ready_count": 0,
    "ros_publish_payload_available_count": 0,
    "ros_publish_payload_blocked_count": 1,
    "ros_publish_status_counts": {"overlay_lag": 1},
    "evidence_event_publish_ready_count": 1
  },
  "debug_fallback": {
    "mjpeg_path_template": "/api/v1/vision/stream/{source}.mjpeg",
    "mjpeg_max_fps_default": 10,
    "mjpeg_max_fps_limit": 30,
    "metrics_path": "/api/v1/metrics",
    "ros_handoff_path": "/api/v1/vision/ros/topics"
  },
  "sources": [
    {
      "source": "tb3_1_picam",
      "has_frame": true,
      "has_overlay": true,
      "latest_frame_seq": 2,
      "latest_overlay_frame_seq": 1,
      "overlay_lag_frames": 1,
      "overlay_visual_state": "fresh",
      "mjpeg_path": "/api/v1/vision/stream/tb3_1_picam.mjpeg",
      "frame_metadata_path": "/api/v1/vision/frame/latest?source=tb3_1_picam",
      "overlay_metadata_path": "/api/v1/vision/overlay/latest?source=tb3_1_picam",
      "metrics_path": "/api/v1/metrics?source=tb3_1_picam",
      "ros_handoff_source_path": "/api/v1/vision/ros/topics?source=tb3_1_picam",
      "ros_ingest_readiness": {
        "readiness_state": "contract_ready",
        "physical_input_topic_configured": true,
        "runtime_subscriber_active": false,
        "http_debug_ingest_path": "/api/v1/vision/frame",
        "required_qos_profile": {
          "reliability": "BEST_EFFORT",
          "history": "KEEP_LAST",
          "depth": 1
        }
      },
      "ros_publish_readiness": {
        "latest_frame_seq": 2,
        "latest_overlay_frame_seq": 1,
        "overlay_ready": false,
        "readiness_state": "overlay_lag",
        "publish_payload_preview": {
          "payload_available": false,
          "topic": "/sf/vision/sources/tb3_1_picam/overlay/compressed",
          "message_type": "sensor_msgs/msg/CompressedImage",
          "reason": "overlay image frame_seq does not match latest frame_seq"
        }
      },
      "evidence_event_publish_readiness": {
        "event_available": true,
        "publish_ready": true,
        "topic": "/sf/vision/events",
        "message_type": "smartfactory_msgs/msg/VisionEvent or JSON bridge payload",
        "schema_version": "vision-event.v1",
        "latest_event_kind": "CONFIRMED",
        "dedup_key": "event_id",
        "payload_contains_image_bytes": false
      },
      "stream_metrics": {"frames_sent_total": 2, "approx_fps": 10.0}
    }
  ]
}
```




## Lane B API-served overlay visual QA

Lane B에서 관제/GUI가 실제로 보게 되는 산출물은 JSON metadata만이 아니라 overlay image입니다. 따라서 API가 반환하는 overlay image 자체도 visual QA 대상에 포함했습니다.

테스트 `test_lane_b_api_served_overlay_visual_qa_distinguishes_fresh_and_stale_warning_band`는 다음을 확인합니다.

- `POST /api/v1/vision/synthetic/frame`으로 fresh overlay와 stale overlay를 생성합니다.
- `GET /api/v1/vision/overlay/latest/image`가 반환하는 실제 JPEG를 OpenCV로 decode합니다.
- stale overlay 상단에 full-width amber warning band가 있는지 pixel threshold로 확인합니다.
- stale metadata의 `visual_state=stale`과 `/vision/overlay/latest` sync metadata가 일치하는지 확인합니다.
- 160px synthetic debug frame에서도 warning text와 하단 compact label이 잘리지 않도록 renderer를 조정했습니다.

Visual QA artifact:

```text
docs/reports/lane-b-visual-qa-2026-06-15/
├── fresh_overlay.jpg
├── stale_overlay.jpg
├── fresh_vs_stale_overlay_comparison.jpg
└── README.md
```

현재 결과는 `124 passed, 1 warning`이며 contract fixtures도 기대대로 동작합니다. 이 visual QA도 Lane B 범위라 ROS2를 시작하지 않고, ROS topic을 publish하지 않으며, JSON metadata에 image bytes를 넣지 않고, `/cmd_vel`/Nav2/control API를 호출하지 않습니다.

## Lane B robot-free 통합 검증

Lane B는 작은 API/metadata slice들이 많이 쌓였기 때문에, 이제 개별 필드 검증뿐 아니라 전체 흐름 검증도 포함합니다.

통합 테스트 `test_lane_b_robot_free_e2e_surfaces_stay_consistent_across_stream_debug_ros_and_metrics`는 다음 흐름을 한 번에 확인합니다.

1. `POST /api/v1/vision/frame`로 raw latest frame 저장. 이 단계에서는 detection/overlay를 inline 실행하지 않습니다.
2. `GET /api/v1/vision/worker/status`로 worker tick pending 상태 확인.
3. `POST /api/v1/vision/worker/tick`으로 `VisionEvent`와 overlay 생성.
4. latest frame image와 overlay image가 실제 artifact로 조회되는지 확인.
5. `/vision/streams`, `/vision/debug/sources`, `/vision/ros/topics`, `/metrics`가 frame seq, overlay seq, ROS ingest readiness, ROS overlay publish readiness, evidence event publish readiness, no-motion/no-control flag, worker/frame metrics에 대해 같은 상태를 말하는지 비교.
6. 새 raw frame을 다시 넣어 overlay lag를 만들고, 모든 discovery surface가 overlay publish payload blocked 상태로 같은 결론을 내는지 확인.

검증 명령:

```bash
./scripts/test_ai_server.sh -q tests/test_api.py tests/test_contract_boundaries.py
./scripts/test_ai_server.sh -q
```

추가로 `test_lane_b_multi_source_e2e_keeps_frame_overlay_event_and_metrics_isolated`는 실제 목표인 다중 카메라 상황을 가정합니다. `tb3_1_picam`과 `tb3_2_picam`에 raw frame을 각각 넣은 뒤 한 source만 worker tick 처리하고, 처리된 source는 `ready_fresh`, 대기 source는 `no_overlay`, global source는 `no_frame`으로 남는지 `/vision/streams`, `/vision/debug/sources`, `/vision/ros/topics`, source-filtered `/metrics`에서 비교합니다. 이후 두 번째 source를 처리하면 publish/event readiness count가 2로 올라가되 global source는 오염되지 않아야 합니다.

`test_lane_b_multi_source_latest_only_backpressure_drops_old_frames_per_source`는 실제 다중 카메라 frame burst 상황을 검증합니다. `tb3_1_picam`에 3개, `tb3_2_picam`에 2개의 raw frame이 빠르게 들어와도 source별 latest frame만 남고 dropped-frame counter가 `tb3_1_picam=2`, `tb3_2_picam=1`로 분리됩니다. 전체 worker tick은 각 source의 최신 frame seq만 처리하고, 두 robot source는 `ready_fresh`가 되며, 이후 `tb3_1_picam`에만 새 frame을 넣으면 해당 source만 `overlay_lag`/publish blocked가 되고 `tb3_2_picam`은 `ready_fresh`로 유지되어야 합니다. 이 상태는 `/vision/streams`, `/vision/debug/sources`, `/vision/ros/topics`, source-filtered `/metrics`에서 함께 확인됩니다.

`test_lane_b_worker_tick_is_idempotent_and_does_not_duplicate_evidence_events`는 이미 최신 overlay와 frame이 동기화된 source를 다시 worker tick했을 때 중복 evidence가 생기지 않는지 검증합니다. 첫 tick은 두 robot source에서 새 evidence를 만들며 `new_event_count_total=2`를 반환합니다. 같은 frame에 대한 두 번째 tick은 두 source 모두 `skipped`, `evidence_action=reused`, `new_event_count_total=0`이어야 하며, `/detections/latest`와 `/metrics.event_store.current_size`는 event ID와 event 개수가 그대로임을 보여야 합니다. 이로써 Lane C/Main dedup 구현 전에도 Lane B worker가 같은 최신 frame을 반복 처리해 event store를 부풀리지 않는다는 기본 idempotency가 확인됩니다.

`test_vision_worker_status_reports_pending_skipped_and_stale_without_processing`는 이제 read-only 상태 preview도 idempotency 의미를 미리 보여주는지 확인합니다. 처리 전 pending source는 `would_create_new_evidence=true`, `evidence_action_if_ticked=created`이고, overlay가 이미 동기화된 source는 `evidence_action_if_ticked=reused`, `expected_new_event_count=0`, `reused_event_count_if_ticked=1`입니다. stale/no-frame source는 `none`과 zero count를 유지합니다.

`test_generated_openapi_artifact_matches_current_app_schema`는 `docs/contracts/ai-server-openapi.json`이 현재 FastAPI `app.openapi()` 결과와 정확히 일치하는지 확인합니다. Lane B에서 worker/status, stream, overlay, ROS handoff 필드를 바꾼 뒤 OpenAPI handoff 문서가 뒤처지는 문제를 막는 final contract freeze guard입니다.

현재 결과는 `125 passed, 1 warning`이며 contract fixtures도 기대대로 동작합니다. 이 통합 검증도 Lane B 범위라 ROS2를 시작하지 않고, ROS topic을 publish하지 않으며, JSON metadata에 image bytes를 넣지 않고, `/cmd_vel`/Nav2/control API를 호출하지 않습니다.

### `GET /api/v1/metrics?source=tb3_1_picam`

Vision Gateway local observability입니다. Main/WMS 상태 API가 아니며, Lane B debug/fallback stream 관찰용 counters를 포함합니다. Optional `source` query를 지정하면 Lane B `stream`, `worker`, `frame_store` counters가 해당 source 기준으로 좁혀집니다. HTTP/model counters는 service-level입니다. Unknown source는 `400`입니다.

Response excerpt:

```json
{
  "generated_at": "2026-06-15T09:00:06+09:00",
  "requested_source": "tb3_1_picam",
  "metrics": {
    "stream": {
      "clients_total": 1,
      "active_clients_total": 0,
      "frames_sent_total": 2,
      "stale_polls_total": 1,
      "by_source": {
        "tb3_1_picam": {
          "clients_total": 1,
          "active_clients": 0,
          "frames_sent_total": 2,
          "stale_polls_total": 1,
          "approx_fps": 10.0
        }
      }
    },
    "worker": {
      "tick_total": {"processed": 1, "skipped": 1},
      "by_source": {"tb3_1_picam": {"processed": 1, "skipped": 1}}
    }
  },
  "frame_store": {
    "sources_with_frames": 1,
    "frame_seq_by_source": {"tb3_1_picam": 2},
    "dropped_frames_by_source": {"tb3_1_picam": 1},
    "dropped_frames_total": 1
  }
}
```

`stream` metrics는 local MJPEG debug/fallback stream 전용입니다. Production browser stream은 rosbridge `9090`입니다.
`dropped_frames_total`은 latest-frame cache에서 새 frame이 들어와 기존 frame snapshot이 덮어써진 횟수입니다.

### `POST /api/v1/detect/image`

업로드 이미지 marker detection/debug. `emit=true`일 때 Main/WMS로 best-effort emit 가능.

Request: `multipart/form-data`

| Field | Required | Note |
| --- | --- | --- |
| `source` | yes | `global_cam_01`, `tb3_1_picam`, `tb3_2_picam` |
| `image` | yes | image file |
| `emit` | no | default false |
| `pose_profile`, `marker_size_m`, `camera_fx/fy/cx/cy`, `camera_dist_coeffs` | no | optional pose/calibration |

Response:

```json
{
  "source": "tb3_1_picam",
  "emitted": false,
  "emit_disabled": false,
  "emit_results": [
    {
      "event_id": "11111111-1111-4111-8111-111111111111",
      "attempted": true,
      "ok": true,
      "status_code": 202,
      "error": null,
      "response": {"accepted": true}
    }
  ],
  "events": [
    {
      "schema_version": "vision-event.v1",
      "event_id": "11111111-1111-4111-8111-111111111111",
      "timestamp": "2026-06-15T09:00:03+09:00",
      "source": "tb3_1_picam",
      "event_kind": "CONFIRMED",
      "class_name": "aruco_marker",
      "confidence": 1.0,
      "robot_id": "tb3_1",
      "frame_id": "tb3_1_pi_camera_optical_frame",
      "metadata": {}
    }
  ]
}
```


### `GET /api/v1/vision/debug/sources?source=tb3_1_picam`

Lane B source readiness snapshot입니다. GUI/Main 개발자가 MJPEG stream을 열지 않고도 frame/overlay/metrics/ROS ingest/publish 준비상태를 확인하는 debug/fallback API입니다. Production stream plane은 계속 rosbridge `9090`입니다.

Query: optional `source`; 생략하면 configured source 전체.

Response excerpt:

```json
{
  "generated_at": "2026-06-15T09:00:06+09:00",
  "primary_stream_plane": "rosbridge",
  "requested_source": "tb3_1_picam",
  "debug_only": true,
  "summary": {
    "sources_total": 1,
    "with_frame_count": 1,
    "with_overlay_count": 1,
    "overlay_lag_count": 0,
    "ros_ingest_contract_ready_count": 1,
    "ros_publish_ready_count": 1,
    "ros_publish_payload_available_count": 1,
    "evidence_event_publish_ready_count": 1,
    "stale_overlay_count": 0,
    "health_status_counts": {"online": 1},
    "ros_ingest_status_counts": {"contract_ready": 1},
    "ros_publish_status_counts": {"ready_fresh": 1}
  },
  "sources": [
    {
      "source": "tb3_1_picam",
      "kind": "robot_pi_camera",
      "robot_id": "tb3_1",
      "health": {"status": "online", "frame_count": 2, "event_count": 2},
      "latest_frame": {"frame_seq": 2, "size_bytes": 1234},
      "latest_overlay": {"frame_seq": 2, "event_count": 1, "visual_state": "fresh"},
      "overlay_lag_frames": 0,
      "topic_exposure": {
        "allowed_browser_topics": [
          "/mission/tb3_1/camera/compressed",
          "/sf/vision/sources/tb3_1_picam/image/compressed",
          "/sf/vision/sources/tb3_1_picam/overlay/compressed"
        ],
        "allowed_ingest_topics": ["/tb3_1/pi_camera/image_raw"],
        "allowed_publish_topics": [
          "/sf/vision/sources/tb3_1_picam/image/compressed",
          "/sf/vision/sources/tb3_1_picam/overlay/compressed",
          "/sf/vision/events"
        ],
        "client_publish_allowed": false,
        "control_topics_allowed": []
      },
      "rosbridge_subscription_hints": {
        "allowed_browser_topics": [
          "/mission/tb3_1/camera/compressed",
          "/sf/vision/sources/tb3_1_picam/image/compressed",
          "/sf/vision/sources/tb3_1_picam/overlay/compressed"
        ],
        "recommended_image_topic": "/sf/vision/sources/tb3_1_picam/image/compressed",
        "recommended_overlay_topic": "/sf/vision/sources/tb3_1_picam/overlay/compressed",
        "legacy_browser_topic": "/mission/tb3_1/camera/compressed",
        "client_publish_allowed": false,
        "control_topics_allowed": []
      },
      "ros_ingest_readiness": {
        "readiness_state": "contract_ready",
        "physical_input_topic_configured": true,
        "runtime_subscriber_active": false,
        "http_debug_ingest_path": "/api/v1/vision/frame",
        "runtime_plan": {
          "executor": "MultiThreadedExecutor",
          "spin_location": "background_thread",
          "http_handler_role": "read_latest_state_only_never_spin_ros2",
          "target_frame_store_source": "tb3_1_picam"
        }
      },
      "ros_publish_readiness": {
        "latest_frame_seq": 2,
        "latest_overlay_frame_seq": 2,
        "overlay_ready": true,
        "readiness_state": "ready_fresh",
        "overlay_visual_state": "fresh",
        "publish_payload_preview": {
          "payload_available": true,
          "topic": "/sf/vision/sources/tb3_1_picam/overlay/compressed",
          "message_type": "sensor_msgs/msg/CompressedImage",
          "frame_seq": 2,
          "content_type": "image/jpeg",
          "size_bytes": 4567,
          "reason": "overlay image is ready for a future background ROS publisher"
        }
      },
      "evidence_event_publish_readiness": {
        "event_available": true,
        "publish_ready": true,
        "topic": "/sf/vision/events",
        "message_type": "smartfactory_msgs/msg/VisionEvent or JSON bridge payload",
        "schema_version": "vision-event.v1",
        "latest_event_id": "11111111-1111-4111-8111-111111111111",
        "latest_event_kind": "CONFIRMED",
        "latest_event_timestamp": "2026-06-15T09:00:03+09:00",
        "dedup_key": "event_id",
        "payload_contains_image_bytes": false,
        "reason": "latest schema-valid VisionEvent is available for future ROS evidence publisher"
      },
      "debug_paths": {
        "frame_ingest": "/api/v1/vision/frame",
        "mjpeg": "/api/v1/vision/stream/tb3_1_picam.mjpeg",
        "mjpeg_default_max_fps": 10,
        "frame_metadata": "/api/v1/vision/frame/latest?source=tb3_1_picam",
        "frame_image": "/api/v1/vision/frame/latest/image?source=tb3_1_picam",
        "overlay_metadata": "/api/v1/vision/overlay/latest?source=tb3_1_picam",
        "overlay_image": "/api/v1/vision/overlay/latest/image?source=tb3_1_picam",
        "worker_tick": "/api/v1/vision/worker/tick",
        "metrics": "/api/v1/metrics",
        "ros_handoff": "/api/v1/vision/ros/topics"
      },
      "stream_metrics": {"frames_sent_total": 1, "approx_fps": 0.0},
      "drop_metrics": {"dropped_frames": 1}
    }
  ]
}
```

`overlay_lag_frames > 0`이면 newer latest frame이 있지만 overlay가 아직 그 frame까지 따라오지 않았다는 뜻입니다. Debug mode에서는 `/api/v1/vision/worker/tick`으로 재처리할 수 있습니다. `requested_source`는 optional source filter를 echo합니다. `topic_exposure_policy`, `topic_exposure_summary`, source별 `topic_exposure`, `rosbridge_subscription_hints`는 `/api/v1/vision/ros/topics`와 `/api/v1/vision/streams`의 ROS/rosbridge allowlist preflight 및 권장 image/overlay 구독 topic과 같은 의미입니다. `debug_only`, `motion_command_allowed=false`, `control_topics_published=[]`는 stream discovery에서도 no-motion/no-control 경계를 노출합니다. `runtime_policy`는 `/api/v1/vision/ros/topics`와 같은 HTTP handler/ROS executor 분리 정책입니다. `summary`는 반환된 source rows 기준으로 계산됩니다. `source` query가 있으면 해당 source 1개만 집계합니다. `health_status_counts`, `ros_ingest_status_counts`, `ros_publish_status_counts`는 같은 rows의 상태별 breakdown입니다. `ros_ingest_readiness`와 `ros_publish_readiness`는 `/api/v1/vision/ros/topics?source=...`의 per-source ingest/publish preflight와 같은 의미이며 stream discovery에도 mirror됩니다. ROS2를 시작하거나 overlay를 publish하지 않습니다. `ros_publish_readiness.publish_payload_preview`는 future background publisher가 해당 source의 cached compressed overlay를 publish해도 되는지 보여줍니다. `ros_publish_readiness`는 해당 source가 현재 future overlay compressed-image publish 가능한 최신 overlay payload를 갖고 있는지 보여줍니다. `evidence_event_publish_readiness`는 해당 source가 현재 future `/sf/vision/events` publish 가능한 최신 `VisionEvent`를 갖고 있는지 보여줍니다. `summary.ros_ingest_contract_ready_count`, `summary.ros_ingest_runtime_subscriber_active_count`, `summary.ros_ingest_status_counts`, `summary.ros_publish_ready_count`, `summary.ros_publish_payload_available_count`, `summary.ros_publish_payload_blocked_count`, `summary.ros_publish_status_counts`, `summary.evidence_event_publish_ready_count`는 반환된 source 중 ingest/publish 가능한 상태 집계입니다.
Errors: unknown source는 `400`.

### `GET /api/v1/vision/overlay/latest?source=tb3_1_picam`

Latest visual-evidence overlay metadata입니다. `sync`는 반환된 overlay가 최신 frame과 맞는지 보여주는 read-only metadata이며 ROS2를 시작하거나 overlay를 publish하지 않습니다.

```json
{
  "generated_at": "2026-06-15T09:00:03+09:00",
  "requested_source": "tb3_1_picam",
  "sync": {
    "latest_frame_seq": 2,
    "latest_overlay_frame_seq": 1,
    "overlay_lag_frames": 1,
    "overlay_visual_state": "fresh"
  },
  "overlay": {
    "source": "tb3_1_picam",
    "frame_seq": 1,
    "event_count": 1,
    "visual_state": "fresh",
    "content_type": "image/jpeg"
  }
}
```

`overlay_lag_frames > 0`이면 newer latest frame이 있지만 overlay가 아직 그 frame까지 따라오지 않았다는 뜻입니다.

### `GET /api/v1/vision/ros/topics`

Lane B/C ROS2/domain-bridge handoff matrix입니다. 실제 ROS2 node를 시작하거나 publish/subscribe하지 않는 read-only 계약 API입니다. Production browser stream plane은 계속 rosbridge `9090`이고, HTTP/MJPEG는 debug/fallback입니다.

Query: optional `source`; 생략하면 전체 source, 지정하면 해당 source만 반환합니다. Unknown source는 `400`입니다.

Response excerpt:

```json
{
  "generated_at": "2026-06-15T09:00:07+09:00",
  "requested_source": "tb3_1_picam",
  "primary_stream_plane": "rosbridge",
  "rosbridge_url": "ws://<vision-host>:9090",
  "debug_only": true,
  "motion_command_allowed": false,
  "migration_policy": "keep existing /mission browser topics; add /sf normalized topics in parallel",
  "control_topics_published": [],
  "topic_exposure_policy": {
    "policy": "explicit_allowlist_only",
    "rosbridge_exposes_all_topics": false,
    "browser_primary_transport": "rosbridge",
    "allowed_message_types": [
      "sensor_msgs/msg/CompressedImage",
      "smartfactory_msgs/msg/VisionEvent or JSON bridge payload"
    ],
    "forbidden_topic_globs": [
      "/cmd_vel", "*/cmd_vel", "/navigate_to_pose", "/follow_path",
      "/parameter_events", "/rosout", "/tf", "/tf_static"
    ],
    "forbidden_capabilities": [
      "motion_command_publish", "nav2_action_call", "parameter_mutation", "raw_dds_forwarding"
    ],
    "client_publish_allowed": false,
    "server_publish_control_allowed": false,
    "auth_required_when_exposed_beyond_private_network": true
  },
  "topic_exposure_summary": {
    "sources_total": 3,
    "allowed_browser_topic_count": 8,
    "allowed_ingest_topic_count": 3,
    "allowed_publish_topic_count": 7,
    "control_topic_allowed_count": 0,
    "client_publish_allowed_source_count": 0,
    "forbidden_topic_glob_count": 8,
    "forbidden_capability_count": 4,
    "explicit_allowlist_only": true,
    "rosbridge_exposes_all_topics": false,
    "server_publish_control_allowed": false,
    "policy_status": "safe",
    "policy_violation_count": 0,
    "policy_violations": []
  },
  "image_ingest_qos": {"reliability": "BEST_EFFORT", "history": "KEEP_LAST", "depth": 1},
  "frame_drop_policy": {
    "cache": "latest_only",
    "drop_stale_frames": true,
    "stale_after_s": 2.0,
    "offline_after_s": 30.0,
    "backpressure": "overwrite_latest_frame_per_source"
  },
  "overlay_publish_qos": {"reliability": "BEST_EFFORT", "history": "KEEP_LAST", "depth": 1, "durability": "VOLATILE"},
  "overlay_publish_policy": {
    "message_type": "sensor_msgs/msg/CompressedImage",
    "encoding": "jpeg",
    "publish_when": "publish_payload_preview.payload_available_true",
    "drop_when": ["no_frame", "no_overlay", "overlay_lag"],
    "max_publish_fps": 10,
    "queue_policy": "keep_last_1_drop_old_overlay",
    "include_stale_warning_band": true,
    "publish_lagging_overlay": false,
    "publish_control_topics": false,
    "http_handlers_may_publish": false
  },
  "evidence_event_publish_policy": {
    "topic": "/sf/vision/events",
    "message_type": "smartfactory_msgs/msg/VisionEvent or JSON bridge payload",
    "schema_version": "vision-event.v1",
    "qos_profile": {"reliability": "RELIABLE", "history": "KEEP_LAST", "depth": 10, "durability": "VOLATILE"},
    "publish_when": "worker_tick_or_detector_emits_schema_valid_vision_event",
    "dedup_key": "event_id",
    "source_of_truth": "Main/WMS remains authoritative; Vision publishes evidence only",
    "publish_control_topics": false,
    "http_handlers_may_publish": false,
    "payload_contains_image_bytes": false
  },
  "runtime_policy": {
    "ros2_started_by_http_request": false,
    "recommended_executor": "MultiThreadedExecutor",
    "http_handlers_must_spin_ros2_executor": false
  },
  "ingest_readiness_summary": {
    "sources_total": 3,
    "contract_ready_count": 3,
    "missing_physical_topic_count": 0,
    "runtime_subscriber_active_count": 0,
    "status_counts": {"contract_ready": 3, "missing_physical_topic": 0}
  },
  "publish_readiness_summary": {
    "sources_total": 3,
    "overlay_ready_count": 1,
    "publish_payload_available_count": 1,
    "publish_payload_blocked_count": 2,
    "overlay_lag_count": 0,
    "no_overlay_count": 0,
    "no_frame_count": 2,
    "status_counts": {"no_frame": 2, "no_overlay": 0, "overlay_lag": 0, "ready_fresh": 1, "ready_stale": 0}
  },
  "sources": [
    {
      "source": "tb3_1_picam",
      "kind": "robot_pi_camera",
      "robot_id": "tb3_1",
      "frame_id": "tb3_1_pi_camera_optical_frame",
      "physical_input_topic": "/tb3_1/pi_camera/image_raw",
      "physical_input_message_type": "sensor_msgs/msg/Image",
      "legacy_browser_topic": "/mission/tb3_1/camera/compressed",
      "legacy_browser_message_type": "sensor_msgs/msg/CompressedImage",
      "normalized_image_topic": "/sf/vision/sources/tb3_1_picam/image/compressed",
      "normalized_image_message_type": "sensor_msgs/msg/CompressedImage",
      "normalized_overlay_topic": "/sf/vision/sources/tb3_1_picam/overlay/compressed",
      "normalized_overlay_message_type": "sensor_msgs/msg/CompressedImage",
      "evidence_event_topic": "/sf/vision/events",
      "qos_profile": {"reliability": "BEST_EFFORT", "history": "KEEP_LAST", "depth": 1},
      "frame_drop_policy": {"cache": "latest_only", "drop_stale_frames": true},
      "overlay_publish_qos": {"reliability": "BEST_EFFORT", "history": "KEEP_LAST", "depth": 1, "durability": "VOLATILE"},
      "overlay_publish_policy": {
        "message_type": "sensor_msgs/msg/CompressedImage",
        "encoding": "jpeg",
        "publish_when": "publish_payload_preview.payload_available_true",
        "drop_when": ["no_frame", "no_overlay", "overlay_lag"],
        "max_publish_fps": 10,
        "queue_policy": "keep_last_1_drop_old_overlay",
        "include_stale_warning_band": true,
        "publish_lagging_overlay": false,
        "publish_control_topics": false,
        "http_handlers_may_publish": false
      },
      "ingest_readiness": {
        "readiness_state": "contract_ready",
        "physical_input_topic_configured": true,
        "runtime_subscriber_active": false,
        "http_debug_ingest_path": "/api/v1/vision/frame",
        "required_qos_profile": {"reliability": "BEST_EFFORT", "history": "KEEP_LAST", "depth": 1},
        "frame_drop_policy": {"cache": "latest_only", "drop_stale_frames": true},
        "runtime_plan": {
          "node_name": "smartfactory_vision_gateway",
          "executor": "MultiThreadedExecutor",
          "spin_location": "background_thread",
          "ingest_adapter": "_store_latest_frame_from_bytes",
          "ingest_adapter_contract": {
            "updates_source_health": true,
            "runs_detection_inline": false,
            "renders_overlay_inline": false,
            "safe_for_http_handlers": true
          },
          "shared_state": "LatestFrameStore",
          "http_handler_role": "read_latest_state_only_never_spin_ros2",
          "target_frame_store_source": "tb3_1_picam"
        },
        "reason": "physical ROS image topic is configured; Lane C can attach a subscriber"
      },
      "publish_readiness": {
        "latest_frame_seq": 1,
        "latest_overlay_frame_seq": 1,
        "frame_age_s": 0.12,
        "overlay_ready": true,
        "readiness_state": "ready_fresh",
        "overlay_visual_state": "fresh",
        "event_count": 1,
        "publish_payload_preview": {
          "payload_available": true,
          "topic": "/sf/vision/sources/tb3_1_picam/overlay/compressed",
          "message_type": "sensor_msgs/msg/CompressedImage",
          "frame_seq": 1,
          "content_type": "image/jpeg",
          "size_bytes": 4567,
          "reason": "overlay image is ready for a future background ROS publisher"
        },
        "runtime_plan": {
          "node_name": "smartfactory_vision_gateway",
          "executor": "MultiThreadedExecutor",
          "spin_location": "background_thread",
          "publisher_callback": "read_latest_overlay_then_publish_compressed_image_when_ready",
          "publish_adapter": "_overlay_publish_payload_preview_for_source",
          "publish_adapter_contract": {
            "input": "source plus latest frame and overlay cache state",
            "output": "publishable compressed overlay metadata when overlay is ready",
            "reads_latest_overlay_cache": true,
            "requires_frame_overlay_seq_match": true,
            "publishes_lagging_overlay": false,
            "publishes_control_topics": false,
            "safe_for_http_handlers": true
          },
          "shared_state": "LatestEvidenceCache plus overlay image cache",
          "shared_state_guard": "threading.Lock around overlay image cache",
          "publish_topic": "/sf/vision/sources/tb3_1_picam/overlay/compressed",
          "publish_message_type": "sensor_msgs/msg/CompressedImage",
          "publish_qos_profile": {"reliability": "BEST_EFFORT", "history": "KEEP_LAST", "depth": 1, "durability": "VOLATILE"},
          "publish_policy": {
            "message_type": "sensor_msgs/msg/CompressedImage",
            "encoding": "jpeg",
            "publish_when": "publish_payload_preview.payload_available_true",
            "drop_when": ["no_frame", "no_overlay", "overlay_lag"],
            "max_publish_fps": 10,
            "queue_policy": "keep_last_1_drop_old_overlay",
            "include_stale_warning_band": true,
            "publish_lagging_overlay": false,
            "publish_control_topics": false,
            "http_handlers_may_publish": false
          },
          "publish_condition": "overlay_ready_true_and_latest_overlay_frame_seq_matches_latest_frame_seq",
          "stale_behavior": "publish_ready_stale_overlay_with_visual_warning_band",
          "lag_behavior": "do_not_publish_lagging_overlay",
          "http_handler_role": "read_latest_state_only_never_publish_ros2",
          "control_publish_allowed": false,
          "startup_owner": "process_startup_or_launch_file_not_http_request",
          "shutdown_owner": "process_signal_handler_or_lifespan_cleanup"
        },
        "reason": "latest overlay matches latest frame"
      },
      "ingest_status": "planned",
      "overlay_publish_status": "planned"
    }
  ]
}
```

`control_topics_published`는 의도적으로 빈 배열입니다. Vision Gateway는 `/cmd_vel` publish 또는 Nav2 action 호출을 하지 않습니다. `image_ingest_qos`, `frame_drop_policy`, `overlay_publish_qos`, `overlay_publish_policy`, `evidence_event_publish_policy`, `runtime_policy`는 Lane C 구현자가 따라야 할 ROS ingest/publish seam입니다. 즉 sensor QoS/keep-last=1, source별 latest-only handoff, HTTP request handler 내부 ROS2 spin 금지를 명시합니다. `ingest_readiness_summary`와 source별 `ingest_readiness`는 future ROS image subscriber용 read-only preflight이며 `contract_ready`, `missing_physical_topic`를 구분합니다. Lane B에서는 실제 ROS subscriber를 시작하지 않으므로 `runtime_subscriber_active=false`입니다. `runtime_plan`은 Lane C 구현 시 ROS2 executor를 background thread에서 돌리고, callback은 HTTP debug ingest와 같은 `_store_latest_frame_from_bytes` adapter를 통해 `LatestFrameStore`에 최신 frame만 저장하며, HTTP handler는 cached state만 읽고 `rclpy.spin*`을 호출하지 말라는 구현 모양을 명시합니다. 해당 adapter는 source health만 갱신하고 detection/overlay는 inline으로 실행하지 않습니다. `publish_readiness_summary`와 source별 `publish_readiness`는 future ROS overlay publisher용 read-only preflight이며 `no_frame`, `no_overlay`, `overlay_lag`, `ready_fresh`, `ready_stale`를 구분합니다. publish-side `runtime_plan`은 background publisher가 overlay cache를 읽고, `_overlay_publish_payload_preview_for_source` adapter contract를 사용하며, `overlay_ready=true`일 때만 compressed overlay image를 publish하고, lagging overlay는 publish하지 않고, stale overlay는 warning band가 포함된 상태로만 publish해야 함을 명시합니다. `publish_payload_preview`는 future ROS publisher가 publish해도 되는 compressed overlay metadata를 보여주는 read-only 값이며 JSON으로 image bytes를 노출하지 않습니다. `publish_payload_available_count`/`publish_payload_blocked_count`는 반환된 source rows 기준 dashboard 집계입니다. `overlay_publish_qos`와 `overlay_publish_policy`는 future publisher가 BEST_EFFORT/KEEP_LAST/depth=1, JPEG compressed image, max 10 FPS, lagging overlay publish 금지, control topic publish 금지, HTTP handler publish 금지를 따라야 함을 구조화합니다. `evidence_event_publish_policy`는 `/sf/vision/events` future evidence event publisher가 schema-valid `VisionEvent v1`, RELIABLE/KEEP_LAST/depth=10, `event_id` dedup key, image bytes 없음, control topic 없음, Main/WMS authoritative 경계를 따라야 함을 명시합니다. `evidence_event_publish_readiness`와 `evidence_event_publish_readiness_summary`는 반환된 source가 현재 future publish 가능한 최신 VisionEvent를 갖고 있는지 보여주는 read-only preflight입니다. motion/control topic publish는 계속 금지입니다. `topic_exposure_summary`는 반환된 source rows 기준 allowlist 집계이며 source filter가 있으면 해당 source 기준으로 좁혀집니다. `control_topic_allowed_count=0`, `client_publish_allowed_source_count=0`, `rosbridge_exposes_all_topics=false`, `policy_status=safe`, `policy_violation_count=0`이 안전 기본값입니다. 향후 설정/registry drift로 control topic이나 client publish가 들어오면 `policy_status=unsafe`와 `policy_violations[]`로 드러나야 합니다. `topic_exposure_policy`는 rosbridge/browser plane이 explicit allowlist 방식이어야 하며, `/cmd_vel`, Nav2 action, parameter mutation, raw DDS forwarding, `/tf`, `/rosout` 같은 범용 내부 topic을 Vision Gateway/GUI plane에 노출하지 말라는 보안/안전 경계를 명시합니다. `source` query가 있으면 summary도 해당 source 기준으로 계산됩니다.

### `POST /api/v1/vision/frame`

Lane B raw frame ingest seam입니다. 업로드 이미지를 latest-frame cache에 저장하지만 detection/overlay 처리는 하지 않습니다. 이후 `/api/v1/vision/worker/tick`으로 처리할 수 있습니다. ROS2 실제 subscribe/publish를 시작하지 않는 debug/fallback API이며 production stream plane이 아닙니다.

Request: `multipart/form-data` with `source`, `image`.

Response excerpt:

```json
{
  "source": "tb3_1_picam",
  "processed": false,
  "frame": {"source": "tb3_1_picam", "frame_seq": 1, "content_type": "image/png", "size_bytes": 1234},
  "overlay": null,
  "ingest_context": {
    "transport": "http_debug",
    "topic": null,
    "stored_in_latest_frame_cache": true,
    "processed_inline": false,
    "source_health_updated": true,
    "ros_callback_compatible": true
  },
  "worker_tick_path": "/api/v1/vision/worker/tick"
}
```

`ingest_context`는 이 HTTP debug endpoint가 future ROS subscriber callback과 같은 latest-frame ingest adapter를 사용한다는 확인값입니다. frame 저장/source health 갱신만 수행하고 detection/overlay는 inline 실행하지 않습니다.

Errors: unknown source 또는 undecodable image는 `400`, form validation은 `422`.

### `GET /api/v1/vision/frame/latest?source=tb3_1_picam`

Lane B raw frame debug metadata API입니다. Latest-frame cache의 가장 최신 원본 frame metadata만 반환합니다. Historical frame 저장소가 아니며 production stream plane도 아닙니다.

Response excerpt:

```json
{
  "generated_at": "2026-06-15T09:00:08+09:00",
  "frame": {
    "source": "tb3_1_picam",
    "frame_seq": 2,
    "frame_timestamp": "2026-06-15T09:00:05+09:00",
    "image": {"width": 160, "height": 160},
    "content_type": "image/jpeg",
    "size_bytes": 1234
  }
}
```

Errors: unknown source는 `400`, 아직 frame이 없으면 `404`.

### `GET /api/v1/vision/frame/latest/image?source=tb3_1_picam`

Lane B raw frame image debug API입니다. GUI/QA가 원본 frame과 `/api/v1/vision/overlay/latest/image`를 비교할 수 있게 합니다. Response `200`은 cached frame `content_type`의 binary image이며 보통 `image/jpeg`입니다. Errors: unknown source는 `400`, 아직 frame이 없으면 `404`.

### `POST /api/v1/vision/synthetic/frame`

Robot-free Lane B 검증용 synthetic ArUco frame ingest입니다. 실제 카메라/ROS2 없이도
latest-frame cache → marker detection → overlay render 경로가 동작하는지 확인합니다.
Production camera ingest가 아니며, production browser stream plane은 계속 rosbridge `9090`입니다.

Request: `application/json`

| Field | Required | Note |
| --- | --- | --- |
| `source` | yes | `global_cam_01`, `tb3_1_picam`, `tb3_2_picam` |
| `marker_id` | no | ArUco `DICT_4X4_50` marker ID `0..49`, default `7` |
| `marker_size` | no | marker pixel size `16..512`, default `96` |
| `padding` | no | white border pixel size `0..512`, default `32` |
| `stale` | no | overlay stale visual/metadata 검증용 flag, default `false` |
| `emit` | no | `/detect/image`와 동일; `WMS_EMIT_ENABLED=true`가 아니면 실제 emit 없음 |

Response:

```json
{
  "source": "tb3_2_picam",
  "emitted": false,
  "emit_disabled": false,
  "emit_results": [],
  "events": [
    {
      "schema_version": "vision-event.v1",
      "marker_id": "ARUCO_4X4_50_9"
    }
  ],
  "overlay": {
    "source": "tb3_2_picam",
    "frame_seq": 1,
    "frame_timestamp": "2026-06-15T09:00:02+09:00",
    "evidence_timestamp": "2026-06-15T09:00:03+09:00",
    "overlay_timestamp": "2026-06-15T09:00:03+09:00",
    "latency_ms": 3.5,
    "event_count": 1,
    "stale": true,
    "visual_state": "stale",
    "image": {"width": 160, "height": 160},
    "content_type": "image/jpeg"
  }
}
```

`events[]`는 실제 응답에서 full `VisionEvent v1`입니다. 위 예시는 전달용 축약본입니다.
Errors: unknown source는 `400`, body validation은 `422`.
`visual_state`는 `fresh|stale`이며 stale overlay JPEG에는 full-width amber warning band가 들어갑니다.

### `GET /api/v1/vision/worker/status?source=tb3_1_picam&max_frame_age_s=2.0`

Lane B read-only worker readiness API입니다. 다음 worker tick이 어떤 결과가 될지 미리 보여주며 detection/overlay 실행, metric 증가, ROS publish를 하지 않습니다.

Response excerpt:

```json
{
  "requested_source": "tb3_1_picam",
  "max_frame_age_s": 2.0,
  "debug_only": true,
  "summary": {
    "sources_total": 1,
    "pending_count": 1,
    "stale_frame_count": 0,
    "would_create_new_evidence_count": 1,
    "expected_new_event_count_total": 0,
    "reused_event_count_if_ticked_total": 0,
    "status_counts": {"no_frame": 0, "processed": 1, "skipped": 0, "stale_frame": 0}
  },
  "sources": [
    {
      "source": "tb3_1_picam",
      "has_frame": true,
      "has_overlay": false,
      "latest_frame_seq": 2,
      "latest_overlay_frame_seq": null,
      "frame_age_s": 0.12,
      "overlay_lag_frames": null,
      "pending": true,
      "next_tick_status": "processed",
      "would_create_new_evidence": true,
      "evidence_action_if_ticked": "created",
      "expected_new_event_count": null,
      "reused_event_count_if_ticked": 0,
      "reason": "new frame pending processing"
    }
  ]
}
```

`summary`는 전체 source 수, pending source 수, stale-frame source 수, next-tick status별 카운트와 idempotency preview count를 제공합니다. `would_create_new_evidence_count`는 다음 tick이 새 evidence를 만들 source 수입니다. `expected_new_event_count_total`은 확정적으로 0인 no-frame/skipped/stale case만 합산하며, detection 실행 전에는 pending source의 event 개수를 아직 모릅니다. `reused_event_count_if_ticked_total`은 skip/reuse 시 새 event-store row를 만들지 않고 응답에 재사용될 overlay event 수입니다. Source-level `evidence_action_if_ticked`는 `created`, `reused`, `none` 중 하나입니다.
`next_tick_status`는 `no_frame`, `processed`, `skipped`, `stale_frame` 중 하나입니다. Errors: unknown source는 `400`, query validation은 `422`.

### `POST /api/v1/vision/worker/tick`

Lane B evidence worker 기반 검증용 one-shot latest-frame processing tick입니다.
저장된 latest frame을 읽어 marker detection + overlay render 경로를 1회 실행합니다.
Production stream plane이 아니며 ROS motion command를 내지 않습니다.

Request: `application/json`

| Field | Required | Note |
| --- | --- | --- |
| `source` | no | 특정 source만 tick; 생략하면 configured source 전체 |
| `force` | no | default `false`; latest overlay가 latest frame_seq와 같으면 skip |
| `stale` | no | 새로 그린 overlay를 stale 상태로 표시하는 검증용 flag |
| `max_frame_age_s` | no | stale-frame skip threshold. 생략 시 `SOURCE_STALE_AFTER_S` 사용 |

Response:

```json
{
  "generated_at": "2026-06-15T09:00:05+09:00",
  "requested_source": "tb3_1_picam",
  "force": false,
  "stale": false,
  "max_frame_age_s": 2.0,
  "summary": {
    "sources_total": 1,
    "processed_count": 1,
    "skipped_count": 0,
    "stale_frame_count": 0,
    "event_count_total": 1,
    "status_counts": {
      "no_frame": 0,
      "processed": 1,
      "skipped": 0,
      "stale_frame": 0
    }
  },
  "results": [
    {
      "source": "tb3_1_picam",
      "status": "processed | skipped | no_frame | stale_frame",
      "frame_seq": 1,
      "frame_age_s": 0.12,
      "max_frame_age_s": 2.0,
      "event_count": 1,
      "overlay": {
        "source": "tb3_1_picam",
        "frame_seq": 1,
        "event_count": 1,
        "stale": false,
        "visual_state": "fresh",
        "content_type": "image/jpeg"
      },
      "reason": "new frame processed"
    }
  ]
}
```

Errors: unknown source는 `400`, body validation은 `422`.
`summary`는 이번 tick의 실제 결과 기준 집계입니다. source 수, processed/skipped/stale_frame/no_frame 분포, 그리고 event 총합을 빠르게 확인하는 용도입니다.
`status=stale_frame`이면 detection/overlay를 실행하지 않고 `event_count=0`, `overlay=null`을 반환합니다. `force=true`는 이 guard를 우회합니다. Stale worker tick으로 새로 그린 overlay도 metadata `visual_state=stale`와 JPEG amber warning band를 포함합니다.

### `POST /api/v1/lift-roi/evaluate`

**Lane 0 production Pull-first endpoint 이름은 이 경로로 유지**합니다.  
현재 구현은 caller-provided image metadata/candidates 평가용이므로, Lane A/B에서 latest-frame pull semantics를 확장해야 합니다.

Production request target:

```json
{
  "request_id": "main-req-20260615-0001",
  "task_id": "123",
  "source": "tb3_1_picam",
  "operation": "PICKUP",
  "roi": {
    "roi_id": "TB3_1_LIFT_ROI",
    "kind": "LIFT",
    "polygon_xy": [[220, 180], [420, 180], [440, 360], [200, 360]]
  },
  "expected_count": 2,
  "stable_frames": 5,
  "count_stable": true,
  "lift_sensor": {
    "lift_up": true,
    "lift_down_complete": null,
    "backoff_complete": null
  },
  "policy": {"min_confidence": 0.5, "min_overlap_ratio": 0.5}
}
```

Response `200`: full `LiftRoiEvidence v1`.

```json
{
  "schema_version": "lift-roi-evidence.v1",
  "evidence_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
  "timestamp": "2026-06-15T09:00:04+09:00",
  "source": "tb3_1_picam",
  "robot_id": "tb3_1",
  "frame_id": "tb3_1_pi_camera_optical_frame",
  "operation": "PICKUP",
  "task_id": "123",
  "image": {"width": 640, "height": 480},
  "roi": {"roi_id": "TB3_1_LIFT_ROI", "kind": "LIFT", "polygon_xy": [[220,180],[420,180],[440,360],[200,360]]},
  "expected_count": 2,
  "stable_frames": 5,
  "count_stable": true,
  "lift_sensor": {"lift_up": true, "lift_down_complete": null, "backoff_complete": null},
  "load": {"count": 2, "empty": false, "accepted_items": [], "rejected_items": []},
  "dropped_item_count": 0,
  "verification": {"status": "CONFIRMED", "reason": "pickup_verified"},
  "policy": {
    "policy_version": "mvp1-lift-roi",
    "load_classes": ["box", "pallet"],
    "min_confidence": 0.5,
    "min_overlap_ratio": 0.5
  },
  "metadata": {"model": "latest-frame-detector", "latency_ms": 42.0}
}
```

Latest-frame failure semantics:

| Case | HTTP | Meaning |
| --- | --- | --- |
| valid latest frame + model available | `200` | returns `LiftRoiEvidence v1` |
| unknown source | `400` | bad request |
| no frame ever received | `404` | nothing to evaluate |
| latest frame stale | `503` | fail-closed; do not return stale success |
| model/runtime unavailable | `503` | fail-closed |
| invalid ROI/policy | `400` or `422` | validation error |
| valid evaluation but evidence uncertain | `200` | `verification.status=CANDIDATE` or `FAILED` |

### `POST /api/v1/lift-roi/evaluate-image`

업로드 이미지 + configured detector/segmenter 평가. 모델 미설정/불가 시 `503` fail-closed.

Request: `multipart/form-data` with `source`, `operation`, `roi_json`, `image`, optional `task_id`, `expected_count`, `stable_frames`, `count_stable`, lift sensor fields, `dropped_item_count`, `policy_json`.

Response `200`: full `LiftRoiEvidence v1`.

---


### `GET /api/v1/vision/stream/{source}.mjpeg?max_fps=10`

Lane B local debug/fallback MJPEG overlay stream입니다. Production browser stream plane은 rosbridge `9090`이며 이 endpoint는 GUI 실험/디버그용입니다.

Query:

| Field | Required | Note |
| --- | --- | --- |
| `max_fps` | no | per-client cap, integer `1..30`, default `10` |

서버는 같은 client stream에 대해 `1 / max_fps`보다 빠르게 multipart frame을 내보내지 않습니다. 새 overlay가 없으면 stale poll로 대기하며 `/api/v1/metrics`의 stream counters에 반영됩니다.
Errors: unknown source는 `400`, overlay 없음은 `404`, invalid `max_fps`는 `422`.

## 4. Main API 계약

### 현재 구현됨: `POST /api/v1/camera/events`

Generic camera audit/business event. 상태 전이 없음. dedup 없음.

Request:

```json
{
  "event_id": "11111111-1111-4111-8111-111111111111",
  "event_type": "PERSON_INTRUSION",
  "robot_name": "tb3_1",
  "location": "STORAGE_A",
  "severity": "WARN",
  "payload": {"source": "tb3_1_picam", "message": "person detected near robot path"}
}
```

Response:

```json
{"ok": true, "message": "camera event accepted"}
```

### Target canonical: `POST /api/v1/vision/events`

Main에 아직 미구현. `VisionEvent v1` canonical ingest target입니다.

Request: one full `VisionEvent v1`.

Response accepted:

```json
{
  "accepted": true,
  "duplicate": false,
  "event_id": "11111111-1111-4111-8111-111111111111",
  "schema_version": "vision-event.v1",
  "wms_processing_status": "queued",
  "stored_at": "2026-06-15T09:00:04+09:00"
}
```

Response duplicate:

```json
{
  "accepted": true,
  "duplicate": true,
  "event_id": "11111111-1111-4111-8111-111111111111",
  "wms_processing_status": "already_seen"
}
```

### Deferred, not MVP: `POST /api/v1/vision/lift-roi/evidence`

LiftRoiEvidence async push 후보. MVP에서는 Pull-first 우선.  
`report_id`는 idempotency key, `evidence_id`는 evidence 원본 ID 후보입니다.  
예시는 축약본이며, 구현 전에는 full `LiftRoiEvidence v1` schema-valid payload로 확장해야 합니다.

---

## 5. Data Contract 요약

### `VisionEvent v1`

Required core fields: `schema_version`, `event_id`, `timestamp`, `source`, `event_kind`, `class_name`, `confidence`, `metadata`, `robot_id`, `frame_id`.

`event_kind`: `CANDIDATE`, `CONFIRMED`, `CLEARED`, `STALE`.

### `LiftRoiEvidence v1`

Required core fields: `schema_version`, `evidence_id`, `timestamp`, `source`, `robot_id`, `frame_id`, `operation`, `task_id`, `image`, `roi`, `expected_count`, `stable_frames`, `count_stable`, `lift_sensor`, `load`, `dropped_item_count`, `verification`, `policy`, `metadata`.

`verification.status`: `CONFIRMED`, `CANDIDATE`, `FAILED`. `ERROR`는 사용하지 않고 source/model unavailable은 HTTP `503`으로 fail-closed 처리합니다.

`task_id`: 현재 AI schema/code는 `string|null`; 채택 방향은 Main 표준에 맞춘 **integer/null migration**입니다. schema/code/fixture 동시 갱신이 필요합니다.

---

## 6. ROS / Stream 계약

- Historical Lane 0 note: browser production video path는 rosbridge `9090`로 기록되어 있었습니다.
- Current v2 supersession: Main-facing production video는 source-selected HTTP/MJPEG Vision Stream Gateway on `:8090`입니다. ROS/rosbridge는 future ADR이 승격하기 전까지 internal allowlisted operator/prototype infrastructure입니다.
- Main API는 video를 proxy하지 않습니다.

Topic migration matrix는 Lane C 전 확정 필요합니다. 채택 방향은 `/mission/...` 회귀 없이 유지하면서 `/sf/...` 표준 topic을 병행 추가하는 것입니다:

| source | physical input | legacy/browser | normalized `/sf` | overlay |
| --- | --- | --- | --- | --- |
| `global_cam_01` | `/global_camera/image_raw` | TBD | `/sf/vision/sources/global_cam_01/image/compressed` | `/sf/vision/sources/global_cam_01/overlay/compressed` |
| `tb3_1_picam` | `/tb3_1/pi_camera/image_raw` | `/mission/tb3_1/camera/compressed` | `/sf/vision/sources/tb3_1_picam/image/compressed` | `/sf/vision/sources/tb3_1_picam/overlay/compressed` |
| `tb3_2_picam` | `/tb3_2/pi_camera/image_raw` | `/mission/tb3_2/camera/compressed` | `/sf/vision/sources/tb3_2_picam/image/compressed` | `/sf/vision/sources/tb3_2_picam/overlay/compressed` |

---

## 7. Movement Safety Boundary

`POST /movement-api/v1/system/safety`는 Movement 소유입니다. 이 문서는 boundary만 정리하며 Movement 구현 계약이 아닙니다.

Vision Gateway는 safety evidence/alert만 낼 수 있습니다. stop/slow 판단과 실행은 Movement/Safety Controller가 담당합니다.

Movement 팀 확인 필요:

- request/response schema
- severity/action enum
- idempotency 또는 event correlation key
- Vision이 Movement를 직접 호출해도 되는지, Main 경유만 허용하는지

---

## 8. Lane 0 Decisions to Close

| # | Decision | Recommendation |
| --- | --- | --- |
| 1 | External env name | `CAMERA_API_BASE` canonical, `VISION_API_BASE` alias only |
| 2 | Main canonical event endpoint | AI/Vision은 `/camera/events`로 임시 audit 보고, `/vision/events`는 target canonical ingest |
| 3 | Lift ROI pull endpoint | `POST /api/v1/lift-roi/evaluate` production path, latest-frame semantics 추가 |
| 4 | `task_id` type | integer/null migration 방향 채택; 현재 string/null schema는 migration constraint |
| 5 | Dedup | VisionEvent `event_id`, Lift ROI push `report_id`; Main dedup storage 필요 |
| 6 | verification status | `CONFIRMED/CANDIDATE/FAILED`, unavailable은 `503` |
| 7 | Stream plane | rosbridge `9090` primary |
| 8 | Source registry/schema | source registry에서 schema enum/OpenAPI/fixture 자동 생성 |
| 9 | Safety | MVP는 Main 보고 우선; direct Movement alert는 별도 승인 후 |

---

## 9. 검토 상태

- OMX Critic 1차: WATCH — endpoint name/schema 예시 충돌 지적.
- 수정 반영: `evaluate-latest` 제거, `/lift-roi/evaluate`로 통일, `LiftRoiEvidence` 예시 schema-valid 형태로 수정, latest-frame failure semantics 추가, Movement boundary-only 명시.
- OMX Critic 재검토: WATCH지만 **Lane 0 discussion/handoff artifact로는 circulation 가능**. Deferred push 예시는 축약본으로 명시함.
