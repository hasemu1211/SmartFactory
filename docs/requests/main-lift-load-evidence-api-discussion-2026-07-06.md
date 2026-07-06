# Main ↔ AI Server lift-load evidence API discussion note

- Date: 2026-07-06
- Status: AI Server local implementation pushed on `feature/ai-server-marker-detection`
- Related endpoint: `POST /api/v1/vision/evidence/lift-load/evaluate`
- Purpose: pick/drop 전후에 Main이 1회 호출해서 global cam 기반 적재/하차 증거를 받는다.

## 1. Main이 호출할 API

```http
POST http://smartfactory-vision.local:8100/api/v1/vision/evidence/lift-load/evaluate
Content-Type: application/json
```

Example:

```json
{
  "source": "global_cam_01",
  "robot_id": "tb3_1",
  "task_id": 303,
  "command_id": 3,
  "operation": "PICK_UP",
  "expected_item_id": "main-owned-item-id",
  "expected_marker_id": 20,
  "expected_item_count": 1,
  "vision_zone_id": "inbound_static_item_zone",
  "burst_frames": 5,
  "min_pass_frames": 1,
  "sample_interval_ms": 80
}
```

Default MVP policy: AI samples up to `burst_frames=5` distinct latest frames, and `min_pass_frames=1` means one valid expected-marker hit is enough for `PASS` only if the same burst does not observe extra item markers/count in the requested ZoneROI. `event.confidence` still reports the observed ratio, e.g. `0.2` for 1/5.

## 2. Required / recommended fields

| Field | Owner | Note |
| --- | --- | --- |
| `source` | AI/Vision | fixed: `global_cam_01` |
| `robot_id` | Main | `tb3_1` or `tb3_2` |
| `task_id` | Main | optional but recommended for DB/event trace |
| `command_id` | Main | optional but recommended for command trace |
| `operation` | Main | recommended: `PICK_UP` or `DROP_OFF`; compatibility aliases `PICKUP`/`DROPOFF` accepted |
| `expected_item_id` | Main | Main-owned item identity; AI stores/returns as evidence metadata only |
| `expected_marker_id` | Main/AI agreed mapping | item ArUco id, currently allowed `20..49`; `0..19` reserved |
| `expected_item_count` | Main | currently 1 for MVP; request rejects 0 |
| `vision_zone_id` | AI/Vision | AI fixed ZoneROI id. Preferred until Main location mapping is agreed. |
| `location_id` | Main | optional alias only if AI config explicitly maps it to `vision_zone_id` |

## 3. Current valid `vision_zone_id` values

Natural item zones:

- `inbound_static_item_zone`
- `outbound_static_item_zone`
- `storage_upper_static_item_zone`
- `storage_lower_static_item_zone`

Reference/non-item zone:

- `charging_reference_zone` → API returns `NO_DECISION/POLICY_NOT_APPLICABLE` for item evidence.

## 4. Current temporary `location_id` aliases

These are operator/lab aliases, not final Main DB ids:

| `location_id` alias | maps to `vision_zone_id` |
| --- | --- |
| `inbound` | `inbound_static_item_zone` |
| `outbound` | `outbound_static_item_zone` |
| `storage_1` | `storage_upper_static_item_zone` |
| `storage_2` | `storage_lower_static_item_zone` |

If Main sends an unmapped `location_id`, AI Server returns `NO_DECISION/POLICY_NOT_APPLICABLE` instead of guessing.

## 5. Response shape

Wrapper:

```json
{
  "schema_version": "vision-lift-load-evaluate.v1",
  "monitor_id": "lift_evidence",
  "source": "global_cam_01",
  "robot_id": "tb3_1",
  "task_id": 303,
  "command_id": 3,
  "operation": "PICKUP",
  "vision_zone_id": "inbound_static_item_zone",
  "result": "PASS",
  "reason_code": "EXPECTED_ITEM_COUNT_MATCH_AND_STABLE",
  "event": {
    "schema_version": "vision-monitor-event.v1",
    "event_type": "ITEM_PICKED",
    "result": "PASS",
    "trusted": false,
    "data_json": {
      "expected_item_id": "main-owned-item-id",
      "expected_marker_ids": ["ARUCO_4X4_50_20"],
      "detected_marker_id": "ARUCO_4X4_50_20",
      "marker_dictionary": "DICT_4X4_50",
      "vision_zone_id": "inbound_static_item_zone",
      "expected_item_count": 1,
      "observed_count": 1,
      "accepted_frames": 1,
      "total_frames": 5,
      "command_satisfying": true
    }
  }
}
```

## 6. Main-side interpretation suggestion

| AI result | Main interpretation suggestion |
| --- | --- |
| `PASS` | Evidence says expected item count/marker was observed at least once in the requested ZoneROI burst. Main may satisfy/record command evidence. |
| `FAIL` | AI saw enough evidence to say expected item/count condition did not match. Main should not auto-complete without operator/business rule. |
| `UNCERTAIN` | Not enough usable evidence even after the internal burst. Main should retry, ask operator, or keep task pending. |
| `NO_DECISION` | Missing/unsupported context: no frame, stale source, unmapped zone, non-natural zone, invalid config. Main should not treat as success/failure. |

AI Server remains evidence-only. It does not issue `HOLD`, `E_STOP`, motion commands, DB writes, or inventory truth changes.

## 7. Validation / safety behavior

- Unknown request fields return `422`.
- `source` is fixed to `global_cam_01`.
- `robot_id` must be `tb3_1` or `tb3_2`.
- `expected_marker_id` must be `20..49`; map/zone markers `0..19` are rejected.
- `min_pass_frames` defaults to `1` and must be `<= burst_frames`.
- Response/event excludes bbox, mask, polygon, raw detections, and control actions.
- If config/frame/mapping is unavailable, API fails closed as `NO_DECISION`.

## 8. Things to agree with Main

1. What are the final Main `location_id` / zone ids?
   - Option A: Main sends AI `vision_zone_id` directly.
   - Option B: Main sends Main domain `location_id`; AI maintains explicit alias map.

2. How should Main store `expected_marker_id` ↔ item mapping?
   - Current physical item MVP uses ArUco marker itself as the item.
   - Candidate stable ids: `20,22,23,24,27,29`.

3. What should Main do on `FAIL` vs `UNCERTAIN`?
   - AI recommendation: `PASS` only is command-satisfying.
   - `FAIL` and `UNCERTAIN` should require Main/operator policy.

4. Should Main retry on `NO_DECISION`?
   - Suggested: retry once/twice if source is fresh but evidence is uncertain; do not retry indefinitely.

5. Which DB fields should store evidence?
   - Suggested minimum: `task_id`, `command_id`, `robot_id`, `operation`, `vision_zone_id` or `location_id`, `expected_item_id`, `expected_marker_id`, `result`, `reason_code`, `trusted=false`, `observed_at`, `event_id`.

## 9. Source documents

- Full API contract: `docs/contracts/ai-server-api.md`
- Generated OpenAPI: `docs/contracts/ai-server-openapi.json`
- Design/RALPLAN context: `docs/technical/vision_api_pull_eval_design_v1.md`
- ArUco candidate validation: `docs/test/global-cam-aruco-item-candidate-validation.md`
