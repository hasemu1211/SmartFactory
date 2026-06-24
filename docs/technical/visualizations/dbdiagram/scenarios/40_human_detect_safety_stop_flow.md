# Scenario 40 — 사람 감지 안전정지/재개 흐름

## 목적

로봇 주행 중 AI Server가 사람을 감지하면, Main이 즉시 안전 incident를 열고 Nav Server에 STOP/PAUSE 명령을 보내며, 정지 확인과 재개 허가를 증거 기반으로 관리한다.

## 중요한 설계 원칙

안전정지는 일반 task 흐름보다 우선한다. 즉, `MOVE` step이 실행 중이어도 사람 감지 증거가 들어오면 현재 작업은 `SAFETY_PAUSED` 또는 `EMERGENCY_STOPPED`로 인터럽트되어야 한다.

## 핵심 테이블

| 테이블 | 역할 |
|---|---|
| `evidence_sources` | 사람 감지 증거를 제출한 카메라/AI source |
| `evidence_artifacts` | 이미지/영상/JSON 증거 원본 또는 URI |
| `evidence_events` | `HUMAN_DETECTED`, `HUMAN_CLEAR`, `STOP_ACKED` 등 |
| `safety_incidents` | 안전 사건의 생명주기 |
| `command_requests` | Nav에 보내는 `STOP`, `PAUSE`, `RESUME` 명령 |
| `command_events` | Nav의 정지 수락/정지 완료/재개 결과 |
| `operator_actions` | 작업자 확인/재개 승인 |
| `decision_snapshots` | Main의 안전정지/재개 판단 근거 |
| `state_transitions` | 로봇/task/step/incident 상태 전이 기록 |

## 정상 안전정지 흐름

```text
1. 로봇이 이동 중
   robots.status = MOVING
   task_steps.status = EXECUTING

2. AI Server가 사람 감지
   evidence_events.evidence_type = HUMAN_DETECTED
   severity = SAFETY_CRITICAL
   artifact_ref_id = 증거 이미지/영상

3. Main이 safety incident 생성
   safety_incidents.incident_type = HUMAN_DETECTED
   safety_incidents.status = OPEN
   triggering_evidence_id = HUMAN_DETECTED evidence

4. Main이 즉시 STOP/PAUSE 명령 생성
   command_requests.command_type = STOP 또는 PAUSE
   target_system = NAV_SERVER
   idempotency_key로 중복 STOP 방지

5. Nav가 정지 처리
   command_events.event_type = ACCEPTED → STOPPED

6. Main이 상태 전이
   robots.status = SAFETY_PAUSED 또는 EMERGENCY_STOPPED
   tasks.status = SAFETY_PAUSED
   task_steps.status = SAFETY_PAUSED
   safety_incidents.status = STOP_ACKED

7. 안전 clear 증거 대기
   evidence_events.evidence_type = HUMAN_CLEAR
   trusted_for_policy = true

8. 작업자 또는 정책이 재개 승인
   operator_actions.action_type = AUTHORIZE_RESUME
   decision_snapshots.decision_type = RESUME_GATE

9. Main이 RESUME 명령 생성
   command_requests.command_type = RESUME

10. Nav가 재개
    command_events.event_type = RESUMED
    incident closed
    task_step 상태를 READY 또는 EXECUTING으로 복귀
```

## 완료 조건

안전정지는 “STOP 명령을 보냈다”가 아니라 다음까지 확인되어야 완료된다.

- 사람 감지 증거 저장
- safety incident 생성
- STOP/PAUSE command 생성
- Nav의 정지 ACK 또는 STOPPED event 수신
- robot/task/step 상태가 안전 상태로 전이
- state transition에 근거 기록

재개는 다음 조건을 만족해야 한다.

- clear evidence가 freshness window 안에 있음
- operator 또는 정책이 재개 승인
- 기존 command fencing token과 충돌하지 않음
- Nav가 RESUME을 수락

## 실패/예외 분기

| 상황 | 처리 |
|---|---|
| STOP 명령 응답 없음 | 재전송, 더 높은 단계의 emergency stop 상태로 전환 |
| AI source stale | trusted_for_safety=false 처리, 수동 확인 요구 |
| clear evidence 없음 | 계속 `SAFETY_PAUSED` 유지 |
| 사람이 다시 감지됨 | incident 유지, RESUME 금지 |
| 운영자 승인 없이 재개 요청 | `api_auth_audit` 또는 operator policy에서 DENY |

## dbdiagram에서 볼 포인트

- `evidence_events → safety_incidents → command_requests`가 안전정지의 핵심 흐름이다.
- `safety_incident_events`는 incident 내부 타임라인이다.
- `operator_actions`는 사람이 개입한 근거를 남긴다.
