# SmartFactory AI Server API Contract v1

- Status: Draft contract for MVP1 implementation planning
- Date: 2026-06-09
- Goal: make AI Server, Main Server/WMS-lite, and GUI work mergeable by API contract before implementation.
- Canonical payload schema: `docs/contracts/vision-event.schema.json`

## Principles

1. **API first**: implementation lanes depend on this contract, not on each other's internal modules.
2. **Evidence only**: AI Server emits `VisionEvent`; WMS-lite owns final task, slot, item, robot, and exception state transitions.
3. **Versioned contract**: all MVP1 endpoints use `/api/v1`; events include `schema_version: vision-event.v1`.
4. **Strict source IDs**: MVP1 camera sources are `global_cam_01`, `tb3_1_picam`, `tb3_2_picam`.
5. **No depth dependency**: MVP1 has no robot-mounted depth camera; `depth_median_m` must be `null`.
6. **Contract-first merge**: schema and endpoint changes merge before AI/WMS/GUI implementation branches.
7. **Strict schema evolution**: because `additionalProperties: false`, any additive field must first be added to the schema and fixtures, then merged across lanes before any service emits it.

## Common response objects

### Error object

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

### `GET /api/v1/health`

Purpose: service liveness/readiness. It must not require all cameras to be online.

Response `200`:

```json
{
  "service": "ai-server",
  "status": "ok",
  "service_version": "0.1.0",
  "contract_version": "vision-event.v1",
  "model_status": "loaded | disabled | error",
  "source_summary": {
    "configured": 3,
    "online": 2,
    "stale": 1,
    "disabled": 0,
    "offline": 0
  }
}
```

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
      "ros_topic": "/global_camera/image_raw"
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
      "ros_topic": "/tb3_1/pi_camera/image_raw"
    }
  ]
}
```

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
