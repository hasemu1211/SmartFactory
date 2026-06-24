# 시나리오별 동작 설명

## Scenario A — 입고 보관

목표:

```text
입고 위치의 item을 창고 슬롯에 보관한다.
```

### 1. 작업 생성

```text
tasks.task_type = INBOUND
tasks.source_location_id = INBOUND_01
tasks.target_location_id = STORAGE_A_01
tasks.item_id = 대상 item
tasks.quantity = 수량
```

### 2. 자원 예약

```text
resource_reservations
  ROBOT    -> tb3_1
  LOCATION -> STORAGE_A_01
  ITEM     -> 대상 item
```

### 3. 명령 생성

```text
commands.sequence_no = 1, command_type = NAV_GOAL,   required_evidence_type = NAV_REACHED
commands.sequence_no = 2, command_type = DOCK_ARUCO, required_evidence_type = ARUCO_DETECTED
commands.sequence_no = 3, command_type = LIFT_UP,    required_evidence_type = LOAD_DETECTED
commands.sequence_no = 4, command_type = NAV_GOAL,   required_evidence_type = NAV_REACHED
commands.sequence_no = 5, command_type = DOCK_ARUCO, required_evidence_type = ARUCO_DETECTED
commands.sequence_no = 6, command_type = LIFT_DOWN,  required_evidence_type = SLOT_CONFIRMED
```

### 4. 증거 수집

AI/Nav/Robot이 `evidence_events`를 생성한다.

```text
NAV_REACHED
ARUCO_DETECTED
LOAD_DETECTED
SLOT_CONFIRMED
```

Main은 현재 command의 `required_evidence_type`과 matching되는 trusted evidence가 있으면 다음 command로 넘어간다.

### 5. 완료 처리

```text
inventory 증가/이동
item_change_logs 기록
task_logs 기록
tasks.status = COMPLETED
resource_reservations.status = RELEASED
```

---

## Scenario B — 출고 피킹

목표:

```text
창고 슬롯의 item을 출고 위치로 이동한다.
```

### 흐름

```text
1. tasks.task_type = OUTBOUND
2. source_location_id = STORAGE_A_01
3. target_location_id = OUTBOUND_01
4. resource_reservations로 robot/location/item 예약
5. commands를 sequence_no 순서로 실행
6. SLOT_CONFIRMED, LOAD_DETECTED, NAV_REACHED 등의 evidence 수집
7. item_change_logs에 OUTBOUND 기록
8. task_logs에 결과 기록
```

출고는 입고와 거의 같지만, 재고 변경 방향이 반대다.

```text
입고: target location 재고 증가
출고: source location 재고 감소 또는 outbound location으로 이동
```

---

## Scenario C — 사람 감지 안전정지

목표:

```text
주행 중 사람이 감지되면 즉시 정지하고, clear 증거가 있어야 재개한다.
```

### 1. 사람 감지 증거 발생

```text
evidence_events.event_type = HUMAN_DETECTED
evidence_events.severity = SAFETY
evidence_events.trusted_for_policy = true
```

### 2. 안전 incident 생성

```text
safety_incidents.status = OPEN
safety_incidents.triggering_evidence_id = HUMAN_DETECTED evidence
```

### 3. STOP 명령 생성

```text
commands.command_type = STOP
commands.required_evidence_type = null
```

### 4. 정지 완료

Nav가 STOP 성공을 반환하면:

```text
commands.status = SUCCEEDED
robots.status = PAUSED
tasks.status = PAUSED
safety_incidents.status = STOPPED
```

### 5. 재개 조건

```text
evidence_events.event_type = HUMAN_CLEAR
trusted_for_policy = true
```

그 후:

```text
commands.command_type = RESUME
safety_incidents.status = CLOSED
```

---

## Scenario D — 명령 실패/재시도

### 1. 명령 timeout

```text
commands.status = TIMEOUT
```

### 2. 재시도 가능하면

```text
새 commands 생성
sequence_no는 동일하거나 다음 번호 사용
idempotency_key는 새로 발급
```

### 3. 재시도 불가하면

```text
tasks.status = NEEDS_REVIEW 또는 FAILED
task_logs.result = FAILURE
```

### 4. 증거 부족이면

예:

```text
LIFT_DOWN은 성공했지만 SLOT_CONFIRMED evidence가 없음
```

처리:

```text
commands.status = ACKED 또는 SUCCEEDED 상태라도
required_evidence_type 미충족이면 task 완료 금지
```

---

## 핵심 판단 규칙

```text
API 성공 != 작업 완료

작업 완료 = command 성공 + required evidence 충족 + 재고/로그 반영
```
