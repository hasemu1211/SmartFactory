# 이해시키기 위한 추천 설명법

## 결론

이 스키마는 테이블을 하나씩 설명하는 것보다, 다음 질문에 답하는 순서로 설명하는 것이 가장 이해하기 쉽다.

```text
1. 지금 공장 상태는 어디에 저장되는가?
2. 어떤 일이 발생하면 task가 어떻게 만들어지는가?
3. task는 어떤 command로 실행되는가?
4. command 완료는 무엇으로 증명하는가?
5. 사람 감지 같은 안전 이벤트는 어떻게 끼어드는가?
6. 완료 후 재고와 로그는 어디에 남는가?
```

---

# 1. 5분 설명용 순서

## Step 1 — 한 문장으로 설명

```text
Task가 일을 정의하고, Command가 실행을 요청하며,
Evidence가 완료 근거를 제공하고,
Logs가 결과와 재고 변화를 남긴다.
```

## Step 2 — 네 묶음으로 나누기

```text
physical_state      = 현재 상태
execution           = 해야 할 일과 실행 명령
evidence_and_safety = 완료 근거와 안전정지
logs                = 결과 기록
```

## Step 3 — 전체 요약 ERD 보기

사용 파일:

```text
dbml/00_recommended_overview_simplified.dbml
```

이때 모든 컬럼을 설명하지 말고, 테이블 간 관계만 설명한다.

---

# 2. 15분 설계 리뷰용 순서

## 1장 — 물리 상태

사용 파일:

```text
dbml/01_physical_inventory.dbml
```

핵심 메시지:

```text
robots는 움직이는 주체,
locations는 입고/창고/출고/충전/슬롯/웨이포인트,
items와 inventory는 현재 재고 상태다.
```

## 2장 — 실행 흐름

사용 파일:

```text
dbml/02_task_command_evidence.dbml
```

핵심 메시지:

```text
tasks는 목표,
commands는 실행 단계,
evidence_events는 command 완료 근거다.
```

## 3장 — 안전정지

사용 파일:

```text
dbml/03_safety_stop.dbml
```

핵심 메시지:

```text
HUMAN_DETECTED evidence가 들어오면 safety_incident가 열리고,
STOP command가 생성되며,
HUMAN_CLEAR 이후에만 재개한다.
```

## 4장 — 로그와 재고 변경

사용 파일:

```text
dbml/04_logs_and_inventory_changes.dbml
```

핵심 메시지:

```text
tasks는 현재 상태,
task_logs는 완료 결과,
inventory는 현재 수량,
item_change_logs는 수량 변경 이유다.
```

## 5장 — 전체 시나리오

사용 파일:

```text
dbml/10_end_to_end_flow.dbml
```

핵심 메시지:

```text
예약 -> 명령 -> 증거 -> 재고 반영 -> 로그 기록 순서로 돈다.
```

---

# 3. 실제 구현자에게 강조할 점

## 3.1 API 성공은 완료가 아니다

```text
commands.status = SUCCEEDED
```

만으로 task를 완료하면 안 된다.

```text
commands.required_evidence_type
```

에 해당하는 trusted evidence가 있어야 한다.

---

## 3.2 task_steps는 일부러 없다

MVP에서는 별도 `task_steps`를 만들지 않는다.

대신:

```text
commands.sequence_no
```

가 command 순서를 표현한다.

이렇게 하면 구조가 단순해진다.

---

## 3.3 safety_incidents는 로그가 아니라 현재 열려 있는 안전 상태다

사람 감지는 단순 로그로만 남기면 안 된다.

```text
safety_incidents.status
```

로 현재 안전 사건이 열려 있는지 즉시 조회할 수 있어야 한다.

---

## 3.4 resource_reservations는 충돌 방지용 최소 장치다

복잡한 lock/lease는 아직 없다.

하지만 최소한 다음은 막아야 한다.

```text
두 로봇이 같은 슬롯을 동시에 예약
두 task가 같은 item을 동시에 출고 예약
```

그래서 `resource_reservations`만 둔다.

---

# 4. 추천 산출물 구성

회의나 발표 자료는 다음 4장 정도면 충분하다.

```text
1. 전체 구조 한 장
2. 입고/출고 정상 흐름 한 장
3. 사람 감지 안전정지 흐름 한 장
4. 테이블별 책임 요약 한 장
```

너무 많은 ERD를 한 번에 보여주면 오히려 이해가 떨어진다.
