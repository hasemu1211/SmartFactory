# SmartFactory Perception-Control Plan

Status: Draft implementation plan for robot-free development first  
Date: 2026-06-11  
Scope: AI Server / central-PC perception logic, ArUco docking math, lift ROI evaluation, synthetic tests

## 1. Decision summary

The SmartFactory vision stack is split into two loops:

1. **Evidence loop** — slower, HTTP/event-oriented, suitable for AI Server `VisionEvent` logging and WMS evidence.
2. **Control loop** — faster, ROS-oriented, suitable for precise docking/parking alignment.

The current 0.5 s snapshot path is acceptable for evidence and GUI/WMS summaries, but it is too slow for closed-loop precise docking. Precise parking must use a faster marker-pose stream, ideally on the central PC while the robot only runs bringup/camera publishers.

## 2. Responsibility split

| Layer | Owns | Must not own |
| --- | --- | --- |
| Robot | TurtleBot3 bringup, camera publish, LiDAR/Nav2 local safety, odom | Heavy AI model execution for MVP, WMS state decisions |
| Central ROS perception/docking node | Fast ArUco pose stream, docking error calculation, bounded low-speed command proposal | WMS DB writes, inventory/task final state |
| AI Server | Image decoding, marker/object/segmentation evidence, ROI/count candidate logic, `VisionEvent` emission | Direct `/cmd_vel`, direct Nav2 action calls, final WMS state |
| Main/WMS | Task/slot/inventory state, pickup/dropoff success policy, retry/abort/manual decisions | Raw image processing, direct pixel assumptions |
| Sensors | Raw observations: camera, LiDAR, lift-up/down sensor, battery | Policy decisions |

## 3. ArUco precise docking design

ArUco is not just a zone detector. It is a pose-based docking primitive.

### 3.1 Flow

```text
WMS selects task/station
  -> Nav2 coarse waypoint near station
  -> central-PC ROS perception estimates marker pose at high rate
  -> docking error = lateral / distance / yaw error
  -> docking controller proposes bounded low-speed command
  -> WMS/robot safety gates allow or stop command
  -> aligned when error tolerances are stable for N frames
```

### 3.2 Required inputs

- Marker dictionary and marker ID mapping per station.
- Marker physical size in meters.
- Camera intrinsic calibration.
- Station target offset, e.g. desired camera-to-marker distance and lateral offset.
- Tolerances:
  - lateral error tolerance
  - distance error tolerance
  - yaw error tolerance
  - required stable frame count

### 3.3 Output concepts

- `pose_estimate.method = ARUCO_POSE` can be used in `VisionEvent v1` for evidence.
- Fast control should not depend on HTTP snapshots.
- Actual robot tuning parameters remain config/tuning data:
  - max linear speed
  - max angular speed
  - lateral gain
  - yaw gain
  - distance gain
  - marker lost timeout
  - stable frame count

## 4. Lift ROI and load verification design

Lift load counting is not final task truth by itself. It is evidence used by WMS together with sensor/task state.

### 4.1 MVP detection path

MVP can count detections whose bounding boxes are sufficiently inside a configured lift ROI.

Candidate checks:

- class is load-like, e.g. `box`, `pallet`
- confidence is above threshold
- bbox center lies inside lift ROI
- bbox/ROI overlap ratio is above threshold
- count is stable for N frames

This is only a candidate/estimate, not the final success criterion.

### 4.2 Segmentation upgrade path

When available, instance segmentation is preferred for load count and dropped-item verification.

Segmentation checks:

- object mask intersection with lift mask
- mask centroid in lift polygon
- mask area-in-ROI ratio
- separation from floor/dropped-item ROI
- temporal stability by `track_id` or instance ID

Semantic segmentation is useful for static regions such as lift bed, floor, charging pad, forbidden zones. It is not sufficient by itself for individual object count.

## 5. Pickup and dropoff success policy

### 5.1 Pickup success

Recommended WMS policy:

```text
lift_up_sensor == true
AND expected load count is stable in lift ROI
AND no dropped-item candidate is present
AND marker/task context matches expected station/item
```

Vision-only success is not enough. Lift sensor provides the physical action evidence; vision checks that the item is still present and not fallen.

### 5.2 Dropoff success

MVP policy can be intentionally simpler:

```text
lift_down/lower command completed
AND robot back-off completed
AND WMS destination state transition succeeded
```

Optional vision strengthening:

```text
lift ROI is empty
AND target slot/drop ROI is occupied by expected object class/count
AND object remains after robot backs away
```

## 6. Robot-free implementation plan

The first implementation slice avoids real robot and physical camera dependencies.

1. Add pure ArUco docking math helpers:
   - camera intrinsics dataclass
   - solvePnP-based marker pose estimation
   - docking error calculation
   - bounded differential-drive command proposal
   - alignment/tolerance check
2. Add pure lift ROI evaluator:
   - bbox center/ROI overlap checks
   - optional mask overlap checks
   - count stability checks
   - pickup/dropoff policy helper results
3. Add synthetic tests:
   - projected ArUco corners with known pose
   - left/right/near/far/yaw docking errors
   - marker-lost/aligned command outputs
   - lift ROI count with inside/outside/partial objects
   - segmentation mask overlap behavior
   - lift sensor + count stability pickup verification

## 7. Robot-available tuning lane

If a robot becomes available mid-work, do not rewrite the design. Open a separate tuning lane.

Ready-to-use tuning assets:

- Runbook: `docs/robot/docking-tuning-runbook.md`
- Config template: `config/perception/docking_tuning.example.yaml`
- Session helper: `scripts/prepare_docking_tuning_session.sh`

### Passive tuning, no robot command

- Robot runs bringup/camera only.
- Central PC subscribes to camera topic.
- Measure camera FPS, latency, ArUco pose noise, marker-lost behavior.
- No `/cmd_vel` publication.

### Low-speed tuning, requires explicit permission

- Publish only bounded low-speed commands.
- Stop on marker loss, timeout, stale frames, E-stop/manual stop.
- Record error traces and tune gains/tolerances.

### Config-only tuning targets

- marker size
- camera intrinsics
- target offset
- P gains
- max linear/angular speeds
- tolerance thresholds
- stable frame count

## 8. Design critique and guardrails

- Do not use 0.5 s HTTP snapshots as the precise docking control loop.
- Do not let AI Server directly control `/cmd_vel`.
- Do not treat bbox-only count as final pickup success.
- Do not force mask/count fields into `VisionEvent v1`; strict schema evolution requires a planned v2 or separate endpoint.
- Keep robot-side MVP minimal: bringup/camera only unless the user explicitly permits robot-side changes.
