# Vision Person Hazard Live Validation

Date: 2026-07-02
Branch: `feature/ai-server-marker-detection`
Required commit or newer: `e263293acbbaf887f8c69ac7a803ea3e6dfb5238`
Scope: live validation for the Main-facing person hazard API with `tb3_1` and `tb3_2` Pi cameras.

## Purpose

Validate that Main can independently enable, poll, and disable person-hazard monitoring for both robots during DRIVE without mixing `tb3_1_picam` and `tb3_2_picam` events.

This test verifies advisory/evidence API behavior only. AI Server must not issue `HOLD`, `E_STOP`, `STOP_COMMAND`, `MOTION_CANCELLED`, or `BLOCKED`; Main remains responsible for cooldown, HOLD/E-stop policy, and DB writes.

## Required runtime conditions

1. AI/Vision laptop is on the same reachable WiFi/LAN as Main.
2. Laptop repo is on `feature/ai-server-marker-detection` at `e263293acbbaf887f8c69ac7a803ea3e6dfb5238` or newer.
3. Vision low-load runtime is running on the laptop:

   ```bash
   cd ~/SmartFactory
   ./scripts/vision/sf_lab.sh down
   ./scripts/vision/sf_lab.sh low-load
   ```

   `global_cam_01`/GoPro is optional for this person-hazard validation. If no
   GoPro is connected, the runtime should keep AI Server and PiCam paths alive
   and record a warning instead of shutting down the full bundle.

4. Robot Pi cameras are publishing:

   ```bash
   # tb3_1 robot
   ROS_DOMAIN_ID=2 ros2 launch turtlebot3_bringup camera_low_bandwidth.launch.py

   # tb3_2 robot
   ROS_DOMAIN_ID=5 ros2 launch turtlebot3_bringup camera_low_bandwidth.launch.py
   ```

5. Main can reach AI Server:

   ```bash
   curl http://smartfactory-vision.local:8100/api/v1/health
   ```

   If hostname resolution fails, use the laptop WiFi IP temporarily:

   ```bash
   curl http://<AI_LAPTOP_IP>:8100/api/v1/health
   ```

## Preflight checks

### AI Server health

```bash
curl http://smartfactory-vision.local:8100/api/v1/health
```

Expected:

- `status` is `ok`.
- Sources include `global_cam_01`, `tb3_1_picam`, and `tb3_2_picam`.

### Monitor state list

```bash
curl http://smartfactory-vision.local:8100/api/v1/vision/monitors
```

Expected:

- `person_drive` appears for both `tb3_1_picam` and `tb3_2_picam`.
- Initial `enabled` values are normally `false` unless Main already enabled them.

### WebRTC camera visibility

Open from Main or the laptop browser:

```text
http://smartfactory-vision.local:8889/tb3_1_picam_full/
http://smartfactory-vision.local:8889/tb3_2_picam_full/
```

Expected: both Pi camera streams are visible.

## Test cases

### 1. Monitor OFF returns no active monitor

```bash
curl 'http://smartfactory-vision.local:8100/api/v1/vision/hazards/person/latest?robot_id=tb3_1'
curl 'http://smartfactory-vision.local:8100/api/v1/vision/hazards/person/latest?robot_id=tb3_2'
```

Expected:

```json
{
  "result": "NO_ACTIVE_MONITOR",
  "event": null
}
```

### 2. Enable only tb3_1 DRIVE monitor

```bash
curl -X PUT http://smartfactory-vision.local:8100/api/v1/vision/monitors/person_drive/state \
  -H 'Content-Type: application/json' \
  -d '{"enabled":true,"source":"tb3_1_picam","operation_state":"DRIVE","task_id":101,"target_fps":3}'
```

Check state:

```bash
curl 'http://smartfactory-vision.local:8100/api/v1/vision/monitors/person_drive/state?robot_id=tb3_1'
curl 'http://smartfactory-vision.local:8100/api/v1/vision/monitors/person_drive/state?robot_id=tb3_2'
```

Expected:

- `tb3_1`: `enabled=true`, `source=tb3_1_picam`, `operation_state=DRIVE`, `task_id=101`.
- `tb3_2`: remains disabled unless separately enabled.

### 3. Validate tb3_1 person advisory

Place a person or validated person target in front of the `tb3_1` Pi camera, then poll:

```bash
curl 'http://smartfactory-vision.local:8100/api/v1/vision/hazards/person/latest?robot_id=tb3_1'
```

Expected when detected:

```json
{
  "result": "ADVISORY",
  "reason_code": "HUMAN_DETECTED",
  "event": {
    "event_type": "HUMAN_DETECTED",
    "source": "tb3_1_picam",
    "robot_id": "tb3_1",
    "task_id": 101,
    "severity": "CRITICAL",
    "trusted": false
  }
}
```

Expected when no person is present:

```json
{
  "result": "NO_RELEVANT_DETECTION",
  "event": null
}
```

### 4. Enable tb3_2 while tb3_1 remains active

```bash
curl -X PUT http://smartfactory-vision.local:8100/api/v1/vision/monitors/person_drive/state \
  -H 'Content-Type: application/json' \
  -d '{"enabled":true,"source":"tb3_2_picam","operation_state":"DRIVE","task_id":102,"target_fps":3}'
```

Check both states:

```bash
curl 'http://smartfactory-vision.local:8100/api/v1/vision/monitors/person_drive/state?robot_id=tb3_1'
curl 'http://smartfactory-vision.local:8100/api/v1/vision/monitors/person_drive/state?robot_id=tb3_2'
```

Expected:

- Both monitors are enabled independently.
- `tb3_1` keeps `task_id=101`.
- `tb3_2` has `task_id=102`.

### 5. Poll both robots independently

```bash
curl 'http://smartfactory-vision.local:8100/api/v1/vision/hazards/person/latest?robot_id=tb3_1'
curl 'http://smartfactory-vision.local:8100/api/v1/vision/hazards/person/latest?robot_id=tb3_2'
```

Expected:

- `tb3_1` responses use `source=tb3_1_picam` and `robot_id=tb3_1`.
- `tb3_2` responses use `source=tb3_2_picam` and `robot_id=tb3_2`.
- Events must not be mixed between robots.

### 6. Disable only tb3_1 and keep tb3_2 active

```bash
curl -X PUT http://smartfactory-vision.local:8100/api/v1/vision/monitors/person_drive/state \
  -H 'Content-Type: application/json' \
  -d '{"enabled":false,"source":"tb3_1_picam","operation_state":"IDLE"}'
```

Poll both:

```bash
curl 'http://smartfactory-vision.local:8100/api/v1/vision/hazards/person/latest?robot_id=tb3_1'
curl 'http://smartfactory-vision.local:8100/api/v1/vision/hazards/person/latest?robot_id=tb3_2'
```

Expected:

- `tb3_1`: `NO_ACTIVE_MONITOR`.
- `tb3_2`: remains active if previously enabled.

### 7. Reject robot/source mismatch

```bash
curl 'http://smartfactory-vision.local:8100/api/v1/vision/hazards/person/latest?robot_id=tb3_1&source=tb3_2_picam'
```

Expected:

- HTTP `400`.
- Error message indicates `robot_id tb3_1 requires source tb3_1_picam`.

## Main polling guidance

During DRIVE, Main should poll per robot:

```text
GET /api/v1/vision/hazards/person/latest?robot_id=tb3_1
GET /api/v1/vision/hazards/person/latest?robot_id=tb3_2
```

Recommended initial polling rate: `2~5Hz` per active robot. For example, `3Hz` means roughly every `333ms`.

Main owns:

- cooldown and duplicate suppression,
- HOLD/E-stop decision,
- DB insertion into `evidence_events` / `safety_stops`,
- task lifecycle state.

AI Server only returns advisory/evidence payloads.

## Pass criteria

The live validation passes when all of the following are true:

- low-load runtime is running.
- `tb3_1_picam_full` and `tb3_2_picam_full` WebRTC streams are visible.
- `person_drive` can be enabled independently for both robots.
- both robots can be active at the same time.
- disabling one robot does not disable the other robot.
- person advisory responses are robot/source correct.
- mismatch requests are rejected.
- Main-facing payload does not include `HOLD`, `E_STOP`, `BLOCKED`, raw bbox, raw mask, polygon, or raw detections.
