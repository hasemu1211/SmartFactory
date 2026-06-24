# dbdiagram.io DBML snippets

> **현재 구현 기준은 `mvp/00_mvp_minimal_schema.dbml`입니다.**  
> 아래 00~04 파일은 전체 설계 리뷰/확장 참고용입니다. 첫 구현은 MVP 11개 테이블로 시작하세요.

사용법: <https://dbdiagram.io/d> → **New Diagram** → 원하는 `.dbml` 파일 내용을 그대로 붙여넣기.

추천 확인 순서:

0. `mvp/00_mvp_minimal_schema.dbml` — 실제 첫 구현 기준 MVP 11개 테이블
1. `00_context_overview.dbml` — 전체 책임 경계와 핵심 테이블만 보는 요약도
2. `01_map_robot_inventory.dbml` — 맵/웨이포인트/정밀주차/로봇/센서/재고/팔레트
3. `02_work_command_evidence.dbml` — 작업 상태머신, Nav 명령, 증거, 안전 incident
4. `03_integration_audit_ops.dbml` — API 호출, inbox/outbox, 인증, 운영자 조작, 감사
5. `04_full_simplified.dbml` — 한 화면에 전체 관계를 보려는 compact all-in-one 버전

권장 방식:

- 구현 논의: `mvp/00_mvp_minimal_schema`부터 시작하기. 확장 설계 질문이 나오면 `00_context_overview`와 01~03으로 들어가기.
- ERD가 너무 복잡하면 `04_full_simplified`보다 도메인별 01~03을 따로 보는 것이 더 깔끔함.
- 00~04 DBML은 **확장 시각화용 축약본**이다. 실제 첫 구현 DDL 초안은 `mvp/00_mvp_minimal_schema.generated.sql`을 우선한다.
