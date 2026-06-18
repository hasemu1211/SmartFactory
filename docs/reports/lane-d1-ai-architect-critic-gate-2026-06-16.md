# Lane D1/D1-AI Architect → Critic Gate Briefing

- Date: 2026-06-16 12:25 KST
- Scope: Lane D1 safe Main/GUI/read-only stream integration with an optional D1-AI model delivery subgoal.
- Source plan: `.omx/plans/lane-d1-safe-main-gui-stream-integration-20260616.md`
- Status: **REVISE before execution as one broad ultragoal**.

## Ordered review result

1. **Architect review: WATCH / conditional approval**
   - Approve the D1 direction only as a safe evidence/GUI integration lane.
   - Canonical Main evidence path stays HTTP: `AI Server -> Main POST /api/v1/vision/events`.
   - GUI imagery uses AI Server pull URLs for raw/overlay snapshots.
   - High-FPS display uses a read-only stream plane such as Movement rosbridge/WebSocket or another allowlisted bridge.
   - AI Server remains evidence-only: no `/cmd_vel`, no Nav2, no teleop, no Main DB/task mutation.
   - Raw YOLO classes `bottle1`, `bottle2`, `bottle3` cannot cross into Main without a class-normalization decision.

2. **Critic review: REVISE**
   - The plan is safe in direction, but should not execute as one broad ultragoal yet.
   - Start with gate-first subgoals: runtime snapshot, Main HTTP smoke, read-only stream allowlist, then live emission and GUI display.
   - D1-AI model delivery requires a separate model gate before live Main delivery.
   - Current live baseline must be refreshed because `http://127.0.0.1:8100/api/v1/health` and `http://192.168.10.63:8100/api/v1/health` were not reachable at 12:25 KST.

## Fixed document gate

D1 may proceed only if these document gates are kept current during every implementation cycle:

| Gate | Required document update | Minimum evidence |
|---|---|---|
| D1-G0 runtime snapshot | `entry.md`, this report or a new dated report, and Main proposal if Main-facing | Current endpoints, LAN IP, panes/processes, stop commands, health checks, source/topic state |
| D1-G1 Main HTTP contract | `docs/contracts/mainserver-vision-evidence-api-proposal-2026-06-16.md`, `docs/contracts/ai-server-api.md`, `entry.md` | Main owner confirms path, `200/202` success, `event_id` idempotency, no image bytes, retry/failure semantics |
| D1-G3 stream allowlist | D1 plan/report and Main proposal | Exact bridge owner/path, exact read-only topics, explicit forbidden-topic check for `/cmd_vel`, Nav2, teleop, params, and whole-graph exposure |
| D1-AI model gate | D1 plan/report, AI Server API docs when behavior changes, `entry.md` | Model path, classes, class mapping, sample images, project-local env plan, latency target, GPU/CPU budget, fail-closed behavior |
| D1-G4 GUI display | Main proposal and entry/reports | GUI shows source status, latest frame/overlay, stale/fresh state, and does not treat stale/candidate evidence as task completion |
| D1-G5 publish docs | Local docs first; Confluence API page only after live verification or explicit user direction | Verified behavior/contract diff and publication note |

## Safe execution sequence

1. **G0 only: refresh live baseline**
   - Check AI Server health, listener, LAN URL, gateway, camera topic, and stop commands.
   - If AI Server/gateway is down, document it; do not claim a live evidence pipeline.

2. **G1 robot-free Main smoke**
   - Use synthetic/offline schema-valid `VisionEvent` payloads.
   - No live camera auto-post and no robot changes.

3. **G3 read-only stream proof**
   - Use Movement rosbridge or an allowlisted stream bridge.
   - Prove no control topics or whole-graph access are exposed.

4. **D1-AI model gate**
   - Build a project-local model env; do not copy `~/venv/venv` wholesale.
   - Load candidate model and run sample-image smoke.
   - Add class mapping before Main delivery. Raw `bottle1/2/3` labels are not Main-contract-safe.

5. **G2 live evidence emission**
   - Enable only after Main endpoint/idempotency is confirmed.
   - Keep disabled by default and fail closed on Main/API/model errors.

6. **G4 GUI display**
   - Show evidence/overlay/status separately from task-completion authority.

7. **G5 docs and Confluence**
   - Update `entry.md` and local API docs in the same implementation cycle.
   - Update Confluence only after live verification or explicit direction to publish draft status.

## User briefing checklist

The user/Main owner should decide or provide:

1. Confirm D1 remains evidence/GUI/read-only stream only; D2 active motion is excluded.
2. Confirm Main canonical ingest path: `POST /api/v1/vision/events`.
3. Confirm success semantics: HTTP `200` or `202`, duplicate `event_id` behavior, and retry/failure behavior.
4. Decide class mapping for model labels: `bottle1/2/3 -> box`, `bottle1/2/3 -> unknown`, or contract expansion.
5. Approve whether D1 may include the D1-AI model subgoal now, or whether AI delivery waits until after G1/G3.
6. Approve stream path: Movement rosbridge/WebSocket, dedicated read-only bridge, or debug-only AI Server MJPEG.
7. Provide Main host/port and test credentials if needed.
8. Approve a restart window if current AI Server/gateway must be brought back up for G0 validation.
9. Confirm who approves/publishes Confluence API updates.

## Current local runtime note

At 2026-06-16 12:25 KST, `curl` to both `127.0.0.1:8100` and `192.168.10.63:8100` failed, and no `:8100` listener was present. `Smartfactory:3.3` shows the AI Server was stopped with Ctrl-C; `Smartfactory:3.5` shows `vision_frame_gateway` was also stopped with Ctrl-C. `Smartfactory:3.2` still shows the robot camera launch log, but live evidence delivery should be considered down until G0 is refreshed.
