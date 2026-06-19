# Source Registry v2 and Evidence Contract Migration Plan

- Status: Draft migration plan for post-MVP1 contract alignment.
- Date: 2026-06-18
- Owner lane: AI Server / Vision contract alignment.
- Scope: plan only; no live robot movement and no ROS control-topic mutation.
- Current source of truth: `config/vision/sources.yaml` (`vision-sources.v1`) plus generated schema/OpenAPI/fixture surfaces.

## 1. Goals

1. Keep the current three MVP1 sources stable while preparing a `vision-sources.v2` registry shape:
   - `global_cam_01`
   - `tb3_1_picam`
   - `tb3_2_picam`
2. Make two TurtleBot3 Pi cameras first-class, symmetric evidence sources for local marker/dock/item/lift ROI evidence.
3. Leave a compatible slot for a future fixed global depth-capable source without making MVP1 depend on depth.
4. Keep evidence advisory-only: AI Server emits evidence; Main/WMS owns task, inventory, exception, and robot state transitions.
5. Migrate `LiftRoiEvidence.task_id` from `string|null` to `integer|null` in one coordinated contract/code/fixture change.

## 2. Non-goals and safety boundaries

- Do not add `/cmd_vel`, Nav2 action, teleop, parameter mutation, whole-graph DDS bridge, `/tf`, or `/rosout` exposure to the vision contract.
- Do not claim depth is available in MVP1. `VisionEvent.depth_median_m` remains `null` until a new depth-capable source and schema version are adopted.
- Do not change physical robot behavior. Validation is staged, synthetic, local, or passive ROS observation only.
- Do not make AI Server authoritative for pickup/dropoff success. `LiftRoiEvidence.verification.status` remains evidence that Main/WMS interprets.

## 3. Current v1 baseline

`vision-sources.v1` stores the source list and drives generated contract surfaces:

| Source | Kind | Robot | Physical input | Normalized image | Normalized overlay | Current evidence use |
| --- | --- | --- | --- | --- | --- | --- |
| `global_cam_01` | `global_rgb` | `null` | `/global_camera/image_raw` | `/sf/vision/sources/global_cam_01/image/compressed` | `/sf/vision/sources/global_cam_01/overlay/compressed` | overview, slot, zone, person/obstacle candidates |
| `tb3_1_picam` | `robot_pi_camera` | `tb3_1` | `/tb3_1/camera/image_raw/compressed` | `/sf/vision/sources/tb3_1_picam/image/compressed` | `/sf/vision/sources/tb3_1_picam/overlay/compressed` | local marker, dock, item, lift ROI evidence |
| `tb3_2_picam` | `robot_pi_camera` | `tb3_2` | `/tb3_2/camera/image_raw/compressed` | `/sf/vision/sources/tb3_2_picam/image/compressed` | `/sf/vision/sources/tb3_2_picam/overlay/compressed` | local marker, dock, item, lift ROI evidence |

Generated surfaces that must not drift:

- `docs/contracts/vision-event.schema.json`
- `docs/contracts/lift-roi-evidence.schema.json`
- `docs/contracts/generated/source-registry.snapshot.json`
- `docs/contracts/fixtures/source-registry.valid.json`
- `docs/contracts/ai-server-openapi.json`

## 4. Proposed `vision-sources.v2` registry shape

Keep all v1 fields and add explicit capability metadata. Proposed additive fields per source:

| Field | Type | Purpose |
| --- | --- | --- |
| `modalities` | array enum | e.g. `rgb`, `compressed_rgb`, `depth`, `aligned_rgb_depth` |
| `evidence_capabilities` | array enum | Which evidence contracts/classes this source may produce. |
| `depth` | object or `null` | Depth topic, message type, alignment frame, unit, and MVP availability. |
| `safety_class` | enum | `evidence_only` for all current/future vision sources unless explicitly approved otherwise. |
| `authority` | object | States that Main/WMS/Movement own final transitions and motion decisions. |

Example source entries, abbreviated:

```yaml
schema_version: vision-sources.v2
sources:
  - source_id: tb3_1_picam
    kind: robot_pi_camera
    robot_id: tb3_1
    modalities: [compressed_rgb]
    evidence_capabilities:
      - aruco_marker
      - qr_marker
      - barcode_marker
      - person_candidate
      - obstacle_candidate
      - lift_roi
      - docking_evidence
    depth: null
    safety_class: evidence_only
    authority:
      state_transitions: main_wms
      motion_control: movement

  - source_id: global_depth_01
    kind: global_rgbd
    robot_id: null
    enabled: false
    modalities: [rgb, depth, aligned_rgb_depth]
    evidence_capabilities:
      - person_candidate
      - obstacle_candidate
      - item_candidate
      - slot_candidate
      - depth_roi
    depth:
      topic: /global_depth_01/aligned_depth_to_color/image_raw
      message_type: sensor_msgs/msg/Image
      content_type: image/depth16
      unit: millimeter
      aligned_to_frame_id: global_depth_01_color_optical_frame
      mvp1_required: false
    safety_class: evidence_only
    authority:
      state_transitions: main_wms
      motion_control: movement
```

`global_depth_01` is a reserved future example, not an MVP1 source. It should remain disabled until hardware, calibration, source health, and schema fixtures exist.

## 5. Evidence contracts covered by v2

### 5.1 `VisionEvent`

`VisionEvent` remains the lightweight event stream for candidates and decoded markers.

| Evidence | Required source support | Contract notes |
| --- | --- | --- |
| QR/barcode | `qr_marker` / `barcode_marker` capability | Use `class_name=qr_marker` or a new schema enum only after schema migration; decoded ID remains `marker_id`. |
| Person | `person_candidate` | `class_name=person`, optional `bbox_xyxy`, `wms_hint=PERSON_CANDIDATE`. |
| Obstacle | `obstacle_candidate` | `class_name=obstacle`, optional ROI/zone; Movement does not subscribe directly. |
| Docking | `docking_evidence` | Marker pose or 2D advisory data only; no direct Nav2 goal or `/cmd_vel`. |
| Depth ROI | `depth_roi` | Requires a v2/v3 schema decision before `depth_median_m` may become non-null. |

### 5.2 `LiftRoiEvidence`

`LiftRoiEvidence` remains the richer ROI/count/verification payload for pickup/dropoff/monitor evidence. It should be allowed only from sources with `lift_roi` capability. TB3 Pi cameras are the primary near-lift sources; global sources may support monitor/dropoff evidence only after calibration rules are documented.

Target `task_id` migration:

| Contract version | `task_id` type | Compatibility rule |
| --- | --- | --- |
| current `lift-roi-evidence.v1` | `string|null` | Existing fixtures/code stay valid until migration lands. |
| migration target | `integer|null` | Main/WMS integer task IDs are represented exactly; `null` remains valid for monitor/debug evidence. |

## 6. Migration phases

### Phase A — Plan and guardrails (this task)

- Publish this migration plan.
- Keep v1 generated surfaces green.
- Document exact test surfaces for source-registry v2 and `task_id` transition.

### Phase B — v2 registry parser in parallel with v1

- Extend `services/ai-server/app/source_registry.py` dataclasses with optional v2 fields and defaults for v1 registries.
- Add parser tests for:
  - v1 registry remains accepted with default capability metadata.
  - v2 registry accepts two TB3 Pi cameras and disabled `global_depth_01`.
  - duplicate `source_id` remains rejected.
  - unknown modality/capability is rejected.
  - every source has `safety_class=evidence_only` unless a future approved contract changes it.

### Phase C — generated surfaces

- Update `scripts/generate/generate_source_registry_surfaces.py` so snapshots preserve v2 capability/depth metadata.
- Keep source enum generation stable for `VisionEvent` and `LiftRoiEvidence`.
- Regenerate:
  - `docs/contracts/generated/source-registry.snapshot.json`
  - `docs/contracts/fixtures/source-registry.valid.json`
  - `docs/contracts/ai-server-openapi.json`

### Phase D — evidence capability policy checks

- Add contract policy validation so:
  - `LiftRoiEvidence.source` must have `lift_roi` capability.
  - docking advisory evidence must come from sources with `docking_evidence`.
  - non-null depth evidence is rejected unless the source has enabled depth metadata and the evidence schema version allows depth.
- Keep current `depth_median_m must be null` checks until that schema migration is explicitly approved.

### Phase E — `task_id` integer/null migration

Perform this as one atomic change:

1. Update `docs/contracts/lift-roi-evidence.schema.json` `task_id` from `string|null` to `integer|null`.
2. Update fixtures:
   - valid pickup/dropoff use integer task IDs,
   - monitor or source mismatch fixtures keep `null` where applicable,
   - add invalid fixture for string task ID after migration.
3. Update `services/ai-server/app/lift_roi_evidence.py` request validation to accept only `int|null` and reject strings/bools.
4. Update FastAPI form parsing in `services/ai-server/app/main.py` so multipart `task_id` is parsed as integer/null and invalid strings fail closed.
5. Update docs/examples in `docs/contracts/ai-server-api.md` and Confluence-report source docs.
6. Regenerate OpenAPI.

## 7. Required regression tests

### Source-registry v2 tests

Add or update tests in `services/ai-server/tests/test_source_registry.py`:

- `test_source_registry_v1_loads_with_default_capabilities`
- `test_source_registry_v2_loads_two_tb3_picams_and_disabled_global_depth_source`
- `test_source_registry_v2_rejects_unknown_capability`
- `test_contract_schema_source_enums_match_registry_after_v2_generation`
- `test_generated_source_registry_snapshot_preserves_capability_metadata`

### Evidence capability tests

Add or update tests in `services/ai-server/tests/test_contract_boundaries.py` or `services/ai-server/tests/test_api_lift_roi.py`:

- lift ROI from `tb3_1_picam` and `tb3_2_picam` is accepted when capability is present,
- lift ROI from a source without `lift_roi` capability is rejected,
- non-null depth payload remains rejected for MVP1 schemas,
- QR/barcode/person/obstacle/docking examples remain advisory evidence only.

### `task_id` integer/null transition tests

Add these tests before/with Phase E:

- JSON endpoint accepts integer `task_id` and echoes it as an integer.
- JSON endpoint accepts `task_id: null`.
- JSON endpoint rejects string `task_id` after migration.
- Multipart endpoint accepts numeric form `task_id` and serializes integer.
- Multipart endpoint rejects non-numeric form `task_id` with the common error envelope.
- Schema fixture validation rejects a string `task_id` invalid fixture.
- Generated OpenAPI exposes `task_id` as `integer` or `null`, not `string`.

Suggested commands:

```bash
python3 scripts/generate/generate_source_registry_surfaces.py
python3 scripts/validate/validate_contracts.py
cd services/ai-server && ./scripts/ai/test_ai_server.sh -q
# or targeted:
cd services/ai-server && .venv/bin/python -m pytest -q \
  tests/test_source_registry.py \
  tests/test_api_lift_roi.py \
  tests/test_contract_boundaries.py
```

## 8. Acceptance criteria

- `config/vision/sources.yaml` remains the single source of truth for source IDs and topic handoff metadata.
- Two TB3 Pi cameras remain explicitly covered and symmetric.
- A future global depth-capable source is documented as disabled/non-MVP until schema and hardware validation exist.
- QR/barcode/person/obstacle/lift ROI/docking evidence paths are mapped to capability metadata and remain advisory.
- `task_id` migration has a concrete integer/null test plan and an atomic implementation sequence.
- Generated contract surfaces and existing contract validation remain green after each phase.

## 9. Coordination protocol evidence

Coordination protocol: coordinated - cross-boundary contracts checked across `config/vision/sources.yaml`, source-registry generation, `VisionEvent`, `LiftRoiEvidence`, Main/WMS task ownership, Lane C ROS topic handoff, and Movement safety boundaries.
