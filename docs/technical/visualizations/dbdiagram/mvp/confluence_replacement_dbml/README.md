# Confluence 교체용 DBML 세트

기준: `../04_mvp_refined_practical.dbml`

아래 파일을 각각 <https://dbdiagram.io/d>에 붙여넣고 PNG/SVG로 캡처해서 Confluence `DB-` 페이지의 지정 위치에 삽입하면 된다.

## 권장 교체 순서

1. `00_recommended_overview_simplified.dbml` — 전체 구조 요약
2. `01_physical_inventory.dbml` — 로봇, 위치, 품목, 재고, 예약
3. `02_task_command_evidence.dbml` — 작업 → 명령 → 증거 → task 결과 로그
4. `03_safety_stop.dbml` — 사람 감지 → STOP → CLEAR → RESUME
5. `04_logs_and_inventory_changes.dbml` — 작업 결과 로그, 재고 변경 로그
6. `10_end_to_end_flow.dbml` — 입고/출고 전체 흐름

## 04 기준 반영 사항

- `safety_stops` 사용
- `reservations` 사용
- `from_location_id/to_location_id` 사용
- `items`는 `id`만 유지
- `robots.domain_id` 추가
- `tasks.task_type`에 `CHARGING` 포함
- `PICK_UP`은 ArUco 정밀 접근 + lift up + 수령 증거까지의 과정
- `DROP_OFF`은 ArUco 정밀 접근 + lift down + 배치 증거까지의 과정
- `command_payload_json`은 사용하지 않음
- 실제 API 호출 스냅샷은 `commands.request_json`, 응답은 `commands.response_json`에 저장
- `task_logs` 포함: 완료/실패/취소 task의 최종 결과와 evidence/query 요약 스냅샷 저장
- 재고 수량 변경 이력은 `item_change_logs`에 저장
