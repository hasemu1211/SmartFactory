# Vision/API 연계 설계 초안 v2 (2026-06-30)

> 상태: 사용자 피드백 반영 로컬 초안. 구현/DB 반영 전 Main/운영 상태명/캘리브레이션 값 확정 필요.

## 1) 재조립된 핵심 결론

- **AI Server는 Main PC에서 REST로 호출 가능한 별도 서비스**로 둔다. 현재 코드 기준 기본 Vision host는 `smartfactory-vision.local` 계열이고, Main 기본 URL은 `smartfactory-main.local:8088`이다. `smartfactory-ai`가 필요하면 DNS/hosts/.env 별칭으로 추가한다.
- 네트워크가 `192.168.30.x`로 바뀌어도 Vision API 계약 자체는 바뀌지 않는다. durable endpoint는 hostname/env 기반으로 유지하고, 고정 IP는 Main fallback/env 또는 현장 smoke 값으로만 다룬다. ROS/DDS discovery, WebRTC ICE advertised host, firewall/port open 여부는 hardware/live preflight에서 별도로 검증한다.
- 세 기능은 **서로 다른 무거운 추론 프로세스 3개**가 아니라, 하나의 Vision 입력/이벤트 저장소 위에 붙는 **상태 기반 monitor profile 3개**로 설계한다.
- 기존 WebRTC/overlay streaming 경로는 건드리지 않는다. API는 가능한 한 **latest frame / latest detection / overlay 결과를 재사용**하고, 필요한 경우에만 저율 inference 또는 1회성 high-res evidence inference를 실행한다.
- AI Server는 `정지/홀드`를 직접 수행하지 않는다. `ADVISORY/CANDIDATE/PASS/FAIL/UNCERTAIN` 같은 **판정 제안**만 반환하고, cooldown·중복 억제·최종 HOLD/E-STOP은 Main이 결정한다.
- DB 저장 payload는 bbox/원시 detection 중심이 아니라, Main이 바로 해석 가능한 `event_type/result/reason_code/confidence/severity/observed_at/image_url` 중심으로 축소한다.

## 2) 용어 정정: ROI는 하나가 아니다

기존 문서의 “global cam에서 고정 ROI crop-first” 표현은 낙하물 감시에는 불충분하다. 아래처럼 분리한다.

| 용어 | 고정/동적 | 의미 | feature 2에서의 역할 |
| --- | --- | --- | --- |
| `MapROI` | 고정 | global cam 이미지 안의 1800mm x 1800mm 작업 맵 영역 | 벽/배경 제거용. **판정 기준이 아니라 연산 절감/좌표 보정 기준** |
| `AllowedZoneROI` | 고정 | lift bay, pickup/drop zone, 주행 가능 영역 등 | 물체가 있어도 정상일 수 있는 영역 제외/참고 |
| `DynamicCarrierROI` | 동적 | 주행 중 움직이는 로봇 리프트/파레트/적재 가능 footprint | “물건이 파레트 위인가, 밖인가”를 판단하는 핵심 기준 |
| `CandidateItem` | 동적 검출 | 학습할 작은 목표 물체(예: 4.5cm x 9cm 파레트/아이템) | 모델 또는 색상+모델 조합으로 검출 |

즉, **낙하물은 ‘dropped_item’이라는 외형 클래스를 학습하는 것이 아니라**, `target_item`이 `DynamicCarrierROI` 밖에 안정적으로 존재할 때 `DROPPED_ITEM_CANDIDATE`로 해석하는 것이 논리적으로 맞다.

## 3) 전체 아키텍처

```text
Camera/WebRTC/ROS ingest
  -> latest frame buffer / overlay stream  (기존 경로 유지)
  -> monitor scheduler                    (상태별 저율/일회성 추론)
  -> internal detections + tracking        (bbox/track은 내부용)
  -> compact event read model              (Main/DB 친화 JSON)
  -> Main REST poll or one-shot evaluate
```

설계 원칙:

1. **streaming과 inference는 분리**한다. 브라우저/운영 스트림은 계속 살아 있어도, heavy AI는 상태별로 decimate한다.
2. **capture는 막지 않는다.** AI가 느려도 최신 프레임만 사용하고 오래된 프레임은 버린다.
3. **원시 bbox는 내부 판단용**으로만 쓰고, Main 반환값에는 기본적으로 넣지 않는다.
4. monitor enable/disable은 AI Server에도 있어야 GPU/CPU 낭비를 줄일 수 있다. 단, cooldown은 Main 소유가 맞다.

## 4) API 초안

### 4.1 공통 monitor 상태 제어

Main이 DRIVE/PICK/DROP/IDLE 상태 전환 시 호출한다.

`PUT /api/v1/vision/monitors/{monitor_id}/state`

예:

```json
{
  "enabled": true,
  "robot_id": "tb3_1",
  "source": "tb3_1_picam",
  "task_id": "task-123",
  "operation_state": "DRIVE",
  "target_fps": 3
}
```

- AI Server 이점: 불필요한 추론을 꺼서 MX450/CPU 사용량을 줄인다.
- Main 이점: 상태 전환 시 어떤 감시가 켜져 있는지 명확해진다.
- cooldown/중복 suppress: 여전히 Main에서 처리한다.

### 4.2 사람 장애물 감시 최신 결과

`GET /api/v1/vision/hazards/person/latest?robot_id=tb3_1&since_event_id=...`

응답 예:

```json
{
  "source": "tb3_1_picam",
  "robot_id": "tb3_1",
  "event_type": "HUMAN_DETECTED",
  "result": "ADVISORY",
  "severity": "EMERGENCY",
  "confidence": 0.74,
  "observed_at": "2026-06-30T...+09:00",
  "reason_code": "PERSON_IN_ROBOT_CAMERA",
  "trusted": false,
  "event_id": "..."
}
```

### 4.3 낙하물 감시 최신 결과

`GET /api/v1/vision/hazards/dropped-item/latest?source=global_cam_01&robot_id=tb3_1&since_event_id=...`

응답 예:

```json
{
  "source": "global_cam_01",
  "robot_id": "tb3_1",
  "task_id": "task-123",
  "event_type": "DROPPED_ITEM_CANDIDATE",
  "result": "ADVISORY",
  "severity": "WARN",
  "confidence": 0.68,
  "observed_at": "2026-06-30T...+09:00",
  "reason_code": "TARGET_ITEM_OUTSIDE_DYNAMIC_CARRIER_ROI",
  "trusted": false,
  "image_url": "/api/v1/evidence/images/...jpg",
  "event_id": "...",
  "data_json": {
    "policy_version": "mvp2",
    "stable_frames": 2,
    "carrier_roi_source": "robot_pose_homography"
  }
}
```

### 4.4 픽업/드롭 전후 적재 증거 평가

`POST /api/v1/vision/evidence/lift-load/evaluate`

요청 예:

```json
{
  "source": "global_cam_01",
  "robot_id": "tb3_1",
  "task_id": "task-123",
  "operation": "PICKUP_BEFORE",
  "expected_item_count": 1,
  "capture_profile": "high_res_burst",
  "external_call_count": 1
}
```

응답 예:

```json
{
  "source": "global_cam_01",
  "robot_id": "tb3_1",
  "task_id": "task-123",
  "event_type": "LIFT_LOAD_EVIDENCE",
  "verification_status": "PASS",
  "result": "LOADED",
  "confidence": 0.91,
  "observed_at": "2026-06-30T...+09:00",
  "reason_code": "EXPECTED_ITEM_VISIBLE_IN_DYNAMIC_CARRIER_ROI",
  "trusted": false,
  "image_url": "/api/v1/evidence/images/...jpg",
  "data_json": {
    "policy_version": "mvp2",
    "burst_frames": 5,
    "accepted_frames": 4
  }
}
```

## 5) Feature 1: 사람 감지 / 긴급정지 제안

- source: `tb3_1_picam`, `tb3_2_picam`
- robot mapping: `tb3_1_picam -> tb3_1`, `tb3_2_picam -> tb3_2`
- 운영: 해당 로봇이 `DRIVE`일 때만 monitor ON
- 모델: COCO 등 사전학습 `person`으로 MVP 가능. 사용자가 가짜 사람 그림으로 person 인식 확인했으므로 fine-tune은 우선순위 낮음.
- confidence 정책: 고정 `0.85`는 높거나 낮을 수 있으므로 API 스키마가 아니라 policy config로 둔다. 긴급정지 성격상 초기에는 recall 우선(`0.45~0.65` 시작 + 1~2 frame 안정성)을 검증한다.
- 최종 정지: AI Server가 아니라 Main/로봇 제어 계층이 수행.

## 6) Feature 2: global cam 낙하물 감시

### 6.1 기존 모순 제거

“lift/drop 고정 구역을 crop해서 판단”은 주행 중 움직이는 파레트를 감시하는 목적과 맞지 않는다. 올바른 구조는 다음이다.

1. global cam에서 **고정 `MapROI`**를 잡는다. 이것은 전체 작업 맵을 잘라 배경을 제거하는 용도다.
2. Main/ROS가 가진 robot pose/task state를 homography로 이미지 좌표에 투영해서 **동적 `DynamicCarrierROI`**를 만든다.
3. 모델은 `target_item`을 찾는다.
4. `target_item` 중심점/footprint가 `DynamicCarrierROI` 밖에 있고, 정상 허용 구역에도 속하지 않으며, N프레임 지속되면 `DROPPED_ITEM_CANDIDATE`를 만든다.

따라서 crop-first는 “움직이는 파레트만 crop해서 맥락을 잃는 것”이 아니라, **전체 맵 영역을 보존한 채 배경만 제거하거나, candidate 주변만 2차 고해상도 확인하는 방식**이어야 한다.

### 6.2 작은 물체 해상도 문제

- 맵 폭: 1800mm
- 목표 크기: 약 45mm x 90mm
- 1080p에서 맵 폭이 거의 꽉 찬다면 45mm는 약 27px, 90mm는 약 54px 수준이다.
- 이를 `imgsz=320`으로 바로 줄이면 45mm 축은 약 8px 정도까지 떨어질 수 있어 검출이 불안정하다.

결론:

- global drop monitor는 무조건 낮은 `imgsz=224~320`만 쓰면 안 된다.
- 권장: `MapROI` 기준 640 이상 또는 tile/2-pass 전략.
- 비용 절감: 색상 구분이 있는 동일 아이템 1개라면 **색상/변화량 prefilter -> 모델 확인**이 가장 현실적이다.
- 운영 fps: MX450에서는 3~5fps를 목표로 하되, 실제 benchmark 전까지는 **1~3fps + 최신 프레임 drop 정책**이 안전하다.

### 6.3 판정 성격

- feature 2는 즉시 HOLD가 아니라 **로그/경고 이벤트**가 우선이다.
- Main이 필요하면 보수적으로 HOLD할 수 있지만, AI Server는 `CANDIDATE/ADVISORY`만 제안한다.

## 7) Feature 3: 픽업/드롭 전후 적재 증거

- 외부 API 호출 빈도: 작업 경계마다 1회.
- 내부 처리: 1회 호출 안에서 필요 시 3~5장 burst capture 후 종합 판단.
- 입력 source: 우선 `global_cam_01` 권장. 같은 카메라면 feature 2와 캘리브레이션/모델 일부를 공유할 수 있다.
- ROI: `robot_id + task_id + operation + robot pose`로 현재 파레트/리프트 예상 위치를 만든다. 파레트 QR이 없으면 Main의 로봇 상태와 homography가 주 기준이고, visual pallet tracker는 보조 검증이다.
- 결과는 엄격해야 하므로 `PASS/FAIL/UNCERTAIN`을 반환한다. 애매하면 false PASS보다 `UNCERTAIN`이 낫다.

## 8) 모델/학습 전략

### 8.1 모델을 어떻게 나눌지

권장 MVP:

1. `person`은 사전학습 모델 재사용.
2. `target_item` 검출용 커스텀 경량 detect 모델 1개를 만든다.
3. feature 2/3은 같은 `target_item` 모델을 공유하되, **추론 profile과 판정 policy는 분리**한다.

즉, 모델은 가능하면 하나로 시작하지만 정책은 분리한다.

| 기능 | 모델 | policy |
| --- | --- | --- |
| 사람 감지 | 사전학습 person | 낮은 threshold + Main E-stop 결정 |
| 낙하물 감시 | custom `target_item` | `target_item`이 동적 carrier 밖인지 판단 |
| 적재 증거 | custom `target_item` 공유 가능 | high-res burst + expected count + ROI + sensor/state 종합 |

### 8.2 학습 라벨

- `dropped_item`을 별도 외형 클래스로 학습하지 않는다.
- 라벨은 `target_item` 중심으로 둔다.
- 필요 시 `pallet/carrier` 또는 `robot_lift` 클래스를 추가하되, 가능하면 robot pose/homography로 동적 ROI를 만드는 편이 더 안정적이다.

### 8.3 데이터셋은 두 조건을 모두 포함해야 한다

feature 2와 3이 같은 물체를 보더라도 조건이 다르다.

- feature 2 데이터: global stream, 주행 중, motion blur, 작은 물체, 배경/그림자/로봇 일부 포함, 파레트 안/밖 모두.
- feature 3 데이터: high-res still/burst, 픽업 전/후, 드롭 전/후, 적재 있음/없음, partial occlusion, 조명 변화.

같은 모델을 쓰려면 이 두 distribution을 모두 학습/검증에 넣어야 한다. 그렇지 않으면 feature 2에서 잘 되는데 feature 3 증거 판단이 흔들리거나 반대가 될 수 있다.

## 9) 하드웨어 제약 반영

대상: i5-1135G7 + MX450 2GB VRAM + RAM 16GB

권장 운영:

- detect 모델 우선, segment 모델은 피한다.
- 한 번에 여러 무거운 모델을 GPU에 올리지 않는다.
- source별 scheduler로 추론량을 제한한다.
- media stream 15~30fps와 AI inference 1~5fps를 분리한다.
- feature 3 high-res burst 중에는 drop monitor fps를 일시 낮추거나 serialize한다.

초기 profile 예:

| profile | source | 상태 | fps/imgsz 권장 |
| --- | --- | --- | --- |
| person_drive | active robot Pi cam | DRIVE | 2~5fps, 320~416 |
| drop_watch | global_cam_01 | DRIVE | 1~3fps, 640 또는 tile/2-pass |
| lift_evidence | global_cam_01 | PICK/DROP boundary | 1회 호출 내부 3~5 burst, high-res |

## 10) DB 저장 형태

Main/DB에는 아래 정도만 저장한다.

```json
{
  "event_type": "DROPPED_ITEM_CANDIDATE",
  "source": "global_cam_01",
  "robot_id": "tb3_1",
  "task_id": "task-123",
  "result": "ADVISORY",
  "severity": "WARN",
  "confidence": 0.68,
  "trusted": false,
  "observed_at": "2026-06-30T...+09:00",
  "image_url": "/api/v1/evidence/images/...jpg",
  "data_json": {
    "reason_code": "TARGET_ITEM_OUTSIDE_DYNAMIC_CARRIER_ROI",
    "policy_version": "mvp2",
    "source_event_id": "..."
  }
}
```

bbox, mask, tile 좌표, track id는 AI 내부 디버그/학습용으로 보관하되 Main 기본 payload에서는 제외한다.

## 11) 남은 결정 사항

1. global cam 캘리브레이션: `MapROI` polygon + homography를 어떻게 저장할지.
2. Main이 robot pose/lift pose를 AI Server에 줄 수 있는지, 또는 AI Server가 ROS topic으로 직접 읽을지.
3. GoPro 실제 해상도/화각/설치 높이에서 45mm x 90mm 물체가 몇 pixel로 잡히는지 실측.
4. 색상 prefilter를 1차 후보 생성으로 쓸지.
5. feature 3에서 global cam만 쓸지, robot Pi cam 보조 증거도 함께 저장할지.

## 12) 구현 우선순위

1. 기존 `/api/v1/detections/latest` 기반 compact response adapter 추가.
2. monitor state API 추가: enable/disable + target fps + source/robot/task context.
3. feature 1 person monitor: 기존 person detection 결과 재사용.
4. global cam calibration 파일: MapROI + homography + allowed zones.
5. feature 2 target item detector + dynamic carrier ROI 판정.
6. feature 3 high-res burst evidence endpoint.
7. MX450 환경에서 profile별 fps/latency benchmark 후 default fps 확정.

## 13) 동시 2대 운용과 DynamicCarrierROI 보강 (2026-06-30 추가)

### 13.1 핵심 정정

두 로봇이 동시에 움직이면 global cam 관점에는 “현재 파레트”가 하나가 아니다. 따라서 AI Server는 `global_cam_01`에 대해 단일 lift ROI를 유지하지 않고, **로봇별 active carrier context**를 유지해야 한다.

```text
(tb3_1, task_id, operation_state, pose_timestamp) -> DynamicCarrierROI(tb3_1)
(tb3_2, task_id, operation_state, pose_timestamp) -> DynamicCarrierROI(tb3_2)
```

### 13.2 누가 어느 파레트인지 결정하는 기준

- 1순위: Main/ROS가 제공하는 `robot_id + task_id + robot_pose + lift_state`.
- 2순위: global cam의 visual `carrier_pallet` detection으로 projected ROI를 확인/보정.
- 금지: 동일하게 생긴 파레트만 보고 `tb3_1`/`tb3_2` identity를 결정하는 것.

즉, 파레트 인식은 필요하지만 **identity source가 아니라 ROI confirmation/refinement source**이다.

### 13.3 낙하물 감시의 소유자 할당

낙하물 감시는 전체 MapROI/tile에서 `target_item`을 찾고, 모든 active DynamicCarrierROI와 비교한다.

- item이 어느 active carrier 안에 있으면 정상.
- item이 모든 active carrier 밖에 있고 MapROI 안에 있으면 dropped candidate.
- owner가 명확하면 `assignment_status=OWNED`, `robot_id=tb3_1|tb3_2`.
- 둘 다 가능하면 `assignment_status=AMBIGUOUS`, `robot_id=null`, optional `related_robot_ids`.
- 어느 쪽도 근거가 없으면 `assignment_status=UNASSIGNED`.
- pose/calibration이 stale이면 `NO_DECISION`.

### 13.4 적재 증거 API의 crop 선택

Feature 3은 반드시 Main이 `robot_id`와 `task_id`를 지정해서 호출한다. AI Server는 요청된 robot의 DynamicCarrierROI만 crop/evaluate한다.

- 두 로봇이 동시에 있어도 `robot_id=tb3_1`이면 tb3_1 carrier만 본다.
- visual `carrier_pallet` detection은 crop이 맞는지 확인/보정한다.
- ROI가 겹치거나 visual confirmation이 불일치하면 `UNCERTAIN_ROI_CONFLICT`를 반환하고 PASS하지 않는다.

### 13.5 학습 전략 반영

커스텀 모델은 MVP부터 `target_item` 단일 class가 아니라, 가능하면 아래 2개 internal class를 라벨링/학습한다.

- `target_item`: 적재/낙하 대상 물체.
- `carrier_pallet`: 파레트/리프트 적재면. 동일하게 생긴 파레트는 같은 class로 라벨링한다.

단, `carrier_pallet`은 로봇 identity를 결정하지 않는다. identity는 Main pose/task context가 정하고, model은 ROI 확인/보정/충돌 감지에 쓴다.

## 14) Main DB `data-structure.md` 호환 검토 추가 (2026-06-30)

`/home/codelab/Downloads/data-structure.md` 기준 Main DB 구조는 큰 방향에서 호환된다. 특히 `evidence_events`를 runtime evidence buffer로 두고, `safety_stops`를 Main/ROS HOLD latch로 두는 구조는 AI Server advisory-only 원칙과 맞다.

이 문서 기준에서는 안전정지 중에도 `tasks.status`를 `BLOCKED`로 바꾸지 않는다. `tasks.status`는 `RUNNING`을 유지하고, 현재 HOLD/RESUME 상태는 `safety_stops.status=OPEN/HOLDING/CLOSED`로만 표현한다. 따라서 Vision API / Main DB adapter는 AI advisory evidence를 `tasks.status=BLOCKED`로 변환하면 안 된다.

다만 아래 규칙은 반드시 지켜야 한다.

1. AI Server에서 온 evidence는 기본 `trusted=false`다. Main이 정책적으로 `safety_stops`를 열 수는 있지만, DB row 자체가 “AI가 최종 truth를 확정했다”는 의미가 되면 안 된다.
2. Main DB의 `evidence_events.data_json`에는 bbox/mask/raw payload 대신 compact 판단 필드만 넣는다.
3. 예시 필드:

```json
{
  "result": "ADVISORY",
  "reason_code": "TARGET_ITEM_OUTSIDE_DYNAMIC_CARRIER_ROI",
  "assignment_status": "OWNED",
  "robot_id": "tb3_1",
  "related_robot_ids": [],
  "policy_version": "mvp2",
  "profile_id": "drop_watch_global_v1",
  "threshold_set_id": "drop_watch_mx450_v1"
}
```

4. `safety_stops`에는 직접 `robot_id`가 없으므로, HOLD를 열 evidence는 반드시 robot-resolvable 해야 한다.
   - `evidence_events.task_id -> tasks.robot_id`로 찾을 수 있거나,
   - `evidence_events.data_json.robot_id`가 명확해야 한다.
5. `assignment_status=AMBIGUOUS` 또는 `UNASSIGNED`이면 robot-specific HOLD를 추측해서 열지 않는다. 기본은 warning/log/review이며, Main이 별도 보수 정책을 가진 경우에만 area/global hold를 결정한다.
6. MVP에서는 `commands.required_evidence_type` 매핑을 고정한다.
   - `PICK_UP` command는 `required_evidence_type=ITEM_PICKED`를 사용한다.
   - `DROP_OFF` command는 `required_evidence_type=ITEM_PLACED`를 사용한다.
   - AI lift evidence API 내부 판단은 `LIFT_LOAD_EVIDENCE`일 수 있지만, PASS pickup은 Main DB adapter에서 `event_type=ITEM_PICKED`, PASS dropoff는 `event_type=ITEM_PLACED`로 변환 저장한다.
   - 원래 AI 판단 세부값은 `data_json.ai_judgement`에 compact하게 둔다.
   - `UNCERTAIN`은 command 진행 근거를 만족하지 않는다.

따라서 DB 구조 자체는 현재 RALPLAN을 막지 않지만, Main DB adapter contract test가 필요하다.
