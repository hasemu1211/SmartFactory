# SmartFactory MVP Recommended Schema

이 버전은 사용자가 준 단순 스키마를 유지하면서, 실제 스마트팩토리 상태머신에 필요한 최소 보완만 추가한 버전이다.

## 추가/변경된 점

1. `camera_events` 대신 `evidence_events` 사용
   - 카메라뿐 아니라 Nav, Robot, Operator도 증거를 만들 수 있기 때문.
2. `safety_incidents` 추가
   - `HUMAN_DETECTED → STOP_SENT → STOPPED → HUMAN_CLEAR → CLOSED` 흐름 추적.
3. `resource_reservations` 추가
   - 로봇 2대, 슬롯/위치, 재고 동시 예약 충돌 방지.
4. `commands.sequence_no` 추가
   - `task_steps` 없이 command가 가벼운 step 순서 역할을 함.
5. `commands.required_evidence_type` 추가
   - 명령 완료를 API 응답만으로 판단하지 않고 필요한 증거와 연결.

## 테이블 구성

```text
physical_state
  robots
  locations
  items
  inventory

execution
  tasks
  commands
  resource_reservations

evidence_and_safety
  evidence_events
  safety_incidents

logs
  task_logs
  item_change_logs
```

## 구현 흐름 예시

```text
1. tasks 생성
2. resource_reservations로 robot/location/item 예약
3. commands를 sequence_no 순서로 생성 또는 실행
4. Nav/API 호출 결과로 commands.status 갱신
5. AI/Nav/Robot이 evidence_events 제출
6. commands.required_evidence_type 충족 시 다음 command 진행
7. HUMAN_DETECTED evidence가 들어오면 safety_incidents 생성 + STOP command 생성
8. 완료 시 inventory, task_logs, item_change_logs 갱신
```

## 의도적으로 넣지 않은 것

- `task_steps`: MVP에서는 `commands.sequence_no`로 대체.
- `camera_events`: `evidence_events`로 흡수.
- `api_call_logs`: MVP에서는 `commands.request_json/response_json`과 `task_logs`로 충분.
- `event_log`: 지금 버전은 `task_logs`, `item_change_logs`, `evidence_events`로 목적별 로그를 유지.
