# Main Person Hazard Integration Requirements

- Date: 2026-07-03
- Audience: Main Backend / Main Dashboard implementers
- Source document clarified: `docs/test/vision-person-hazard-live-validation.md`
- Status: Main handoff draft based on current repo implementation. Live Confluence was not checked for this handoff per project-owner instruction.

## 0. Scope decision

This document is the **Main integration requirements** document.

`docs/test/vision-person-hazard-live-validation.md` remains an **AI Server direct live-validation checklist**. Main should not treat that test document as the complete integration policy, DB policy, or safety-latch policy.

The Main integration boundary is:

```text
Robot PiCam / AI Server detection
  -> AI Server advisory person hazard API
  -> Main Backend polling and policy
  -> Main-owned DB write / HOLD / E-stop decision
```

AI Server is advisory/evidence only. AI Server must not issue motion commands, write Main DB rows, or decide final HOLD/E-stop.

## 1. 기준 브랜치/커밋

Use the following baseline for Main integration work:

| Item | Value |
| --- | --- |
| Branch | `feature/ai-server-marker-detection` |
| Minimum required commit | `0b18223` or newer |
| Older commit notes | `e263293` introduced dual-robot person monitors; `f3210a8` fixed optional-camera runtime behavior. They are superseded by `0b18223`; do not use the older two hashes as competing baselines. |

Guaranteed API surface at this baseline:

| API | Required for Main person hazard? | Purpose |
| --- | --- | --- |
| `GET /api/v1/health` | Yes | AI Server process/model/source summary health. |
| `GET /api/v1/vision/monitors` | Yes | Inspect monitor states. `person_drive` is robot/source-scoped; do not key only by `monitor_id`. |
| `GET /api/v1/vision/monitors/person_drive/state?robot_id={robot_id}` | Yes | Read one robot's person monitor state. |
| `PUT /api/v1/vision/monitors/person_drive/state` | Yes | Enable/disable one robot's DRIVE person monitor. |
| `GET /api/v1/vision/hazards/person/latest?robot_id={robot_id}` | Yes | Poll latest advisory person hazard for one robot. |
| `GET /api/v1/vision/streams?source={source}` | Recommended | Discover WebRTC/MJPEG stream URLs. |
| `POST /api/v1/vision/streams/{source}/webrtc/offer?view=full` | Optional | Media-only WebRTC offer/fallback descriptor when Main implements WHEP/offer flow. |

## 2. Main 연동 방식

### 2.1 Decision

Main Backend should call AI Server directly over service-to-service HTTP for monitor lifecycle and hazard polling.

```text
Main Backend -> http://smartfactory-vision.local:8100/api/v1/...
```

The browser/dashboard may use Main Backend proxy endpoints if Main wants same-origin UI access, but safety decisions must be made in Main Backend, not in the browser.

### 2.2 Optional Main proxy paths

If Main adds proxy endpoints, keep the AI Server schema unchanged and add Main policy decisions in separate Main-owned fields/tables.

Suggested proxy shape:

| Main path | Proxies to AI Server |
| --- | --- |
| `PUT /api/v1/vision/monitors/person_drive/state` | `PUT /api/v1/vision/monitors/person_drive/state` |
| `GET /api/v1/vision/monitors/person_drive/state?robot_id={robot_id}` | same |
| `GET /api/v1/vision/monitors` | same |
| `GET /api/v1/vision/hazards/person/latest?robot_id={robot_id}` | same |
| `GET /api/v1/vision/streams?source={source}` | same, for dashboard media discovery |

Proxy rules:

- Do not rewrite `event.trusted` from AI Server.
- Do not add `bbox`, `mask`, `polygon`, or raw detections to the proxied hazard payload.
- Do not expose AI Server advisory response as a motion command.

## 3. Monitor lifecycle

### 3.1 Enable on DRIVE start

When a robot enters DRIVE for a Main task, Main must enable the matching person monitor:

```bash
curl -X PUT "$AI_SERVER/api/v1/vision/monitors/person_drive/state" \
  -H 'Content-Type: application/json' \
  -d '{
    "enabled": true,
    "source": "tb3_1_picam",
    "operation_state": "DRIVE",
    "task_id": 101,
    "target_fps": 3
  }'
```

For `tb3_2`:

```json
{
  "enabled": true,
  "source": "tb3_2_picam",
  "operation_state": "DRIVE",
  "task_id": 102,
  "target_fps": 3
}
```

`task_id` values above are examples only. Main must pass its current task ID.

### 3.2 Disable on DRIVE end/cancel/failure

Main must disable the matching monitor on every terminal or non-DRIVE branch:

- normal DRIVE completion,
- operator cancel,
- task failure,
- robot state leaves DRIVE,
- robot disconnect where Main no longer wants to consume advisory person hazards for that task.

Disable one robot without affecting the other:

```bash
curl -X PUT "$AI_SERVER/api/v1/vision/monitors/person_drive/state" \
  -H 'Content-Type: application/json' \
  -d '{
    "enabled": false,
    "source": "tb3_1_picam",
    "operation_state": "IDLE"
  }'
```

### 3.3 Task ID change

If a robot starts a new DRIVE task while a previous monitor state may still be active, Main must reassert state for the new task.

Recommended sequence:

1. Disable previous state for that robot/source.
2. Enable new state with the new `task_id`.
3. Locally record the enable time.
4. Ignore any returned `event.observed_at` earlier than the local enable time or older than the stale threshold in section 8.

A single PUT with the new `task_id` is accepted by AI Server, but disable-then-enable is clearer for Main logs and stale-event filtering.

### 3.4 target_fps

| Value | Policy |
| --- | --- |
| Recommended | `3` fps per active robot |
| Main allowed range | `1..5` fps for this lab profile |
| AI Server validation today | positive number only (`> 0`) |

Main should cap itself to `1..5` even if AI Server currently accepts a larger positive value. `target_fps` is monitor intent and load guidance; Main polling policy remains Main-owned.

### 3.5 Two robots simultaneous DRIVE

Supported and required:

- `tb3_1` and `tb3_2` can both be enabled at the same time.
- States are independent.
- Disabling one robot must not disable the other.
- Poll each robot separately with `robot_id`.

## 4. Robot/source mapping

This mapping is a fixed contract for person hazard monitoring:

| `robot_id` | `source` |
| --- | --- |
| `tb3_1` | `tb3_1_picam` |
| `tb3_2` | `tb3_2_picam` |

### 4.1 Mismatch behavior

Example mismatch request:

```text
GET /api/v1/vision/hazards/person/latest?robot_id=tb3_1&source=tb3_2_picam
```

Expected response:

| Field | Value |
| --- | --- |
| HTTP status | `400` |
| `error.code` | `BAD_REQUEST` |
| `error.message` | contains `robot_id tb3_1 requires source tb3_1_picam` |
| Main retry? | No. This is a caller bug/configuration error. Fix mapping, do not retry with backoff. |

Monitor-state mismatch is also rejected:

```json
{
  "enabled": true,
  "source": "tb3_1_picam",
  "robot_id": "tb3_2",
  "operation_state": "DRIVE"
}
```

Expected: HTTP `400`, message contains `source 'tb3_1_picam' requires robot_id 'tb3_1'`.

## 5. Person hazard response schema

Endpoint:

```text
GET /api/v1/vision/hazards/person/latest?robot_id={tb3_1|tb3_2}
```

### 5.1 Top-level response

Top-level schema for this endpoint:

```json
{
  "schema_version": "vision-person-hazard-latest.v1",
  "monitor_id": "person_drive",
  "source": "tb3_1_picam",
  "robot_id": "tb3_1",
  "result": "ADVISORY",
  "reason_code": "HUMAN_DETECTED",
  "event": {}
}
```

Top-level `result` enum for this endpoint only:

| result | Meaning |
| --- | --- |
| `ADVISORY` | Active DRIVE monitor found a person event. See `event`. |
| `NO_ACTIVE_MONITOR` | Monitor is disabled, missing, not DRIVE, or source/robot state does not match. |
| `NO_RELEVANT_DETECTION` | Monitor is active, but latest scanned events contain no person detection. |

Top-level `reason_code` enum for this endpoint only:

- `HUMAN_DETECTED`
- `NO_ACTIVE_MONITOR`
- `NO_RELEVANT_DETECTION`

Top-level timestamp/confidence:

- Top-level response has no `timestamp` or `confidence` field.
- Use `event.observed_at` and `event.confidence` when `event != null`.

### 5.2 Non-null event schema for person hazard

When `result=ADVISORY`, `event` is a compact `vision-monitor-event.v1` object.

Person-hazard non-null event fields Main should consume:

| Field | Person hazard value/policy |
| --- | --- |
| `event.schema_version` | `vision-monitor-event.v1` |
| `event.event_id` | AI Server generated UUID for this advisory response. Use `data_json.source_event_id` for source detection dedup if needed. |
| `event.event_type` | `HUMAN_DETECTED` |
| `event.source` | `tb3_1_picam` or `tb3_2_picam` |
| `event.robot_id` | `tb3_1` or `tb3_2` |
| `event.task_id` | Current monitor state's `task_id`; can be integer, string, or null. Main should require it to match current task before action. |
| `event.command_id` | `null` for person hazard. |
| `event.result` | `ADVISORY` |
| `event.severity` | `CRITICAL` |
| `event.confidence` | Number `0..1` or `null`, derived from source detection confidence. |
| `event.reason_code` | `HUMAN_DETECTED` |
| `event.trusted` | Always `false`. |
| `event.observed_at` | ISO datetime from source detection timestamp or AI Server time fallback. This is the timestamp Main should stale-gate. |
| `event.image_url` | `null` for current person hazard. |
| `event.policy_version` | `mvp2` |
| `event.profile_id` | `person_drive_picam_v1` |
| `event.threshold_set_id` | `person_pretrained_nano_v1` |
| `event.data_json.result` | `ADVISORY` |
| `event.data_json.reason_code` | `HUMAN_DETECTED` |
| `event.data_json.assignment_status` | `OWNED` |
| `event.data_json.related_robot_ids` | `[]` |
| `event.data_json.task_id_ref` | Same task ID reference as event task. |
| `event.data_json.source_event_id` | Underlying source detection event ID, if available. |

Example:

```json
{
  "schema_version": "vision-person-hazard-latest.v1",
  "monitor_id": "person_drive",
  "source": "tb3_1_picam",
  "robot_id": "tb3_1",
  "result": "ADVISORY",
  "reason_code": "HUMAN_DETECTED",
  "event": {
    "schema_version": "vision-monitor-event.v1",
    "event_id": "00000000-0000-4000-8000-000000000001",
    "event_type": "HUMAN_DETECTED",
    "source": "tb3_1_picam",
    "robot_id": "tb3_1",
    "task_id": 101,
    "command_id": null,
    "result": "ADVISORY",
    "severity": "CRITICAL",
    "confidence": 0.87,
    "reason_code": "HUMAN_DETECTED",
    "trusted": false,
    "observed_at": "2026-07-03T09:00:00+09:00",
    "image_url": null,
    "policy_version": "mvp2",
    "profile_id": "person_drive_picam_v1",
    "threshold_set_id": "person_pretrained_nano_v1",
    "data_json": {
      "result": "ADVISORY",
      "reason_code": "HUMAN_DETECTED",
      "policy_version": "mvp2",
      "profile_id": "person_drive_picam_v1",
      "threshold_set_id": "person_pretrained_nano_v1",
      "assignment_status": "OWNED",
      "related_robot_ids": [],
      "task_id_ref": 101,
      "source_event_id": "source-person-event-1"
    }
  }
}
```

### 5.3 Raw detection exclusion guarantee

The Main-facing person hazard advisory must not include:

- `bbox`
- `bbox_xyxy`
- `mask`
- `mask_rle`
- `polygon`
- `raw_detections`
- `detections`
- image bytes
- motion/control action strings such as `HOLD`, `E_STOP`, `STOP_COMMAND`, `MOTION_CANCELLED`

This is enforced by `vision-monitor-event.v1` schema/tests. Main should reject any advisory payload that violates this compact contract.

## 6. Advisory와 Main 안전정지 정책 경계

### 6.1 AI Server policy

For person hazard:

- AI Server response is always advisory-only.
- AI Server returns `trusted=false` for non-null `event`.
- AI Server must not write Main DB.
- AI Server must not issue motion commands.
- AI Server must not publish or return final state values such as `HOLD`, `E_STOP`, `STOP_COMMAND`, `MOTION_CANCELLED`, or `BLOCKED`.
- AI Server must not publish `/cmd_vel`, Nav2 goals, teleop commands, or ROS parameter mutation as part of this API.

### 6.2 Main evidence_events policy

Main may insert an `evidence_events` row when all are true:

1. Current Main robot state is DRIVE.
2. The relevant robot monitor is enabled or Main just enabled it.
3. `response.result == "ADVISORY"`.
4. `event.event_type == "HUMAN_DETECTED"`.
5. `event.robot_id` and `event.source` match the fixed mapping.
6. `event.task_id` matches Main's current task for that robot.
7. `event.observed_at` is fresh under section 8 stale policy.
8. Main dedup/cooldown accepts it.

Store AI Server evidence as `trusted=false` unless Main has a separate explicit promotion policy. Do not store raw bbox/mask/detections because the API does not provide them.

### 6.3 Main safety_stops / HOLD policy

Main owns final HOLD/E-stop.

AI Server `ADVISORY/HUMAN_DETECTED` is an input signal, not a trusted final safety latch.

Recommended Main behavior:

- For runtime safety action, Main may trigger HOLD according to Main-owned policy when a fresh advisory matches active DRIVE task/robot and passes Main cooldown/dedup rules.
- If Main DB logic only allows `safety_stops` from trusted evidence, do not reinterpret AI Server `trusted=false` as trusted. Instead either:
  - record `evidence_events` as untrusted advisory and create a separate Main-owned safety decision row, or
  - keep runtime HOLD state separate from evidence trust until a Main promotion policy exists.
- Main should not wait for AI Server to command HOLD; AI Server will not do that.

## 7. Camera/WebRTC 검증 조건

### 7.1 Required for person hazard validation

Required camera sources for person hazard:

| Source | Required? | Reason |
| --- | --- | --- |
| `tb3_1_picam` | Required when validating `tb3_1` |
| `tb3_2_picam` | Required when validating `tb3_2` |
| `global_cam_01` / GoPro | Optional for person hazard |

GoPro/global cam is not required for person hazard Main integration. If GoPro is disconnected, AI Server health should still be `status=ok` as long as AI Server is alive; `source_summary` may show `global_cam_01` offline/stale. Main must not fail person hazard integration solely because GoPro is offline.

### 7.2 PiCam WebRTC browser paths

Current lab profile browser paths:

```text
http://smartfactory-vision.local:8889/tb3_1_picam_full/
http://smartfactory-vision.local:8889/tb3_2_picam_full/
```

The path is `{source}_{view}`, with `view=full`. Do not use:

```text
http://smartfactory-vision.local:8889/tb3_1_picam/
http://smartfactory-vision.local:8889/tb3_2_picam/
```

### 7.3 Discovery vs direct construction

Main should prefer discovery for resilience:

```text
GET /api/v1/vision/streams?source=tb3_1_picam
GET /api/v1/vision/streams?source=tb3_2_picam
```

Use the `stream_transports[]` entry with:

- `kind == "webrtc"`
- `view == "full"`
- `sidecar.browser_url` for operator/demo browser embed
- `sidecar.whep_url` for WHEP-capable player integration

Direct path construction is acceptable only for current lab smoke tests and must include `_full`.

## 8. Polling / failure handling

### 8.1 Polling rate

During DRIVE, Main should poll per active robot:

```text
GET /api/v1/vision/hazards/person/latest?robot_id=tb3_1
GET /api/v1/vision/hazards/person/latest?robot_id=tb3_2
```

Recommended:

| Setting | Value |
| --- | --- |
| Polling rate | `2..5 Hz` per active robot |
| Initial value | `3 Hz` per active robot |
| Request timeout | `500 ms` preferred, `1000 ms` max for lab WiFi |
| Backoff on transient network error | Start `250..500 ms`, cap near `2 s`, reset on success |
| Dedup key | Prefer `event.data_json.source_event_id`; fallback to `event.event_id` plus `event.observed_at` |

### 8.2 Stale event policy

Main must stale-gate `ADVISORY` responses because the latest endpoint summarizes recent AI detections and should not be treated as proof that the person is still visible indefinitely.

Recommended policy:

- Treat `event.observed_at` older than `2.0 s` as stale for HOLD/evidence creation.
- Also ignore events with `event.observed_at` earlier than the local monitor enable time for the current task.
- If Main needs stricter stopping, use `1.0 s`; if WiFi is unstable, do not exceed `3.0 s` without operator approval.

Stale advisory handling:

- Do not create a new person-hazard `safety_stops` row from stale advisory.
- Do not infer `NO_RELEVANT_DETECTION` from stale advisory; instead mark the vision signal as stale/degraded and continue polling.

### 8.3 Result handling

| AI result | Main handling |
| --- | --- |
| `ADVISORY` + fresh `HUMAN_DETECTED` | Main performs task/robot/source/staleness/dedup checks, then records untrusted evidence and/or triggers Main-owned HOLD policy. |
| `ADVISORY` but stale | Ignore for new HOLD; mark stale/degraded if repeated. |
| `NO_ACTIVE_MONITOR` | Expected when robot is not in DRIVE or Main disabled monitor. If Main believes robot is DRIVE, reassert monitor state and log integration warning. |
| `NO_RELEVANT_DETECTION` | No current person advisory. Do not write person evidence. Continue polling while DRIVE. |
| HTTP `400` | Main bug/config error. Do not retry blindly; fix request. |
| AI Server unreachable/timeout | Mark vision hazard input unavailable/degraded. Do not treat as “no person”. Do not create AI trusted evidence. Main may apply a separate Main-owned fail-safe policy if required. |

## 9. Pass criteria

Main integration is complete when all are true:

1. Main uses branch `feature/ai-server-marker-detection` at commit `0b18223` or newer for AI Server.
2. Main can reach `GET /api/v1/health` on AI Server by hostname or configured fallback IP.
3. Main enables `person_drive` for `tb3_1` without enabling `tb3_2`.
4. Main enables `person_drive` for `tb3_2` without disabling `tb3_1`.
5. Main supports both robots active at the same time.
6. Main disables one robot monitor without disabling the other.
7. Main polls `GET /api/v1/vision/hazards/person/latest?robot_id=...` separately per robot.
8. No source/robot event mixing occurs:
   - `tb3_1` response uses `tb3_1_picam` and `tb3_1`.
   - `tb3_2` response uses `tb3_2_picam` and `tb3_2`.
9. Mismatch request is rejected with HTTP `400`; Main does not retry it as transient.
10. Main rejects or ignores any advisory payload containing raw bbox/mask/polygon/detections or motion command fields.
11. Main records AI person hazard evidence as `trusted=false` unless a separate Main-owned promotion policy exists.
12. Main owns DB writes, cooldown, dedup, stale filtering, and HOLD/E-stop decisions.
13. AI Server performs no Main DB write and emits no motion command.
14. PiCam WebRTC paths are either discovered from `/api/v1/vision/streams` or use the confirmed lab paths `tb3_1_picam_full` / `tb3_2_picam_full`.
15. GoPro/global cam offline does not block person hazard validation if the required PiCam source is online.

## 10. Quick Main implementation checklist

For each robot entering DRIVE:

1. Resolve mapping: `robot_id -> source`.
2. `PUT /vision/monitors/person_drive/state enabled=true` with source, DRIVE, task_id, target_fps=3.
3. Record local monitor enable time.
4. Poll `/vision/hazards/person/latest?robot_id=...` at ~3 Hz.
5. On fresh `ADVISORY/HUMAN_DETECTED`, run Main policy: task match, stale gate, dedup/cooldown, DB write, runtime HOLD if Main policy says so.
6. On DRIVE exit/cancel/fail, `PUT enabled=false` for that robot/source.
7. Keep robot states independent; never key `person_drive` solely by monitor_id.
