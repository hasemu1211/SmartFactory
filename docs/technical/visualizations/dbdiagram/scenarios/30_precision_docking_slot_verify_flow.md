# Scenario 30 — ArUco 정밀주차/슬롯 검증 흐름

## 목적

일반 주행으로는 슬롯 앞까지 접근하고, 슬롯 또는 파레트의 ArUco marker를 이용해 마지막 수 cm 수준의 정밀주차를 수행한다. 이후 AI/센서 증거로 슬롯 상태를 검증한다.

## 왜 별도 시나리오로 분리했는가

정밀주차는 단순 이동과 다르다. 일반 `NAV_GOAL`은 waypoint까지 이동하는 것이고, `DOCK_ARUCO`는 marker 인식, pose 안정성, calibration version, retry 정책이 필요하다.

## 핵심 테이블

| 테이블 | 역할 |
|---|---|
| `maps`, `map_zones`, `waypoints` | 접근 지점과 docking 시작 지점 정의 |
| `storage_slots` | 슬롯의 현재 상태와 접근 waypoint |
| `docking_markers` | ArUco marker ID, family, expected pose, docking profile |
| `evidence_sources` | global cam, PiCamera 등 증거 출처 |
| `sensor_calibrations`, `sensor_mounts` | 카메라/좌표계 보정 정보 |
| `command_requests` | `NAV_GOAL`, `DOCK_ARUCO` 명령 |
| `docking_attempts` | 각 docking 시도별 오차와 결과 |
| `evidence_events` | marker 검출, pose 안정화, 슬롯 empty/occupied 확인 |
| `decision_snapshots` | Main의 성공/실패 판단 결과 |

## 정상 흐름

```text
1. Main이 target slot을 선택
   storage_slots.status = EMPTY 또는 OCCUPIED
   approach_waypoint_id 확인
   docking_marker_id 확인

2. 접근 waypoint로 이동
   command_requests.command_type = NAV_GOAL
   target = storage_slots.approach_waypoint_id

3. Nav가 일반 주행 완료 보고
   command_events.event_type = SUCCEEDED
   evidence_events.evidence_type = NAV_GOAL_REACHED

4. Main이 정밀주차 step 시작
   task_steps.step_type = DOCK_ARUCO
   command_requests.command_type = DOCK_ARUCO
   command_requests.map_version, calibration_version 기록

5. Nav/Robot PiCamera가 ArUco marker 탐색
   evidence_events.evidence_type = ARUCO_MARKER_DETECTED
   evidence_source_id = tb3_x_picam

6. 정밀 pose 안정화
   docking_attempts.error_xy_m
   docking_attempts.error_yaw_rad
   docking_attempts.stable_frame_count

7. 성공 기준 충족
   error_xy_m <= threshold
   error_yaw_rad <= threshold
   stable_frame_count >= threshold

8. 슬롯 상태 검증
   AI global cam 또는 PiCamera가 SLOT_EMPTY_CONFIRMED/SLOT_OCCUPIED_CONFIRMED 제출

9. Main이 decision snapshot 저장
   decision_snapshots.decision_type = DOCKING_RESULT_EVALUATION 또는 SLOT_VERIFY

10. step 상태 전이
    task_steps.status = SUCCEEDED
    state_transitions에 근거 기록
```

## 완료 조건

- 올바른 marker ID가 검출되어야 한다.
- marker pose가 현재 map/calibration version 기준으로 해석되어야 한다.
- XY/Yaw 오차가 허용치 이내여야 한다.
- 일정 frame 수 이상 안정적이어야 한다.
- 슬롯 empty/occupied 증거가 작업 목적과 일치해야 한다.

## 실패/예외 분기

| 상황 | 처리 |
|---|---|
| marker 미검출 | 재시도, 조명/카메라 상태 확인, `RETRY_WAIT` |
| marker ID 불일치 | 잘못된 슬롯 가능성, `MANUAL_REVIEW` |
| calibration version 불일치 | 명령 중단, calibration 갱신 필요 |
| 오차가 줄지 않음 | docking_attempts 실패 기록 후 retry |
| AI와 Robot 증거 충돌 | Main이 `CONFLICTING_EVIDENCE`로 판단하고 보류 |

## dbdiagram에서 볼 포인트

- `storage_slots → docking_markers → waypoints`가 위치/정밀주차 기준이다.
- `sensor_calibrations/sensor_mounts`는 증거의 신뢰성을 결정한다.
- `docking_attempts`는 단순 성공/실패가 아니라 “얼마나 오차가 있었는지”를 남긴다.
