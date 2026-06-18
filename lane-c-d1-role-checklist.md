# Lane C / Lane D 역할 분담 체크리스트 (2026-06-15)

## 목표
- **이 파일은 구현 없이 설계 이해/운영 협업용입니다.**
- Lane C(ROS Domain Bridge 수동 통합)와 Lane D(성능/튜닝/도킹 정밀) 경계를 정리합니다.

---

## 1) 내가 구현/튜닝해줄 수 있는 항목 (Lane C 중심)

### 1.1 자동으로 진행할 항목
- 토픽/브릿지 정책 설계 정렬
- `source_id` ↔ ROS topic 매핑 정합
- `image/compressed` 우선 아키텍처 제안
- 스트림·overlay·evidence 동기화 메타(시퀀스/타임스탬프) 구조 정리
- `rosbridge` 안전 allowlist 정책 정합
- 브릿지 노출 금지 토픽 제어 (`/cmd_vel`, Nav2 액션, 파라미터 전수 노출 등)
- 실측용 체크 명령 목록과 기준값 계산식 정리

### 1.2 사용자 확인만 필요한 항목(최소 변경)
- 테스트 승인 시간대(로봇/네트워크 점검 가능 창)
- 포트/접속 범위 허용(로컬PC/AI/rosbridge)
- 소스별 임계치(드롭율, 지연, stale 허용치) 한 번만 확정
- 실기 테스트 범위 동의(안전 허용 범위)

### 1.3 보안/운영 체크
- 비밀정보는 파일/문서에 평문 저장 X (운영 메모는 분리)
- Lane C 단계에서는 모션/제어 토픽을 절대 발행하지 않음
- `vision`/`camera` evidence는 판단 근거로만 사용, Main/Movement가 최종 결정

---

## 2) Lane C에서 허용되는 로봇 측 일시 실행 요소

- 기본 원칙: **로봇 영구 설정 변경 없음**
- 허용된 로봇 측 동작은 기존 SSH 세션에서의 **일시 camera launch**와 read-only topic 확인뿐입니다.
  - `QT_QPA_PLATFORM=offscreen ros2 launch turtlebot3_bringup camera.launch.py`
  - `ros2 topic list/info/hz`
- 실행 시 인자로 주입되는 항목만 반영됨 (실행 중단/재실행으로 되돌리기 가능)
  - `source`별 snapshot/bridge 토픽(실험용) 여부
  - 스냅샷/POST 주기, 타임아웃
  - 압축전송 사용 여부(권장: compressed)
  - AI 전송 endpoint 주소
- 기존 카메라 브링업 런치 파일/패키지/캘리브레이션/systemd/ROS_DOMAIN_ID는 수정하지 않음

### 2.1 Lane C 금지 항목

- package 설치, launch 파일 수정, systemd/autostart 변경
- `.bashrc`, `ROS_DOMAIN_ID`, 네트워크, calibration 파일 영구 변경
- `/cmd_vel` publish, Nav2 action 호출, teleop 실행
- 전체 ROS graph를 generic rosbridge/domain bridge로 노출
- 기존 robot bringup 재시작 또는 중단

---

## 3) 사용자가 직접 준비해야 하는 항목(필수 아님, Lane D 성격이 큼)

### 3.1 Lane D에서 필요한 것으로 분류
- ArUco 마커 보드/샘플 이미지 새로 준비
- AI 학습/가중치 모델 선정/교체
- 카메라 캘리브레이션 재측정
- 실제 도킹 정밀도 튜닝(거리/오프셋/게인)

### 3.2 결론
- **“아루코 그림 들고 있어야 한다”나 “학습 데이터가 필요하다”는 요청은 주로 Lane D 성격**입니다.
- Lane C 자체는 `학습`/`표식 제조`가 기본 아웃오브스코프입니다.

---

## 4) 지금 당장 정리해야 할 질문(예/아니오로 빠르게)

1. 실기 검증(예/아니오): Robot1 우선 / Robot2 순차
2. 브릿지 allowlist 정책 확정(예: `/sf/vision/*` 허용, motion topic 비노출)
3. Lane C 테스트 임계치: 허용 지연, 허용 drop, stale 기준
4. Camera API 포인트: 8090 반영 동의 여부
5. /mission(레거시)와 /sf(신규) 동시 유지 기간 동의

---

## 5) 한 줄 요약
- **Lane C:** 내가 구조/테스트 자동화/파라미터 템플릿/운영설정 정합 담당
- **Lane D:** 사용자 보유 데이터, 마커/보드, 정밀 튜닝치, 학습/보정 데이터가 필요한 영역

