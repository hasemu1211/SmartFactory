# SmartFactory MVP Refined Practical Schema Review

기준 파일:

```text
04_mvp_refined_practical.dbml
```

이 버전은 `03_mvp_lean_simple_terms`에서 너무 많이 쉬운 용어로 바꾼 부분을 실무형 이름으로 되돌리고, 사용자가 요청한 최소화 방향을 반영한 버전이다.

---

## 1. 반영한 요청 요약

| 요청 | 반영 |
| --- | --- |
| `safety_stops`, `reservations`, `from_location_*`, `to_location_*`는 유지 | 유지하되 id 통일 원칙에 따라 `from_location_id`, `to_location_id`로 사용 |
| 나머지 쉬운 용어는 원복 | `inventory`, `evidence_events`, `item_change_logs`로 원복 |
| `code` 말고 `id`로 통일 | 모든 PK/FK 이름을 `id`, `*_id`로 통일 |
| `items.unit` 제거 | 제거 |
| `DOCK_ARUCO + LIFT_UP` 합치기 | `PICK_UP` command로 통합 |
| `DOCK_ARUCO + LIFT_DOWN` 합치기 | `DROP_OFF` command로 통합 |
| `robots`에 domainID 컬럼 추가 | `domain_id integer` 추가 |
| `task_type`에 charging 추가 | `CHARGING` 추가 |
| `command_payload_json` 삭제 | task에서 payload 제거, command API 합성용 `location_id`, `request_json` 사용 |

---

## 2. 구조 비교

| 항목 | 기존 추천안 02 | Lean 03 | Refined 04 |
| --- | ---: | ---: | ---: |
| 테이블 | 11 | 10 | 10 |
| 컬럼 | 121 | 89 | 90 |
| 관계 | 30 | 24 | 25 |
| Enum | 8 | 0 | 0 |

`04_mvp_refined_practical.dbml`은 DBML 공식 CLI로 PostgreSQL 변환 검증을 통과했다.

---

## 3. 용어 정리

### 유지한 쉬운 용어

| 용어 | 유지 이유 |
| --- | --- |
| `safety_stops` | 실제 의미가 사람 감지/안전 정지 흐름이라 직관적 |
| `reservations` | `resource_reservations`보다 짧고 충분히 명확함 |
| `from_location_id` | 출발 위치 의미가 명확함 |
| `to_location_id` | 도착 위치 의미가 명확함 |

### 원복한 용어

| Lean 03 | Refined 04 | 이유 |
| --- | --- | --- |
| `stock` | `inventory` | DB/물류 문맥에서 더 표준적 |
| `proofs` | `evidence_events` | AI/Nav/Robot이 제출하는 event 성격이 더 명확함 |
| `stock_logs` | `item_change_logs` | 품목 수량 변경 로그라는 의미가 더 구체적 |
| `order_no` | `sequence_no` | command 순서 컬럼명으로 더 일반적 |
| `required_proof` | `required_evidence_type` | evidence_events와 매칭되는 컬럼임이 명확함 |

---

## 4. `id` 통일 방식

Refined 04에서는 `code` 컬럼을 쓰지 않고, 모든 참조를 `id` 또는 `*_id`로 통일했다.

예:

```text
robots.id = tb3_1
locations.id = STORAGE_A_01
items.id = BOLT_M3
tasks.robot_id -> robots.id
tasks.from_location_id -> locations.id
tasks.to_location_id -> locations.id
```

주의:

- 여기서 `id`는 MVP용 안정 식별자다.
- 실제 운영에서 UUID가 필요해지면 `id uuid` + `display_name text` 구조로 바꿀 수 있다.
- 현재는 사람이 읽는 값이 곧 id라서 DBML과 발표 자료가 단순해진다.

---

## 5. Command 단순화

기존 세분화:

```text
NAV_GOAL
DOCK_ARUCO
LIFT_UP
LIFT_DOWN
STOP
RESUME
```

Refined 04:

```text
NAV_GOAL
PICK_UP
DROP_OFF
STOP
RESUME
START_CHARGING
STOP_CHARGING
```

### 5.1 `PICK_UP`

`PICK_UP`은 다음 과정을 하나의 command로 본다.

```text
ArUco 정밀 접근 + lift up + 적재 확인
```

필요 evidence 예:

```text
ITEM_PICKED
```

내부적으로는 AI/Nav/Robot이 아래 evidence를 낼 수 있다.

```text
ARUCO_DETECTED
LOAD_DETECTED
ITEM_PICKED
```

### 5.2 `DROP_OFF`

`DROP_OFF`은 다음 과정을 하나의 command로 본다.

```text
ArUco 정밀 접근 + lift down + 배치 확인
```

필요 evidence 예:

```text
ITEM_PLACED
```

내부적으로는 아래 evidence를 낼 수 있다.

```text
ARUCO_DETECTED
SLOT_CONFIRMED
ITEM_PLACED
```

---

## 6. Charging task

`tasks.task_type`에 `CHARGING`을 추가했다.

사용 목적:

```text
배터리가 낮으면 일반 작업 할당을 막고,
충전 위치로 이동하는 task를 생성한다.
```

예시 흐름:

```text
1. robots.battery_level < threshold
2. Main Scheduler가 CHARGING task 생성
3. to_location_id = CHARGE_01
4. command NAV_GOAL to CHARGE_01
5. command START_CHARGING
6. robots.status = CHARGING
```

---

## 7. `domain_id` 추가

`robots.domain_id`는 ROS2 `ROS_DOMAIN_ID`를 표현한다.

필요한 이유:

```text
두 로봇 또는 여러 ROS2 runtime을 네트워크에서 분리하거나 식별하기 위함
```

예:

```text
tb3_1.domain_id = 11
tb3_2.domain_id = 12
```

---

## 8. `command_payload_json` 삭제와 API 호출 합성

`tasks.command_payload_json`은 제거했다.

이유:

- task는 목표만 가져야 한다.
- 실제 API 요청은 command 실행 시점에 합성하는 것이 더 명확하다.
- command payload가 task에 있으면 task와 command 책임이 섞인다.

대체 방식:

```text
commands.command_type
commands.location_id
tasks.from_location_id
tasks.to_location_id
locations.x/y/yaw/marker_id
robots.id/domain_id
```

위 정보를 조합해서 실제 API 요청을 만들고, 생성된 요청 스냅샷은 아래에 저장한다.

```text
commands.request_json
commands.response_json
```

즉:

```text
Task = 무엇을 할지
Command = 어떤 API를 호출할지
request_json = 실제 호출한 payload snapshot
```

---

## 9. Refined 04의 추천 sequence

### INBOUND 예시

```text
1. NAV_GOAL  -> from_location_id 또는 입고 approach
2. PICK_UP   -> from_location_id
3. NAV_GOAL  -> to_location_id 또는 slot approach
4. DROP_OFF  -> to_location_id
```

### OUTBOUND 예시

```text
1. NAV_GOAL  -> from_location_id 또는 slot approach
2. PICK_UP   -> from_location_id
3. NAV_GOAL  -> to_location_id 또는 outbound area
4. DROP_OFF  -> to_location_id
```

### CHARGING 예시

```text
1. NAV_GOAL        -> CHARGE_01
2. START_CHARGING  -> CHARGE_01
```

---

## 10. 남은 검토 포인트

| 항목 | 검토 이유 |
| --- | --- |
| `id text` 유지 여부 | 운영 DB에서 UUID를 쓸지, 사람이 읽는 ID를 쓸지 결정 필요 |
| Enum/check constraint | 현재는 text status/kind라 오타 방지 장치가 약함 |
| `PICK_UP`, `DROP_OFF` 내부 evidence 정책 | `ITEM_PICKED`, `ITEM_PLACED`를 어떤 조건으로 만들지 정의 필요 |
| Charging 완료 조건 | 배터리 몇 % 이상이면 완료인지 기준 필요 |
| ACTIVE reservation 중복 방지 | 실제 PostgreSQL에서는 partial unique index 권장 |

---

## 11. 현재 추천

현재 사용자가 요구한 방향에는 `04_mvp_refined_practical.dbml`이 가장 적합하다.

이유:

1. `id` 기반으로 통일되어 혼란이 적다.
2. 너무 쉬운 용어로 바꾼 부분은 다시 실무형 용어로 원복했다.
3. PICK/PLACE 계열 command가 실제 로봇 작업 단위에 더 가깝다.
4. Charging task와 ROS domain_id가 반영되어 로봇 운영 관점이 보강됐다.
5. 컬럼 수는 기존 추천안보다 줄어든 상태를 유지한다.
