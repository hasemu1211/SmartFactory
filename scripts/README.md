# SmartFactory scripts guide

Korean version: [`README.ko.md`](README.ko.md).
Filesystem ownership / placement rules: [`../docs/technical/project-filesystem-ownership.md`](../docs/technical/project-filesystem-ownership.md).

This directory contains local operator/developer entrypoints. Prefer these
scripts over ad-hoc commands so Main/Vision integration stays reproducible.

## Current Main/Vision quick start

### 1. Publish the temporary Vision hostname for a lab session

```bash
./scripts/publish_vision_mdns_alias.py
```

Default behavior:

- publishes `smartfactory-vision.local -> <first LAN IPv4>` via Avahi/mDNS
- runs in the foreground
- withdraws the record when stopped with `Ctrl-C`
- does **not** change `/etc/hosts`, hostname, router DHCP, or DNS

Use this only for local/lab validation. Production should use router DHCP
reservation plus DNS/mDNS hostname configuration:

For dated lab DHCP/DNS handoff details, see
[`docs/requests/main-vision-runtime-config-request-2026-06-19.md`](../docs/requests/main-vision-runtime-config-request-2026-06-19.md).
Verify MAC/IP values before publishing externally or after DHCP/router changes.

Dry check:

```bash
./scripts/publish_vision_mdns_alias.py --print-only
```

### 2. Start the Main-compatible Vision bundle

```bash
VISION_MODEL_WORKER_ENABLED=false ./scripts/run_d1_vision_multi_source_gateway_bundle.sh
```

The bundle starts:

```text
0.0.0.0:8100   AI Server
0.0.0.0:8090   public HTTP/MJPEG Vision Stream Gateway
127.0.0.1:18090 internal tb3_1 overlay bridge
127.0.0.1:18091 internal tb3_2 overlay bridge
```

Current default callback settings:

```env
MAIN_SERVER_URL=http://smartfactory-main.local:8088
WMS_VISION_EVENTS_PATH=/api/v1/vision/events
WMS_EMIT_ENABLED=false
```

`WMS_EMIT_ENABLED=false` is intentional for safe default operation. Set it to
`true` only when you explicitly want Vision to POST evidence events into Main.

### 3. Smoke checks

```bash
curl http://smartfactory-vision.local:8100/api/v1/health
curl http://smartfactory-vision.local:8090/api/v1/vision/bridge/status
curl http://smartfactory-main.local:8088/api/v1/vision/bridge/status
```

Expected while robots/cameras are absent:

- services return HTTP `200`
- `motion_command_allowed=false`
- sources may show `no_frame` or offline/stale state until camera frames arrive

## Script groups

### AI Server

- `setup_ai_server_env.sh` — create/update the AI Server Python environment
- `setup_ai_server_model_env.sh` — model/runtime dependency setup helper
- `run_ai_server.sh` — AI Server only (`:8100`)
- `test_ai_server.sh` — local AI Server test helper

### D1 Vision / Main integration

- `publish_vision_mdns_alias.py` — temporary `smartfactory-vision.local` mDNS A record publisher
- `run_d1_vision_multi_source_gateway_bundle.sh` — official local/Main integration bundle
- `run_d1_vision_stream_gateway.py` — ROS-free public HTTP/MJPEG source mux (`:8090`)
- `run_d1_vision_bundle.sh` — narrower single-source debug bundle
- `run_d1_vision_domain_sidecar.sh` — extra source/domain sidecar
- `smoke_main_dashboard_gateway.sh` — report-only Main/Vision endpoint smoke check

### Contracts / validation / generated surfaces

- `validate_contracts.py` — contract/schema checks
- `generate_source_registry_surfaces.py` — source-registry-derived fixtures/OpenAPI snapshot
- `validate_deployment_assets.py` — Docker/systemd deployment asset checks

### Miscellaneous reports/assets

- `check-confluence-env.sh`
- `prepare_docking_tuning_session.sh`
- `generate-drawio-architectures.py`
- `render-scenario-sequence-diagrams.py`
- `create_sprint3_presentation_pptx.py`

## Notes

- Follow the active runbook/session evidence for where to keep live processes;
  durable README files should not hard-code transient tmux pane/window IDs.
- Keep robot motion, Nav2, teleop, and `/cmd_vel` outside these Vision scripts.
- Do not commit generated `__pycache__` directories; they are local runtime cache.
