# Vision Evidence/Advisory Safety Contract

- Status: Safety boundary note for current AI Server / Vision Gateway integration.
- Date: 2026-06-18
- Scope: AI Server, Vision Gateway ROS sidecars, read-only overlay stream bridge, Main/GUI handoff.

## Contract

Vision components are evidence/advisory surfaces only. They may observe camera frames, produce overlays, expose source health, publish schema-valid evidence topics when explicitly implemented, and report advisory docking values for tuning. They must not own robot motion, task state, inventory state, or ROS graph mutation.

## Explicitly forbidden surfaces

| Surface | Contract |
| --- | --- |
| `/cmd_vel` | Vision must not publish, proxy, bridge, or expose it to clients. |
| Nav2 actions | Vision must not call `navigate_to_pose`, `follow_path`, recovery, cancel, or any action-client motion API. |
| Teleop | Vision bundles must not start teleop or keyboard joystick processes. |
| ROS parameter mutation | Vision HTTP/GUI/bridge surfaces must not mutate robot parameters or expose parameter-write APIs. |
| Whole-graph bridge | Vision must not expose unrestricted rosbridge/DDS graph access; source-specific allowlists only. |
| Main/WMS state mutation | Vision evidence does not directly advance tasks, inventory, pickup/dropoff, or exception state. |

## Allowed outputs

- HTTP metadata and image/overlay debug endpoints.
- Source-scoped rosbridge subscription hints for allowlisted image/overlay topics.
- Future `/sf/vision/events` evidence-topic publication, if schema-valid and source-scoped.
- Passive ArUco/docking observations with `advisory_only[...]` values for human tuning.
- Read-only preflight/status endpoints that summarize readiness and safety policy.

## Required response invariants

AI Server discovery/handoff endpoints must keep these invariant values unless a new safety review explicitly changes the contract:

```json
{
  "debug_only": true,
  "motion_command_allowed": false,
  "control_topics_published": [],
  "topic_exposure_policy": {
    "rosbridge_exposes_all_topics": false,
    "publish_control_topics": false,
    "client_publish_allowed": false
  }
}
```

The forbidden topic glob list must include `/cmd_vel`, `*/cmd_vel`, Nav2 action-like topics, ROS parameter surfaces, `/tf`, `/tf_static`, and `/rosout` where those surfaces could leak whole-graph access.

## Current guard evidence

| Layer | Guard |
| --- | --- |
| AI Server API | `services/ai-server/tests/test_api_streams_ros.py` asserts empty `control_topics_published`, no whole-graph rosbridge exposure, forbidden `/cmd_vel`, and no publish-control policy. |
| API fixtures/helpers | `services/ai-server/tests/api_test_helpers.py` encodes safe topic exposure defaults. |
| ROS frame gateway | `ros2/smartfactory_perception_ros/test/test_vision_frame_gateway.py` rejects `/cmd_vel` input/publish topics and asserts no command/Nav2 publishers. |
| ROS overlay bridge | `ros2/smartfactory_perception_ros/test/test_vision_overlay_stream_bridge.py` enforces source/topic allowlists, read-only mutation rejection, and no command/Nav2 publishers. |
| Passive docking monitor | `ros2/smartfactory_perception_ros/test/test_aruco_pose_monitor.py` checks advisory-only output and no `/cmd_vel` publishers. |
| Run scripts | `scripts/run_d1_vision_bundle.sh`, `scripts/run_d1_vision_multi_source_gateway_bundle.sh`, and `scripts/run_d1_vision_domain_sidecar.sh` state that no robot motion, Nav2, teleop, `/cmd_vel`, robot-side persistent services, or whole-graph bridge are started. |

## Verification commands

```bash
# AI Server safety/discovery checks
cd services/ai-server && .venv/bin/python -m pytest -q tests/test_api_streams_ros.py tests/test_api_worker_debug.py tests/test_api_frames_overlays.py

# ROS sidecar read-only checks
cd ros2/smartfactory_perception_ros && pytest -q test/test_vision_frame_gateway.py test/test_vision_overlay_stream_bridge.py test/test_aruco_pose_monitor.py

# Static forbidden-surface search; expected hits should be tests/docs/deny-lists, not publishers/action clients.
rg -n "create_publisher\(.*cmd_vel|ActionClient\(.*(navigate_to_pose|follow_path)|teleop|rosbridge_exposes_all_topics.*true|publish_control_topics.*true|client_publish_allowed.*true" services scripts ros2 docs
```

## Integration rule

If a future lane needs active movement, it must be a Movement/Safety Controller task with explicit approval. Vision may provide evidence to Main/WMS or Movement, but the control decision and command publisher must remain outside Vision.
