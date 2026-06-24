# 테이블 설명과 관계 가이드

## 1. 전체를 네 묶음으로 보기

```text
physical_state
  robots, locations, items, inventory

execution
  tasks, commands, resource_reservations

evidence_and_safety
  evidence_events, safety_incidents

logs
  task_logs, item_change_logs
```

---

# 2. 테이블별 설명

## 2.1 `robots`

로봇 2대의 현재 상태를 저장한다.

예:

```text
tb3_1: IDLE
tb3_2: MOVING
```

주요 관계:

```text
robots.current_location_id -> locations.id
robots.active_task_id      -> tasks.id
```

주로 쓰는 곳:

- Main Scheduler: 어떤 로봇을 배정할지 판단
- Nav Server: 로봇 상태 업데이트
- Operator UI: 현재 로봇 상태 표시

---

## 2.2 `locations`

입고지역, 창고 슬롯, 출고지역, 충전 위치, waypoint를 모두 표현한다.

예:

```text
INBOUND_01
STORAGE_A_01
STORAGE_A_01_APPROACH
OUTBOUND_01
CHARGE_01
```

중요 필드:

| 필드 | 의미 |
|---|---|
| `location_type` | AREA/WAYPOINT/SLOT/CHARGE |
| `parent_location_id` | 슬롯/웨이포인트가 속한 상위 구역 |
| `approach_location_id` | 슬롯 접근 전 waypoint |
| `aruco_marker_id` | 정밀주차용 marker |

---

## 2.3 `items`

부품 마스터다.

예:

```text
BOLT_M3
MOTOR_A
SENSOR_KIT
```

`items` 자체는 위치를 가지지 않는다. 위치별 수량은 `inventory`가 가진다.

---

## 2.4 `inventory`

특정 location에 특정 item이 몇 개 있는지 나타낸다.

```text
(item_id, location_id) = primary key
```

예:

```text
BOLT_M3 at STORAGE_A_01 = 30 ea
```

주의:

- 이 MVP는 “개별 파레트 추적”보다 “품목/위치별 수량 관리”에 가깝다.
- 파레트 단위 추적이 필요해지면 나중에 `inventory_units` 또는 `pallets`로 분리한다.

---

## 2.5 `tasks`

사람 또는 시스템이 원하는 작업 단위다.

예:

```text
INBOUND: 입고 위치의 item을 창고 슬롯으로 이동
OUTBOUND: 창고 슬롯의 item을 출고 위치로 이동
MOVE: 단순 위치 이동
RECOVERY: 복구 작업
```

주요 관계:

```text
tasks.robot_id            -> robots.id
tasks.item_id             -> items.id
tasks.source_location_id  -> locations.id
tasks.target_location_id  -> locations.id
```

---

## 2.6 `commands`

실제로 Nav Server 또는 Robot Bridge에 보내는 명령이다.

예:

```text
NAV_GOAL
DOCK_ARUCO
LIFT_UP
LIFT_DOWN
STOP
RESUME
```

중요한 설계 포인트:

```text
commands.sequence_no
```

이 필드가 `task_steps`를 대체한다.

예:

```text
1 NAV_GOAL
2 DOCK_ARUCO
3 LIFT_UP
4 NAV_GOAL
5 DOCK_ARUCO
6 LIFT_DOWN
```

```text
commands.required_evidence_type
```

명령 완료를 인정하기 위해 필요한 증거 타입이다.

예:

```text
NAV_GOAL   -> NAV_REACHED
DOCK_ARUCO -> ARUCO_DETECTED
LIFT_UP    -> LOAD_DETECTED
LIFT_DOWN  -> SLOT_CONFIRMED
```

---

## 2.7 `resource_reservations`

로봇/위치/아이템을 특정 task가 선점했음을 나타낸다.

필요한 이유:

```text
tb3_1과 tb3_2가 같은 슬롯을 동시에 목표로 잡는 문제 방지
두 task가 같은 재고를 동시에 출고하려는 문제 방지
```

MVP에서는 복잡한 lock/lease를 만들지 않고 이 테이블 하나로 시작한다.

---

## 2.8 `evidence_events`

AI/Nav/Robot/Operator가 제출하는 증거다.

예:

```text
NAV_REACHED
ARUCO_DETECTED
LOAD_DETECTED
SLOT_CONFIRMED
HUMAN_DETECTED
HUMAN_CLEAR
```

중요 필드:

| 필드 | 의미 |
|---|---|
| `event_type` | 증거 종류 |
| `source_type` | GLOBAL_CAMERA/PICAMERA/NAV_SERVER/ROBOT/OPERATOR |
| `confidence` | AI confidence |
| `severity` | INFO/WARN/ERROR/SAFETY |
| `trusted_for_policy` | 완료/안전 판단에 써도 되는 증거인지 |
| `command_id` | 어떤 command 완료 근거인지 |

---

## 2.9 `safety_incidents`

사람 감지 등 안전 사건의 lifecycle을 저장한다.

대표 흐름:

```text
OPEN -> STOP_SENT -> STOPPED -> CLEAR_PENDING -> RESUME_ALLOWED -> CLOSED
```

주요 관계:

```text
triggering_evidence_id -> evidence_events.id  // HUMAN_DETECTED
stop_command_id        -> commands.id         // STOP
clear_evidence_id      -> evidence_events.id  // HUMAN_CLEAR
```

---

## 2.10 `task_logs`

완료된 task의 요약 로그다.

`tasks`는 현재 상태를 가진다.  
`task_logs`는 완료 결과를 보관한다.

예:

```text
task 102 completed successfully
robot tb3_1 moved item A from INBOUND_01 to STORAGE_A_01
```

---

## 2.11 `item_change_logs`

재고 수량 변경 이력이다.

예:

```text
INBOUND +10
RESERVED -10
OUTBOUND -5
CORRECTION +1
```

중요한 이유:

- 현재 재고는 `inventory`
- 재고 변경 이유는 `item_change_logs`

---

# 3. 관계를 한 줄로 요약

```text
robots + locations + items + inventory = 현재 물리 상태

tasks = 해야 할 일
commands = 실제 실행 명령
resource_reservations = 충돌 방지용 선점

evidence_events = 완료/안전 판단 근거
safety_incidents = 안전 사건 상태

task_logs + item_change_logs = 결과 기록
```
