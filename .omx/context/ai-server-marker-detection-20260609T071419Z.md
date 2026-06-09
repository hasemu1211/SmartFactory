# Context Snapshot: AI Server Marker Detection Team Run

## Task statement
Implement the next AI Server phase on branch `feature/ai-server-marker-detection`: replace the mock `/api/v1/detect/image` response with real deterministic marker detection first, while keeping the API-first `VisionEvent` contract stable.

## Desired outcome
- AI Server remains a separate FastAPI process, not a ROS2 in-process node.
- `/api/v1/detect/image` can process an uploaded image and emit contract-valid `VisionEvent` objects.
- ArUco/QR/marker detection is added before YOLO/person/object work.
- Tests and contract validation pass.
- ROS2 bringup remains compatible and does not depend on heavy AI packages.

## Known facts/evidence
- Current branch: `feature/ai-server-marker-detection`.
- SmartFactory repo baseline commit: `a97e688 Scaffold AI server development environment`.
- ROS2 workspace has `smartfactory_bringup` commit: `8d9a28e Add SmartFactory ROS2 bringup scaffold`.
- Canonical event contract: `docs/contracts/vision-event.schema.json`.
- API contract: `docs/contracts/ai-server-api.md`.
- AI Server scaffold: `services/ai-server/app/main.py`.
- Test command: `make ai-test`.
- ROS2 build command: `make ros-build-bringup`.
- Confirmed MVP1 camera sources: `global_cam_01`, `tb3_1_picam`, `tb3_2_picam`.
- Confirmed robot IDs: `tb3_1`, `tb3_2`.
- Confirmed LiDAR: LDS-03.
- No robot depth camera / D435 in MVP1.

## Constraints
- AI Server emits evidence only. It must not command `/cmd_vel`, Nav2, or emergency behavior.
- Main/WMS owns final state transitions.
- Keep AI Python dependencies isolated from ROS2 `PYTHONPATH` pollution.
- Do not change source IDs, robot IDs, schema fields, or endpoint shapes without explicit v2 contract discussion.
- Avoid YOLO/heavy model dependency until deterministic marker detection is passing.

## Unknowns/open questions
- Exact marker family to prioritize: ArUco dictionary, QR, AprilTag, or all staged.
- Whether fixture marker images already exist in repository or should be generated for tests.
- Whether OpenCV contrib features are available/needed for `aruco` in the chosen package.
- Whether QR decoding should use OpenCV QRCodeDetector only or an additional decoder later.

## Likely codebase touchpoints
- `services/ai-server/app/main.py`
- `services/ai-server/app/contracts.py`
- New detector module: `services/ai-server/app/detectors.py` or `services/ai-server/app/detectors/marker.py`
- `services/ai-server/requirements.txt`
- `services/ai-server/requirements.lock`
- `services/ai-server/tests/test_api.py`
- New fixture tests/images under `services/ai-server/tests/fixtures/`
- Optional docs update: `services/ai-server/README.md`, `docs/technical/development-environment.md`

## Suggested team lanes
1. Implementer lane: OpenCV marker detector + endpoint integration.
2. Test/contract lane: generated fixture images, tests, schema-policy validation.
3. Critic/reviewer lane: boundary review for API drift, ROS2 contamination, dependency risk.

## Stop rules
- Stop and ask before changing the canonical `VisionEvent` schema.
- Stop and ask before adding YOLO/Torch dependencies.
- Stop and ask before modifying live Confluence or publishing diagrams.

## User clarification added before team launch
- ROS2-related local skills have been imported into `/home/codelab/.codex/skills` and workers should use them where relevant:
  - `ros2-development` for launch/package/environment patterns.
  - `robot-perception` for marker/camera/image-processing choices.
  - `robotics-testing` for fixture and API test design.
  - `robot-bringup` only for boundary checks with ROS2 launch; do not turn AI Server into a ROS2 node.
- Existing OpenCV scripts under `/home/codelab/opencv_test/src` may be inspected as reference only:
  - `_aruco_capture_check.py`
  - `aruco_detector.py`
  - `generate_aruco.py`
  - related robot-control scripts
- Preference: create a clean new AI Server implementation unless a small reference idea is clearly useful. Do not copy old scripts wholesale, and do not import robot-control behavior into AI Server.
- Keep OpenCV marker detection deterministic and API-first.
