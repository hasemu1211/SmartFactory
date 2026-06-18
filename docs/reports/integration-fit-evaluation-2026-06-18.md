# SmartFactory Integration Fit Evaluation — 2026-06-18

## Verdict

The current D1 vision gateway direction is fit for the next local/Main integration milestone if it stays inside the existing safety boundary:

- AI Server remains an API/evidence service, not a ROS participant.
- ROS/domain-specific camera and stream handling stays in sidecars and scripts.
- Main/WMS remains the source of truth for decisions and state transitions.
- Main/GUI should consume one source-based base URL on `:8090` instead of direct per-robot service URLs.
- Real-robot use is **not part of the default execution path**. Only optional, temporary, read-only camera/topic smoke is acceptable after local gates pass.

## Boundary fit

### AI Server

Fit: good.

- The route/helper cleanup moved OpenAPI/schema helpers into `services/ai-server/app/openapi_schemas.py`.
- `services/ai-server/app/main.py` still owns FastAPI routes and imports no ROS2, YOLO, or Torch runtime modules as hard dependencies.
- Public endpoint behavior is preserved by the AI Server test suite and generated OpenAPI drift checks.

Risk to watch:

- Do not let AI Server absorb ROS domain handling, robot control, Nav2, or camera transport ownership.
- Keep future helper extraction small and behavior-preserving; prioritize pure schema/serialization helpers before stateful route logic.

### ROS sidecars and gateway scripts

Fit: good for D1.

- `scripts/run_d1_vision_multi_source_gateway_bundle.sh` is the canonical local/Main integration entrypoint.
- Thin Makefile aliases (`vision-check`, `vision-run`, `vision-config`, `vision-smoke-local`, `ros-test`) reduce operator ambiguity while keeping underlying scripts visible.
- `make ros-launch-smoke` verifies central bringup can start with optional camera/AI/WMS/Nav2 paths disabled.

Risk to watch:

- Avoid adding a whole-graph bridge by default.
- Keep per-source and per-domain handling explicit.
- Keep `use_nav2:=false` and optional robot services false in smoke/default paths.

### Main/GUI stream contract

Fit: good.

- Main/GUI should use one public base URL on `:8090` and select streams by `source`.
- The source registry drives canonical source IDs: `global_cam_01`, `tb3_1_picam`, `tb3_2_picam`.
- Generated surfaces and OpenAPI snapshots were regenerated and checked with no git drift.

Risk to watch:

- Any source ID/topic rename must update `config/vision/sources.yaml`, generated contract surfaces, OpenAPI, fixtures, scripts, and docs together.
- Do not introduce per-robot GUI URLs as a second source of truth.

### Semantic event handoff

Fit: good.

- Vision events remain evidence-only.
- `wms_hint` is non-authoritative; WMS/Main owns final task, slot, and exception state.
- Contract fixtures validate both accepted and rejected event shapes.

Risk to watch:

- Do not add AI-server-side final state transitions.
- Keep marker/ROI evidence strict enough for WMS policy decisions.

### Model runtime and performance realism

Fit: acceptable for local integration, not yet production-performance certified.

- `make vision-check` disables the model worker by default for safe preflight, while `make vision-run` follows the bundle script default (`VISION_MODEL_WORKER_ENABLED=true`) unless the operator overrides it.
- The async frame/process path and source stream gateway are present, but performance claims should remain conservative until measured with representative cameras and explicit model-worker settings.

Risk to watch:

- Do not present synthetic/local smoke results as real robot throughput.
- Record whether the model worker was enabled, plus FPS, latency, stale/drop policy, and source-specific failures when moving to live camera checks.

## Robot safety and real-robot status

Real robot was **not used** for this cleanup/refactor execution.

Default forbidden actions remain:

- No `/cmd_vel` publishing.
- No Nav2 execution.
- No teleop.
- No robot-side persistent package, launch, systemd, or parameter changes.
- No parameter mutation.
- No whole-graph bridge.

Optional future live step, only after local gates pass:

1. Temporary camera/topic read-only smoke.
2. No motion/control topics.
3. No persistent robot-side changes.
4. Capture source, topic, timestamp, frame rate, and any stale/drop evidence.

## Verification evidence

Leader verification after team integration:

- `./scripts/test_ai_server.sh -q` → 133 passed.
- `python3 scripts/validate_contracts.py` → passed.
- `python3 scripts/validate_deployment_assets.py` → passed.
- `make source-registry-surfaces` → regenerated surfaces with clean git status.
- `make deploy-validate` → passed.
- `make ros-test` → 38 passed.
- `make ros-launch-smoke` → passed with optional robot/control services disabled.
- `make vision-check` → passed and printed Main/GUI `:8090` source URLs.
- `git diff --check`, shell syntax, and selected script `py_compile` → passed.

## Recommendation

Proceed with local/Main integration using `make vision-check` then `make vision-run` as the operator path. Treat live robot camera checks as an explicit, optional, read-only follow-up gate, not as part of the default cleanup/refactor success criteria.
