# MVP 흐름과 인터페이스

## 1. 책임 분리

| 구성요소 | 책임 |
|---|---|
| Main Server | DB 상태머신, task/step 판단, 명령 생성, 증거 검증 |
| Nav Server | 주행, ArUco docking, lift 명령 실행 |
| AI Server | 글로벌캠/PiCamera 기반 증거 생성 |
| Robot | bringup, 센서/리프트/주행 endpoint |
| Operator UI | 안전 확인, 수동 승인, 오류 처리 |

---

## 2. 최소 상태 흐름

```text
tasks
  PENDING → RUNNING → COMPLETED
                 └→ PAUSED / FAILED / NEEDS_REVIEW

task_steps
  PENDING → READY → COMMAND_SENT → EXECUTING → WAITING_EVIDENCE → COMPLETED
                                             └→ FAILED

commands
  PENDING → SENT → ACKED → SUCCEEDED
              └→ FAILED / TIMEOUT / CANCELLED
```

핵심은 `task`를 바로 완료하지 않고, `task_steps` 단위로 명령과 증거를 붙이는 것이다.

---

## 3. 입고 보관 MVP 흐름

```text
1. tasks 생성
   task_type = INBOUND_STORE
   source_location_id = 입고 위치
   target_location_id = 창고 슬롯
   inventory_unit_id = 입고 파레트

2. task_steps 생성
   MOVE → DOCK → LIFT_UP → MOVE → DOCK → LIFT_DOWN → VERIFY → COMMIT

3. resource_reservations 생성
   ROBOT, LOCATION, INVENTORY_UNIT 예약

4. Main이 다음 READY step 조회

5. commands 생성
   command_type = NAV_GOAL / DOCK_ARUCO / LIFT_UP / LIFT_DOWN
   target_system = NAV_SERVER

6. Nav가 실행 후 commands.status 갱신 또는 이벤트 전달

7. AI/Nav/Robot이 evidence_events 저장
   NAV_REACHED, ARUCO_DETECTED, LOAD_DETECTED, SLOT_CONFIRMED

8. Main이 required_evidence 충족 확인
   충족 시 task_steps.status = COMPLETED

9. COMMIT step에서 상태 확정
   inventory_units.current_location_id = target_location_id
   inventory_units.current_robot_id = null
   locations.status = OCCUPIED

10. event_log에 상태 변경/명령/API/재고 변경 기록
```

---

## 4. 출고 피킹 MVP 흐름

```text
1. tasks 생성
   task_type = OUTBOUND_PICK
   source_location_id = 창고 슬롯
   target_location_id = 출고 위치
   inventory_unit_id = 출고 파레트

2. inventory_units.status = RESERVED
   source slot도 RESERVED 처리

3. MOVE/DOCK/LIFT_UP으로 파레트 수령
   evidence: SLOT_CONFIRMED, LOAD_DETECTED

4. inventory_units.current_robot_id = robot_id
   inventory_units.current_location_id = null
   source slot status = AVAILABLE

5. 출고 위치로 MOVE 후 LIFT_DOWN
   evidence: SLOT_CONFIRMED 또는 DROP_CONFIRMED

6. COMMIT
   inventory_units.status = OUTBOUND
   current_location_id = target_location_id
```

---

## 5. 사람 감지 안전정지 MVP 흐름

```text
1. AI가 사람 감지
   evidence_events.evidence_type = HUMAN_DETECTED
   severity = SAFETY
   trusted_for_policy = true

2. Main이 safety_incidents 생성
   status = OPEN

3. Main이 STOP command 생성
   command_type = STOP
   target_system = NAV_SERVER

4. Nav가 정지 수행
   commands.status = SUCCEEDED

5. Main 상태 전이
   robots.status = PAUSED
   tasks.status = PAUSED
   task_steps.status = FAILED 또는 READY로 되돌릴 수 있도록 보류
   safety_incidents.status = STOPPED

6. HUMAN_CLEAR 증거 + operator 승인 후 RESUME command 생성

7. safety_incidents.status = CLOSED
   task 재개 또는 복구 task 생성
```

---

## 6. 인터페이스 최소 계약

### 6.1 Main → Nav

`commands` 기반으로 Nav API를 호출한다.

필수 필드:

```text
command_id
command_type
robot_code
task_id
step_id
idempotency_key
request_json
deadline_at
```

대표 command:

```text
NAV_GOAL
DOCK_ARUCO
LIFT_UP
LIFT_DOWN
STOP
RESUME
```

### 6.2 Nav → Main

MVP에서는 두 방식 중 하나만 선택해도 된다.

1. Nav API 응답으로 `commands.status` 갱신
2. Nav event endpoint로 `event_log` 또는 `evidence_events` 저장

초기 구현은 단순하게 `commands.response_json`과 `commands.status` 갱신으로 충분하다.

### 6.3 AI → Main

AI는 상태를 직접 바꾸지 않고 증거만 제출한다.

필수 필드:

```text
source_code
evidence_type
confidence
severity
artifact_uri 또는 payload_json
observed_at
```

### 6.4 Operator → Main

운영자 조작은 별도 테이블을 만들지 않고 MVP에서는 `event_log`에 남긴다.

예:

```text
event_type = OPERATOR_ACTION
actor = OPERATOR
payload_json = { action: 'AUTHORIZE_RESUME', operator_id: '...' }
```

---

## 7. MVP에서 지켜야 할 최소 규칙

1. Main 외에는 `tasks.status`, `task_steps.status`를 직접 바꾸지 않는다.
2. AI는 `evidence_events`만 쓴다.
3. Nav는 `commands` 결과만 돌려준다.
4. 모든 상태 변경은 `event_log`에 남긴다.
5. 작업 완료는 `required_evidence`가 충족되어야 한다.
6. 안전 증거 `HUMAN_DETECTED`는 일반 step 흐름보다 우선한다.
