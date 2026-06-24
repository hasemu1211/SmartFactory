# SmartFactory scenario DBML pack

> **주의: 이 폴더는 확장 설명용입니다. 실제 첫 구현 기준은 `../mvp/00_mvp_minimal_schema.dbml`입니다.**  
> 기능 중복을 줄인 MVP에서는 로그성 테이블을 `event_log`로, 위치/슬롯/웨이포인트를 `locations`로 통합했습니다.

이 폴더는 `dbdiagram.io/d`에서 보기 쉽게 **시나리오별로 쪼갠 DBML + 흐름 설명문**이다.

사용법:

1. <https://dbdiagram.io/d> 접속
2. **New Diagram** 생성
3. 보고 싶은 `.dbml` 파일 내용을 왼쪽 DBML 편집기에 붙여넣기
4. 같은 번호의 `.md` 설명문을 보면서 흐름 추적

## 파일 목록

| 번호 | 시나리오 | DBML | 설명문 |
|---:|---|---|---|
| 10 | 입고 파레트 보관 | `10_inbound_store_flow.dbml` | `10_inbound_store_flow.md` |
| 20 | 출고 피킹 | `20_outbound_pick_flow.dbml` | `20_outbound_pick_flow.md` |
| 30 | ArUco 정밀주차/슬롯 검증 | `30_precision_docking_slot_verify_flow.dbml` | `30_precision_docking_slot_verify_flow.md` |
| 40 | 사람 감지 안전정지/재개 | `40_human_detect_safety_stop_flow.dbml` | `40_human_detect_safety_stop_flow.md` |
| 50 | 2대 로봇 예약/할당/충돌 방지 | `50_multi_robot_reservation_dispatch_flow.dbml` | `50_multi_robot_reservation_dispatch_flow.md` |
| 60 | 장애/타임아웃/수동복구 | `60_failure_recovery_manual_flow.dbml` | `60_failure_recovery_manual_flow.md` |
| 70 | 하드웨어/상태제어/로그/인터페이스 구분 | `70_layered_elements_interfaces.dbml` | `70_layered_elements_interfaces.md` |

## 읽는 추천 순서

1. 처음 설계 설명: `10 → 20 → 40`
2. 로봇 제어/정밀주차 설명: `30`
3. 스케줄러/멀티로봇 설명: `50`
4. 운영 안정성/디버깅 설명: `60`
5. 계층/인터페이스 설명: `70`

## 설계 원칙 요약

- Main Server는 DB 상태머신과 정책 판단을 담당한다.
- Nav Server는 주행/정밀주차/리프트 명령 실행을 담당한다.
- AI Server는 글로벌캠/PiCamera 기반 증거를 생성한다.
- Robot은 bringup, 센서, 리프트, 주행 실행 endpoint로 둔다.
- MVP에서는 작업 완료를 API 응답만으로 확정하지 않고 `evidence_events`로 확인한다.
- MVP에서는 모든 상태 변경/API/작업자/오류/재고 이력을 `event_log`에 남긴다.
