# SmartFactory MVP Lean Schema Review

기준:

```text
기존 추천안: 02_mvp_recommended_with_safety_reservation.dbml
lean 버전: 03_mvp_lean_simple_terms.dbml
```

## 1. 줄인 결과

| 항목 | 기존 추천안 | Lean 버전 | 감소 |
| --- | ---: | ---: | ---: |
| 테이블 | 11 | 10 | -1 |
| 컬럼 | 121 | 89 | -32 |
| 관계 | 30 | 24 | -6 |
| Enum | 8 | 0 | -8 |

Lean 버전은 PostgreSQL 변환 검증을 통과했다.

```text
03_mvp_lean_simple_terms.dbml
10 tables, 89 columns, 24 refs
```

---

## 2. 핵심 판단

초기 구현에서는 아래 방향이 더 단순하다.

```text
id + code + name을 모두 두지 않는다.
사람이 읽을 수 있고 안정적인 code가 있으면 code를 PK로 쓴다.
완료 이력은 별도 task_logs 대신 tasks의 started_at/finished_at/status로 시작한다.
카메라/증거/안전/예약 용어는 더 쉬운 단어로 줄인다.
```

---

## 3. 합친 것 / 뺀 것

### 3.1 `items.id + item_code + item_name` 축소

기존:

```text
items.id
items.item_code
items.item_name
items.unit
```

Lean:

```text
items.code
items.unit
```

이유:

- MVP에서는 품목 코드가 곧 식별자 역할을 할 수 있다.
- `BOLT_M3`, `MOTOR_A`처럼 사람이 읽을 수 있는 코드라면 별도 `id`가 없어도 된다.
- `item_name`은 표시용인데, 초기에는 `code`만으로도 충분하다.

나중에 되돌릴 조건:

- 품목 코드가 자주 바뀐다.
- 한국어 표시명/영문 코드/ERP 코드가 모두 필요하다.
- 같은 표시명에 여러 품목 코드가 생긴다.

---

### 3.2 `locations.id + code + name` 축소

기존:

```text
locations.id
locations.code
locations.name
```

Lean:

```text
locations.code
```

이유:

- 위치는 `INBOUND_01`, `STORAGE_A_01`, `OUTBOUND_01`처럼 code 자체가 의미 있다.
- UI 표시명은 code를 그대로 보여줘도 MVP에서는 충분하다.

나중에 되돌릴 조건:

- 사용자에게 더 자연스러운 표시명이 필요하다.
- 위치 코드와 표시명을 분리해야 한다.
- 지도 버전별 location ID 관리가 필요하다.

---

### 3.3 `robots.id + robot_code + robot_name` 축소

기존:

```text
robots.id
robots.robot_code
robots.robot_name
```

Lean:

```text
robots.code
```

이유:

- 로봇은 2대이고 `tb3_1`, `tb3_2`가 안정적인 식별자다.
- 별도 이름은 UI에서 code로 대체 가능하다.

나중에 되돌릴 조건:

- 로봇 수가 늘어난다.
- 표시명/시리얼번호/ROS namespace를 별도로 관리해야 한다.

---

### 3.4 `task_logs` 제거

기존:

```text
tasks
task_logs
```

Lean:

```text
tasks.created_at
tasks.started_at
tasks.finished_at
tasks.status
tasks.error
```

이유:

- 기존 `task_logs`는 `tasks`와 중복되는 컬럼이 많다.
- MVP에서는 task 자체가 완료 상태와 시작/종료 시간을 가져도 충분하다.

나중에 되돌릴 조건:

- 완료 task를 별도 archive/log 테이블로 분리해야 한다.
- task row가 수정되어도 완료 당시 snapshot을 보존해야 한다.
- 감사 목적의 append-only task history가 필요하다.

---

### 3.5 Enum 제거

기존:

```text
robot_status
task_status
command_status
...
```

Lean:

```text
status text
kind text
```

이유:

- 초기 설계와 dbdiagram 이해 목적에서는 enum이 많으면 읽기 복잡하다.
- 실제 구현 초기에 상태값이 바뀔 가능성이 있다.
- 상태값은 애플리케이션 상수 또는 check constraint로 나중에 고정할 수 있다.

나중에 되돌릴 조건:

- 상태값이 안정화된다.
- DB 레벨에서 강한 검증이 필요하다.
- 잘못된 status 문자열이 들어가는 문제가 발생한다.

---

## 4. 쉬운 용어로 바꾼 것

| 기존 용어 | Lean 용어 | 이유 |
| --- | --- | --- |
| `inventory` | `stock` | 재고 수량이라는 의미가 더 짧고 직관적 |
| `evidence_events` | `proofs` | “증거”라는 의미를 짧게 표현 |
| `safety_incidents` | `safety_stops` | 실제 기능이 사람 감지 정지라 더 직접적 |
| `resource_reservations` | `reservations` | resource라는 추상어 제거 |
| `item_change_logs` | `stock_logs` | 재고 변경 로그라는 의미를 간단히 표현 |
| `sequence_no` | `order_no` | 명령 순서라는 의미를 더 쉽게 표현 |
| `required_evidence_type` | `required_proof` | 완료에 필요한 증거를 간단히 표현 |
| `source_location_id` | `from_location_code` | 출발 위치라는 의미가 명확함 |
| `target_location_id` | `to_location_code` | 도착 위치라는 의미가 명확함 |
| `severity` | `level` | 중요도 레벨이라는 의미로 단순화 |
| `trusted_for_policy` | `trusted` | 완료 판단에 사용할 수 있는 증거인지 단순 표현 |

---

## 5. Lean 버전 테이블 구성

```text
state
  robots
  locations
  items
  stock

work
  tasks
  reservations
  commands

proof_and_safety
  proofs
  safety_stops

logs
  stock_logs
```

---

## 6. Lean 버전에서 남긴 핵심 기능

Lean으로 줄여도 아래 기능은 유지된다.

| 기능 | 유지 여부 | 관련 테이블 |
| --- | --- | --- |
| 현재 로봇 상태 | 유지 | `robots` |
| 위치/슬롯/웨이포인트 | 유지 | `locations` |
| 품목별 현재 재고 | 유지 | `items`, `stock` |
| 작업 생성/상태 | 유지 | `tasks` |
| 순차 명령 실행 | 유지 | `commands.order_no` |
| 명령 완료 증거 | 유지 | `commands.required_proof`, `proofs.kind` |
| 사람 감지 안전정지 | 유지 | `proofs`, `safety_stops`, `commands` |
| 자원 선점 | 유지 | `reservations` |
| 재고 변경 이력 | 유지 | `stock_logs` |

---

## 7. Lean 버전에서 약해지는 것

| 약해지는 부분 | 이유 | 대응 |
| --- | --- | --- |
| 표시명 관리 | `name` 계열 컬럼 제거 | code를 표시명으로 사용 |
| 완료 task snapshot | `task_logs` 제거 | tasks의 시작/종료/상태로 시작 |
| DB 레벨 상태 검증 | enum 제거 | 앱 상수 또는 추후 check constraint |
| 상세 하드웨어 매핑 | camera_id/lift_id 제거 | 필요 시 hardware_devices 추가 |
| 개별 파레트 추적 | items+stock 구조 유지 | 필요 시 pallets/inventory_units 추가 |

---

## 8. 추천 판단

처음 구현과 발표용으로는 Lean 버전이 더 낫다.

```text
03_mvp_lean_simple_terms.dbml
```

이유:

1. 테이블/컬럼 수가 줄어 이해하기 쉽다.
2. code 기반 PK라 dbdiagram에서 관계를 따라가기 쉽다.
3. 어려운 용어가 줄었다.
4. 그래도 task-command-proof-safety-stock 흐름은 유지된다.

다만 실제 운영 DB로 굳히기 전에는 아래를 다시 검토하는 것이 좋다.

1. code를 PK로 계속 써도 되는가?
2. task_logs 없이도 완료 이력 요구를 만족하는가?
3. enum/check constraint 없이 상태값 오타를 막을 수 있는가?
4. 파레트 개별 추적이 필요한가?
