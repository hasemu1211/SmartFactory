# SmartFactory cleanup inventory — worker-1

- Created: 2026-06-18T01:05:03Z
- Team: execute-approved-smar-49a6278f
- Task: 1 — execute approved cleanup/refactor plan, Phase 0 inventory/baseline slice
- Approved plan source: /home/codelab/Desktop/Project/SmartFactory/.omx/plans/smartfactory-cleanup-refactor-execution-plan-20260618.md
- Ultragoal state: leader-owned; worker did not mutate .omx/ultragoal.
- Real robot: not used. No /cmd_vel, Nav2, teleop, parameter mutation, or robot-side persistent changes performed.

## Git state
```text
## HEAD (no branch)
?? docs/reports/cleanup-inventory-20260618-worker1.md
```

## Hotspot sizes
```text
  2962 services/ai-server/app/main.py
  2788 services/ai-server/tests/test_api.py
    35 Makefile
  1732 entry.md
  7517 total
```

## File inventory by plan surface

### AI Server app
```text
services/ai-server/app/__init__.py
services/ai-server/app/config.py
services/ai-server/app/contracts.py
services/ai-server/app/detectors.py
services/ai-server/app/docking.py
services/ai-server/app/event_store.py
services/ai-server/app/evidence_cache.py
services/ai-server/app/frame_store.py
services/ai-server/app/lift_roi.py
services/ai-server/app/lift_roi_evidence.py
services/ai-server/app/main.py
services/ai-server/app/model_adapters.py
services/ai-server/app/observability.py
services/ai-server/app/overlay.py
services/ai-server/app/pose_profiles.py
services/ai-server/app/source_health.py
services/ai-server/app/source_registry.py
services/ai-server/app/vision_interfaces.py
services/ai-server/app/wms_client.py
```

### AI Server tests
```text
services/ai-server/tests/generated_fixtures.py
services/ai-server/tests/test_api.py
services/ai-server/tests/test_contract_boundaries.py
services/ai-server/tests/test_deployment_assets.py
services/ai-server/tests/test_detectors.py
services/ai-server/tests/test_docking.py
services/ai-server/tests/test_event_store.py
services/ai-server/tests/test_generated_fixtures.py
services/ai-server/tests/test_lift_roi.py
services/ai-server/tests/test_model_adapters.py
services/ai-server/tests/test_observability.py
services/ai-server/tests/test_overlay.py
services/ai-server/tests/test_pose_profiles.py
services/ai-server/tests/test_source_health.py
services/ai-server/tests/test_source_registry.py
services/ai-server/tests/test_vision_interfaces.py
services/ai-server/tests/test_wms_client.py
```

### Contracts / generated fixtures
```text
docs/contracts/ai-server-openapi.json
docs/contracts/fixtures/source-registry.valid.json
docs/contracts/generated/source-registry.snapshot.json
docs/contracts/lift-roi-evidence.schema.json
docs/contracts/vision-event.schema.json
services/ai-server/tests/generated_fixtures.py
services/ai-server/tests/test_source_registry.py
```

### Scripts / entrypoints
```text
scripts/create_sprint3_presentation_pptx.py
scripts/generate-drawio-architectures.py
scripts/generate_source_registry_surfaces.py
scripts/prepare_docking_tuning_session.sh
scripts/render-scenario-sequence-diagrams.py
scripts/run_ai_server.sh
scripts/run_d1_vision_bundle.sh
scripts/run_d1_vision_domain_sidecar.sh
scripts/run_d1_vision_multi_source_gateway_bundle.sh
scripts/run_d1_vision_stream_gateway.py
scripts/setup_ai_server_env.sh
scripts/setup_ai_server_model_env.sh
scripts/test_ai_server.sh
scripts/validate_contracts.py
scripts/validate_deployment_assets.py
```

### ROS workspace
```text
ros2/smartfactory_perception_ros/README.md
ros2/smartfactory_perception_ros/config/lane_c_domain_bridge_allowlist.yaml
ros2/smartfactory_perception_ros/launch/ai_snapshot_clients.launch.py
ros2/smartfactory_perception_ros/launch/aruco_pose_monitor.launch.py
ros2/smartfactory_perception_ros/launch/vision_frame_gateway.launch.py
ros2/smartfactory_perception_ros/launch/vision_overlay_stream_bridge.launch.py
ros2/smartfactory_perception_ros/package.xml
ros2/smartfactory_perception_ros/resource/smartfactory_perception_ros
ros2/smartfactory_perception_ros/setup.cfg
ros2/smartfactory_perception_ros/setup.py
ros2/smartfactory_perception_ros/smartfactory_perception_ros/__init__.py
ros2/smartfactory_perception_ros/smartfactory_perception_ros/aruco_pose_monitor.py
ros2/smartfactory_perception_ros/smartfactory_perception_ros/image_snapshot_client.py
ros2/smartfactory_perception_ros/smartfactory_perception_ros/vision_frame_gateway.py
ros2/smartfactory_perception_ros/smartfactory_perception_ros/vision_overlay_stream_bridge.py
ros2/smartfactory_perception_ros/test/test_aruco_pose_monitor.py
ros2/smartfactory_perception_ros/test/test_image_snapshot_client.py
ros2/smartfactory_perception_ros/test/test_vision_frame_gateway.py
ros2/smartfactory_perception_ros/test/test_vision_overlay_stream_bridge.py
```

### Docs and runbooks
```text
docs/confluence/Sprint3 Presentation/Sprint_3_Presentation.pptx
docs/confluence/Sprint3 Presentation/reference.md
docs/confluence/Sprint3 Presentation/ros_bridge_web.png
docs/confluence/architecture/hardware-architecture.drawio
docs/confluence/architecture/software-architecture.drawio
docs/confluence/sequence-diagrams/scenario-01-inbound-storage-sequence.png
docs/confluence/sequence-diagrams/scenario-01-inbound-storage-sequence.seq.txt
docs/confluence/sequence-diagrams/scenario-02-outbound-sequence.png
docs/confluence/sequence-diagrams/scenario-02-outbound-sequence.seq.txt
docs/confluence/sequence-diagrams/scenario-03-obstacle-risk-sequence.png
docs/confluence/sequence-diagrams/scenario-03-obstacle-risk-sequence.seq.txt
docs/confluence/sequence-diagrams/scenario-04-auto-charge-sequence.png
docs/confluence/sequence-diagrams/scenario-04-auto-charge-sequence.seq.txt
docs/contracts/ai-server-api.md
docs/contracts/ai-server-openapi.json
docs/contracts/fixtures/lift-roi-evidence.invalid.count-mismatch.json
docs/contracts/fixtures/lift-roi-evidence.invalid.source-robot-mismatch.json
docs/contracts/fixtures/lift-roi-evidence.valid.dropoff.json
docs/contracts/fixtures/lift-roi-evidence.valid.pickup.json
docs/contracts/fixtures/source-registry.valid.json
docs/contracts/fixtures/vision-event.invalid.bad-bbox-order.json
docs/contracts/fixtures/vision-event.invalid.bad-format.json
docs/contracts/fixtures/vision-event.invalid.confirmed-marker-no-marker-id.json
docs/contracts/fixtures/vision-event.invalid.depth-non-null.json
docs/contracts/fixtures/vision-event.invalid.missing-robot-id.json
docs/contracts/fixtures/vision-event.invalid.source-robot-mismatch.json
docs/contracts/fixtures/vision-event.valid.global.json
docs/contracts/fixtures/vision-event.valid.stale.global.json
docs/contracts/fixtures/vision-event.valid.tb3_1.json
docs/contracts/fixtures/vision-event.valid.tb3_2.json
docs/contracts/generated/source-registry.snapshot.json
docs/contracts/lift-roi-evidence.schema.json
docs/contracts/mainserver-vision-evidence-api-proposal-2026-06-16.md
docs/contracts/vision-event.schema.json
docs/reports/ai-server-lane-status-2026-06-15.md
docs/reports/api-confluence-update-2026-06-16-d1-async-qos.md
docs/reports/api-confluence-update-2026-06-16-d1-bundle.md
docs/reports/api-confluence-update-2026-06-16-lane-c.md
docs/reports/api-confluence-update-2026-06-16.md
docs/reports/cleanup-inventory-20260618-worker1.md
docs/reports/lane-b-visual-qa-2026-06-15/README.md
docs/reports/lane-b-visual-qa-2026-06-15/fresh_overlay.jpg
docs/reports/lane-b-visual-qa-2026-06-15/fresh_vs_stale_overlay_comparison.jpg
docs/reports/lane-b-visual-qa-2026-06-15/stale_overlay.jpg
docs/reports/lane-c-safe-vision-frame-gateway-2026-06-16.md
docs/reports/lane-d1-ai-architect-critic-gate-2026-06-16.md
docs/reports/lane-d1-ai-ros-overlay-stream-implementation-2026-06-16.md
docs/reports/lane-d1-readonly-ros-overlay-stream-bridge-2026-06-16.md
docs/reports/lane-d1-safe-ultragoal-plan-2026-06-16.md
docs/reports/lane0-contract-brief-2026-06-15.md
docs/reports/lane0-contract-confluence-summary-2026-06-15.md
docs/reports/main-camera-api-alignment-questions-2026-06-15.md
docs/robot/docking-tuning-runbook.md
docs/robot/robot1-picam-aruco-ai-server-qa-2026-06-11.md
docs/runbooks/d1-vision-bundle-local-main-usage.md
docs/runbooks/d1-vision-bundle-main-handoff.md
docs/state-diagram/confluence-body.md
docs/state-diagram/mermaid-img-url.txt
docs/state-diagram/mermaid-svg-url.txt
docs/state-diagram/puppeteer-config.json
docs/state-diagram/state-diagram-dot.png
docs/state-diagram/state-diagram.dot
docs/state-diagram/state-diagram.mmd
docs/state-diagram/state-diagram.png
docs/state-diagram/state-diagram.svg
docs/technical/ai-vision-pipeline-research.md
docs/technical/development-environment.md
docs/technical/perception-control-plan.md
docs/technical/ros2-friendly-environment-plan.md
```

## Boundary scan seed commands

These commands are safe/read-only and should be retained for the final verification phase:

```bash
python3 - <<'PY'
import ast, pathlib, sys
deny={'rclpy','launch','sensor_msgs','geometry_msgs','nav2_msgs'}
hits=[]
for path in pathlib.Path('services/ai-server/app').rglob('*.py'):
    tree=ast.parse(path.read_text(), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split('.')[0] in deny: hits.append((str(path), alias.name))
        elif isinstance(node, ast.ImportFrom) and node.module:
            if node.module.split('.')[0] in deny: hits.append((str(path), node.module))
print(hits)
sys.exit(1 if hits else 0)
PY
grep -RInE 'create_publisher\(.*cmd_vel|ActionClient\(.*nav2|ros2 launch.*nav2|teleop|client_publish_allowed=true|publish_control_topics=true|rosbridge' services scripts ros2 || true
```

## Suggested non-overlap execution slices

1. Worker-1/meta: inventory and baseline evidence only (this report).
2. AI route extraction lane: `services/ai-server/app/main.py` plus new `services/ai-server/app/api/*.py`; verify OpenAPI/API tests after each move.
3. Test split lane: `services/ai-server/tests/test_api.py` to endpoint-focused files; move-only first.
4. Entrypoint lane: `Makefile`, `scripts/run_d1_vision_multi_source_gateway_bundle.sh`, supporting runbook references; thin aliases only.
5. Docs lane: `entry.md` + `docs/reports`/runbooks; verify Confluence only before public claims.

## Subagent change-slice probe integrated

- Subagent: `019ed841-8e44-7561-bb7e-b3d3a812e19e` (change-slice probe).
- Recommended safe first implementation slice: move shared error handling, OpenAPI helpers, middleware/exception handlers from `services/ai-server/app/main.py` into `services/ai-server/app/api/` without changing route URLs, response schemas, middleware order, or app import behavior.
- Primary migration hazards: preserve AI Server ROS-free boundary; keep `app` import-safe for contract tooling; keep generated OpenAPI and existing tests stable after each move.
- Non-overlap decision for worker-1: record this guidance here only; do not edit route/test/script/doc implementation surfaces owned by other active workers.

## Baseline command log

Filled by worker verification commands in this task result.
