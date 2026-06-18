# Lane D1 Safe Ultragoal Plan Summary

- Date: 2026-06-16 Asia/Seoul
- Source plan: `.omx/plans/lane-d1-safe-main-gui-stream-integration-20260616.md`

## Verdict

Lane D1 is safe to plan and execute if it stays in performance/GUI/Main integration and read-only stream scope. It must not include Lane D2 active motion, Nav2 execution, teleop, `/cmd_vel`, or robot-side persistent changes.

## AI model answer

A new heavyweight AI model should not be bundled into the first D1 ultragoal by default. D1 should use the current OpenCV ArUco marker detector and existing disabled/fail-closed Lift ROI model adapter. A real model attachment needs a separate subgoal with weights, classes, sample images, runtime install method, latency target, and fail-closed validation.

## Additional critique/design needed?

Yes. D1 should have explicit critic and design gates before implementation because it can easily blur four planes:

1. Main semantic evidence ingest,
2. GUI video streaming,
3. ROS/rosbridge topic exposure,
4. AI model/runtime performance.

## Validation answer

The current validation method is valid if it separates raw camera FPS, AI overlay FPS, GUI stream FPS, and Main evidence latency. Repeated HTTP image polling is not a valid high-FPS stream validation method; rosbridge/WebSocket or stream-native transport should be measured separately.

## Recommended next action

Start with D1-G1 Main HTTP evidence handshake using synthetic/offline AI events. In parallel, design D1-G3 read-only stream exposure through Movement rosbridge or a dedicated allowlisted stream bridge. Do not enable live camera auto-post to Main until Main's `/api/v1/vision/events` behavior and idempotency are confirmed.


## Updated D1-AI environment recommendation

Working YOLO runtime is in `~/venv/venv`, not in the current AI Server service env. `~/venv/venv` has `ultralytics 8.4.63`, `torch 2.12.0+cu130`, CUDA available, and an RTX 5060; however it lacks FastAPI/uvicorn/pydantic/httpx/jsonschema, so it cannot run the current AI Server directly. The current `services/ai-server/.venv` can run AI Server but lacks `ultralytics`/`torch`.

Recommended approach: create a reproducible project-local model env such as `services/ai-server/.venv-yolo` from AI Server requirements plus pinned model extras. Do not copy the whole external venv blindly. Use `/home/codelab/yolo_test/runs/segment/bottle_detection_yolov8s_seg/weights/best.pt` as the first candidate model, with `/home/codelab/yolo_test/runs/detect/bottle_detection_yolov8s/weights/best.pt` as detection fallback.

Contract caveat: the trained classes are `bottle1`, `bottle2`, `bottle3`, but project contracts currently allow `box`/`pallet` for load evidence and a small enum for `VisionEvent`. Add an explicit class normalization layer before Main delivery, e.g. bottle classes to `box` only if that is the intended demo semantics.
