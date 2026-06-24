# SmartFactory MVP Recommended — 이해용 가이드 패키지

기준 DBML:

```text
../02_mvp_recommended_with_safety_reservation.dbml
```

이 폴더는 위 MVP 스키마를 처음 보는 사람이 쉽게 이해하도록 만든 설명/시각화 패키지다.

## 추천 읽는 순서

1. `table_relationship_guide.md`
   - 각 테이블이 무엇을 책임지는지
   - 어떤 테이블과 연결되는지
   - 어떤 서버가 주로 쓰는지

2. `column_dictionary.md`
   - 각 테이블 컬럼의 의미
   - 왜 필요한지
   - enum 값과 구현 시 보완 제약

3. `scenario_walkthrough.md`
   - 입고 보관
   - 출고 피킹
   - 사람 감지 안전정지
   - 장애/재시도

4. `dbml/` 안의 분할 DBML을 dbdiagram.io에서 보기
   - 전체를 한 번에 보지 말고, 목적별로 나누어 보는 것이 좋다.

## dbdiagram.io 권장 순서

| 순서 | 파일 | 목적 |
|---:|---|---|
| 0 | `dbml/00_recommended_overview_simplified.dbml` | 전체 구조를 아주 간단히 보기 |
| 1 | `dbml/01_physical_inventory.dbml` | 로봇/위치/재고 상태 이해 |
| 2 | `dbml/02_task_command_evidence.dbml` | 작업 → 명령 → 증거 흐름 이해 |
| 3 | `dbml/03_safety_stop.dbml` | 사람 감지 안전정지 lifecycle 이해 |
| 4 | `dbml/04_logs_and_inventory_changes.dbml` | 완료 로그/재고 변경 로그 이해 |
| 5 | `dbml/10_end_to_end_flow.dbml` | 입고/출고 시나리오 전체 흐름 보기 |

## 핵심 설명 방식

이 스키마는 다음 한 문장으로 설명할 수 있다.

```text
Task가 일을 정의하고, Command가 로봇/Nav에게 실행을 요청하며,
Evidence가 완료 근거를 제공하고, Logs가 결과와 재고 변화를 남긴다.
```
