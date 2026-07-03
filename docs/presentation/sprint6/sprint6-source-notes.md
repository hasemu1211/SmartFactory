# Sprint 6 발표 메모 — AI/Vision 쪽 이번 주 성과

## 한 줄 요약

이번 주에는 “카메라 영상을 보는 것”에서 끝나지 않고, Main이 실제로 호출할 수 있는 **안전/감시용 Vision API 구조**와 **현장 튜닝 가능한 Global Cam ROI**를 만들고 검증했다.

## 1. 주행 중 PiCam 사람 감지 API

- 로봇 Pi 카메라(`tb3_1_picam`, `tb3_2_picam`)에서 `person`을 감지한다.
- Main은 로봇이 `DRIVE`일 때만 monitor를 켠다.
- AI Server는 정지 명령을 직접 내리지 않고, `ADVISORY / HUMAN_DETECTED`만 반환한다.
- 최종 HOLD/E-stop, cooldown, DB 저장은 Main이 담당한다.

발표 문장 예시:

> “로봇 주행 중 PiCam에 사람이 잡히면 AI Server는 Main에게 위험 신호만 전달하고, 실제 정지 판단은 Main이 하도록 분리했습니다.”

근거 자료:

- `assets/01-tb3_1-person-detection-overlay.jpg`
- `assets/01-person-hazard-compact.json`
- `capture-log-summary.md`

## 2. 두 로봇 동시 감시 구조

- `tb3_1`과 `tb3_2`가 동시에 DRIVE일 수 있으므로 monitor state를 로봇별로 독립시켰다.
- `tb3_1_picam -> tb3_1`, `tb3_2_picam -> tb3_2` 매핑을 유지한다.
- 잘못된 조합 예: `robot_id=tb3_1&source=tb3_2_picam`은 400으로 거절한다.

발표 문장 예시:

> “두 로봇이 동시에 움직여도, 각 로봇의 카메라와 위험 이벤트가 섞이지 않도록 robot_id/source를 분리했습니다.”

## 3. 노트북용 low-load Vision runtime

- AI 서버를 별도 노트북에서 띄우고 Main PC가 REST/WebRTC로 접근한다.
- MX450/저전력 노트북 환경을 고려해 live stream과 AI inference FPS를 분리했다.
- PiCam과 Global Cam stream을 유지하면서도 무거운 처리는 필요한 상태에서만 실행하는 방향으로 정리했다.

발표 문장 예시:

> “AI Server는 Main과 분리된 노트북에서 돌아가며, 영상 스트리밍은 유지하되 AI 추론은 저율로 돌려 부하를 낮췄습니다.”

## 4. 운영자 PC에서 노트북 Vision runtime 제어

- 운영자 PC에서 AI 노트북에 직접 접속하지 않아도 `restart-low-load` API로 재시작/파라미터 변경이 가능하다.
- `--git-pull`도 지원해서 코드 업데이트 후 low-load runtime을 다시 띄울 수 있다.
- 허용된 파라미터만 바꿀 수 있게 allowlist를 둬서 임의 shell 실행은 막았다.

발표 문장 예시:

> “현장 튜닝 때 노트북으로 매번 이동하지 않고, 운영자 PC에서 파라미터를 바꿔 재시작할 수 있게 했습니다.”

## 5. Global Cam Map ROI + ArUco 기준 고정

- Global Cam에서 전체 작업 맵 영역(Map ROI)을 overlay로 표시한다.
- ArUco marker 11/12를 기준으로 맵 ROI를 잡고, marker 12가 잡히면 ROI를 LOCK한다.
- ROI가 흔들리는 문제를 줄이고, 다음 단계인 구역 ROI/낙하물 감시/학습 데이터 수집의 기준선을 만든다.

발표 문장 예시:

> “낙하물 감시를 바로 학습하기 전에, 먼저 Global Cam 영상에서 ‘우리 맵이 어디인지’를 안정적으로 잡는 기준선을 만들었습니다.”

근거 자료:

- `assets/02-global-map-roi-locked.jpg`

## 다음 단계

1. Map ROI 안에서 입고/출고/충전/창고/주행구역 등 세부 구역 ROI 잡기
2. 낙하물/적재 증거용 데이터 수집 스크립트 정리
3. `target_item`, `carrier_pallet` 라벨링 전략으로 모델 학습 준비
4. 낙하물 감시 API와 pick/drop 증거 API 구현/검증
