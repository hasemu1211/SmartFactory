# Scenario 10 — 입고 파레트 보관 흐름

## 목적

입고 지역에 들어온 파레트를 로봇이 들어 올리고, 창고 슬롯까지 이동한 뒤, ArUco 정밀주차와 증거 검증을 거쳐 재고 상태를 `STORED`로 확정하는 흐름이다.

## 주요 참여자

- **Main Server**: 작업 생성, step 상태 전이, 증거 검증, 재고 확정
- **Nav Server**: 주행, ArUco docking, lift up/down 실행
- **AI Server**: 글로벌캠/PiCamera 기반 파레트/슬롯/마커 증거 제출
- **Robot**: bringup 상태에서 Nav 명령을 실행하는 하드웨어 endpoint

## 핵심 테이블

| 테이블 | 역할 |
|---|---|
| `work_orders` | 입고 보관 요청의 상위 업무 단위 |
| `tasks` | 로봇에게 할당 가능한 `STORE_PALLET` 작업 |
| `task_steps` | MOVE/DOCK/LIFT/VERIFY/COMMIT 등 순차 실행 단위 |
| `reservations` | 로봇, 슬롯, 파레트 선점 |
| `command_requests` | Main이 Nav에 보내는 실행 명령 |
| `command_events` | Nav가 명령 진행/완료/실패를 보고하는 이벤트 |
| `evidence_events` | AI/Nav/Robot이 제출한 완료 판단 근거 |
| `decision_snapshots` | Main이 증거를 보고 판단한 결과 스냅샷 |
| `inventory_transactions` | 재고 변경 이력 |
| `state_transitions` | 상태 변경 감사 로그 |

## 정상 흐름

```text
1. 입고 요청 생성
   work_orders.order_type = INBOUND_STORE

2. Main이 task 생성
   tasks.task_type = STORE_PALLET
   tasks.status = READY

3. Main이 step 생성
   MOVE_TO_INBOUND
   DOCK_PALLET
   LIFT_UP
   MOVE_TO_SLOT
   DOCK_SLOT
   LIFT_DOWN
   VERIFY_SLOT
   COMMIT_INVENTORY

4. Main이 자원 예약
   reservations: ROBOT, PALLET, SLOT
   storage_slots.status = RESERVED
   pallets.status = RESERVED_STORE

5. MOVE_TO_INBOUND step 실행
   command_requests.command_type = NAV_GOAL
   Nav Server가 로봇 이동 수행

6. 도착 증거 수집
   evidence_events.evidence_type = NAV_GOAL_REACHED
   task_steps.status = SUCCEEDED

7. 파레트 정밀 접근
   command_requests.command_type = DOCK_ARUCO
   evidence_events.evidence_type = ARUCO_MARKER_DETECTED

8. 리프트 상승
   command_requests.command_type = LIFT_UP
   evidence_events.evidence_type = LIFT_LOAD_DETECTED
   pallets.current_robot_id = robots.id
   pallets.status = ON_ROBOT

9. 창고 슬롯 접근 및 정밀주차
   NAV_GOAL → DOCK_ARUCO
   evidence: DOCKING_POSE_STABLE, SLOT_EMPTY_CONFIRMED

10. 리프트 하강 및 배치 검증
    command_requests.command_type = LIFT_DOWN
    evidence_events.evidence_type = SLOT_OCCUPIED_CONFIRMED

11. Main이 증거 정책 평가
    decision_snapshots.decision_type = INVENTORY_COMMIT

12. 재고 확정
    pallets.current_slot_id = storage_slots.id
    pallets.current_robot_id = null
    pallets.status = STORED
    storage_slots.status = OCCUPIED
    inventory_transactions.transaction_type = STORE

13. 상태 전이 기록
    state_transitions에 task/step/robot/slot/pallet 변경 이유와 근거 저장
```

## 완료 조건

단순히 Nav API가 성공했다고 끝내지 않는다. 최소한 다음 증거가 필요하다.

- 로봇이 목표 지점에 도착했다는 Nav 증거
- ArUco marker가 인식되었다는 정밀주차 증거
- 리프트에 파레트가 올라갔다는 load 증거
- 목표 슬롯이 비어있었고, 하강 후 점유되었다는 AI/센서 증거
- Main의 evidence policy 평가 결과

## 실패/예외 분기

| 상황 | 처리 |
|---|---|
| 슬롯이 이미 점유됨 | task step을 `BLOCKED` 또는 `MANUAL_REVIEW`로 전환 |
| ArUco 인식 실패 | `DOCK_ARUCO` retry 후 실패 시 복구 task 생성 |
| 리프트 load 미감지 | `LIFT_UP` 실패, 사람이 확인 필요 |
| AI 증거 confidence 낮음 | `WAITING_EVIDENCE` 유지 또는 추가 촬영 요청 |
| Nav timeout | `command_requests.status = TIMEOUT`, 재시도/복구 흐름으로 이동 |

## dbdiagram에서 볼 포인트

- `work_orders → tasks → task_steps`가 작업 상태머신의 뼈대다.
- `task_steps → command_requests → command_events`가 실행 명령 흐름이다.
- `task_steps → evidence_events → decision_snapshots`가 증거 기반 완료 판단 흐름이다.
- `pallets/storage_slots/inventory_transactions`가 최종 재고 반영 흐름이다.
