# Scenario 70 — 하드웨어 / 상태제어 / 로그·감사 / 인터페이스 구분

## 목적

이 문서는 SmartFactory 시스템을 이해하기 쉽게 다음 4개 관점으로 나눈다.

1. **하드웨어적 요소**
2. **상태제어적 요소**
3. **로그·증거·감사 요소**
4. **서비스 간 인터페이스**

이 구분은 구현할 때 책임이 섞이지 않게 하기 위한 기준이다.

---

# 1. 하드웨어적 요소

하드웨어적 요소는 “현실 세계에 실제로 존재하거나, 센서/로봇/리프트/카메라 상태를 나타내는 데이터”다.

## 관련 테이블

| 테이블 | 의미 |
|---|---|
| `robots` | 로봇 본체 상태. 예: `tb3_1`, `tb3_2` |
| `robot_capabilities` | 로봇이 가능한 기능. 예: lift, PiCamera, ArUco docking |
| `robot_state_samples` | 로봇 pose, battery, nav/lift 상태 샘플 |
| `lift_state_events` | 리프트 up/down/load 감지 이벤트 |
| `evidence_sources` | 글로벌캠, PiCamera, Nav status source |
| `sensor_calibrations` | 카메라 intrinsic/extrinsic, hand-eye, map-camera 보정 |
| `sensor_mounts` | 센서가 로봇/공장 어디에 장착되어 있는지 |
| `evidence_artifacts` | 이미지, 영상, JSON 등 원본 증거 파일 |

## 책임 원칙

- Main Server가 모터나 리프트를 직접 제어하지 않는다.
- Main은 `command_requests`를 만들고, Nav가 로봇 제어를 수행한다.
- AI는 카메라/영상 기반 증거를 생성하지만, task 성공 여부를 직접 확정하지 않는다.
- Robot은 bringup과 하드웨어 endpoint 역할에 집중한다.

## 하드웨어 계층의 대표 상태

```text
robots.status
  IDLE
  MOVING
  DOCKING
  LIFTING
  SAFETY_PAUSED
  ERROR
  OFFLINE

lift_state_events.state
  UP
  DOWN
  MOVING
  ERROR
```

---

# 2. 상태제어적 요소

상태제어적 요소는 “Main Server가 DB를 보고 어떤 작업을 다음에 실행할지 결정하는 제어 평면”이다.

## 관련 테이블

| 테이블 | 의미 |
|---|---|
| `work_orders` | 사람이 요청한 큰 업무 단위 |
| `tasks` | 로봇에게 할당 가능한 작업 단위 |
| `task_steps` | 순차 실행 단계. MOVE/DOCK/LIFT/VERIFY/COMMIT |
| `evidence_policies` | step 완료에 필요한 증거 조건 |
| `reservations` | 로봇/슬롯/파레트/구역 선점 |
| `resource_locks` | 주행 중 corridor, docking zone 등의 짧은 lock |
| `scheduler_leases` | scheduler 중복 실행 방지 |
| `command_requests` | Nav/AI/Robot bridge로 보내는 명령 |
| `safety_incidents` | 안전 사건 상태머신 |
| `decision_snapshots` | Main이 내린 판단의 입력/결과 스냅샷 |

## 상태제어 핵심 원칙

```text
Task는 의도다.
Step은 실행 단위다.
Command는 외부 시스템에 보내는 명령이다.
Evidence는 완료 판단 근거다.
Transition은 왜 상태가 바뀌었는지 남기는 감사 기록이다.
```

즉, 아래를 분리해야 한다.

| 개념 | 예시 | 저장 위치 |
|---|---|---|
| 할 일 | 파레트 P-001을 A-01에 넣기 | `tasks` |
| 실행 단계 | A-01 앞까지 이동 | `task_steps` |
| 외부 명령 | Nav에 `/goal` 호출 | `command_requests` |
| 실행 결과 | Nav가 도착했다고 보고 | `command_events` |
| 완료 근거 | AI가 슬롯 점유 확인 | `evidence_events` |
| 최종 판단 | evidence policy 만족 | `decision_snapshots` |
| 상태 변경 | step succeeded | `state_transitions` |

---

# 3. 로그·증거·감사 요소

로그적인 요소는 “나중에 왜 그렇게 판단했는지 재현할 수 있게 남기는 데이터”다.

## 관련 테이블

| 테이블 | 의미 |
|---|---|
| `api_call_logs` | 실제 HTTP/API 호출 요청/응답 기록 |
| `command_events` | Nav/AI/Robot bridge가 보낸 명령 진행 이벤트 |
| `evidence_events` | AI/Nav/Robot/Operator가 제출한 증거 이벤트 |
| `evidence_artifacts` | 이미지/영상/JSON artifact URI와 hash |
| `inbox_events` | 외부 이벤트 수신 큐 |
| `outbox_events` | 외부 시스템으로 보낼 이벤트 큐 |
| `dead_letter_events` | 반복 처리 실패 이벤트 격리 |
| `operator_actions` | 작업자 승인/확인/취소/수동 조작 이력 |
| `state_transitions` | 모든 상태 변경의 이유와 근거 |

## 로그와 상태의 차이

상태 테이블은 현재 상태를 빠르게 보기 위한 것이다.

```text
robots.status = MOVING
pallets.status = ON_ROBOT
task_steps.status = EXECUTING
```

로그/감사 테이블은 과거에 무슨 일이 있었는지 추적하기 위한 것이다.

```text
state_transitions
api_call_logs
command_events
evidence_events
operator_actions
```

따라서 로그성 테이블은 원칙적으로 append-only에 가깝게 운용하는 것이 좋다.

---

# 4. 서비스 간 인터페이스

## 전체 인터페이스 방향

```text
Main Server → Nav Server
  command_requests: NAV_GOAL, DOCK_ARUCO, LIFT_UP, LIFT_DOWN, STOP, RESUME

Nav Server → Main Server
  command_events, robot_state_samples, lift_state_events

AI Server → Main Server
  evidence_events, evidence_artifacts

Robot → Nav Server
  ROS2 topic/action/service 수준의 실제 주행/리프트 실행

Operator UI → Main Server
  operator_actions, manual confirm, resume authorization
```

## 인터페이스별 최소 계약

### 4.1 Main → Nav Command API

필수 필드:

```text
command_id
command_type
robot_id
task_id
step_id
idempotency_key
fencing_token
deadline_at
payload
```

권장 규칙:

- 같은 `idempotency_key`는 중복 실행하지 않는다.
- 만료된 `fencing_token`의 명령은 무시한다.
- `deadline_at` 이후에는 명령을 새로 평가한다.
- Nav는 명령을 받으면 `ACCEPTED` 또는 `REJECTED`를 반드시 돌려준다.

### 4.2 Nav → Main Event API

필수 필드:

```text
command_id
external_event_id
event_type
robot_id
observed_at
payload
```

대표 event type:

```text
ACCEPTED
STARTED
FEEDBACK
SUCCEEDED
FAILED
STOPPED
SAFETY_PAUSED
```

### 4.3 AI → Main Evidence API

필수 필드:

```text
external_event_id
dedupe_key
source_id
source_system
evidence_type
confidence
severity
observed_at
artifact_uri 또는 artifact_ref_id
```

대표 evidence type:

```text
HUMAN_DETECTED
HUMAN_CLEAR
ARUCO_MARKER_DETECTED
SLOT_EMPTY_CONFIRMED
SLOT_OCCUPIED_CONFIRMED
LIFT_LOAD_DETECTED
```

권장 규칙:

- `observed_at`은 AI 서버 생성 시간이 아니라 실제 관측 시간이어야 한다.
- `dedupe_key`로 같은 frame/event 중복 처리를 방지한다.
- 안전 관련 evidence는 `trusted_for_safety` source에서 온 것만 policy 판단에 사용한다.

### 4.4 Operator UI → Main API

대표 action:

```text
ACK_SAFETY
AUTHORIZE_RESUME
MANUAL_CONFIRM
CANCEL_TASK
RETRY_TASK
ADJUST_INVENTORY
```

권장 규칙:

- 모든 operator action은 `operator_actions`에 남긴다.
- 안전 재개는 operator ID와 reason이 반드시 필요하다.
- 수동 조작 후에는 reconciliation snapshot을 남긴다.

---

# 5. 계층별 금지사항

| 금지사항 | 이유 |
|---|---|
| Main이 로봇 모터/리프트를 직접 제어 | 책임 경계 붕괴, 안전 추적 어려움 |
| Nav가 task 성공/재고 성공을 직접 확정 | Nav는 실행자이지 업무 판단자가 아님 |
| AI가 DB의 task 상태를 직접 바꿈 | AI는 증거 제출자여야 함 |
| API 응답만으로 step 완료 처리 | 실제 상황 증거가 없으면 위험 |
| 로그 테이블을 수정/삭제 중심으로 운용 | 사고 재현과 감사가 어려움 |
| 예약과 lock을 하나로 합침 | 장기 선점과 순간 경로 점유 정책이 섞임 |

---

# 6. 한 줄 요약

```text
하드웨어 계층은 사실을 만든다.
상태제어 계층은 다음 행동을 결정한다.
로그·감사 계층은 왜 그렇게 되었는지 증명한다.
인터페이스 계약은 각 계층이 서로를 침범하지 않게 막는다.
```
