# SmartFactory MVP DB design

이 폴더의 현재 최신 기준은 `04_mvp_refined_practical.dbml`이다.

`04`는 다음 사용자 피드백을 반영한 실무형 MVP 스키마다.

- 모든 주요 참조를 `*_id`로 통일
- `items`는 MVP에서 `id` 하나로 단순화
- `robots.domain_id` 추가
- `tasks.task_type`에 `CHARGING` 포함
- `PICK_UP` = ArUco 정밀 접근 + lift up + 수령 확인
- `DROP_OFF` = ArUco 정밀 접근 + lift down + 배치 확인
- `commands.request_json/response_json`으로 실제 API 요청/응답 스냅샷 저장
- `task_logs` 포함: 완료/실패/취소 task의 최종 결과 스냅샷 저장

## 주요 파일

| 파일 | 용도 |
| --- | --- |
| `04_mvp_refined_practical.dbml` | 현재 최신 추천 DBML |
| `04_mvp_refined_practical.generated.sql` | DBML에서 생성한 PostgreSQL DDL 초안 |
| `04_mvp_refined_practical_column_dictionary.md` | 최신 열 사전 |
| `confluence_replacement_dbml/` | Confluence 그림 교체용 분할 DBML |

## MVP 버전 선택

| 파일 | 추천 상황 |
| --- | --- |
| `01_mvp_minimal_no_safety_reservation.dbml` | 정말 최소 구현. 안전정지/예약 없이 시작 |
| `02_mvp_recommended_with_safety_reservation.dbml` | 증거 기반 완료 + 안전정지 + 예약 포함 원안 |
| `03_mvp_lean_simple_terms.dbml` | 더 쉬운 용어/최소 컬럼 실험안 |
| `04_mvp_refined_practical.dbml` | 현재 최신 추천. 실무형 최소안 |

## 04 핵심 테이블

| 그룹 | 테이블 | 책임 |
| --- | --- | --- |
| State | `locations`, `robots`, `items`, `inventory` | 현재 위치/로봇/품목/재고 상태 |
| Work | `tasks`, `reservations`, `commands` | 작업 정의, 예약, 명령 실행 |
| Evidence & Safety | `evidence_events`, `safety_stops` | 완료 증거, 안전정지 lifecycle |
| Logs | `task_logs`, `item_change_logs` | 작업 결과 스냅샷, 재고 변경 이력 |

## 04 스키마 요약

```text
테이블: 11개
컬럼: 105개
관계: 29개
```

테이블 목록:

1. `locations`
2. `robots`
3. `items`
4. `inventory`
5. `tasks`
6. `reservations`
7. `commands`
8. `evidence_events`
9. `safety_stops`
10. `task_logs`
11. `item_change_logs`

## dbdiagram.io 사용법

전체 구조를 한 번에 보려면:

1. <https://dbdiagram.io/d> 접속
2. New Diagram
3. `04_mvp_refined_practical.dbml` 전체 붙여넣기

Confluence에 보기 좋게 나눠 넣으려면:

1. `confluence_replacement_dbml/00_recommended_overview_simplified.dbml`
2. `confluence_replacement_dbml/01_physical_inventory.dbml`
3. `confluence_replacement_dbml/02_task_command_evidence.dbml`
4. `confluence_replacement_dbml/03_safety_stop.dbml`
5. `confluence_replacement_dbml/04_logs_and_inventory_changes.dbml`
6. `confluence_replacement_dbml/10_end_to_end_flow.dbml`

순서대로 캡처해서 Confluence `DB-` 페이지의 지정 위치에 삽입한다.
