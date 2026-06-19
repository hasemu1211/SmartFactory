# SmartFactory project filesystem ownership

Created: 2026-06-19 KST
Status: local planning/operations guide; local docs are drafts unless live Confluence or user-confirmed facts say otherwise.

This document defines how to organize files by **actual purpose, callers, and runtime ownership**. It is not a cosmetic folder-renaming checklist.

## Non-negotiable compatibility rules

- Keep root operator entrypoints stable until a wrapper-backed move is implemented and verified.
- Do not broad-move `scripts/`, `ros2/`, `ops/`, or `services/` only to make the tree look cleaner.
- If a file is referenced by Makefile, tests, systemd, Docker, runbooks, or operator commands, either keep it in place or leave a root compatibility wrapper.
- Preserve the current Main/Vision contract:
  - `MAIN_SERVER_URL=http://smartfactory-main.local:8088`
  - Main-facing stream base: `http://smartfactory-vision.local:8090`
  - `smartfactory-vision.local` is temporary mDNS in this repo unless router/DNS/hostname is configured outside the repo.
  - `WMS_EMIT_ENABLED=false` is the safe default.
- Session-specific live-process placement, such as the current tmux window used for validation, belongs in runbooks or `.omx/reports`; do not bake transient pane/window IDs into durable placement rules.
- No active robot motion, `/cmd_vel`, Nav2, teleop, ROS parameter mutation, robot-side persistence, live systemd mutation, or whole-graph rosbridge exposure belongs to this cleanup path.

## Top-level ownership

| Path | Owner | Belongs here | Does not belong here |
|---|---|---|---|
| `services/ai-server/` | FastAPI AI/Vision evidence service | HTTP APIs, app factory, route modules, runtime state, source registry integration, detection/evidence/cache logic, service tests | ROS node startup, shell process orchestration, systemd install steps |
| `ros2/smartfactory_perception_ros/` | ROS2 sidecars and adapters | ROS launch files, ROS nodes, camera snapshot clients, frame gateway, overlay stream bridge, ROS-specific tests/config | FastAPI app construction, WMS/Main DB ownership, operator shell bundles |
| `scripts/` | Operator/developer entrypoints | Local setup/run/test/smoke/generate/validate/report helpers; stable root wrappers for commands users type | Long-lived service internals that should be importable modules; live system mutation without explicit ops gate |
| `ops/` | Deployment assets | systemd units, future env examples, deployment runbooks, deploy validators | Local dev-only scripts, service implementation code |
| `docs/` | Draft docs/contracts/runbooks/reports | local contracts, requests, runbooks, technical plans, reports | Unverified public/timeline claims without Confluence/user confirmation |
| `config/` | Runtime/config source of truth | source registry, perception profiles, vision config | generated docs or ad-hoc runtime cache |
| `.omx/` | OMX workflow state/evidence | plans, context snapshots, ledgers, reports | product source code or human-facing canonical docs |
| `omx_wiki/` | persistent local project wiki | session notes, local memory, searchable notes | authoritative external/public docs |

## `services/ai-server/` placement rules

Current accepted seams:

- `app.main:app` stays a compatibility wrapper for uvicorn, Docker, and existing scripts.
- `app.factory:create_app` is the canonical app construction seam.
- `app/api/health.py` owns health/source/latest-detections read-model routes.
- `runtime_routes.register_routes()` remains the wiring owner for middleware, exception handlers, runtime context binding, and API module registration.
- `app/api/*` must not import `runtime_routes` or private runtime state from `runtime_routes`.

Future service moves should be by route/domain ownership:

| Candidate | Destination rule | Move style |
|---|---|---|
| Health/source/latest-detections | Already in `app/api/health.py` | Verify/checkpoint only |
| Vision/frame/overlay/worker/detect/lift ROI routes | `app/api/<cohesive-surface>.py` | Move as-is behind injected context, then test |
| Runtime stores/context/observability | `app/runtime_*` or current focused modules | Do not move unless reducing coupling |
| Pure detection/evidence helpers | service-owned pure modules first | Promote to shared package only by future ADR |
| WMS/Main callback client | integration module | Preserve `WMS_EMIT_ENABLED=false` default |

## `scripts/` placement rules

Root scripts are the stable compatibility surface. Implementation files are
classified by purpose under subdirectories, while the root wrapper names stay
stable for Makefile targets, runbooks, service files, and operator muscle memory.

| Class | Root compatibility entrypoints | Implementation location | Placement decision |
|---|---|---|---|
| AI Server | `run_ai_server.sh`, `setup_ai_server_env.sh`, `setup_ai_server_model_env.sh`, `test_ai_server.sh` | `scripts/ai/` | Root wrappers stay stable; implementation owns AI Server setup/run/test behavior |
| Vision/Main operator entrypoints | `publish_vision_mdns_alias.py`, `run_d1_vision_multi_source_gateway_bundle.sh`, `run_d1_vision_stream_gateway.py`, `run_d1_vision_bundle.sh`, `run_d1_vision_domain_sidecar.sh`, `smoke_main_dashboard_gateway.sh`, `prepare_docking_tuning_session.sh` | `scripts/vision/` | Root wrappers preserve existing operator commands; implementation owns Vision/Main lab runtime helpers |
| Validation | `validate_contracts.py`, `validate_deployment_assets.py` | `scripts/validate/` | Root wrappers preserve Makefile/docs/tests |
| Generation | `generate_source_registry_surfaces.py` | `scripts/generate/` | Root wrapper preserves contract generation command |
| Reports/assets | `create_sprint3_presentation_pptx.py`, `generate-drawio-architectures.py`, `render-scenario-sequence-diagrams.py` | `scripts/reports/` | Report generators are separated from runtime/operator scripts |
| Ops checks | `check-confluence-env.sh` | `scripts/ops/` | Ops/environment checks are not runtime service internals |
| Shared shell helpers | n/a | `scripts/lib/vision_bundle_common.sh` | Source-only helpers; no process starts or filesystem mutation |

Wrapper rule:

```bash
#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "${SCRIPT_DIR}/<group>/<implementation>.sh" "$@"
```

The wrapper must preserve arguments, environment defaults, exit codes, and
operator-visible output. Python wrappers use the same compatibility principle by
`execv`-ing the grouped implementation with the same interpreter and arguments.

## `ros2/` placement rules

- Keep ROS package layout compatible with colcon, launch files, and console scripts.
- ROS-aware sidecars may import ROS dependencies; FastAPI service startup must not import/start ROS runtime.
- Split oversized ROS modules only behind stable launch/console names.
- ROS tests must stay near the ROS package under `ros2/smartfactory_perception_ros/test/`.

## `ops/` placement rules

- `ops/systemd/smartfactory-ai-server.service` remains the current validated deployment asset.
- Future `ops/env/*.env.example` or `EnvironmentFile=` migration is allowed only with deployment validator/test updates.
- Do not install, reload, or mutate live systemd state in this cleanup path.

## `docs/` placement rules

| Class | Destination | Notes |
|---|---|---|
| Contracts/API snapshots | `docs/contracts/` | Keep generated surfaces byte-stable unless intentional |
| Operator runbooks | `docs/runbooks/` | Commands must match root wrappers or updated entrypoints |
| Requests/handoffs | `docs/requests/` | Use for external/Main/router/DNS requests |
| Technical architecture/plans | `docs/technical/` | Local draft unless verified externally |
| Reports/evidence | `docs/reports/` or `.omx/reports/` | `.omx/reports` for workflow evidence; `docs/reports` for durable human-facing reports |
| GUI/design | `docs/gui/`, `DESIGN.md` | Product/UI guidance |

## Verification before moving anything

Minimum checks for wrapper/path edits:

```bash
git diff --check
bash -n scripts/*.sh scripts/lib/*.sh
python3 -m py_compile <touched-python-files>
rg -n "<old-path>|<new-path>" .
```

Service route changes:

```bash
rg -n "runtime_routes" services/ai-server/app/api --glob '!**/__pycache__/**' --glob '!*.pyc'
PYTHONPATH=services/ai-server services/ai-server/.venv/bin/python -m pytest -q \
  services/ai-server/tests/test_contract_boundaries.py::test_health_matches_api_contract_fields \
  services/ai-server/tests/test_contract_boundaries.py::test_sources_match_api_contract_fields_and_do_not_require_ros_imports \
  services/ai-server/tests/test_contract_boundaries.py::test_latest_detections_contract_limit_is_bounded_to_50
```

Final structural slice gates are sized to touched surfaces; use the full approved plan when broad code movement occurs.
