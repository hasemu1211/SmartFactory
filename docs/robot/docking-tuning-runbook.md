# Docking / Parking Tuning Runbook

Status: ready-to-use tuning checklist  
Date: 2026-06-11  
Scope: ArUco precision docking and lift ROI tuning, separated from robot-free implementation work

## 1. Purpose

This runbook lets the team start tuning whenever a robot becomes available, without changing the main AI Server development plan.

The default tuning mode is **passive**:

- robot runs bringup/camera only,
- central PC observes ROS topics,
- no `/cmd_vel` is published,
- no robot-side files/configs are changed.

Low-speed active tuning is a later gated step and requires explicit user permission.

## 2. Safety and permission rules

Allowed without additional permission, based on current project agreement:

- SSH into Robot1 when the user has opened/approved the session.
- Start/stop/restart:

```bash
ros2 launch turtlebot3_bringup camera.launch.py
```

Requires explicit user permission before doing:

- modifying robot files/config/packages,
- installing packages on robot,
- changing robot system/network/services,
- publishing `/cmd_vel` or running any active motion controller,
- touching Robot2 while someone else is using it.

All ROS CLI work should be done in the managed Development tmux pane/window requested by the user.

## 3. Tuning lane overview

### Phase A — Passive observation, no motion

Goal: validate camera stream and marker pose quality.

Measurements:

- camera topic availability,
- compressed/raw FPS,
- frame latency if available,
- ArUco detection stability,
- solvePnP pose noise,
- marker loss behavior.

No robot motion is allowed in this phase.

### Phase B — Static calibration/tolerance preparation

Goal: convert observations into config values.

Tune or confirm:

- marker physical size,
- camera intrinsics,
- station marker IDs,
- target docking offset,
- lateral/distance/yaw tolerances,
- required stable frame count.

### Phase C — Low-speed active docking, permission required

Goal: tune command gains and speed limits.

Hard gates:

- explicit user permission,
- manual stop/E-stop ready,
- max speed limits configured,
- marker loss means immediate stop,
- stale frame timeout means immediate stop,
- no active tuning while people are in the path.

## 3.1 Pose profile config

AI Server can compute optional ArUco pose evidence using named profiles from:

```text
config/perception/aruco_pose_profiles.example.json
```

Use this for computer-only or passive tuning sessions so the API request only
needs `pose_profile=<name>`. Keep these values as tuning data:

- marker size,
- camera intrinsics,
- source binding,
- expected marker ID,
- station target offset notes.

Do not treat placeholder intrinsics as active docking calibration. After editing
the profile file, restart the AI Server because profiles are cached in process.

## 4. Passive session setup

Use the helper script from repo root:

```bash
./scripts/prepare_docking_tuning_session.sh
```

It creates a session folder under `.omx/reports/docking-tuning/` and copies the config template.

To print safe passive ROS check commands without running them:

```bash
./scripts/prepare_docking_tuning_session.sh --print-commands
```

To run passive checks later from the managed ROS CLI pane only:

```bash
./scripts/prepare_docking_tuning_session.sh --passive-check
```

`--passive-check` must not publish motion commands. It only inspects topic list/type/hz.

## 5. Recommended passive checks

Robot camera launch, when permitted/needed:

```bash
ros2 launch turtlebot3_bringup camera.launch.py
```

Central PC checks:

```bash
ros2 topic list | grep camera
ros2 topic type /camera/image_raw/compressed
ros2 topic hz /camera/image_raw/compressed
```

If raw is needed for comparison:

```bash
ros2 topic hz /camera/image_raw
```

Expected current evidence from Robot1 QA:

- `/camera/image_raw/compressed` is about 30 Hz.
- `/camera/image_raw` is lower, about 13 Hz in the previous Robot1 observation.
- Prefer compressed for bandwidth-sensitive AI snapshot/evidence paths.

## 6. ArUco pose tuning checklist

Prepare:

- print or display known marker ID,
- measure marker size in meters,
- confirm dictionary, currently `DICT_4X4_50`,
- capture camera intrinsics or use a temporary clearly-marked estimate,
- choose station target offset.

Record per station:

- `marker_id`,
- `marker_size_m`,
- `target_distance_m`,
- `target_lateral_offset_m`,
- `target_yaw_rad`,
- tolerances,
- observed pose jitter at rest,
- detection dropout rate.

Recommended initial tolerances for lab tuning:

```text
lateral <= 0.04 m
distance <= 0.04 m
yaw <= 5 deg
stable frames >= 5
```

Tighten only after passive noise measurements show that tighter thresholds are stable.

## 7. Lift ROI tuning checklist

Prepare:

- define lift ROI polygon in image coordinates,
- define optional floor/dropped-item ROI,
- record expected object classes, e.g. `box`, `pallet`,
- choose minimum confidence,
- choose bbox/mask overlap threshold,
- choose stable frame count.

MVP evidence rule:

```text
class is load-like
AND confidence >= threshold
AND bbox center inside lift ROI
AND bbox or mask overlap ratio >= threshold
AND count is stable for N frames
```

Pickup success is not vision-only:

```text
lift_up_sensor == true
AND load count stable
AND no dropped-item candidate
```

Dropoff MVP can remain sequence-based:

```text
lift_down/lower complete
AND robot backoff complete
AND WMS destination state updated
```

Optional vision strengthening:

```text
lift ROI empty
AND target/drop ROI occupied
```

## 8. Active tuning guardrails

When active tuning is approved, initial limits should be conservative:

```yaml
max_linear_mps: 0.03
max_angular_radps: 0.20
marker_lost_stop: true
stale_timeout_ms: 300
```

Increase only after logs show stable behavior.

Stop immediately if:

- marker is lost,
- pose jumps unexpectedly,
- frame stream becomes stale,
- person/obstacle enters the path,
- operator requests stop,
- robot deviates from expected station approach.

## 9. Artifacts to save per tuning session

Save under `.omx/reports/docking-tuning/<timestamp>/`:

- copied config used for the session,
- topic list/type/hz logs,
- marker pose jitter logs,
- screenshots or camera frames if available,
- final chosen parameters,
- open issues and next tuning request.

## 10. Relation to implementation plan

This tuning lane is deliberately separate from the robot-free implementation plan in `docs/technical/perception-control-plan.md`.

Robot-free work can continue without robot access. When robot access appears, this runbook can be used immediately for passive measurement, then later for permission-gated low-speed tuning.
