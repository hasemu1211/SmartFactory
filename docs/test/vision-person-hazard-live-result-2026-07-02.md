# Vision Person Hazard Live Result — 2026-07-02

Date: 2026-07-02 11:54-11:56 KST  
Branch: `feature/ai-server-marker-detection`  
HEAD during test: `1d0a89f`  
Scope: Main 없이 AI/Vision laptop local API로 `tb3_1`, `tb3_2` person hazard monitor live 검증

## Summary

PASS with workaround.

Two TurtleBot Pi camera sources were ingested by the AI Server, YOLO person detections were converted into Main-facing advisory person hazard responses, and per-robot monitor state stayed independent.

Main was not used. No Main DB write, HOLD, E-stop, motion command, or control topic publish was performed.

## Runtime used

The standard `sf_lab.sh low-load` path was attempted first, but it starts GoPro processes and the supervisor shuts the runtime down when no GoPro is connected. For this person-hazard-only test, the bundle was started directly in tmux `Smartfactory:3.4` with GoPro/WebRTC supervisor bypassed:

```bash
cd /home/hasam/Desktop/project/SmartFactory
AI_SERVER_HOST=0.0.0.0 \
VISION_MODEL_WORKER_ENABLED=true \
VISION_MODEL_PATH=/home/hasam/yolo_test/yolov8n.pt \
VISION_MODEL_TASK=detect \
VISION_MODEL_DEVICE=cpu \
VISION_MODEL_IMGSZ=224 \
VISION_MODEL_CONF=0.35 \
VISION_GATEWAY_REQUEST_TIMEOUT_SEC=8.0 \
VISION_GATEWAY_PERIOD_SEC=0.5 \
VISION_GATEWAY_PUBLISH_OUTPUT_PERIOD_SEC=0.5 \
VISION_GATEWAY_PUBLISH_OVERLAY=false \
VISION_GATEWAY_PUBLISH_EVIDENCE=false \
./scripts/vision/run_d1_vision_multi_source_gateway_bundle.sh
```

Robot camera bringup was already running before this test:

```bash
# tb3_1
ROS_DOMAIN_ID=2 ros2 launch turtlebot3_bringup camera_low_bandwidth.launch.py

# tb3_2
ROS_DOMAIN_ID=5 ros2 launch turtlebot3_bringup camera_low_bandwidth.launch.py
```

## Preflight evidence

`GET /api/v1/health` returned:

- `status`: `ok`
- `model_status`: `loaded`
- model worker: `worker_enabled=true`, `worker_active=true`
- model path configured on CPU detect profile
- `source_summary.online=2`, `offline=1` (`global_cam_01` was offline; both PiCam sources were online)

Process snapshot showed the direct bundle runtime alive:

- AI Server uvicorn on `0.0.0.0:8100`
- `vision_frame_gateway` for `tb3_1_picam`, `ROS_DOMAIN_ID=2`
- `vision_frame_gateway` for `tb3_2_picam`, `ROS_DOMAIN_ID=5`
- public stream gateway on `0.0.0.0:8090`

Debug source evidence:

- `tb3_1_picam`: `status=online`, `frame_count=63`, latest frame `320x240`, latest event `CANDIDATE`
- `tb3_2_picam`: `status=online`, `frame_count=68`, latest frame `320x240`, latest event `CANDIDATE`

Raw evidence file: `.run/vision/person-hazard-live-20260702-115613/api-smoke.txt`

## Test results

### 1. Initial monitors disabled

`GET /api/v1/vision/monitors` showed both person monitors disabled initially:

- `tb3_1`: `enabled=false`, `source=tb3_1_picam`, `operation_state=IDLE`
- `tb3_2`: `enabled=false`, `source=tb3_2_picam`, `operation_state=IDLE`

Polling while disabled returned `NO_ACTIVE_MONITOR` for both robots.

### 2. Enable both monitors independently

Commands:

```bash
curl -X PUT http://127.0.0.1:8100/api/v1/vision/monitors/person_drive/state \
  -H 'Content-Type: application/json' \
  -d '{"enabled":true,"source":"tb3_1_picam","operation_state":"DRIVE","task_id":101,"target_fps":3}'

curl -X PUT http://127.0.0.1:8100/api/v1/vision/monitors/person_drive/state \
  -H 'Content-Type: application/json' \
  -d '{"enabled":true,"source":"tb3_2_picam","operation_state":"DRIVE","task_id":102,"target_fps":3}'
```

Result:

- `tb3_1`: `enabled=true`, `task_id=101`, `revision=1`
- `tb3_2`: `enabled=true`, `task_id=102`, `revision=1`

### 3. Person hazard latest for both robots

`tb3_1` returned advisory:

- `result=ADVISORY`
- `reason_code=HUMAN_DETECTED`
- `source=tb3_1_picam`
- `robot_id=tb3_1`
- `task_id=101`
- `severity=CRITICAL`
- `trusted=false`
- observed confidence example: `0.5282794833183289`

`tb3_2` returned advisory:

- `result=ADVISORY`
- `reason_code=HUMAN_DETECTED`
- `source=tb3_2_picam`
- `robot_id=tb3_2`
- `task_id=102`
- `severity=CRITICAL`
- `trusted=false`
- observed confidence example: `0.7187461256980896`

Pass: events were not mixed between robots.

### 4. Mismatch rejection

Command:

```bash
curl -i 'http://127.0.0.1:8100/api/v1/vision/hazards/person/latest?robot_id=tb3_1&source=tb3_2_picam'
```

Result:

- HTTP `400 Bad Request`
- message: `robot_id tb3_1 requires source tb3_1_picam`

Pass.

### 5. Disable only tb3_1

Command:

```bash
curl -X PUT http://127.0.0.1:8100/api/v1/vision/monitors/person_drive/state \
  -H 'Content-Type: application/json' \
  -d '{"enabled":false,"source":"tb3_1_picam","operation_state":"IDLE"}'
```

Result:

- `tb3_1` poll returned `NO_ACTIVE_MONITOR`
- `tb3_2` remained enabled and returned `ADVISORY/HUMAN_DETECTED` with `task_id=102`

Pass: disabling one robot did not disable the other.


### 6. tb3_2 refresh after brief person exposure

After the initial run, `tb3_2` was briefly exposed to a person target again and polled 12 times from the local AI Server API. `tb3_2` returned fresh `ADVISORY/HUMAN_DETECTED` events and the source event timestamp advanced as expected.

Observed refresh sequence examples:

```text
12:01:10 confidence=0.6269 source_event_id=59ca1412-...
12:01:12 confidence=0.5939 source_event_id=c0871289-...
12:01:16 confidence=0.5567 source_event_id=97ca99de-...
12:01:20 confidence=0.5336 source_event_id=b6cbbea8-...
12:01:21 confidence=0.5108 source_event_id=bede5929-...
12:01:23 confidence=0.4228 source_event_id=eec37855-...
```

All refreshed `tb3_2` responses preserved the expected routing fields:

- `result=ADVISORY`
- `reason_code=HUMAN_DETECTED`
- `source=tb3_2_picam`
- `robot_id=tb3_2`
- `task_id=102`

Conclusion: the earlier repeated `tb3_2` timestamp was consistent with briefly showing a person and then receiving no newer person detection. When a person was visible again, `tb3_2` produced new person hazard events with updated `observed_at`, confidence, and `source_event_id`.

## Safety result

The AI Server response remained advisory/evidence-only:

- no `HOLD`
- no `E_STOP`
- no `STOP_COMMAND`
- no `MOTION_CANCELLED`
- no `BLOCKED`
- no Main DB write attempted
- runtime command used `VISION_GATEWAY_PUBLISH_EVIDENCE=false`
- runtime command used `VISION_GATEWAY_PUBLISH_OVERLAY=false` to keep this focused on local API/person hazard evidence


## Main PC / same-LAN manual polling

The live process was bound to `AI_SERVER_HOST=0.0.0.0`, and startup output detected the Vision laptop LAN IP as `192.168.30.3`. Therefore another computer on the same `192.168.30.x` local network, including a Main server PC, can poll the same API directly while the live process remains running.

Use hostname first if mDNS/hosts resolution works:

```bash
curl http://smartfactory-vision.local:8100/api/v1/health
curl 'http://smartfactory-vision.local:8100/api/v1/vision/hazards/person/latest?robot_id=tb3_1'
curl 'http://smartfactory-vision.local:8100/api/v1/vision/hazards/person/latest?robot_id=tb3_2'
```

If hostname resolution fails, use the detected LAN IP from this run:

```bash
curl http://192.168.30.3:8100/api/v1/health
curl 'http://192.168.30.3:8100/api/v1/vision/hazards/person/latest?robot_id=tb3_1'
curl 'http://192.168.30.3:8100/api/v1/vision/hazards/person/latest?robot_id=tb3_2'
```

The receiving PC does not need to run Main for this smoke test; it only needs network reachability to TCP port `8100` on the Vision laptop. Main-side DB/HOLD/E-stop policy remains outside this local API test.

## Bugs / issues found during live run

### Bug 1 — `sf_lab.sh low-load` is not usable for PiCam-only person hazard when GoPro is absent

Attempted command:

```bash
AI_SERVER_HOST=0.0.0.0 \
VISION_MODEL_WORKER_ENABLED=true \
VISION_MODEL_PATH=./yolov8n.pt \
VISION_MODEL_TASK=detect \
VISION_MODEL_DEVICE=cpu \
VISION_MODEL_IMGSZ=224 \
./scripts/vision/sf_lab.sh low-load
```

Observed failure:

- AI Server started and became healthy.
- Vision Stream Gateway started and became healthy.
- The profile then started GoPro stream setup.
- No GoPro was connected, so `scripts/vision/start_gopro_webcam_stream.py` failed with `open_gopro.domain.exceptions.FailedToFindDevice`.
- `sf_vision.sh` supervisor observed one child exit and shut down the full runtime, including the still-useful AI Server and PiCam gateways.

Impact:

- Blocks local person-hazard-only validation if GoPro is not available.
- Workaround was to run `run_d1_vision_multi_source_gateway_bundle.sh` directly, bypassing GoPro/WebRTC supervisor.

Suggested fix:

- Add a PiCam/person-hazard-only profile, for example `lab-tb3-person-hazard`, with `SF_VISION_GOPRO_ENABLED=false` and no GoPro child process.
- Alternatively, make GoPro optional/non-fatal in low-load mode when the requested validation scope is PiCam-only.

Evidence:

- `.run/vision/logs/gopro-stream.log`
- `.run/vision/logs/vision-bundle.log`

### Bug 2 — `VISION_GATEWAY_REQUEST_TIMEOUT_SEC=8` crashes ROS parameter declaration

Attempted direct bundle run used:

```bash
VISION_GATEWAY_REQUEST_TIMEOUT_SEC=8
```

Observed failure:

```text
rclpy.exceptions.InvalidParameterTypeException: Trying to set parameter 'request_timeout_sec' to '8' of type 'INTEGER', expecting type 'DOUBLE': request_timeout_sec
```

Workaround:

```bash
VISION_GATEWAY_REQUEST_TIMEOUT_SEC=8.0
```

Impact:

- Easy operator footgun: shell env values that look numeric but have no decimal are passed through as ROS integer parameters, while the node declared the parameter as double.

Suggested fix:

- Normalize numeric env values in `run_d1_vision_multi_source_gateway_bundle.sh` before passing ROS args, e.g. convert `8` to `8.0` for double parameters.
- Or declare/parse the ROS parameter more permissively in `vision_frame_gateway.py`.

### Observation — public bridge status can show `no_frame` before AI source debug catches up

Early `GET http://127.0.0.1:8090/api/v1/vision/bridge/status` showed `no_frame` for the PiCam upstreams immediately after startup, while later AI debug source endpoints showed both PiCam sources online with frames and fresh overlays.

This was not a blocker for person hazard API validation, but it is worth checking separately if the Main UI relies on the public gateway status during startup.

## Verdict

The Main-facing person hazard API is live-testable without Main and passed the two-TurtleBot local validation:

- independent per-robot enable/disable works,
- both robots can be active at the same time,
- person advisory events are source/robot/task correct,
- mismatched robot/source requests are rejected,
- disabling one robot does not disable the other,
- AI Server remains advisory-only.

Remaining work is operator/runtime polish around the launch path, not the person hazard API contract itself.
