# Lane 0 Contract Brief — Vision Gateway / Main / Movement

- Date: 2026-06-15 Asia/Seoul
- Audience: Main Server, GUI, Movement, Vision/AI Server contributors
- Purpose: Lane 0에서 합의해야 할 계약 API, 반환값, 미결정 사항을 압축 정리한다.
- Status: **Lane 0 contract alignment artifact**. 구현 착수 문서가 아니라, 팀 간 합의용 계약 브리프다.

---

## 0. Lane 0 Adopted Decisions

2026-06-15 사용자 결정 반영:

| 항목 | 채택안 | 의미 |
| --- | --- | --- |
| Interim Main reporting | AI/Vision은 `/api/v1/camera/events`로 임시 보고 | Main의 `/vision/events` 구현 전까지 audit/business event로만 사용한다. 상태 전이/evidence canonical ingest로 오해하면 안 된다. |
| `task_id` | integer migration 추천안 채택 | Main 표준에 맞춰 최종 계약은 integer/null로 이동한다. 단 현재 schema/code는 string/null이므로 migration 단계가 필요하다. |
| `/vision/events` | Main이 Lane A 직후 canonical ingest로 구현하는 방향 | `/camera/events`는 임시 경로, `/vision/events`가 최종 VisionEvent ingest 경로다. |
| dedup | Main에 `inbound_reports` 또는 동등 테이블 추가 | VisionEvent는 `event_id`, Lift ROI push는 `report_id` 기준으로 중복 제거한다. |
| source topic migration | `/mission/...` 회귀 없이 유지 + `/sf/...` 표준 병행 추가 | GUI/rosbridge 기존 topic을 깨지 않고 새 표준 topic으로 전환한다. |
| Movement safety | MVP는 Main 보고 우선, 긴급 direct Movement alert는 별도 승인 후 | Vision은 `/cmd_vel`/Nav2를 직접 제어하지 않는다. |
| registry/schema | schema enum을 source registry에서 자동 생성 | `config/vision/sources.yaml`을 source of truth로 두고 schema/OpenAPI/test fixture를 생성/검증한다. |

---

## 1. One-line Architecture Decision

영상/overlay/evidence 생성은 **Vision Gateway(Camera/AI Server)** 가 담당하고, task/inventory 최종 상태 전이는 **Main Server** 가 담당한다. Vision Gateway는 DB 직접 접근, `/cmd_vel`, Nav2 action, motion authority를 가지지 않는다. 긴급 stop/slow 실행 권한은 **Movement/Safety Controller** 에 있다.

---

## 2. Base URLs / Ports

| Service | Base | Status | Note |
| --- | --- | --- | --- |
| Main API | `http://<main-host>:8080/api/v1` | 확정 | Main 답변 기준. `8000`은 legacy GUI 정적 서버. |
| Vision/Camera API | `http://<vision-host>:8090/api/v1` | Lane 0 target | 외부 통합 env 이름은 `CAMERA_API_BASE`. |
| Vision internal alias | `VISION_API_BASE=http://<vision-host>:8090/api/v1` | optional | 내부 별칭만 허용. `CAMERA_API_BASE`와 다르면 startup에서 거부 권장. |
| rosbridge stream | `ws://<vision-host>:9090` | target | Browser video/overlay stream 기본 경로. |
| Legacy AI Server | `http://127.0.0.1:8100` | dev/backward compatible | 현재 repo 기본값. 배포 계약값은 8090으로 이동. |

---

## 3. Endpoint Summary

### 3.1 Vision/Camera API — already implemented or compatibility endpoints

#### `GET /api/v1/health`

Purpose: Vision service liveness/readiness. 모든 카메라 online을 요구하지 않는다.

Response `200` shape:

```json
{
  "service": "ai-server",
  "status": "ok",
  "service_version": "0.1.0",
  "contract_version": "vision-event.v1",
  "model_status": "loaded",
  "models": {
    "marker": { "status": "loaded", "name": "opencv-marker-detector" },
    "lift_roi": {
      "status": "disabled | loaded | error",
      "task": "segment | detect",
      "path_configured": false,
      "device": "cpu"
    }
  },
  "source_summary": {
    "configured": 3,
    "online": 0,
    "stale": 0,
    "disabled": 0,
    "offline": 3
  },
  "event_retention": { "maxlen": 200, "size": 0 },
  "main_server_url": "http://127.0.0.1:8000",
  "sources": ["global_cam_01", "tb3_1_picam", "tb3_2_picam"]
}
```

Notes:
- `main_server_url`/legacy values are backward-compatible fields; Lane 0 이후 8080/8090 env로 정리 필요.

#### `GET /api/v1/sources`

Purpose: Vision source registry/health.

Response `200` shape:

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
      "notes": "front marker/dock/local item evidence",
      "ros_topic": "/tb3_1/pi_camera/image_raw"
    }
  ]
}
```

#### `GET /api/v1/detections/latest?source={source}&limit={1..50}`

Purpose: local/debug latest VisionEvent feed. Main/WMS state 대체용이 아니다.

Response `200` shape:

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

#### `POST /api/v1/detect/image`

Purpose: uploaded image marker detection/debug endpoint. Optional best-effort emit to Main/WMS.

Request: `multipart/form-data`

| Field | Required | Type | Note |
| --- | --- | --- | --- |
| `source` | yes | string | `global_cam_01`, `tb3_1_picam`, `tb3_2_picam` |
| `image` | yes | file | image bytes |
| `emit` | no | boolean | default `false`; if true, best-effort emit |
| `pose_profile` | no | string | optional pose calibration profile |
| `marker_size_m` | no | number | optional |
| `camera_fx/fy/cx/cy` | no | number | optional intrinsics |
| `camera_dist_coeffs` | no | string | optional JSON/list string |

Response `200` shape:

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
      "response": { "accepted": true }
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

Error:
- `400`: unknown source or invalid image
- `422`: request validation error
- `500`: unexpected server error

#### `POST /api/v1/lift-roi/evaluate`

Purpose: Lane 0에서 **production Pull-first endpoint 이름은 Main 답변/Camera spec과 맞춰 이 경로로 유지**한다. 단, 현재 구현은 caller-provided metadata/candidates를 평가하는 compatibility/debug semantics이므로, Lane A/B에서 latest-frame pull semantics를 추가/확장해야 한다. Main이 camera image/candidates를 들고 있지 않기 때문이다.

Request body shape:

```json
{
  "source": "tb3_1_picam",
  "operation": "PICKUP",
  "task_id": "123",
  "image": { "width": 640, "height": 480 },
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
  "candidates": []
}
```

Response `200`: full `LiftRoiEvidence v1`.

#### `POST /api/v1/lift-roi/evaluate-image`

Purpose: uploaded image + configured detector/segmenter로 Lift ROI evidence 생성.

Request: `multipart/form-data`

| Field | Required | Type | Note |
| --- | --- | --- | --- |
| `source` | yes | string | source ID |
| `operation` | yes | enum | `PICKUP`, `DROPOFF`, `MONITOR` |
| `roi_json` | yes | JSON string | `{roi_id, kind, polygon_xy}` |
| `image` | yes | file | image bytes |
| `task_id` | no | string currently | Lane 0에서 integer/null migration 결정 필요 |
| `expected_count` | no | integer/null | non-negative |
| `stable_frames` | no | integer | default `1` |
| `count_stable` | no | boolean | default `false` |
| `lift_up` | no | boolean/null | pickup sensor evidence |
| `lift_down_complete` | no | boolean/null | dropoff sensor evidence |
| `backoff_complete` | no | boolean/null | robot backoff evidence |
| `dropped_item_count` | no | integer/null | non-negative |
| `policy_json` | no | JSON string | optional policy override |

Response `200`: full `LiftRoiEvidence v1`.

Error:
- `400`: invalid source/input/ROI
- `503`: model path/package/runtime unavailable; fail-closed
- `500`: unexpected server error

### 3.2 Vision/Camera API — Lane 0 target production semantics

#### `POST /api/v1/lift-roi/evaluate` — chosen production Pull-first path

Purpose: Main Pull-first MVP endpoint. Endpoint name follows Main answer and Camera Server spec. Main sends task/ROI context; Vision Gateway evaluates its latest frame for `source`. Main does **not** upload camera image/candidates in the normal production path.

Compatibility note: current repo already has `POST /api/v1/lift-roi/evaluate`, but current implementation expects caller-provided `image` metadata/candidates. Lane 0 chooses the path name; Lane A/B must update/extend implementation semantics without breaking fixtures.

Proposed request body:

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
  "policy": {
    "min_confidence": 0.5,
    "min_overlap_ratio": 0.5
  }
}
```

Proposed response `200`: full `LiftRoiEvidence v1`.

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
  "image": { "width": 640, "height": 480 },
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
  "load": {
    "count": 2,
    "empty": false,
    "accepted_items": [],
    "rejected_items": []
  },
  "dropped_item_count": 0,
  "verification": {
    "status": "CONFIRMED",
    "reason": "pickup_verified"
  },
  "policy": {
    "policy_version": "mvp1-lift-roi",
    "load_classes": ["box", "pallet"],
    "min_confidence": 0.5,
    "min_overlap_ratio": 0.5
  },
  "metadata": {
    "model": "latest-frame-detector",
    "latency_ms": 42.0
  }
}
```

Production latest-frame semantics:

| Case | Recommended HTTP | Body | Rationale |
| --- | --- | --- | --- |
| valid latest frame + model available | `200` | full `LiftRoiEvidence v1` | normal pull result |
| source ID unknown | `400` | common error | bad request |
| source known but no frame ever received | `404` | common error | nothing to evaluate |
| latest frame older than freshness threshold | `503` | common error | fail-closed; do not return stale success |
| model/runtime unavailable | `503` | common error | fail-closed |
| ROI/policy schema invalid | `422` or `400` | common error | use existing validation convention consistently |
| evidence uncertainty after valid evaluation | `200` | `verification.status=CANDIDATE` or `FAILED` | model ran, but evidence did not confirm |

Freshness rule to confirm in Lane 0:
- default freshness threshold should reuse `SOURCE_STALE_AFTER_S` unless Main requires a task-specific stricter value.
- `request_id` is request-correlation only. It is not currently allowed inside `LiftRoiEvidence.metadata` because current schema has `additionalProperties=false`; add it only after schema migration.

Lane 0 decision still needed:
- Should `task_id` remain string/null for current `LiftRoiEvidence v1`, or migrate schema/code to integer/null? For this brief, response examples use string `"123"` to stay current-schema-valid.

### 3.3 Main API — currently implemented

#### `POST /api/v1/camera/events`

Purpose: generic camera audit/business event. 현재 Main에서 구현됨. 상태 전이 없음.

Request body:

```json
{
  "event_id": "11111111-1111-4111-8111-111111111111",
  "event_type": "PERSON_INTRUSION",
  "robot_name": "tb3_1",
  "location": "STORAGE_A",
  "severity": "WARN",
  "payload": {
    "source": "tb3_1_picam",
    "message": "person detected near robot path"
  }
}
```

Response `200`:

```json
{
  "ok": true,
  "message": "camera event accepted"
}
```

Important:
- No state transition.
- No dedup today. Same `event_id` can create multiple rows in Main current implementation.
- Do not use this as proof that semantic VisionEvent ingest is complete.

### 3.4 Main API — target canonical evidence ingest

#### `POST /api/v1/vision/events`

Purpose: canonical single `VisionEvent v1` ingest. Main agrees directionally, but not implemented yet.

Request body: one `VisionEvent v1`.

Minimal shape:

```json
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
  "bbox_xyxy": null,
  "track_id": null,
  "marker_id": "ARUCO_4X4_50_7",
  "zone": null,
  "roi_id": null,
  "pose_estimate": null,
  "metadata": {}
}
```

Response `202` accepted:

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

Response `200` duplicate/idempotent:

```json
{
  "accepted": true,
  "duplicate": true,
  "event_id": "11111111-1111-4111-8111-111111111111",
  "wms_processing_status": "already_seen"
}
```

Error:
- `422`: validation error
- `409`: optional state conflict, if Main chooses conflict semantics

#### `POST /api/v1/vision/lift-roi/evidence` — deferred, not MVP

Purpose: future async push of LiftRoiEvidence to Main. Main agreed path name but it is not implemented and not MVP-required.

Proposed request envelope — abbreviated example, not a full current-schema `LiftRoiEvidence v1` object. Full implementation must embed the complete `LiftRoiEvidence v1` payload or update this section with a full schema-valid example before implementation:

```json
{
  "report_id": "report-20260615-0001",
  "evidence": {
    "schema_version": "lift-roi-evidence.v1",
    "evidence_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    "task_id": "123",
    "source": "tb3_1_picam",
    "operation": "PICKUP",
    "verification": {
      "status": "CONFIRMED",
      "reason": "pickup_verified"
    }
  }
}
```

Proposed response accepted:

```json
{
  "accepted": true,
  "duplicate": false,
  "report_id": "report-20260615-0001",
  "evidence_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
  "wms_processing_status": "queued"
}
```

Lane 0 recommendation:
- MVP에서는 구현하지 않는다.
- 나중에 필요하면 `report_id`를 idempotency key, `evidence_id`를 evidence 원본 ID로 사용한다.

### 3.5 Movement API — safety authority

#### `POST /movement-api/v1/system/safety` — boundary only, not implementation handoff

Purpose: Movement-owned safety stop/slow endpoint. Vision Gateway may send alert only if explicitly approved; it must not own motion decision. This section is **not** a final Movement implementation contract.

Proposed request example:

```json
{
  "source": "tb3_1_picam",
  "robot_name": "tb3_1",
  "severity": "CRITICAL",
  "event_type": "PERSON_INTRUSION",
  "evidence_id": "11111111-1111-4111-8111-111111111111",
  "recommended_action": "STOP",
  "reason": "person detected inside robot safety ROI"
}
```

Response: Movement team contract required. Lane 0 only confirms boundary, not implementation.

Movement must confirm before implementation handoff:
- request/response schema
- severity/action enum
- idempotency or event correlation key
- whether Vision may call Movement directly, or whether Vision must report to Main only and Main/Movement coordinates safety

---

## 4. Data Contracts

### `VisionEvent v1`

Use for lightweight marker/person/obstacle/item events.

Required important fields:

| Field | Type | Note |
| --- | --- | --- |
| `schema_version` | string | `vision-event.v1` |
| `event_id` | uuid string | dedup key in target Main implementation |
| `timestamp` | date-time string | event time |
| `source` | enum/string | MVP sources: `global_cam_01`, `tb3_1_picam`, `tb3_2_picam` |
| `event_kind` | enum | `CANDIDATE`, `CONFIRMED`, `CLEARED`, `STALE` |
| `class_name` | enum/string | `aruco_marker`, `person`, `obstacle`, etc. |
| `confidence` | number/null | 0..1 |
| `robot_id` | string/null | robot camera maps to robot; global camera null |
| `frame_id` | string | ROS/frame mapping |
| `metadata` | object | extra non-authoritative evidence |

### `LiftRoiEvidence v1`

Use for richer lift/pickup/dropoff ROI evidence.

Important fields:

| Field | Type | Lane 0 decision |
| --- | --- | --- |
| `schema_version` | string | `lift-roi-evidence.v1` |
| `evidence_id` | uuid string | original evidence ID |
| `source` | source ID | registry/schema consistency required |
| `operation` | enum | `PICKUP`, `DROPOFF`, `MONITOR` |
| `task_id` | currently string/null | Main standard is integer; Lane 0 must decide migration |
| `image` | object | `{width,height}` |
| `roi` | object | `{roi_id,kind,polygon_xy}` |
| `load` | object | count + accepted/rejected items |
| `verification.status` | enum | `CONFIRMED`, `CANDIDATE`, `FAILED`; no `ERROR` |
| `metadata` | object | latency/request/frame metadata |

---

## 5. ROS / Stream Contract

Lane 0 default decision:

- Browser production video path: rosbridge `9090`.
- Vision HTTP/MJPEG/WS stream endpoints, if added, are debug/fallback only unless Lane 0 explicitly changes this.
- Main API does not proxy video.

Topic migration matrix to complete before Lane C. 채택 방향은 `/mission/...` 회귀 없이 유지하면서 `/sf/...` 표준 topic을 병행 추가하는 것입니다:

| source | physical input topic | legacy/browser topic | normalized `/sf` topic | overlay topic | bridge direction | status |
| --- | --- | --- | --- | --- | --- | --- |
| `global_cam_01` | `/global_camera/image_raw` | TBD | TBD | TBD | input→normalized/overlay | open |
| `tb3_1_picam` | `/tb3_1/pi_camera/image_raw/compressed` | `/mission/tb3_1/camera/compressed` | TBD `/sf/...` | TBD | keep legacy + add normalized | open |
| `tb3_2_picam` | `/tb3_2/pi_camera/image_raw/compressed` | `/mission/tb3_2/camera/compressed` | TBD `/sf/...` | TBD | keep legacy + add normalized | open |

---

## 6. Lane 0 Decisions to Close

| # | Decision | Recommendation |
| --- | --- | --- |
| 1 | External env name | Use `CAMERA_API_BASE`; `VISION_API_BASE` alias only. |
| 2 | Main canonical event endpoint | **Adopted:** AI/Vision uses `/camera/events` only as interim audit reporting; `/vision/events` remains target canonical ingest. |
| 3 | Lift ROI pull endpoint | Use `POST /api/v1/lift-roi/evaluate` as production path; extend semantics to latest-frame pull. |
| 4 | `task_id` type | **Adopted direction:** migrate final contract to integer/null. Current string/null schema remains a migration constraint until updated. |
| 5 | Dedup | **Adopted:** `VisionEvent.event_id`; Lift ROI push envelope `report_id`; Main adds `inbound_reports`/equivalent dedup storage. |
| 6 | `verification.status` | Keep `CONFIRMED/CANDIDATE/FAILED`; use HTTP `503` for model/source unavailable. |
| 7 | Stream plane | rosbridge `9090` primary; Vision HTTP stream debug/fallback only. |
| 8 | Source registry/schema | **Adopted:** generate schema enum/OpenAPI/test fixtures from source registry; registry is source of truth. |
| 9 | Safety | **Adopted:** MVP reports to Main first; direct Movement alert requires explicit safety approval; Movement owns stop/slow. |

---

## 7. Lane 0 Completion Criteria

Lane 0 is complete only when:

1. This contract brief is accepted or corrected by Main/Vision/Movement/GUI owners.
2. API names and response shapes above are reflected in the implementation plan.
3. `task_id` integer/null migration decision is recorded and schema/code migration task is created.
4. Production pull endpoint is fixed as `POST /api/v1/lift-roi/evaluate`; latest-frame semantics are documented.
5. `/camera/events` is explicitly documented as audit-only interim, not semantic evidence ingest.
6. Topic migration matrix has concrete physical, legacy `/mission`, standard `/sf`, and overlay topics for each source.
7. Safety path cannot be interpreted as Vision owning robot motion.

