# Scenario 20 — 출고 피킹 흐름

## 목적

창고 슬롯에 보관된 특정 파레트를 로봇이 픽업해서 출고 위치로 이동시키고, 출고 완료 증거를 기반으로 재고를 출고 상태로 확정하는 흐름이다.

## 핵심 차이점

입고 흐름과 반대로, 출고는 `storage_slots.status = OCCUPIED` 상태에서 시작한다. Main은 파레트와 슬롯을 먼저 예약하고, 로봇이 슬롯으로 이동하여 파레트를 들어 올린 뒤 출고 지점에 내려놓는다.

## 핵심 테이블

| 테이블 | 역할 |
|---|---|
| `work_orders` | 출고 요청 |
| `tasks` | `PICK_PALLET` 실행 단위 |
| `pallets` | 출고 대상 파레트 |
| `storage_slots` | 출고 대상 파레트가 있던 슬롯 |
| `reservations` | 파레트/슬롯/로봇/출고 lane 예약 |
| `command_requests` | Nav/lift 실행 명령 |
| `evidence_events` | 슬롯 점유, lift load, 출고 drop 확인 |
| `inventory_transactions` | `RESERVE`, `PICK`, `SHIP`, `VERIFY` 이력 |

## 정상 흐름

```text
1. 출고 요청 생성
   work_orders.order_type = OUTBOUND_PICK

2. Main이 출고 대상 파레트 조회
   part_catalog.part_no 기준으로 pallets 탐색
   pallets.status = STORED
   pallets.current_slot_id 존재

3. Main이 task 생성
   tasks.task_type = PICK_PALLET
   tasks.source_slot_id = 파레트가 있는 슬롯
   tasks.target_waypoint_id = 출고 drop 지점

4. 예약 처리
   reservations: PALLET, SLOT, ROBOT, OUTBOUND_LANE
   pallets.status = RESERVED_OUTBOUND
   storage_slots.status = RESERVED

5. 슬롯 접근 이동
   command_requests.command_type = NAV_GOAL
   evidence_events.evidence_type = NAV_GOAL_REACHED

6. 슬롯 정밀주차
   command_requests.command_type = DOCK_ARUCO
   evidence_events.evidence_type = SLOT_OCCUPIED_CONFIRMED

7. 파레트 들어올림
   command_requests.command_type = LIFT_UP
   evidence_events.evidence_type = LIFT_LOAD_DETECTED
   pallets.current_robot_id = robots.id
   pallets.current_slot_id = null
   pallets.status = ON_ROBOT
   storage_slots.status = EMPTY

8. 출고 위치로 이동
   command_requests.command_type = NAV_GOAL
   evidence_events.evidence_type = NAV_GOAL_REACHED

9. 출고 위치에 내려놓기
   command_requests.command_type = LIFT_DOWN
   evidence_events.evidence_type = OUTBOUND_DROP_CONFIRMED

10. 재고 출고 확정
    pallets.status = OUTBOUND 또는 SHIPPED
    inventory_transactions.transaction_type = SHIP

11. 모든 변경을 state_transitions에 기록
```

## 완료 조건

- 출고 대상 파레트가 정확히 식별되어야 한다.
- 출고 전 파레트가 원래 슬롯에 있었다는 증거가 필요하다.
- 리프트 상승 후 load 감지가 필요하다.
- 출고 위치에서 drop 완료 증거가 필요하다.
- 최종 재고 트랜잭션이 기록되어야 한다.

## 실패/예외 분기

| 상황 | 처리 |
|---|---|
| 요청 부품 재고 없음 | work_order를 `BLOCKED` 또는 `FAILED` 처리 |
| 파레트가 슬롯에 없음 | `VERIFY_SLOT` 또는 수동 확인으로 전환 |
| 리프트 load 감지 실패 | 재시도 후 `MANUAL_REVIEW` |
| 출고 지점 막힘 | 다른 outbound waypoint 선택 또는 대기 |
| 주행 중 사람 감지 | Scenario 40 안전정지 흐름으로 인터럽트 |

## dbdiagram에서 볼 포인트

- `tasks.source_slot_id`와 `target_waypoint_id`가 출고 흐름의 핵심이다.
- `pallets.status`가 `STORED → RESERVED_OUTBOUND → ON_ROBOT → OUTBOUND/SHIPPED`로 바뀐다.
- `inventory_transactions`가 실제 재고 이력을 보존한다.
