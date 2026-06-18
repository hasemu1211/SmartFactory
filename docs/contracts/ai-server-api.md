# SmartFactory AI Server API Contract v1

- Status: Draft contract for MVP1 implementation planning; AI Server endpoints below reflect the 2026-06-16 local implementation.
- Date: 2026-06-16
- Goal: make AI Server, Main Server/WMS-lite, and GUI work mergeable by API contract before implementation.
- Canonical payload schemas: `docs/contracts/vision-event.schema.json`, `docs/contracts/lift-roi-evidence.schema.json`
- Generated OpenAPI snapshot: `docs/contracts/ai-server-openapi.json`

## Principles

1. **API first**: implementation lanes depend on this contract, not on each other's internal modules.
2. **Evidence only**: AI Server emits `VisionEvent`; WMS-lite owns final task, slot, item, robot, and exception state transitions.
3. **Versioned contract**: all MVP1 endpoints use `/api/v1`; events include `schema_version: vision-event.v1`.
4. **Strict source IDs**: MVP1 camera sources are `global_cam_01`, `tb3_1_picam`, `tb3_2_picam`.
5. **No depth dependency**: MVP1 has no robot-mounted depth camera; `depth_median_m` must be `null`.
6. **Contract-first merge**: schema and endpoint changes merge before AI/WMS/GUI implementation branches.
7. **Strict schema evolution**: because `additionalProperties: false`, any additive field must first be added to the schema and fixtures, then merged across lanes before any service emits it.
8. **Registry-derived sources**: `config/vision/sources.yaml` is the source of truth for source IDs, robot IDs, frame IDs, ROS topics, schema enums, OpenAPI source hints, and generated source fixture/snapshot files.

## Source registry surfaces

Lane A source metadata is generated from `config/vision/sources.yaml`:

- `docs/contracts/vision-event.schema.json` source enum
- `docs/contracts/lift-roi-evidence.schema.json` source enum
- `docs/contracts/generated/source-registry.snapshot.json`
- `docs/contracts/fixtures/source-registry.valid.json`
- `docs/contracts/ai-server-openapi.json` source enum hints

Regenerate them after source/topic edits:

```bash
python3 scripts/generate_source_registry_surfaces.py
```

Current MVP1 sources are `global_cam_01`, `tb3_1_picam`, and `tb3_2_picam`. Robot PiCam physical input topics are compressed image handoff topics (`/tb3_1/camera/image_raw/compressed`, `/tb3_2/camera/image_raw/compressed`) while legacy `/mission/.../camera/compressed` browser topics remain preserved during migration.

Forward migration plan: `docs/contracts/source-registry-v2-evidence-contract-migration-plan-2026-06-18.md` defines the proposed `vision-sources.v2` capability/depth metadata, two-TB3-PiCam coverage, future disabled global depth-capable source slot, advisory-only evidence boundaries, and the `LiftRoiEvidence.task_id` integer/null transition test plan.

## Common response objects

### Error object

AI Server error responses use one common JSON envelope. The same `X-Request-ID`
value is also returned as an HTTP response header.

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "VisionEvent failed schema validation",
    "details": ["robot_id is required"],
    "request_id": "req_20260609_0001"
  }
}
```

Current AI Server error codes include `BAD_REQUEST`, `VALIDATION_ERROR`,
`CONTRACT_VALIDATION_FAILED`, `SERVICE_UNAVAILABLE`, and generic `HTTP_ERROR`
for unmapped status codes.

Recommended status codes:

| Code | Meaning |
| ---: | --- |
| 200 | successful read or idempotent duplicate ingest |
| 202 | event accepted for WMS processing |
| 400 | malformed request, bad query parameter, or invalid multipart payload |
| 404 | requested source/event not found |
| 409 | contract/schema version conflict that cannot be processed |
| 422 | JSON schema or policy validation error |
| 503 | source/model unavailable |

## AI Server endpoints

MVP1 keeps two evidence layers separate:

- `VisionEvent v1` is the lightweight event stream for marker/person/obstacle/item candidates.
- `LiftRoiEvidence v1` is the richer ROI/count/verification summary for lift load pickup/dropoff decisions.

Do **not** force lift count, mask, or stability fields into `VisionEvent v1`.
WMS/Main may later translate a confirmed `LiftRoiEvidence` result into its own
task/inventory transition, but AI Server remains evidence-only.

### `GET /api/v1/health`

Purpose: service liveness/readiness. It must not require all cameras to be online.

Response `200`:

```json
{
  "service": "ai-server",
  "status": "ok",
  "service_version": "0.1.0",
  "contract_version": "vision-event.v1",
  "model_status": "loaded",
  "models": {
    "marker": {
      "status": "loaded",
      "name": "opencv-marker-detector"
    },
    "lift_roi": {
      "status": "disabled | loaded | error",
      "task": "segment | detect",
      "path_configured": false,
      "device": "cpu"
    }
  },
  "source_summary": {
    "configured": 3,
    "online": 2,
    "stale": 1,
    "disabled": 0,
    "offline": 0
  },
  "event_retention": {
    "maxlen": 200,
    "size": 0
  }
}
```

`model_status` is retained as a backward-compatible marker/base-service status.
Use `models.marker` and `models.lift_roi` for model-specific readiness.
`models.lift_roi.status=disabled` means `/api/v1/lift-roi/evaluate-image` will
fail closed with HTTP `503` until `VISION_MODEL_PATH` is configured.

### `GET /api/v1/sources`

Purpose: exact source list and health for AI/WMS/GUI integration.

Response `200`:

```json
{
  "sources": [
    {
      "source": "global_cam_01",
      "kind": "global_rgb",
      "robot_id": null,
      "enabled": true,
      "status": "online | stale | offline | disabled",
      "frame_id": "global_camera_frame",
      "last_frame_at": "2026-06-09T15:30:00+09:00",
      "last_frame_age_s": 0.25,
      "last_event_at": "2026-06-09T15:30:00+09:00",
      "last_event_kind": "CONFIRMED",
      "last_event_id": "11111111-1111-4111-8111-111111111111",
      "last_marker_id": "ARUCO_4X4_50_7",
      "frame_count": 42,
      "event_count": 3,
      "target_fps": 10,
      "notes": "overview/slot/zone evidence",
      "ros_topic": "/global_camera/image_raw",
      "ros_message_type": "sensor_msgs/msg/Image",
      "ros_content_type": "image/raw"
    },
    {
      "source": "tb3_1_picam",
      "kind": "robot_pi_camera",
      "robot_id": "tb3_1",
      "enabled": true,
      "status": "online",
      "frame_id": "tb3_1_pi_camera_optical_frame",
      "last_frame_at": "2026-06-09T15:30:00+09:00",
      "last_frame_age_s": 0.12,
      "last_event_at": null,
      "last_event_kind": null,
      "last_event_id": null,
      "last_marker_id": null,
      "frame_count": 10,
      "event_count": 0,
      "target_fps": 10,
      "notes": "front marker/dock/local item evidence",
      "ros_topic": "/tb3_1/camera/image_raw/compressed",
      "ros_message_type": "sensor_msgs/msg/CompressedImage",
      "ros_content_type": "image/jpeg"
    }
  ]
}
```

`ros_topic`, `ros_message_type`, and `ros_content_type` are registry-derived handoff fields for Lane C; they do not mean the FastAPI process has started a ROS subscriber.

Source status is freshness-based. A configured source is `offline` until a
valid frame is decoded. After a frame, it is `online` until
`SOURCE_STALE_AFTER_S`, then `stale` until `SOURCE_OFFLINE_AFTER_S`, then
`offline` again. `last_event_*` fields update only when a detection event is
generated; marker-free frames still refresh `last_frame_at` and `frame_count`.

### `GET /api/v1/detections/latest?source=global_cam_01&limit=10`

Purpose: debug/latest detection feed from AI Server. WMS state should still come from WMS ingest, not direct GUI coupling.

Query parameters:

| Name | Required | Description |
| --- | --- | --- |
| `source` | no | one of `global_cam_01`, `tb3_1_picam`, `tb3_2_picam`; omit for all |
| `limit` | no | integer 1-50, default 10 |

Response `200`:

```json
{
  "generated_at": "2026-06-09T15:30:03+09:00",
  "events": [
    { "schema_version": "vision-event.v1", "event_id": "11111111-1111-4111-8111-111111111111" }
  ]
}
```

`events[]` items must be full `VisionEvent` objects conforming to `vision-event.schema.json`; shortened above only for readability.

### `GET /api/v1/metrics?source=tb3_1_picam`

Purpose: local AI Server observability snapshot for development, operations, and
contract smoke tests. This is not a WMS state API.

Query parameters:

| Name | Required | Description |
| --- | --- | --- |
| `source` | no | configured source ID. When set, Lane B `stream`, `worker`, and `frame_store` counters are scoped to that source. HTTP/model counters remain service-level. |

Response `200`:

```json
{
  "generated_at": "2026-06-12T14:30:03+09:00",
  "requested_source": "tb3_1_picam",
  "metrics": {
    "http": {
      "request_total": 3,
      "status_total": {"200": 3},
      "route_total": [
        {"method": "GET", "path": "/api/v1/health", "count": 1}
      ]
    },
    "detect_image": {"calls_total": 1, "events_total": 1},
    "lift_roi": {
      "evaluations_total": 1,
      "verification_total": {"CONFIRMED": 1}
    },
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
  "event_store": {"maxlen": 200, "size": 1},
  "frame_store": {
    "sources_with_frames": 1,
    "frame_seq_by_source": {"tb3_1_picam": 2},
    "dropped_frames_by_source": {"tb3_1_picam": 1},
    "dropped_frames_total": 1
  }
}
```

`stream` metrics apply only to the local debug/fallback MJPEG stream. They do
not describe the production rosbridge plane. `dropped_frames_total` counts old
latest-frame snapshots overwritten by newer frames; the store intentionally keeps
only the newest frame per source. If `source` is provided, `stream.by_source`,
`worker.by_source`, worker `tick_total`, and `frame_store` are scoped to the
requested source. Unknown source returns `400`.

### `POST /api/v1/detect/image`

Purpose: offline fixture/manual image test. This is for development and contract tests, not the main live video path.

Request: `multipart/form-data`

| Field | Required | Description |
| --- | --- | --- |
| `source` | yes | source ID to evaluate as |
| `image` | yes | image file |
| `emit` | no | `false` default; if `true`, AI Server may POST accepted events to Main Server |
| `pose_profile` | no | named profile from `ARUCO_POSE_PROFILES_PATH`; cannot be combined with manual calibration fields |
| `marker_size_m` | no | positive marker size in meters; required with camera intrinsics to compute optional ArUco pose |
| `camera_fx` | no | camera focal length x in pixels; required for optional ArUco pose |
| `camera_fy` | no | camera focal length y in pixels; required for optional ArUco pose |
| `camera_cx` | no | camera principal point x in pixels; required for optional ArUco pose |
| `camera_cy` | no | camera principal point y in pixels; required for optional ArUco pose |
| `camera_dist_coeffs` | no | optional comma-separated OpenCV distortion coefficients for optional ArUco pose |

When `pose_profile` is provided, the server loads marker size and camera
intrinsics from `ARUCO_POSE_PROFILES_PATH` (default:
`config/perception/aruco_pose_profiles.example.json`). Profile source/marker ID
must match the request/detection before pose is emitted; otherwise the marker
event remains valid but `pose_estimate` stays `null`.

When all manual marker/camera calibration fields are provided, ArUco marker
events may also include `pose_estimate.method=ARUCO_POSE`. In MVP1 this is
camera-frame planar docking evidence: `pose_estimate.x` is lateral offset in
meters, `pose_estimate.y` is forward marker distance in meters, and
`pose_estimate.yaw` is marker face yaw in radians. If profile/manual calibration
fields are omitted, `pose_estimate` remains `null`. Partial calibration input or
combining `pose_profile` with manual calibration fields is rejected with HTTP
`400` so the server does not emit ambiguous pose estimates.

Emission is disabled by default at runtime. `emit=true` only requests emission;
the server attempts outbound WMS ingest only when `WMS_EMIT_ENABLED=true`.

Response `200`:

```json
{
  "source": "tb3_1_picam",
  "emitted": false,
  "emit_disabled": true,
  "emit_results": [],
  "events": [
    { "schema_version": "vision-event.v1", "event_id": "22222222-2222-4222-8222-222222222222" }
  ]
}
```

`events[]` items must be full `VisionEvent` objects.

`emitted` is an outcome flag, not an echo of the request flag. It is `true`
only when all of the following are true:

- request field `emit=true`
- runtime setting `WMS_EMIT_ENABLED=true`
- at least one event was generated
- every attempted WMS ingest returned HTTP `200` or `202`

Otherwise `emitted` is `false`. WMS ingest failure must not fail this endpoint;
the local detection result remains useful evidence.

When emission is enabled and attempted, `emit_results[]` contains one item per
event:

```json
{
  "event_id": "22222222-2222-4222-8222-222222222222",
  "attempted": true,
  "ok": true,
  "status_code": 202,
  "error": null,
  "response": {
    "accepted": true,
    "duplicate": false,
    "wms_processing_status": "queued"
  }
}
```

`response` is parsed JSON when the WMS response body is JSON; otherwise it is
`null`. For transport errors, timeouts, and non-2xx responses, `ok` is `false`
and `error` contains a short diagnostic string.

### `POST /api/v1/lift-roi/evaluate`

Purpose: evaluate caller-provided detector/segmenter candidates against a
configured lift or target-slot ROI and return a contract-valid
`LiftRoiEvidence v1` payload. This endpoint is implemented as the stable seam
for synthetic tests, offline fixtures, and future model providers.

Canonical response schema: `docs/contracts/lift-roi-evidence.schema.json`.

Request shape:

```json
{
  "source": "tb3_1_picam",
  "operation": "PICKUP",
  "task_id": "TASK-IN-0001",
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
  "candidates": [
    {
      "class_name": "box",
      "bbox_xyxy": [240, 210, 310, 290],
      "confidence": 0.91,
      "track_id": "box-1",
      "evidence_type": "bbox",
      "mask_area_px": null
    }
  ]
}
```

Response `200` is a full `LiftRoiEvidence v1` object. Example excerpt:

```json
{
  "schema_version": "lift-roi-evidence.v1",
  "evidence_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
  "source": "tb3_1_picam",
  "robot_id": "tb3_1",
  "operation": "PICKUP",
  "expected_count": 2,
  "count_stable": true,
  "load": {
    "count": 2,
    "empty": false,
    "accepted_items": [
      {
        "class_name": "box",
        "bbox_xyxy": [240, 210, 310, 290],
        "confidence": 0.91,
        "evidence_type": "bbox",
        "center_inside_roi": true,
        "overlap_ratio": 0.98,
        "reason": "accepted"
      }
    ],
    "rejected_items": []
  },
  "dropped_item_count": 0,
  "verification": {
    "status": "CONFIRMED",
    "reason": "pickup_verified"
  }
}
```

Policy constraints validated by fixtures:

- source/robot mapping follows the same policy as `VisionEvent v1`.
- `load.count` must equal `accepted_items.length`.
- `load.empty` must match `load.count == 0`.
- accepted items must use `reason=accepted` and have `center_inside_roi=true`.
- confirmed pickup requires `expected_count`, matching count, stable count,
  `lift_up=true`, and `dropped_item_count=0`.
- confirmed dropoff requires `lift_down_complete=true` and `backoff_complete=true`.

This contract allows either bbox-only detection or instance segmentation:

- `evidence_type=bbox`: ROI overlap is computed from the bounding box area.
- `evidence_type=instance_mask`: ROI overlap is computed from the instance mask;
  the contract stores only summary fields such as `mask_area_px`, not raw masks.

### `POST /api/v1/lift-roi/evaluate-image`

Purpose: evaluate lift ROI evidence from an uploaded image using the configured
optional detector/segmenter runtime. Instance masks are preferred when the model
returns masks; bbox detections remain supported as fallback.

Request: `multipart/form-data`

| Field | Required | Description |
| --- | --- | --- |
| `source` | yes | source ID to evaluate as |
| `operation` | yes | `PICKUP`, `DROPOFF`, or `MONITOR` |
| `roi_json` | yes | JSON object with `roi_id`, `kind`, and `polygon_xy` |
| `image` | yes | image file |
| `task_id` | no | WMS task correlation ID or null |
| `expected_count` | no | non-negative expected load count |
| `stable_frames` | no | integer >= 1; default 1 |
| `count_stable` | no | boolean; default false |
| `lift_up` | no | nullable pickup lift sensor evidence |
| `lift_down_complete` | no | nullable dropoff lift-down evidence |
| `backoff_complete` | no | nullable robot backoff evidence |
| `dropped_item_count` | no | non-negative count; defaults from detector class when available |
| `policy_json` | no | optional policy object overriding load classes/confidence/overlap |

Runtime configuration:

```env
VISION_MODEL_PATH=/models/lift-load-seg.pt
VISION_MODEL_TASK=segment   # segment or detect
VISION_MODEL_CONF=0.5
VISION_MODEL_IOU=0.5
VISION_MODEL_IMGSZ=640
VISION_MODEL_DEVICE=cpu
```

Response `200`: full `LiftRoiEvidence v1`.

Response `503`: common error object when model path/package/runtime is
unavailable. This is fail-closed behavior; the endpoint must not return success
when the configured vision model cannot run.

## Lane B debug/fallback stream and overlay APIs

Production browser video remains rosbridge `9090` unless a later contract changes it.
The following endpoints are local Vision Gateway debug/fallback surfaces for robot-free
synthetic validation and GUI integration experiments. They must not be treated as the
primary ROS/browser video plane.

### `POST /api/v1/vision/synthetic/frame`

Purpose: generate one deterministic synthetic ArUco frame, push it through the
same latest-frame, marker-detection, and overlay-rendering path used by
`POST /api/v1/detect/image`, and return events plus overlay metadata. This is a
robot-free Lane B validation endpoint; it is not a production camera ingest path.

Request JSON:

```json
{
  "source": "tb3_2_picam",
  "marker_id": 9,
  "marker_size": 96,
  "padding": 32,
  "stale": true,
  "emit": false
}
```

| Field | Required | Description |
| --- | --- | --- |
| `source` | yes | configured source ID: `global_cam_01`, `tb3_1_picam`, or `tb3_2_picam` |
| `marker_id` | no | ArUco `DICT_4X4_50` marker ID, integer `0..49`; default `7` |
| `marker_size` | no | generated marker size in pixels, integer `16..512`; default `96` |
| `padding` | no | white border around the marker in pixels, integer `0..512`; default `32` |
| `stale` | no | if `true`, mark the rendered overlay metadata and image as stale for visual-state testing |
| `emit` | no | same semantics as `/api/v1/detect/image`; emission is still disabled unless `WMS_EMIT_ENABLED=true` |

Response `200`:

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

`events[]` items are full `VisionEvent` objects in real responses; the example is
shortened for readability. `visual_state` is `fresh` or `stale`; stale overlays
also include a full-width amber warning band in the JPEG. Errors: `400` unknown
source or generator failure, `422` body validation error.

### `GET /api/v1/vision/worker/status?source=tb3_1_picam&max_frame_age_s=2.0`

Purpose: return a read-only preview of what the next worker tick would do for
one source or all configured sources. It does not run detection, does not render
overlays, and does not change worker metrics. This is a Lane B debug/scheduling
surface for the future background evidence worker.

Query parameters:

| Name | Required | Description |
| --- | --- | --- |
| `source` | no | configured source ID; omit for all sources |
| `max_frame_age_s` | no | stale-frame threshold. Default is `SOURCE_STALE_AFTER_S` |

Response `200` excerpt:

```json
{
  "generated_at": "2026-06-15T09:00:05+09:00",
  "requested_source": "tb3_1_picam",
  "max_frame_age_s": 2.0,
  "debug_only": true,
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
      "max_frame_age_s": 2.0,
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

`summary` gives GUI/ops a quick count of total sources, pending sources, stale-frame sources, next-tick status totals, and idempotency preview totals. `would_create_new_evidence_count` counts sources whose next non-forced tick would create new evidence. `expected_new_event_count_total` sums deterministic zero-count cases only; pending detection-dependent sources report `expected_new_event_count=null` until tick execution. `reused_event_count_if_ticked_total` counts overlay events that would be represented by skipped/reused sources without creating new event-store rows.
`next_tick_status` can be `no_frame`, `processed`, `skipped`, or `stale_frame`. Source-level `evidence_action_if_ticked` can be `created`, `reused`, or `none`.
Errors: `400` unknown source, `422` query validation error.

### `POST /api/v1/vision/worker/tick`

Purpose: run one controlled latest-frame processing tick for the future evidence
worker path. It reads the latest stored frame for one source or all configured
sources, reuses the marker-detection/overlay renderer, and returns per-source
worker status. This is a debug/control surface for Lane B validation, not a
production stream plane and not a ROS motion endpoint.

Request JSON:

```json
{
  "source": "tb3_1_picam",
  "force": false,
  "stale": false,
  "max_frame_age_s": 2.0
}
```

| Field | Required | Description |
| --- | --- | --- |
| `source` | no | configured source ID; omit to tick all configured sources |
| `force` | no | default `false`; when false, skip frames whose overlay already matches latest `frame_seq` |
| `stale` | no | default `false`; mark any newly rendered overlay metadata and image as stale for visual-state testing |
| `max_frame_age_s` | no | stale-frame skip threshold. Default is `SOURCE_STALE_AFTER_S`; `force=true` overrides this guard |

Response `200`:

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
    "new_event_count_total": 1,
    "reused_event_count_total": 0,
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
      "new_event_count": 1,
      "evidence_action": "created",
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

Errors: `400` unknown source, `422` body validation error.

`summary` is computed from the actual tick results in this response. It lets GUI/Main/debug callers quickly see how many sources were processed, skipped, stale-frame blocked, or empty. `event_count_total` is the number of events represented by the response, including reused overlay evidence on skipped sources. `new_event_count_total` is the idempotency-safe count of newly created evidence events during this tick. `reused_event_count_total` counts events represented from already-synced overlays. Result-level `evidence_action` is `created`, `reused`, or `none`.

If the latest frame age is greater than `max_frame_age_s`, worker tick returns
`status=stale_frame`, `event_count=0`, and `overlay=null` instead of running
detection. `force=true` intentionally bypasses this guard for debug reprocessing.

Overlay metadata includes `visual_state=fresh|stale`. Stale overlays also include
a full-width amber warning band in the JPEG so GUI/debug users do not confuse old
evidence with current task success.

### `GET /api/v1/vision/streams`

Purpose: describe available source stream surfaces and make the production/debug
split explicit.

Query parameters:

| Name | Required | Description |
| --- | --- | --- |
| `source` | no | configured source ID; omit to return all sources |

Response `200` excerpt:

```json
{
  "generated_at": "2026-06-15T09:00:03+09:00",
  "requested_source": "tb3_1_picam",
  "primary_stream_plane": "rosbridge",
  "rosbridge_url": "ws://<vision-host>:9090",
  "debug_only": true,
  "motion_command_allowed": false,
  "control_topics_published": [],
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
  "debug_fallback": {
    "frame_ingest_path": "/api/v1/vision/frame",
    "mjpeg_path_template": "/api/v1/vision/stream/{source}.mjpeg",
    "mjpeg_max_fps_default": 10,
    "mjpeg_max_fps_limit": 30,
    "frame_metadata_path": "/api/v1/vision/frame/latest?source={source}",
    "frame_image_path": "/api/v1/vision/frame/latest/image?source={source}",
    "overlay_metadata_path": "/api/v1/vision/overlay/latest?source={source}",
    "overlay_image_path": "/api/v1/vision/overlay/latest/image?source={source}",
    "metrics_path": "/api/v1/metrics",
    "source_snapshot_path": "/api/v1/vision/debug/sources",
    "worker_status_path": "/api/v1/vision/worker/status",
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
      "topic_exposure": {
        "allowed_browser_topics": [
          "/mission/tb3_1/camera/compressed",
          "/sf/vision/sources/tb3_1_picam/image/compressed",
          "/sf/vision/sources/tb3_1_picam/overlay/compressed"
        ],
        "client_publish_allowed": false,
        "control_topics_allowed": []
      },
      "rosbridge_subscription_hints": {
        "recommended_image_topic": "/sf/vision/sources/tb3_1_picam/image/compressed",
        "recommended_overlay_topic": "/sf/vision/sources/tb3_1_picam/overlay/compressed",
        "legacy_browser_topic": "/mission/tb3_1/camera/compressed",
        "client_publish_allowed": false,
        "control_topics_allowed": []
      },
      "ros_ingest_readiness": {
        "readiness_state": "contract_ready",
        "physical_input_topic_configured": true,
        "physical_input_message_type": "sensor_msgs/msg/CompressedImage",
        "physical_input_content_type": "image/jpeg",
        "physical_input_transport": "compressed",
        "runtime_subscriber_active": false,
        "http_debug_ingest_path": "/api/v1/vision/frame",
        "required_qos_profile": {
          "reliability": "BEST_EFFORT",
          "history": "KEEP_LAST",
          "depth": 1
        },
        "reason": "source registry has a physical ROS image topic; Lane C can attach a background subscriber"
      },
      "ros_publish_readiness": {
        "latest_frame_seq": 2,
        "latest_overlay_frame_seq": 1,
        "overlay_ready": false,
        "readiness_state": "overlay_lag",
        "overlay_visual_state": "fresh",
        "publish_payload_preview": {
          "payload_available": false,
          "topic": "/sf/vision/sources/tb3_1_picam/overlay/compressed",
          "message_type": "sensor_msgs/msg/CompressedImage",
          "frame_seq": 1,
          "content_type": "image/jpeg",
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
      "frame_ingest_path": "/api/v1/vision/frame",
      "mjpeg_path": "/api/v1/vision/stream/tb3_1_picam.mjpeg",
      "mjpeg_default_max_fps": 10,
      "frame_metadata_path": "/api/v1/vision/frame/latest?source=tb3_1_picam",
      "frame_image_path": "/api/v1/vision/frame/latest/image?source=tb3_1_picam",
      "overlay_metadata_path": "/api/v1/vision/overlay/latest?source=tb3_1_picam",
      "overlay_image_path": "/api/v1/vision/overlay/latest/image?source=tb3_1_picam",
      "source_snapshot_path": "/api/v1/vision/debug/sources?source=tb3_1_picam",
      "worker_status_path": "/api/v1/vision/worker/status?source=tb3_1_picam",
      "metrics_path": "/api/v1/metrics?source=tb3_1_picam",
      "ros_handoff_path": "/api/v1/vision/ros/topics",
      "ros_handoff_source_path": "/api/v1/vision/ros/topics?source=tb3_1_picam",
      "stream_metrics": {
        "clients_total": 1,
        "active_clients": 0,
        "frames_sent_total": 2,
        "stale_polls_total": 1,
        "approx_fps": 10.0
      }
    }
  ]
}
```

If `source` is provided, `sources` contains only that source. Response-level `summary` is computed over the returned rows only; with `source` filtering it summarizes that one source. `overlay_lag_count` counts sources where an overlay exists but has not caught up to the latest frame, `synced_overlay_count` counts sources whose latest overlay matches the latest frame, and `stale_overlay_count` counts stale visual overlays. Source entries now advertise `metrics_path=/api/v1/metrics?source=...` and `ros_handoff_source_path=/api/v1/vision/ros/topics?source=...` so GUI/debug callers can stay source-scoped across discovery, metrics, and ROS handoff. They also include `latest_frame_seq`, `latest_overlay_frame_seq`, `overlay_lag_frames`, and `overlay_visual_state` so a dashboard can see whether the debug overlay has caught up to the latest frame without opening `/vision/debug/sources`. `topic_exposure_policy`, `topic_exposure_summary`, per-source `topic_exposure`, and `rosbridge_subscription_hints` mirror the ROS/rosbridge allowlist preflight so GUI clients can choose safe rosbridge image/overlay topics directly from stream discovery. Top-level `debug_only`, `motion_command_allowed=false`, and `control_topics_published=[]` mirror `/api/v1/vision/ros/topics` so stream discovery also exposes the no-motion/no-control boundary. Top-level `runtime_policy` mirrors `/api/v1/vision/ros/topics` and states that HTTP handlers must not start, spin, or publish through ROS2. Per-source `ros_ingest_readiness` mirrors the read-only future ROS image subscriber preflight from `/api/v1/vision/ros/topics`; `summary.ros_ingest_contract_ready_count`, `summary.ros_ingest_runtime_subscriber_active_count`, and `summary.ros_ingest_status_counts` are computed over returned source rows. Per-source `ros_publish_readiness` mirrors the read-only future overlay compressed-image publisher preflight from `/api/v1/vision/ros/topics`; `summary.ros_publish_ready_count`, `summary.ros_publish_payload_available_count`, `summary.ros_publish_payload_blocked_count`, and `summary.ros_publish_status_counts` are computed over returned source rows. Per-source `evidence_event_publish_readiness` mirrors the read-only future `/sf/vision/events` publish preflight from `/api/v1/vision/ros/topics`, and `summary.evidence_event_publish_ready_count` counts returned sources that currently have a latest schema-valid `VisionEvent` eligible for future publish. Unknown source returns `400`.

### `GET /api/v1/vision/ros/topics`

Purpose: return a read-only ROS2/domain-bridge handoff matrix for Lane B/C
planning. This endpoint does not start ROS2 and does not publish/subscribe at
request time. It exists so GUI/Main/ROS developers can align on physical input
topics, preserved legacy browser topics, and planned normalized `/sf/...` topics
before Lane C. Production browser streaming remains rosbridge `9090`; HTTP/MJPEG
remains debug/fallback.

Query parameters:

| Name | Required | Description |
| --- | --- | --- |
| `source` | no | configured source ID; omit to return all sources |

Response `200` excerpt:

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
    "http_handlers_must_spin_ros2_executor": false,
    "threading_model": "ROS2 executor outside FastAPI request handlers with lock-protected latest-frame handoff"
  },
  "ingest_readiness_summary": {
    "sources_total": 3,
    "contract_ready_count": 3,
    "missing_physical_topic_count": 0,
    "runtime_subscriber_active_count": 0,
    "status_counts": {
      "contract_ready": 3,
      "missing_physical_topic": 0
    }
  },
  "publish_readiness_summary": {
    "sources_total": 3,
    "overlay_ready_count": 1,
    "publish_payload_available_count": 1,
    "publish_payload_blocked_count": 2,
    "overlay_lag_count": 0,
    "no_overlay_count": 0,
    "no_frame_count": 2,
    "status_counts": {
      "no_frame": 2,
      "no_overlay": 0,
      "overlay_lag": 0,
      "ready_fresh": 1,
      "ready_stale": 0
    }
  },
  "evidence_event_publish_readiness_summary": {
    "sources_total": 3,
    "publish_ready_count": 1,
    "no_event_count": 2
  },
  "sources": [
    {
      "source": "tb3_1_picam",
      "kind": "robot_pi_camera",
      "robot_id": "tb3_1",
      "frame_id": "tb3_1_pi_camera_optical_frame",
      "physical_input_topic": "/tb3_1/camera/image_raw/compressed",
      "physical_input_message_type": "sensor_msgs/msg/CompressedImage",
      "physical_input_content_type": "image/jpeg",
      "physical_input_transport": "compressed",
      "legacy_browser_topic": "/mission/tb3_1/camera/compressed",
      "legacy_browser_message_type": "sensor_msgs/msg/CompressedImage",
      "normalized_image_topic": "/sf/vision/sources/tb3_1_picam/image/compressed",
      "normalized_image_message_type": "sensor_msgs/msg/CompressedImage",
      "normalized_overlay_topic": "/sf/vision/sources/tb3_1_picam/overlay/compressed",
      "normalized_overlay_message_type": "sensor_msgs/msg/CompressedImage",
      "evidence_event_topic": "/sf/vision/events",
      "evidence_event_message_type": "smartfactory_msgs/msg/VisionEvent or JSON bridge payload",
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
          "source_registry_path": "/home/codelab/Desktop/Project/SmartFactory/config/vision/sources.yaml",
          "physical_input_topic": "/tb3_1/camera/image_raw/compressed",
          "physical_input_message_type": "sensor_msgs/msg/CompressedImage",
          "physical_input_content_type": "image/jpeg",
          "physical_input_transport": "compressed",
          "subscription_callback": "registry_source_image_message_to_latest_frame_store_put",
          "ingest_adapter": "_store_latest_frame_from_bytes",
          "ingest_adapter_contract": {
            "input": "registry source plus encoded image bytes plus content_type from HTTP or future ROS callback",
            "output": "StoredFrame in LatestFrameStore",
            "updates_source_health": true,
            "runs_detection_inline": false,
            "renders_overlay_inline": false,
            "safe_for_http_handlers": true,
            "raw_image_requires_callback_encoding": true
          },
          "shared_state": "LatestFrameStore",
          "shared_state_guard": "threading.Lock inside frame store",
          "http_handler_role": "read_latest_state_only_never_spin_ros2",
          "backpressure": "overwrite_latest_frame_per_source",
          "target_frame_store_source": "tb3_1_picam",
          "startup_owner": "process_startup_or_launch_file_not_http_request",
          "shutdown_owner": "process_signal_handler_or_lifespan_cleanup"
        },
        "reason": "source registry has a physical ROS image topic; Lane C can attach a background subscriber"
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

`control_topics_published` is intentionally empty. Vision Gateway must not
publish `/cmd_vel` or call Nav2 actions. `image_ingest_qos`, `frame_drop_policy`,
`overlay_publish_qos`, `overlay_publish_policy`, `evidence_event_publish_policy`, and per-source message-type
fields are the Lane C implementation seam: subscribe with sensor QoS/keep-last=1,
keep only the latest frame per source, and publish compressed image/overlay topics
with keep-last=1/drop-old-overlay behavior without running ROS2 from HTTP request
handlers.
`ingest_readiness_summary` and per-source `ingest_readiness` are read-only
preflight signals for the future ROS image subscriber. `contract_ready` means a
source registry has a physical ROS image topic and Lane C can attach a background subscriber;
`missing_physical_topic` means the source registry/env must be fixed before ROS
ingest. `runtime_subscriber_active` remains `false` in Lane B because this
endpoint does not start ROS2. `runtime_plan` records the intended Lane C process
shape: ROS2 spins in a background `MultiThreadedExecutor`, callbacks write to
the lock-protected `LatestFrameStore`, HTTP handlers only read cached state and
must never call `rclpy.spin*`, and startup/shutdown are owned by process
lifecycle or launch files, not by a request. `publish_readiness_summary` and per-source
`publish_readiness` are read-only preflight signals for the future ROS overlay
publisher. They distinguish `no_frame`, `no_overlay`, `overlay_lag`,
`ready_fresh`, and `ready_stale`; they do not publish to ROS2. The publish-side
`runtime_plan` records that a background publisher should read the overlay cache,
use `_overlay_publish_payload_preview_for_source` as the publish adapter contract,
publish only compressed overlay images when `overlay_ready=true`, skip lagging
overlays, preserve stale overlays only with their visual warning band, and never
publish motion/control topics. `publish_payload_preview` is read-only metadata for
the future compressed overlay message; it never publishes ROS and exposes no image
bytes in JSON. `publish_payload_available_count` and
`publish_payload_blocked_count` are response-level dashboard counts over returned
source rows. `overlay_publish_qos` and `overlay_publish_policy` are the structured
future publisher settings: BEST_EFFORT/KEEP_LAST/depth=1, JPEG compressed image,
max 10 FPS, no lagging overlay publish, no control topic publish, and no HTTP
handler publish. `evidence_event_publish_policy` separately declares the future
`/sf/vision/events` evidence event publisher contract: schema-valid
`VisionEvent v1`, RELIABLE/KEEP_LAST/depth=10, `event_id` dedup key, no image
bytes, no control topics, and Main/WMS remains authoritative. `evidence_event_publish_readiness` and `evidence_event_publish_readiness_summary` are read-only checks showing whether each returned source currently has a latest VisionEvent eligible for future publish. If `source` is provided, `sources`,
`ingest_readiness_summary`, and `publish_readiness_summary` are scoped to that
one source. Unknown source
returns `400`.


### `GET /api/v1/vision/debug/sources?source=tb3_1_picam`

Purpose: return a one-shot Lane B readiness snapshot for one source or all
configured sources. This lets GUI/Main developers check whether a source has a
latest frame, a latest overlay, overlay/frame lag, ROS ingest/publish preflight,
stream metrics, and debug paths without opening the MJPEG stream. It is a
debug/fallback surface only; production browser streaming remains rosbridge
`9090`.

Query parameters:

| Name | Required | Description |
| --- | --- | --- |
| `source` | no | configured source ID; omit for all sources |

Response `200` excerpt:

```json
{
  "generated_at": "2026-06-15T09:00:06+09:00",
  "requested_source": "tb3_1_picam",
  "primary_stream_plane": "rosbridge",
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
      "health": {
        "status": "online",
        "last_frame_at": "2026-06-15T09:00:05+09:00",
        "last_frame_age_s": 0.1,
        "frame_count": 2,
        "event_count": 2
      },
      "latest_frame": {
        "source": "tb3_1_picam",
        "frame_seq": 2,
        "frame_timestamp": "2026-06-15T09:00:05+09:00",
        "image": {"width": 160, "height": 160},
        "content_type": "image/jpeg",
        "size_bytes": 1234
      },
      "latest_overlay": {
        "source": "tb3_1_picam",
        "frame_seq": 2,
        "event_count": 1,
        "visual_state": "fresh"
      },
      "overlay_lag_frames": 0,
      "topic_exposure": {
        "allowed_browser_topics": [
          "/mission/tb3_1/camera/compressed",
          "/sf/vision/sources/tb3_1_picam/image/compressed",
          "/sf/vision/sources/tb3_1_picam/overlay/compressed"
        ],
        "allowed_ingest_topics": ["/tb3_1/camera/image_raw/compressed"],
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
        "worker_status": "/api/v1/vision/worker/status?source=tb3_1_picam",
        "metrics": "/api/v1/metrics?source=tb3_1_picam",
        "metrics_all": "/api/v1/metrics",
        "ros_handoff": "/api/v1/vision/ros/topics?source=tb3_1_picam",
        "ros_handoff_all": "/api/v1/vision/ros/topics"
      },
      "stream_metrics": {"frames_sent_total": 1, "approx_fps": 0.0},
      "drop_metrics": {"dropped_frames": 1}
    }
  ]
}
```

`overlay_lag_frames > 0` means a newer latest frame exists but the latest overlay
still belongs to an older frame. A worker tick can reconcile this in debug mode.
`requested_source` echoes the optional source filter. `topic_exposure_policy`, `topic_exposure_summary`, per-source `topic_exposure`, and `rosbridge_subscription_hints` mirror `/api/v1/vision/ros/topics` and `/api/v1/vision/streams` so GUI/Main can see the ROS/rosbridge allowlist preflight and the recommended image/overlay subscription topics from the source snapshot as well. `topic_exposure_summary` is computed over returned `sources`; when `source` is provided it summarizes that one source only. `summary` is also computed over returned `sources`; when `source` is provided it summarizes that one source only. `health_status_counts`, `ros_ingest_status_counts`, and `ros_publish_status_counts` provide dashboard-friendly breakdowns of the same returned rows. `ros_ingest_readiness` and `ros_publish_readiness` mirror the per-source ROS image subscriber and overlay publisher preflight from `/api/v1/vision/ros/topics?source=...`; they are read-only and do not start ROS2 or publish overlays. `ros_publish_readiness.publish_payload_preview` tells whether a future background publisher may publish the cached compressed overlay image for that source. `evidence_event_publish_readiness` mirrors `/api/v1/vision/ros/topics` and tells whether that source currently has a latest `VisionEvent` eligible for future `/sf/vision/events` publishing. `summary.ros_ingest_contract_ready_count`, `summary.ros_publish_payload_available_count`, and `summary.evidence_event_publish_ready_count` count returned sources whose ingest contract, overlay payload, or evidence event is ready/eligible. Errors: `400` unknown source.

### `POST /api/v1/vision/frame`

Purpose: store one uploaded raw frame in the latest-frame cache without running
detection or rendering an overlay. This is a Lane B robot-free ingest seam for
future ROS2/camera ingest: callers can push a frame, inspect it with
`GET /api/v1/vision/frame/latest`, and then process it with
`POST /api/v1/vision/worker/tick`. It is debug/fallback only, not historical
frame storage, and not the production browser stream plane.

Request: `multipart/form-data`

| Field | Required | Description |
| --- | --- | --- |
| `source` | yes | configured source ID |
| `image` | yes | decodable image file |

Response `200`:

```json
{
  "source": "tb3_1_picam",
  "processed": false,
  "frame": {
    "source": "tb3_1_picam",
    "frame_seq": 1,
    "frame_timestamp": "2026-06-15T09:00:08+09:00",
    "image": {"width": 160, "height": 160},
    "content_type": "image/png",
    "size_bytes": 1234
  },
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

`ingest_context` confirms this HTTP endpoint uses the same latest-frame ingest
adapter intended for a future background ROS subscriber callback. It stores the
frame and updates source health, but does not run detection or render an overlay
inline.

Lane C ROS sidecar use: `smartfactory_perception_ros/vision_frame_gateway`
subscribes to a configured `sensor_msgs/msg/CompressedImage` topic and sends this
same multipart request. The sidecar keeps ROS2 out of FastAPI, uses latest-frame
semantics, and can then call `POST /api/v1/vision/worker/tick` plus read
`GET /api/v1/vision/overlay/latest/image` to publish safe `/sf/vision/...`
overlay/evidence ROS topics. It never publishes motion/control topics.

Lane C live Robot1 smoke output on 2026-06-16 after a temporary camera launch:

```json
{
  "generated_at": "2026-06-16T10:28:18.741327+09:00",
  "frame": {
    "source": "tb3_1_picam",
    "frame_seq": 15,
    "image": {"width": 640, "height": 480},
    "content_type": "image/jpeg",
    "size_bytes": 88311
  }
}
```

Errors: `400` unknown source or undecodable image, `422` missing form fields.

### `GET /api/v1/vision/frame/latest?source=tb3_1_picam`

Purpose: return latest raw frame metadata for one source from the latest-frame
cache. This is a Lane B debug/fallback endpoint for visual QA and GUI
experiments. It keeps only the newest frame per source; it is not historical
frame storage and not the production browser stream plane.

Response `200`:

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

Errors: `400` unknown source, `404` no latest frame available yet.

### `GET /api/v1/vision/frame/latest/image?source=tb3_1_picam`

Purpose: return the latest raw cached frame image for one source. This lets GUI
or QA users compare the original frame with `/api/v1/vision/overlay/latest/image`
without opening the MJPEG stream.

Response `200`: binary image using the cached frame `content_type`, normally
`image/jpeg`. Errors: `400` unknown source, `404` no latest frame available yet.

### `GET /api/v1/vision/overlay/latest?source=tb3_1_picam`

Purpose: return latest visual-evidence overlay metadata for one source.

Response `200`:

```json
{
  "generated_at": "2026-06-15T09:00:03+09:00",
  "requested_source": "tb3_1_picam",
  "sync": {
    "latest_frame_seq": 1,
    "latest_overlay_frame_seq": 1,
    "overlay_lag_frames": 0,
    "overlay_visual_state": "fresh"
  },
  "overlay": {
    "source": "tb3_1_picam",
    "frame_seq": 1,
    "frame_timestamp": "2026-06-15T09:00:02+09:00",
    "evidence_timestamp": "2026-06-15T09:00:03+09:00",
    "overlay_timestamp": "2026-06-15T09:00:03+09:00",
    "latency_ms": 3.5,
    "event_count": 1,
    "stale": false,
    "visual_state": "fresh",
    "image": {"width": 640, "height": 480},
    "content_type": "image/jpeg"
  }
}
```

`sync` lets GUI/debug callers see whether the returned overlay still matches the newest frame. `overlay_lag_frames > 0` means a newer frame exists and the overlay belongs to an older frame. Errors: `400` unknown source, `404` no overlay available yet.

### `GET /api/v1/vision/overlay/latest/image?source=tb3_1_picam`

Purpose: return latest overlay image as `image/jpeg`.

Errors: `400` unknown source, `404` no overlay image available yet.

### `GET /api/v1/vision/stream/{source}.mjpeg?max_fps=10`

Purpose: debug/fallback MJPEG stream of latest overlay JPEGs. This endpoint drops
old frames by reading the latest overlay only; it does not queue every frame.

Query parameters:

| Name | Required | Description |
| --- | --- | --- |
| `max_fps` | no | per-client debug stream cap, integer `1..30`, default `10` |

The stream emits at most one latest overlay per `1 / max_fps` seconds. This
protects the local FastAPI debug/fallback plane during GUI experiments; it does
not configure production rosbridge `9090`. Each multipart frame includes an
`X-Debug-Max-FPS` part header for smoke/debug visibility.

Errors: `400` unknown source, `404` no overlay image available yet, `422` invalid `max_fps`.

## Main Server/WMS-lite endpoints consumed by AI Server

### `POST /api/v1/vision/events`

Purpose: authoritative ingest point for one AI evidence event.

Request body: one `VisionEvent` conforming to `docs/contracts/vision-event.schema.json` and policy validation in `scripts/validate_contracts.py`.

Response `202` accepted:

```json
{
  "accepted": true,
  "duplicate": false,
  "event_id": "11111111-1111-4111-8111-111111111111",
  "schema_version": "vision-event.v1",
  "wms_processing_status": "queued",
  "stored_at": "2026-06-09T15:30:04+09:00"
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

Response `422` validation error uses the common error object.

Required WMS ingest behavior:

- Duplicate `event_id` must not create duplicate event-log rows.
- `STALE` events update source/zone freshness but must not directly complete or fail tasks.
- `CANDIDATE` events can be displayed and logged, but WMS policy decides whether to promote downstream state.
- `CONFIRMED` marker events may support slot/item/dock verification only when WMS policy and task context allow it.
- AI Server must never write directly to WMS DB.

### `POST /api/v1/vision/events/batch` optional, not MVP1 start gate

If implemented later, batch ingest must return per-item acceptance/rejection. Do not make AI Server depend on batch ingest for MVP1.

## GUI-facing Main Server endpoints

### `GET /api/v1/vision/events/latest?source=global_cam_01&limit=20`

Purpose: GUI Vision Detail and Robot Evidence summaries.

Response `200`:

```json
{
  "generated_at": "2026-06-09T15:30:05+09:00",
  "events": [
    { "schema_version": "vision-event.v1", "event_id": "11111111-1111-4111-8111-111111111111" }
  ]
}
```

### `GET /api/v1/vision/sources`

Purpose: GUI source health/staleness display derived from WMS ingest timestamps and AI source status.

Response `200`:

```json
{
  "sources": [
    {
      "source": "global_cam_01",
      "robot_id": null,
      "status": "online | stale | offline | disabled",
      "last_event_at": "2026-06-09T15:30:00+09:00",
      "last_frame_at": "2026-06-09T15:30:00+09:00"
    }
  ]
}
```

### `WS /ws/events`

Purpose: GUI receives WMS-normalized state/events. Raw AI evidence may appear as evidence entries, but GUI actions must target WMS/Main Server APIs.

Minimum message shape:

```json
{
  "type": "VISION_EVENT_INGESTED",
  "timestamp": "2026-06-09T15:30:05+09:00",
  "event_id": "11111111-1111-4111-8111-111111111111",
  "source": "global_cam_01",
  "summary": "Box candidate in STORAGE_A01_ROI",
  "wms_effect": "evidence_logged"
}
```

## Event-kind policy examples

| Kind | Required meaning | Example |
| --- | --- | --- |
| `CANDIDATE` | detected evidence, not enough alone for final WMS state | YOLO sees person/box for N frames |
| `CONFIRMED` | deterministic or policy-confirmed evidence | AprilTag/QR/ArUco marker decoded with marker_id |
| `CLEARED` | previously tracked evidence is no longer present | obstacle/person candidate has disappeared for policy window |
| `STALE` | source/ROI has no fresh frames/events | camera/source timeout; class must be `unknown`, hint `VISION_STALE` |


## Lane B robot-free integrated scenario validation

The Lane B API surfaces are also covered by an integrated robot-free scenario test:

```bash
./scripts/test_ai_server.sh -q tests/test_api.py tests/test_contract_boundaries.py
```

The scenario `test_lane_b_robot_free_e2e_surfaces_stay_consistent_across_stream_debug_ros_and_metrics` verifies the single-source end-to-end debug/fallback flow:

1. `POST /api/v1/vision/frame` stores a raw latest frame without inline detection.
2. `GET /api/v1/vision/worker/status` reports the pending worker tick.
3. `POST /api/v1/vision/worker/tick` creates a schema-valid `VisionEvent` and overlay.
4. `GET /api/v1/vision/frame/latest/image` and `GET /api/v1/vision/overlay/latest/image` return the expected visual artifacts.
5. `GET /api/v1/vision/streams`, `GET /api/v1/vision/debug/sources`, `GET /api/v1/vision/ros/topics`, and `GET /api/v1/metrics` agree on frame sequence, overlay sequence, ROS ingest readiness, ROS overlay publish readiness, evidence event publish readiness, no-motion/no-control safety flags, and worker/frame metrics.
6. A newer raw frame creates a deliberate overlay lag; all discovery surfaces agree that overlay publish payload is blocked until the worker catches up.

The scenario `test_lane_b_multi_source_e2e_keeps_frame_overlay_event_and_metrics_isolated` verifies multi-source isolation for the actual multi-camera target:

1. Two robot camera sources ingest raw frames independently.
2. Running the worker tick for only one source creates overlay/evidence only for that source.
3. `streams`, `debug/sources`, and `ros/topics` agree that the processed source is `ready_fresh`, the waiting source remains `no_overlay`, and the global camera remains `no_frame`.
4. Source-filtered metrics keep worker counters and frame-store sequences scoped to the requested source.
5. Processing the second source later raises overlay/event readiness counts from one source to two without contaminating the global camera row.

The scenario `test_lane_b_multi_source_latest_only_backpressure_drops_old_frames_per_source` verifies source-scoped latest-only/backpressure behavior under frame bursts:

1. `tb3_1_picam` receives three raw frames and `tb3_2_picam` receives two raw frames before any worker tick.
2. The latest-frame cache keeps only the newest frame per source, with `frame_seq_by_source={tb3_1_picam: 3, tb3_2_picam: 2}` and source-scoped dropped-frame counters `{tb3_1_picam: 2, tb3_2_picam: 1}`.
3. A worker tick across all configured sources processes only those latest frame sequences, while `global_cam_01` remains `no_frame`.
4. `streams`, `debug/sources`, `ros/topics`, and source-filtered `metrics` agree that both robot sources become `ready_fresh` and publish/event-ready.
5. A later burst frame for only `tb3_1_picam` creates `overlay_lag` and blocks that source's publish payload while `tb3_2_picam` remains `ready_fresh`.

The scenario `test_lane_b_worker_tick_is_idempotent_and_does_not_duplicate_evidence_events` verifies that repeated all-source worker ticks do not duplicate evidence for already-synced frames:

1. First tick over two robot camera sources creates two new events and reports `new_event_count_total=2`.
2. A second tick over the same latest frames returns `skipped` for both robot sources, `evidence_action=reused`, and `new_event_count_total=0` while `event_count_total=2` still describes the reused overlay evidence represented in the response.
3. `GET /api/v1/detections/latest` and `GET /api/v1/metrics` prove the event store remains at two events with the same event IDs, avoiding duplicate evidence before Lane C/Main dedup is added.
4. Stream and ROS handoff summaries remain `ready_fresh`/publish-ready after the skipped tick.

The existing status-preview scenario `test_vision_worker_status_reports_pending_skipped_and_stale_without_processing` now also verifies read-only idempotency preview fields. Before tick, pending sources report `would_create_new_evidence=true` and `evidence_action_if_ticked=created`; after a synced overlay exists, the same source reports `evidence_action_if_ticked=reused`, `expected_new_event_count=0`, and `reused_event_count_if_ticked=1`; stale/no-frame cases remain `none` with zero new events.

The contract-freeze guard `test_generated_openapi_artifact_matches_current_app_schema` verifies that `docs/contracts/ai-server-openapi.json` is byte-regenerated from the current FastAPI `app.openapi()` schema. This prevents Lane B API/docs handoff drift after worker/status, stream, overlay, and ROS handoff fields change.

Current validation result: `125 passed, 1 warning`; contract fixtures behaved as expected.

This is still Lane B validation only: it does not start ROS2, publish ROS topics, expose image bytes in JSON metadata, or invoke `/cmd_vel`/Nav2/control APIs.


## Lane B API-served overlay visual QA

Lane B overlay visual output is covered by an API-served visual QA test and saved artifact set.

Test:

```bash
./scripts/test_ai_server.sh -q tests/test_api.py tests/test_overlay.py tests/test_contract_boundaries.py
```

The scenario `test_lane_b_api_served_overlay_visual_qa_distinguishes_fresh_and_stale_warning_band` verifies that overlays returned by `GET /api/v1/vision/overlay/latest/image` differ visually between fresh and stale evidence:

- fresh overlay remains normal evidence visualization;
- stale overlay has a full-width amber warning band;
- stale metadata reports `visual_state=stale`;
- small debug frames use shortened warning/bottom labels so the warning remains readable.

Visual QA artifacts are stored under:

```text
docs/reports/lane-b-visual-qa-2026-06-15/
```

Files:

- `fresh_overlay.jpg`
- `stale_overlay.jpg`
- `fresh_vs_stale_overlay_comparison.jpg`
- `README.md`

This is still Lane B debug/fallback evidence visualization. The overlay image is available as binary JPEG from image endpoints, but JSON metadata does not embed image bytes and the server does not publish ROS topics in Lane B.


Lane C sidecar validation on 2026-06-16 proved the same overlay endpoint can feed
a safe ROS overlay publisher. Live Robot1 smoke produced synced overlay metadata:

```json
{
  "requested_source": "tb3_1_picam",
  "sync": {
    "latest_frame_seq": 15,
    "latest_overlay_frame_seq": 15,
    "overlay_lag_frames": 0,
    "overlay_visual_state": "fresh"
  },
  "overlay": {
    "source": "tb3_1_picam",
    "frame_seq": 15,
    "event_count": 0,
    "visual_state": "fresh",
    "image": {"width": 640, "height": 480},
    "content_type": "image/jpeg"
  }
}
```

This does not add a new FastAPI endpoint or change OpenAPI schemas; it documents
the Lane C ROS sidecar that consumes existing API surfaces.

## Contract fixtures and validation

Fixture directory: `docs/contracts/fixtures/`

- Valid fixtures exist for `global_cam_01`, `tb3_1_picam`, `tb3_2_picam`, and `STALE`.
- Invalid fixtures cover wrong source/robot pairing, missing robot ID, non-null depth, missing marker ID for confirmed marker, and invalid bbox order.

Validation command:

```bash
python3 scripts/validate_contracts.py
```

## Merge gates

Before parallel implementation:

- [x] `docs/contracts/vision-event.schema.json` exists.
- [x] Example valid event fixtures exist for each source under `docs/contracts/fixtures/`.
- [x] Example invalid event fixtures cover wrong source/robot pairing and non-null depth.
- [x] Contract validation can run locally via `python3 scripts/validate_contracts.py`.
- [ ] AI Server, WMS ingest, and GUI lanes agree on event names and `/api/v1` paths.
- [ ] Git repository is initialized before multi-worker source implementation.

## Versioning rules

- Additive optional fields can stay in `vision-event.v1` only after the field is added to `vision-event.schema.json`, fixtures are updated, and all lanes tolerate it.
- Required field changes, enum removals/renames, or source ID changes require `vision-event.v2` and `/api/v2` planning.
- AI Server may update model versions without API changes if event semantics stay stable.

## Lane D1 integration planning note: Main/GUI/stream split

Lane D1 is planned as a safe performance/GUI/Main integration lane, not an
active robot-control lane. It does not change the current FastAPI route set by
itself.

Current recommended split:

- Main semantic evidence ingest: Main should expose `POST /api/v1/vision/events`
  and accept schema-valid `VisionEvent v1` JSON. AI Server treats HTTP `200` or
  `202` as a successful downstream emit when emission is enabled.
- Evidence images: Main/GUI should pull binary images from AI Server endpoints
  such as `GET /api/v1/vision/frame/latest/image?source=tb3_1_picam` and
  `GET /api/v1/vision/overlay/latest/image?source=tb3_1_picam`. Image bytes
  remain out of `VisionEvent` JSON.
- High-FPS browser stream: use a stream-native read-only plane such as
  Movement-owned rosbridge/WebSocket `9090` or another allowlisted stream bridge.
  The AI Server MJPEG endpoint remains debug/fallback, and repeated HTTP image
  polling is not the production stream plan.
- ROS safe topics currently published by the Lane C sidecar may be bridged only
  when allowlisted/read-only:
  `/sf/vision/sources/tb3_1_picam/overlay/compressed` and `/sf/vision/events`.
  Control topics such as `/cmd_vel`, teleop, Nav2 action/service topics, and
  parameter mutation surfaces remain forbidden.

AI model scope for D1:

- Current marker evidence uses the loaded OpenCV ArUco detector.
- Optional Lift ROI model adapters remain disabled/fail-closed unless a concrete
  model path, classes, sample images, runtime install method, and latency target
  are approved in a separate model subgoal.
- A new heavyweight model should not be silently added as part of the first D1
  stream/Main integration ultragoal.

D1 validation must report raw camera FPS, AI overlay FPS, GUI stream FPS, and
Main evidence latency separately. Comparing camera input FPS directly with AI
overlay FPS is misleading because `vision_frame_gateway` can intentionally
throttle overlay/evidence processing.


### Current local YOLO runtime discovery for Lane D1-AI

The currently running AI Server environment (`services/ai-server/.venv`) contains
the FastAPI service dependencies but does not contain `ultralytics` or `torch`.
A separate local environment, `~/venv/venv`, contains `ultralytics 8.4.63` and
`torch 2.12.0+cu130` with CUDA available on an NVIDIA GeForce RTX 5060, but it
does not contain the FastAPI service dependencies.

For project use, do not copy the whole external venv. Create a reproducible
project model environment or model extras file, then run the AI Server with that
environment only after smoke tests pass. Candidate model paths from prior local
YOLO work are:

```text
/home/codelab/yolo_test/runs/segment/bottle_detection_yolov8s_seg/weights/best.pt
/home/codelab/yolo_test/runs/detect/bottle_detection_yolov8s/weights/best.pt
/home/codelab/yolo_test/bottle_detection/data.yaml
```

The dataset classes are `bottle1`, `bottle2`, and `bottle3`. These labels are
not directly valid public contract classes for `VisionEvent v1` or load classes
for `LiftRoiEvidence v1`; a class normalization/config layer is required before
Main delivery.

## Lane D1/D1-AI Architect-Critic gate note

On 2026-06-16, the Lane D1 plan was reviewed in Architect -> Critic order.

- Architect status: conditional approval for a safe evidence/GUI/read-only stream integration lane.
- Critic status: revise before executing as one broad ultragoal.
- No new API route is introduced by this note.
- Canonical Main evidence delivery remains `AI Server -> Main POST /api/v1/vision/events` with schema-valid `VisionEvent v1` JSON.
- Binary images stay out of `VisionEvent`; Main/GUI should pull raw or overlay images from AI Server image endpoints when needed.
- High-FPS GUI streaming should use a stream-native read-only plane, not repeated HTTP snapshot polling.
- D1-AI model output must be normalized to public contract classes before Main delivery. Current local model labels `bottle1`, `bottle2`, and `bottle3` are not valid public Main-facing classes as-is.
- D1-AI model runtime setup must be project-local/reproducible, smoke-tested on sample images, latency-measured, and fail-closed before live Main emission.

## D1-AI pretrained model and ROS overlay stream update

This cycle adds optional worker-side model candidates for AI overlay generation. It does not add a new HTTP route.

Runtime configuration:

| Environment variable | Default | Meaning |
|---|---:|---|
| `AI_SERVER_VENV_DIR` | `services/ai-server/.venv` | Optional runner override for a project-local model environment such as `services/ai-server/.venv-yolo`. |
| `VISION_MODEL_WORKER_ENABLED` | `false` | Enables optional model candidates during `/api/v1/vision/worker/tick`. Disabled/fail-closed by default. |
| `VISION_MODEL_PATH` | empty | Model path/name. Recommended pretrained smoke value: `yolov8n.pt`. |
| `VISION_MODEL_TASK` | `segment` | `detect` or `segment`; pretrained YOLO smoke should use `detect`. |
| `VISION_MODEL_CLASS_MAP_JSON` | `{"bottle":"box","person":"person"}` | Normalizes model classes to public `VisionEvent v1` classes. |
| `VISION_MODEL_UNMAPPED_CLASS` | `unknown` | Public class used for unmapped model labels. |
| `VISION_MODEL_MAX_EVENTS` | `20` | Per-frame cap for model-generated candidate events. |

Model candidate behavior:

- Model candidates are emitted as schema-valid `VisionEvent v1` with `event_kind=CANDIDATE`.
- They are overlaid on the cached overlay image and can then be republished by `vision_frame_gateway` to `/sf/vision/sources/<source>/overlay/compressed`.
- The production/high-FPS AI overlay video path is the ROS overlay topic through a read-only rosbridge/stream bridge.
- `GET /api/v1/vision/frame/latest/image`, `GET /api/v1/vision/overlay/latest/image`, and `GET /api/v1/vision/stream/{source}.mjpeg` remain debug/fallback surfaces and are not the acceptance path for high-FPS GUI video.

Recommended pretrained run command:

```bash
AI_SERVER_VENV_DIR=/home/codelab/Desktop/Project/SmartFactory/services/ai-server/.venv-yolo \
AI_SERVER_HOST=0.0.0.0 \
AI_SERVER_PORT=8100 \
VISION_MODEL_WORKER_ENABLED=true \
VISION_MODEL_PATH=yolov8n.pt \
VISION_MODEL_TASK=detect \
VISION_MODEL_CLASS_MAP_JSON='{"bottle":"box","person":"person"}' \
VISION_MODEL_UNMAPPED_CLASS=unknown \
./scripts/run_ai_server.sh
```

The companion setup helper is `./scripts/setup_ai_server_model_env.sh`, which creates `services/ai-server/.venv-yolo` from `services/ai-server/requirements-model.txt`.

## D1 read-only ROS overlay stream bridge endpoints

This cycle adds a ROS package bridge, not a new AI Server FastAPI route. The
bridge subscribes to the AI overlay ROS topic produced by `vision_frame_gateway`
and serves a browser-friendly MJPEG view. It is read-only and must not expose
`/cmd_vel`, Nav2, teleop, parameter mutation, `/rosout`, `/tf`, or a whole ROS
graph.

Primary ROS input:

```text
/sf/vision/sources/tb3_1_picam/overlay/compressed
```

### GET /api/v1/vision/bridge/status

Returns the stream bridge status and enabled overlay source list.

Example response:

```json
{
  "service": "smartfactory-vision-overlay-stream-bridge",
  "version": "0.1.0",
  "read_only": true,
  "motion_command_allowed": false,
  "mutation_methods_allowed": [],
  "transport": "ros2-subscribe-compressed-image-to-mjpeg",
  "host": "0.0.0.0",
  "port": 8090,
  "max_fps": 30.0,
  "sources": [
    {
      "source": "tb3_1_picam",
      "overlay_topic": "/sf/vision/sources/tb3_1_picam/overlay/compressed",
      "has_frame": true,
      "latest_sequence_id": 12,
      "frame_age_s": 0.034,
      "content_type": "image/jpeg",
      "stale": false,
      "view_path": "/api/v1/vision/overlay/view?source=tb3_1_picam",
      "stream_path": "/api/v1/vision/overlay/stream?source=tb3_1_picam"
    }
  ]
}
```

### GET /api/v1/vision/overlay/view?source=tb3_1_picam

Returns a minimal HTML page containing the MJPEG overlay stream. This is for
operator/browser verification and GUI integration smoke.

### GET /api/v1/vision/overlay/stream?source=tb3_1_picam&max_fps=30

Returns `multipart/x-mixed-replace` MJPEG from the latest ROS overlay
`CompressedImage`. `max_fps` is clamped to `1..30`. The bridge sends only new
frames and drops stale duplicates.

Alias endpoints are also available for simple browser usage:

- `GET /view/tb3_1_picam`
- `GET /stream/tb3_1_picam.mjpeg?max_fps=30`

Validation completed for this bridge:

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

## D1 live model runtime correction: `AI_SERVER_EXTRA_PYTHONPATH`

`./scripts/run_ai_server.sh` intentionally unsets inherited `PYTHONPATH` so the
FastAPI AI Server does not accidentally import ROS2 runtime packages. For a
project-local model environment, prefer `AI_SERVER_VENV_DIR=services/ai-server/.venv-yolo`.
For a temporary live smoke using an already-known model-only environment, the
runner now supports an explicit override:

| Environment variable | Default | Meaning |
|---|---:|---|
| `AI_SERVER_EXTRA_PYTHONPATH` | empty | Optional explicit model-only Python path appended after the inherited ROS PYTHONPATH is cleared. Do not point this at ROS2 workspaces. |

Temporary live smoke example:

```bash
AI_SERVER_EXTRA_PYTHONPATH=/home/codelab/venv/venv/lib/python3.12/site-packages \
AI_SERVER_VENV_DIR=/home/codelab/Desktop/Project/SmartFactory/services/ai-server/.venv \
AI_SERVER_HOST=0.0.0.0 \
AI_SERVER_PORT=8100 \
VISION_MODEL_WORKER_ENABLED=true \
VISION_MODEL_PATH=/home/codelab/Desktop/Project/SmartFactory/yolov8n.pt \
VISION_MODEL_TASK=detect \
VISION_MODEL_DEVICE=0 \
VISION_MODEL_IMGSZ=320 \
VISION_MODEL_CONF=0.35 \
VISION_MODEL_CLASS_MAP_JSON='{"bottle":"box","person":"person"}' \
VISION_MODEL_UNMAPPED_CLASS=unknown \
./scripts/run_ai_server.sh
```

Validation after this correction produced a fresh `tb3_1_picam` overlay with
`event_count=5`; latest detections included normalized `box`, `person`, and
`unknown` `VisionEvent v1` candidates.

## POST /api/v1/vision/frame/process

Added on 2026-06-16 KST for the D1 async gateway hot path.

Purpose: store one latest frame and immediately update detection/overlay cache in one ROS-free HTTP request. This is intended for `vision_frame_gateway`; Main should use the public `:8090` stream gateway instead of calling this endpoint directly.

Request: `multipart/form-data`

| Field | Type | Required | Description |
|---|---|---:|---|
| `source` | string | yes | Source id such as `tb3_1_picam` or `tb3_2_picam`. |
| `image` | file | yes | PNG/JPEG frame bytes. |
| `force` | boolean | no, default `true` | Process even if an overlay already exists for the latest frame. |
| `stale` | boolean | no, default `false` | Render stale-warning overlay state for test/debug cases. |

Example request:

```bash
curl -F source=tb3_1_picam \
  -F force=true \
  -F stale=false \
  -F image=@frame.jpg \
  http://127.0.0.1:8100/api/v1/vision/frame/process
```

Example response shape:

```json
{
  "source": "tb3_1_picam",
  "processed": true,
  "status": "processed",
  "frame_seq": 42,
  "event_count": 2,
  "new_event_count": 2,
  "evidence_action": "created",
  "frame": {
    "source": "tb3_1_picam",
    "frame_seq": 42,
    "content_type": "image/jpeg",
    "size_bytes": 12345,
    "image": {"width": 640, "height": 480}
  },
  "overlay": {
    "source": "tb3_1_picam",
    "frame_seq": 42,
    "event_count": 2,
    "visual_state": "fresh"
  },
  "events": [],
  "reason": "forced",
  "ingest_context": {
    "transport": "http_debug",
    "topic": null,
    "stored_in_latest_frame_cache": true,
    "processed_inline": true,
    "source_health_updated": true,
    "ros_callback_compatible": true
  }
}
```

Errors: `400` for unknown source or invalid image bytes; `422` for malformed form input.

D1 bundle usage:

- `VISION_GATEWAY_PROCESS_FRAME_INLINE=true` uses this endpoint.
- `VISION_GATEWAY_ASYNC_PIPELINE=true` keeps only the latest pending frame per source.
- `VISION_GATEWAY_PUBLISH_LAGGING_OVERLAY=false` prevents stale overlay/frame sequence mismatches from being published.
- QoS is configurable through the bundle env vars; current live profile uses reliable image/overlay QoS with depth `1`.
