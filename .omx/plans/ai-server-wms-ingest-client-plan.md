# Plan: AI Server WMS Ingest Client

- Date: 2026-06-11 Asia/Seoul
- Repo: `/home/codelab/Desktop/Project/SmartFactory`
- Scope: MVP1 AI Server outbound ingest for ArUco-only VisionEvent evidence
- Status: APPROVED by Architect/Critic review on 2026-06-11

## Requirements Summary

1. Use the existing API contract as the working Main/WMS contract unless a live Main/WMS implementation contradicts it:
   - AI Server debug/manual endpoint is `POST /api/v1/detect/image` (`docs/contracts/ai-server-api.md:128-152`).
   - Main/WMS ingest endpoint is `POST /api/v1/vision/events` (`docs/contracts/ai-server-api.md:154-175`).
   - Request body is one schema-valid `VisionEvent` (`docs/contracts/ai-server-api.md:158-160`).
2. Preserve AI Server boundaries:
   - AI Server remains API-first and evidence-only (`services/ai-server/app/main.py:16-20`).
   - AI Server remains ROS2-free / YOLO-free / Torch-free for MVP1; live robot and yolo_test are not required for this slice.
3. Keep current detection behavior:
   - `POST /api/v1/detect/image` validates source, decodes image, detects ArUco, builds VisionEvents, stores them locally (`services/ai-server/app/main.py:171-208`).
   - VisionEvents are contract-validated before returning (`services/ai-server/app/main.py:56-95`, `services/ai-server/app/contracts.py`).
4. Add optional outbound WMS emission controlled by config and request flag.

## Decision Defaults I Can Set Without More User Input

- Treat `docs/contracts/ai-server-api.md` as the current internal Main/WMS contract for MVP1.
- Implement only single-event POST to `/api/v1/vision/events`; do not implement batch now.
- Use best-effort emit policy for MVP1: WMS emit failure must not make image detection fail.
- Do not use live robots for this work; use offline generated ArUco fixtures and mocked HTTP clients.
- Do not introduce YOLO, Torch, or ROS2 imports into `services/ai-server`.
- Keep `emit=false` as default so tests and manual uploads do not unexpectedly call WMS.

## Architect Review Adjustments Applied

Architect review accepted the direction but required these corrections before implementation:

- Document the response change before code because `emit_results` is a new route-response surface.
- Add `httpx` to runtime dependencies, not only dev dependencies.
- Keep the WMS client explicitly async because `detect_image` is an async route.
- Define `emitted` semantics precisely; do not leave it as a request-flag echo.
- Keep the slice offline-only: no live robot SSH, no yolo_test integration, no ROS/YOLO/Torch imports.

## Proposed API Behavior

### `POST /api/v1/detect/image`

Existing response fields remain:

```json
{
  "source": "tb3_1_picam",
  "emitted": false,
  "events": []
}
```

Add a stable response shape with `emit_results` always present as a list. Define `emitted` as: `true` only when `emit=true`, `wms_emit_enabled=true`, at least one event exists, and every attempted WMS POST returns HTTP 200 or 202. Otherwise `emitted=false`. Recommended shape:

```json
{
  "source": "tb3_1_picam",
  "emitted": true,
  "events": [{ "schema_version": "vision-event.v1" }],
  "emit_results": [
    {
      "event_id": "...",
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
  ]
}
```

Failure example, still with HTTP 200 from `detect/image`:

```json
{
  "source": "tb3_1_picam",
  "emitted": false,
  "events": [{ "schema_version": "vision-event.v1" }],
  "emit_results": [
    {
      "event_id": "...",
      "attempted": true,
      "ok": false,
      "status_code": 503,
      "error": "WMS ingest returned HTTP 503",
      "response": null
    }
  ]
}
```

Rationale: `events` are still useful evidence; WMS connectivity is a downstream integration concern.

## Implementation Steps

1. Update the API docs first (`docs/contracts/ai-server-api.md`) to define `emit_results`, `emit_disabled`, and exact `emitted` semantics. Keep `docs/contracts/vision-event.schema.json` unchanged because this is a route-response change, not a VisionEvent change.
2. Add runtime HTTP dependency:
   - Move/add `httpx` into `services/ai-server/requirements.txt`.
   - Regenerate/update `services/ai-server/requirements.lock` if lockfile workflow is used by setup script.
3. Add WMS emit settings in `services/ai-server/app/config.py`:
   - `wms_emit_enabled: bool = false`
   - `wms_emit_timeout_s: float = 2.0`
   - `wms_emit_retries: int = 0`
   - optional path setting `wms_vision_events_path: str = "/api/v1/vision/events"`
4. Add `services/ai-server/app/wms_client.py`:
   - `EmitResult` dataclass or plain dict helper.
   - `build_wms_ingest_url(settings) -> str` safely joins base URL and path.
   - `async emit_vision_event(event, settings=None, client=None) -> dict` using `httpx.AsyncClient`.
   - Treat 200 and 202 as success; non-2xx as `ok=false` result, not exception to endpoint.
   - Catch timeout/network errors and return `ok=false` result.
5. Wire `detect_image` in `services/ai-server/app/main.py`:
   - Keep source validation, image decode, detection, local store unchanged.
   - If `emit and settings.wms_emit_enabled`, emit each generated event.
   - Return `emitted=true` only if `emit=true`, emit is enabled, at least one event exists, and all attempted WMS posts succeeded with HTTP 200/202.
   - If `emit=true` but config disabled, do not call network; return `emitted=false`, `emit_results=[]`, `emit_disabled=true`.
   - If there are zero events, return `emitted=false`, `emit_results=[]`; this is not an error.
6. Add tests:
   - Config disabled: `emit=true` makes no network call and still returns events.
   - Success: mocked WMS 202 returns ok result.
   - Duplicate/idempotent: mocked WMS 200 returns ok result.
   - Failure: mocked WMS 503 or transport error returns HTTP 200 detection response with `ok=false` emit result.
   - Timeout: handled as `ok=false` without failing detection.
   - Contract: emitted event remains valid `VisionEvent`.
7. Update docs/readme/env examples:
   - `services/ai-server/README.md` env vars and best-effort semantics.
   - `services/ai-server/.env.example` for the WMS emit settings.
   - Define `emit_results[].response` as parsed JSON only; use `null` for non-JSON responses and errors.
8. Verify:
   - Required for this slice: `./scripts/test_ai_server.sh -q`
   - Optional regression check after nearby ROS/env edits: `make ros-build-bringup`.

## Acceptance Criteria

- `emit=false` default performs no outbound HTTP and existing tests continue passing.
- With `emit=true` and `wms_emit_enabled=false`, AI Server performs no outbound HTTP, returns `emitted=false`, `emit_disabled=true`, and `emit_results=[]`.
- With `emit=true` and `wms_emit_enabled=true`, AI Server posts each generated VisionEvent once to `{MAIN_SERVER_URL}/api/v1/vision/events`.
- WMS HTTP `202` accepted and `200` duplicate/idempotent are treated as success; `emitted=true` only when all attempted posts succeed.
- WMS non-2xx, timeout, and connection errors do not fail image detection; response includes per-event failure details.
- AI Server still has no `rclpy`, YOLO, or Torch imports in runtime package.
- No live robot SSH access is required for this slice.
- Test suite passes: `./scripts/test_ai_server.sh -q`.

## Risks and Mitigations

- Risk: Main/WMS real implementation differs from docs. Mitigation: isolate WMS client behind one module and keep base URL/path configurable.
- Risk: silent emit failure hides integration problems. Mitigation: response includes `emit_results`; later add structured logs/metrics.
- Risk: endpoint response shape breaks existing tests/users. Mitigation: update API docs first, preserve existing `source`, `emitted`, `events`, and add `emit_results`/`emit_disabled` additively with stable semantics.
- Risk: long WMS calls slow manual detection. Mitigation: async HTTP client, short timeout default 2s, no retries by default.
- Risk: accidentally pulling ROS/YOLO into AI Server. Mitigation: keep existing dependency/import boundary tests and add a WMS-client-focused test only using `httpx`.

## Deferred Work

- Live camera/snapshot adapter as a separate ROS2/process bridge.
- WMS batch ingest.
- Durable local retry queue.
- Structured logging, request IDs, metrics.
- YOLO/object detection integration; explicitly out of MVP1 ArUco-only slice unless scope changes.

## User Questions Before Implementation

None blocking for MVP1 best-effort implementation. The only later business question is whether WMS emit failures should become hard failures in production. For MVP1, default to best-effort because AI Server is evidence producer and WMS connectivity should not invalidate local detection evidence.


## Review Verdicts

- Architect: direction approved with required corrections: document response contract first, add `httpx` to runtime deps, use async client, define `emitted` semantics, stay offline/ROS-free/YOLO-free.
- Critic: APPROVED. No blocking user question is required before MVP1 implementation. Executor notes: update tests expecting old `emitted` echo behavior; define `emit_results[].response` as JSON-or-null; AI-server-local tests are sufficient for this slice.
