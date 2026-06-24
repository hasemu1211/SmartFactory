# Scenario 60 — 장애/타임아웃/수동복구 흐름

## 목적

Nav/API timeout, 낮은 신뢰도의 증거, 충돌하는 증거, 로봇 heartbeat stale, inbox/outbox dead letter 같은 운영 장애가 발생했을 때 Main이 재시도/복구/수동개입으로 안전하게 전환하는 흐름이다.

## 왜 필요한가

로봇 시스템은 정상 흐름보다 예외 흐름이 더 중요하다. API 호출 실패, 센서 미검출, Nav 응답 지연, 사람이 끼어드는 상황이 반드시 발생한다. 이때 DB에 근거를 남기지 않으면 “왜 멈췄는지”, “재시도해도 되는지”, “재고가 맞는지”를 판단하기 어렵다.

## 핵심 테이블

| 테이블 | 역할 |
|---|---|
| `command_requests` | 명령 상태, 재시도 번호, deadline, supersede 관리 |
| `command_events` | 명령 진행 이벤트 |
| `api_call_logs` | API 요청/응답/오류 기록 |
| `inbox_events` | 외부 이벤트 수신 큐 |
| `outbox_events` | 외부로 보낼 이벤트 큐 |
| `dead_letter_events` | 반복 실패한 이벤트 격리 |
| `evidence_events` | 실패/충돌/낮은 신뢰도 증거 |
| `operator_actions` | 작업자 수동 확인/취소/재시도 승인 |
| `manual_control_sessions` | 수동 조작 세션과 복귀 reconciliation |
| `decision_snapshots` | 재시도/수동검토/복구계획 판단 |
| `state_transitions` | 모든 상태 변경 감사 로그 |

## 장애 발생 흐름 예시

```text
1. Main이 Nav 명령 생성
   command_requests.status = SENT
   deadline_at 설정

2. API 호출 기록
   api_call_logs.started_at 저장
   response_status 또는 error_code 저장

3. deadline 초과
   command_requests.status = TIMEOUT
   task_steps.status = RETRY_WAIT 또는 BLOCKED

4. Main이 retry 정책 평가
   decision_snapshots.decision_type = RETRY_DECISION

5-A. 재시도 가능
   command_requests.attempt_no 증가
   새 idempotency_key 또는 같은 idempotency_key 정책 적용
   task_steps.status = COMMAND_SENT

5-B. 재시도 불가
   task_steps.status = MANUAL_REVIEW
   tasks.status = MANUAL_REVIEW

6. 운영자 개입
   operator_actions.action_type = MANUAL_CONFIRM 또는 RETRY_TASK 또는 CANCEL_TASK

7. 수동 조작 필요 시
   manual_control_sessions.status = ACTIVE
   robot.status = OPERATOR_PAUSED

8. 수동 조작 종료 후 reconciliation
   실제 robot pose, lift state, pallet/slot 상태 확인
   manual_control_sessions.status = RECONCILING → CLOSED

9. Main이 복구 task 생성 또는 기존 task 재개
   tasks.parent_task_id로 원래 task와 연결 가능

10. 모든 전이를 state_transitions에 기록
```

## inbox/outbox 장애 흐름

```text
1. AI/Nav/Robot 이벤트 수신
   inbox_events.processing_status = PENDING

2. 처리 성공
   inbox_events.processing_status = PROCESSED

3. 처리 실패
   retry_count 증가
   next_attempt_at 설정

4. max_attempts 초과
   inbox_events.processing_status = DEAD_LETTERED
   dead_letter_events 생성

5. 운영자 또는 batch job이 해결
   dead_letter_events.resolved_at 기록
```

## 완료 조건

장애 복구는 다음 중 하나로 명확히 끝나야 한다.

- 재시도 성공 후 원래 step이 `SUCCEEDED`
- 복구 task가 생성되어 원래 task가 `BLOCKED/RECOVERY`로 정리됨
- 운영자가 수동 확인 후 `MANUAL_REVIEW → READY/RUNNING`으로 복귀
- 운영자가 취소하여 task가 `FAILED/CANCELLED`
- dead letter가 해결 또는 영구 보류로 분류됨

## 실패/예외 분기

| 상황 | 처리 |
|---|---|
| Nav API timeout 반복 | command failed, recovery task 생성 |
| evidence confidence 낮음 | 추가 증거 요청 또는 manual review |
| AI와 Nav 증거 충돌 | conflicting evidence로 보류 |
| Robot heartbeat stale | robot.status = STALE/OFFLINE, 안전정지 |
| 수동조작 후 DB와 현실 불일치 | reconciliation snapshot 저장 후 재고/위치 보정 |

## dbdiagram에서 볼 포인트

- `api_call_logs`는 HTTP/API 레벨의 사실 기록이다.
- `command_requests`는 시스템 명령 상태다.
- `evidence_events`는 판단 근거다.
- `decision_snapshots`는 왜 retry/manual/recovery가 선택됐는지 남긴다.
- `manual_control_sessions`는 사람이 로봇을 건드린 기간을 시스템 상태와 분리해준다.
