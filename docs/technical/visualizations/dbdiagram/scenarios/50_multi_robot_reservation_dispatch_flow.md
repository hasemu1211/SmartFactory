# Scenario 50 — 2대 로봇 예약/할당/충돌 방지 흐름

## 목적

로봇이 2대 이상일 때 Main Scheduler가 어떤 로봇을 어떤 작업에 배정할지 결정하고, 슬롯/파레트/구역/경로 자원을 예약해서 충돌을 줄이는 흐름이다.

## 왜 필요한가

단순히 `tasks.robot_id`만 넣으면 다음 문제가 생긴다.

- 두 로봇이 같은 슬롯에 접근할 수 있음
- 같은 좁은 aisle에 동시에 진입할 수 있음
- 한 로봇이 집으려던 파레트를 다른 작업이 예약할 수 있음
- scheduler가 중복 실행될 때 같은 step을 두 번 실행할 수 있음

그래서 `reservations`, `resource_locks`, `scheduler_leases`가 필요하다.

## 핵심 테이블

| 테이블 | 역할 |
|---|---|
| `robots` | 로봇 현재 상태와 배터리/heartbeat |
| `robot_capabilities` | 로봇별 기능 차이 |
| `robot_state_samples` | 최근 pose, battery, lift/nav 상태 샘플 |
| `waypoint_edges` | 이동 가능한 경로와 corridor 정책 |
| `reservations` | 장기적 선점: robot, pallet, slot, zone |
| `resource_locks` | 짧은 실행 중 lock: aisle, edge, docking zone |
| `scheduler_leases` | scheduler 중복 실행 방지용 step lease |
| `command_requests` | 실제 Nav 명령 |
| `state_transitions` | 예약/락/할당 이력 |

## 정상 흐름

```text
1. Main Scheduler가 READY task 조회
   tasks.status = READY

2. 후보 로봇 조회
   robots.status = IDLE
   battery_level 충분
   last_heartbeat_at 최신
   robot_capabilities에 필요한 기능 있음

3. 후보 경로/자원 확인
   target slot, pallet, waypoint_edges, map_zones 확인
   이미 ACTIVE reservation이나 lock이 있는지 확인

4. 로봇 선택
   거리, 배터리, 우선순위, capability, 현재 위치 기준으로 점수 계산

5. reservation 생성
   reservations: ROBOT, PALLET, SLOT, ZONE
   tasks.assigned_robot_id = 선택된 robot
   robots.status = RESERVED

6. 다음 step lease 획득
   scheduler_leases.step_id = 실행할 step
   lease_token 발급
   이 lease를 가진 scheduler만 command 생성 가능

7. 실행 직전 resource lock 생성
   resource_locks: WAYPOINT_EDGE, ZONE, DOCKING_MARKER 등
   좁은 통로/정밀주차 zone 중복 진입 방지

8. command 생성
   command_requests.fencing_token = lease_token 또는 별도 token
   Nav에 명령 전송

9. step 완료 시 lock 해제
   resource_locks.lock_status = RELEASED

10. task 완료 시 reservation 해제
    reservations.status = RELEASED
    robot.status = IDLE
```

## 완료 조건

- 한 task의 실행 step은 하나의 active lease만 가져야 한다.
- 하나의 로봇은 동시에 하나의 active task만 수행해야 한다.
- 하나의 슬롯/파레트는 동시에 하나의 active reservation만 가져야 한다.
- 좁은 waypoint edge나 docking zone은 lock 정책에 따라 동시 진입을 제한해야 한다.

## 실패/예외 분기

| 상황 | 처리 |
|---|---|
| 로봇 heartbeat stale | 후보에서 제외, robot.status = STALE |
| 배터리 부족 | 충전 task 우선 생성 또는 후보 제외 |
| slot reservation 충돌 | 다른 slot 선택 또는 task BLOCKED |
| scheduler lease 만료 | 다른 scheduler가 takeover 가능 |
| lock 해제 누락 | expires_at 기반 자동 만료 + 감사 로그 |

## dbdiagram에서 볼 포인트

- `reservations`는 “작업 전체 기간 동안 선점”이다.
- `resource_locks`는 “특정 step 실행 중 잠깐 잠금”이다.
- `scheduler_leases`는 “중복 scheduler 실행 방지”다.
- 이 셋을 분리해야 데드락/중복명령/자원경합을 줄일 수 있다.
