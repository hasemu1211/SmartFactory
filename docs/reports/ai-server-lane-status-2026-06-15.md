# SmartFactory AI Server Lane 현황 보고서

- 작성일: 2026-06-15
- 기준 파일: `entry.md`
- 기준 저장소: `/home/codelab/Desktop/Project/SmartFactory`
- 대상 브랜치: `feature/ai-server-marker-detection`
- 검증 명령: `./scripts/test_ai_server.sh -q`
- 최근 검증 결과: `85 passed, 1 warning`

> 이 문서는 로컬 저장소 기준 현황 정리입니다. Confluence 라이브 페이지까지 검증한 최종 문서는 아닙니다.

---

## 1. 전체 요약

현재 SmartFactory AI Server 작업은 다음 상태입니다.

| Lane | 현재 상태 | 쉽게 말하면 | 남은 일 |
| --- | --- | --- | --- |
| A. Completed robot-free stack | 완료 | 로봇 없이 컴퓨터에서 만들 수 있는 기본 기능은 완료 | 안정 베이스 유지, 회귀 테스트 |
| B. Remaining no-physical-tuning work | 거의 완료 | 실제 로봇 없이 가능한 AI Server 기능 대부분 구현 | 실제 모델 weight 선택/검증, WMS/Main 실제 연동 |
| C. Robot-available passive tuning | 대기 | 로봇과 카메라를 켜고 관찰만 하는 튜닝 | FPS, pose noise, ROI, marker 안정성 측정 |
| D. Permission-gated active tuning | 승인 전 차단 | 로봇을 실제로 조금 움직이는 튜닝 | 사용자 명시 승인 후 저속 주행/정렬 튜닝 |

한 문장으로 정리하면 다음과 같습니다.

> AI Server는 “사진을 보고 근거를 만드는 서버”까지는 상당히 구현되어 있고 테스트도 통과합니다. 하지만 “실제 모델 파일로 현장 이미지 검증”, “WMS/Main이 최종 작업 성공을 결정하는 연동”, “로봇을 실제로 움직이는 튜닝”은 아직 남아 있습니다.

---

## 2. Lane B 잔여 작업

### 2.1 Lane B 현재 상태

Lane B는 `entry.md` 기준으로 **Mostly done**, 즉 “대부분 완료” 상태입니다.

이미 구현된 주요 내용은 다음과 같습니다.

- Detector/segmenter seam
- Lift ROI API
- Segmentation-primary adapter
- Observability
- Bounded retention
- Central-PC deployment assets

쉽게 말하면 다음과 같습니다.

> 사진을 받아서 박스나 팔레트 같은 물체 후보가 리프트 영역 안에 있는지 계산하고, 나중에 YOLO나 segmentation 모델을 꽂을 수 있는 자리까지 만들어둔 상태입니다.

---

### 2.2 B 잔여 1 — 실제 모델 weight 선택 및 검증

아직 실제로 사용할 YOLO/segmentation 모델 파일이 정해지지 않았습니다.

현재 구현은 모델을 꽂을 수 있는 구조만 준비되어 있습니다.

현재 가능한 것:

- `VISION_MODEL_PATH` 환경변수로 모델 경로 설정
- `VISION_MODEL_TASK=segment` 또는 `detect` 선택
- confidence, IoU, image size, device 설정
- segmentation mask가 있으면 mask 기반 평가
- mask가 없으면 bbox 기반 평가로 fallback
- 모델 경로 또는 Ultralytics 패키지가 없으면 fail-closed 처리

아직 남은 것:

1. 실제 박스/팔레트/낙하물 샘플 이미지 준비
2. 사용할 YOLO 또는 segmentation 모델 weight 선택
3. `VISION_MODEL_PATH`에 모델 파일 경로 설정
4. offline sample image로 검출률 확인
5. 오검출, 미검출, 속도 확인
6. Lift ROI threshold 조정
   - confidence
   - mask overlap ratio
   - bbox overlap ratio
   - stable frame count
7. 실제 운영에 쓸 class 이름 정리
   - 예: `box`, `pallet`, `dropped_item`

쉽게 말하면 다음과 같습니다.

> 전기 콘센트와 스위치는 만들어 놨지만, 실제로 꽂을 전자기기인 모델 파일은 아직 고르지 않은 상태입니다.

---

### 2.3 B 잔여 2 — WMS/Main Lift ROI gate 실제 구현

현재 AI Server는 `LiftRoiEvidence`라는 증거를 만들 수 있습니다. 그러나 그 증거를 보고 “작업 성공” 또는 “작업 실패”를 최종 결정하는 WMS/Main 구현은 이 저장소에 아직 없습니다.

현재 가능한 것:

- AI Server가 lift ROI evidence 생성
- pickup/dropoff 후보 판단
- `CONFIRMED` 또는 `CANDIDATE` 상태 생성
- VisionEvent best-effort WMS 전송 seam 존재

아직 없는 것:

- 실제 WMS/Main 서비스 구현
- `LiftRoiEvidence`를 받는 WMS endpoint
- WMS task state machine
- inventory state transition
- pickup/dropoff authoritative gate
- GUI 상태 반영
- WMS audit log/persistence

남은 작업:

1. 실제 WMS/Main 서비스 위치 확인
2. WMS/Main API contract 확정
3. 예를 들어 다음 endpoint 설계/구현

```text
POST /api/v1/lift-roi/evidence
```

4. WMS가 다음 조건을 검사하도록 구현
   - `task_id`가 현재 작업과 맞는가
   - `source`와 `robot_id`가 배정된 로봇/카메라와 맞는가
   - 현재 작업 단계가 pickup/dropoff 검증 단계인가
   - `verification.status == CONFIRMED`인가
   - `evidence_id`가 중복이 아닌가
5. WMS가 상태를 전이
   - pickup confirmed
   - dropoff confirmed
   - retry
   - exception
   - manual check
6. 모든 결정 이유를 GUI와 log에 남김

쉽게 말하면 다음과 같습니다.

> AI Server는 “사진을 보니 물건이 실린 것 같습니다”라고 말할 수 있습니다. 하지만 “그럼 작업 완료!”라고 최종 도장을 찍는 WMS/Main은 아직 구현되어 있지 않습니다.

---

## 3. Lane C 남은 작업

### 3.1 Lane C 현재 상태

Lane C는 **Robot-available passive tuning**입니다.

즉, 로봇과 카메라가 실제로 필요하지만 로봇을 움직이지는 않는 단계입니다.

쉽게 말하면 다음과 같습니다.

> 로봇을 움직이지 않고, 카메라로 표지판이 잘 보이는지 관찰하는 과학 실험 단계입니다.

---

### 3.2 C에서 해야 할 일

로봇과 카메라를 사용할 수 있는 시간이 생기면 다음을 측정해야 합니다.

1. Robot PiCam topic 확인
   - `/camera/image_raw/compressed`
   - `/camera/image_raw`
2. 카메라 FPS 측정
   - 이전 Robot1 QA에서는 compressed topic이 약 30Hz였음
3. ArUco marker가 안정적으로 보이는지 확인
4. pose noise 측정
   - 좌우 오차
   - 거리 오차
   - yaw 오차
5. marker lost가 얼마나 자주 발생하는지 확인
6. camera intrinsic 값 확인 또는 보정
7. marker 실제 크기 측정
8. station별 marker ID 정리
9. target docking offset 정리
10. Lift ROI polygon을 실제 이미지 기준으로 조정
11. passive ArUco pose monitor로 관찰 로그 확보
12. `/cmd_vel`은 절대 발행하지 않음

---

### 3.3 C에서 금지되는 것

C 단계에서는 다음을 하면 안 됩니다.

- 로봇 이동 명령 발행
- `/cmd_vel` 발행
- 로봇 파일/설정 변경
- robot-side package 설치
- active docking controller 실행

즉, C는 관찰만 하는 단계입니다.

---

## 4. Lane D 남은 작업

### 4.1 Lane D 현재 상태

Lane D는 **Permission-gated active tuning**입니다.

즉, 사용자가 명시적으로 허락하기 전까지 차단된 단계입니다.

쉽게 말하면 다음과 같습니다.

> 실제 RC카를 움직여서 주차 연습하는 단계이므로, 반드시 사용자 승인과 안전 조건이 필요합니다.

---

### 4.2 D를 시작하기 위한 조건

D를 시작하려면 먼저 다음 조건이 필요합니다.

1. 사용자의 명시적 승인
   - 예: “저속 주행 튜닝 진행해도 된다”
2. 수동 정지 가능 상태
3. 사람이나 장애물이 없는 환경
4. marker loss 시 즉시 정지 조건
5. stale frame timeout 시 즉시 정지 조건
6. 속도 제한 설정
7. 안전하게 테스트할 공간 확보

---

### 4.3 D에서 해야 할 일

승인 후에는 다음 작업을 수행합니다.

1. 저속 `/cmd_vel` 발행 테스트
2. ArUco marker 기반 docking error 확인
3. docking gain 조정
   - distance gain
   - lateral gain
   - yaw gain
4. 속도 제한 조정
   - max linear speed
   - max angular speed
5. 정렬 tolerance 조정
   - lateral tolerance
   - distance tolerance
   - yaw tolerance
   - stable frame count
6. marker loss 시 정지 확인
7. stale frame 시 정지 확인
8. 과회전, 흔들림, 정렬 실패 기록
9. 성공/실패 로그 저장

---

## 5. 현재 구현 상황 상세

## 5.1 AI Server API

현재 FastAPI 기반 AI Server가 구현되어 있습니다.

구현된 endpoint는 다음과 같습니다.

- `GET /api/v1/health`
- `GET /api/v1/sources`
- `GET /api/v1/detections/latest`
- `GET /api/v1/metrics`
- `POST /api/v1/detect/image`
- `POST /api/v1/lift-roi/evaluate`
- `POST /api/v1/lift-roi/evaluate-image`

의미:

> 서버 상태 확인, 카메라 source 상태 확인, 최근 detection 조회, metric 조회, 이미지 detection, lift ROI 평가 기능이 구현되어 있습니다.

---

## 5.2 Marker detection

현재 marker detection은 OpenCV ArUco 전용입니다.

가능한 것:

- 이미지 byte decode
- OpenCV ArUco `DICT_4X4_50` 탐지
- marker ID 생성
  - 예: `ARUCO_4X4_50_0`
- bounding box 계산
- corner 좌표 보존
- `VisionEvent v1` 생성

현재 범위 밖:

- QR marker
- AprilTag marker
- YOLO/Torch 기반 marker detection
- ROS2 직접 import

의미:

> MVP1 marker slice에서는 QR이나 AprilTag가 아니라 OpenCV ArUco만 사용합니다.

---

## 5.3 ArUco pose / docking math

구현된 것:

- camera intrinsics 구조
- solvePnP 기반 marker pose 추정
- lateral/distance/yaw error 계산
- 정렬 여부 판단
- stable alignment count 계산
- bounded docking command proposal 계산
- marker lost 시 정지 command 반환

중요한 제한:

- 실제 `/cmd_vel` 발행은 하지 않음
- 로봇을 직접 움직이지 않음
- AI Server는 motion authority가 아님

의미:

> 로봇이 어느 방향으로 조금 움직이면 좋을지 계산은 할 수 있지만, 실제로 로봇에게 움직이라고 명령하지는 않습니다.

---

## 5.4 Lift ROI evidence

구현된 것:

- Lift 영역 polygon 입력
- bbox 후보 평가
- instance mask 후보 평가
- class filter
  - `box`
  - `pallet`
- confidence threshold
- ROI overlap ratio
- expected count 비교
- count stable 여부 확인
- lift sensor 정보 반영
- pickup/dropoff verification 결과 생성
- `LiftRoiEvidence v1` schema validation

의미:

> 리프트 위에 물건이 몇 개 있는지, 안정적으로 보이는지, 들어 올렸는지/내렸는지에 대한 근거 자료를 만드는 기능입니다.

---

## 5.5 Detector/segmenter seam

구현된 내부 구조:

- `DetectionBox`
- `InstanceMask`
- `DetectorResult`
- `DetectorSegmenter`
- bbox normalization
- confidence validation
- polygon mask rasterization
- Lift ROI candidate 변환

의미:

> 특정 모델에 강하게 묶이지 않고, 나중에 YOLO든 다른 segmentation 모델이든 교체해서 연결할 수 있게 중간 규격을 만들어둔 상태입니다.

---

## 5.6 Optional Ultralytics adapter

구현된 것:

- `VISION_MODEL_PATH`가 있을 때만 model loading 시도
- `ultralytics`는 서버 시작 필수 dependency가 아님
- task는 `segment` 또는 `detect`
- segmentation mask가 있으면 `InstanceMask` 사용
- mask가 없으면 bbox fallback
- 모델이 없으면 endpoint가 HTTP 503으로 fail-closed

의미:

> 무거운 AI 모델이 없어도 서버는 뜨고, 모델을 설정했을 때만 실제 segmentation을 시도합니다.

---

## 5.7 Source health / event retention / metrics

구현된 것:

- source별 frame 상태 추적
- source별 event 상태 추적
- `online`, `stale`, `offline`, `disabled` 상태 판단
- latest detection ring buffer
- request ID
- structured JSON log
- `/api/v1/metrics`

의미:

> 카메라가 살아 있는지, 최근 이벤트가 있는지, API가 몇 번 호출됐는지 볼 수 있습니다.

---

## 5.8 WMS emit seam

현재 구현된 것은 `VisionEvent` best-effort 전송입니다.

가능한 것:

- `POST {MAIN_SERVER_URL}/api/v1/vision/events`
- HTTP 200/202 성공 처리
- timeout 처리
- non-2xx 실패 처리
- WMS 전송 실패와 local detection 성공을 분리

아직 없는 것:

- `LiftRoiEvidence` WMS ingest
- WMS task state machine
- inventory state transition
- authoritative pickup/dropoff gate
- GUI state update

의미:

> marker evidence를 WMS로 보내는 통로는 있지만, lift ROI evidence로 실제 작업 상태를 바꾸는 WMS 쪽 기능은 아직 없습니다.

---

## 5.9 ROS2 side

구현된 것:

- `smartfactory_perception_ros`
- `image_snapshot_client`
- raw image subscribe
- compressed image subscribe
- AI Server `/api/v1/detect/image`로 snapshot post
- passive `aruco_pose_monitor`
- `/cmd_vel` publisher 없음

Robot1 QA 기록:

- `/camera/image_raw/compressed`는 약 30Hz
- phone-displayed ArUco ID `0` 감지
- `image_snapshot_client`가 compressed frame을 AI Server로 전송
- AI Server가 `ARUCO_4X4_50_0` event 생성

의미:

> ROS2 카메라 영상을 AI Server로 보내거나, passive하게 ArUco pose를 관찰하는 기능은 준비되어 있습니다. 하지만 로봇 이동 명령은 내리지 않습니다.

---

## 5.10 Deployment assets

구현된 것:

- `services/ai-server/Dockerfile`
- `docker-compose.ai-server.yml`
- `ops/systemd/smartfactory-ai-server.service`
- healthcheck
- 환경변수 기반 설정
- 중앙 PC에서 독립 process/container로 실행 가능

의미:

> 지금은 중앙 PC에서 AI Server를 독립 서비스처럼 실행할 수 있고, 나중에 별도 AI Server PC로 분리하기 좋은 구조입니다.

---

## 6. 현재 테스트 상태

실행한 명령:

```bash
./scripts/test_ai_server.sh -q
```

결과:

```text
85 passed, 1 warning
```

의미:

> 현재 로컬 AI Server 테스트와 contract fixture 검증은 통과했습니다.

주의:

- warning 1개는 Starlette/FastAPI testclient 관련 deprecation warning입니다.
- 기능 실패는 아닙니다.

---

## 7. 현재 Git 작업트리 주의점

현재 저장소는 깨끗한 상태가 아닙니다.

확인된 상태:

- 수정된 파일 다수
- 새로 추가된 untracked 파일 다수
- 삭제된 `docs/confluence` 기존 파일 일부
- 새 architecture/sequence/presentation 관련 파일 존재

의미:

> 구현과 테스트는 통과하지만, 아직 커밋 정리, 문서 정리, Confluence 검증이 필요한 작업트리 상태입니다.

---

## 8. 최종 정리

### 완료된 것

- AI Server 기본 API
- OpenCV ArUco marker detection
- `VisionEvent v1` 생성
- optional ArUco pose evidence
- pure docking math
- Lift ROI evaluator
- `LiftRoiEvidence v1`
- detector/segmenter seam
- optional Ultralytics adapter
- source health
- bounded event retention
- metrics/logging
- WMS VisionEvent emit seam
- ROS2 image snapshot adapter
- passive ArUco pose monitor
- Docker/systemd deployment assets
- synthetic/API tests

### 아직 남은 것

1. 실제 segmentation/detection model weight 선택
2. offline sample image 검증
3. Lift ROI threshold 현장 조정
4. 실제 WMS/Main `LiftRoiEvidence` ingest/gate 구현
5. GUI/WMS 상태 전이 연동
6. 로봇 사용 가능 시간에 passive tuning
7. 사용자 승인 후 active low-speed docking tuning
8. 작업트리 정리 및 필요한 커밋 구성
9. Confluence 라이브 문서 검증 및 반영

---

## 9. 다음 추천 순서

추천 순서는 다음과 같습니다.

1. 현재 변경분 정리
   - 어떤 파일이 AI Server 구현인지
   - 어떤 파일이 문서/Confluence 산출물인지 구분
2. B 마무리 1단계
   - 실제 모델 weight 후보 선택
   - sample image offline 검증
3. B 마무리 2단계
   - WMS/Main 서비스 또는 API contract 확보
   - `LiftRoiEvidence` ingest/gate 구현 계획 확정
4. C 진행
   - 로봇/카메라 passive tuning window 확보
   - FPS, marker pose noise, ROI 측정
5. D 진행
   - 사용자 명시 승인 후에만 저속 active tuning

