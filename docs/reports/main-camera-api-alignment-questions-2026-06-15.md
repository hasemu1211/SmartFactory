# Main Server ↔ Camera/Vision Gateway API 정렬 제안 및 확인 질문

- 작성일: 2026-06-15
- 작성 위치: SmartFactory repo
- 목적: Camera Server / AI Server / Vision Gateway 쪽 구현에 들어가기 전에 Main Server 팀과 API 계약, 책임 경계, 포트, 이벤트 경로를 먼저 합의하기 위함
- 참고 파일:
  - `/home/codelab/Downloads/CAMERA_SERVER_API_SPEC.md`
  - `docs/contracts/ai-server-api.md`
  - `docs/contracts/lift-roi-evidence.schema.json`
  - `.omx/plans/vision-gateway-ros-domain-bridge-plan-20260615.md`
  - `.omx/reports/vision-gateway-api-review/architect-camera-api-spec-review.md`
  - `.omx/reports/vision-gateway-api-review/critic-camera-api-spec-review.md`

---

## 1. 먼저 제안하는 방향

현재 Camera Server API 명세는 큰 방향은 좋습니다.

핵심 방향:

- 실시간 영상은 Main API로 보내지 않는다.
- Camera/Vision Gateway가 영상 수집, 영상 스트리밍, AI evidence 생성을 담당한다.
- Main Server는 task, inventory, robot 상태의 최종 source of truth를 유지한다.
- Camera/Vision Gateway는 Main DB에 직접 접근하지 않는다.
- Camera/Vision Gateway는 robot motion authority를 갖지 않는다.

이 방향은 유지하는 것을 제안합니다.

다만 구현 전에 아래 항목은 Main Server 팀과 먼저 합의가 필요합니다.

---

## 2. 제안 아키텍처

권장 구조는 다음과 같습니다.

```text
ROS2 Cameras / Robots
  -> Camera/Vision Gateway
       - camera frame ingest
       - multi-camera source registry
       - latest frame cache
       - AI inference/evidence
       - visual overlay stream
       - source health
       - evidence/event emit
  -> Browser / GUI
       - video stream
       - visual evidence overlay

Camera/Vision Gateway
  -> Main Server
       - VisionEvent evidence
       - Camera audit/business event
       - LiftRoiEvidence if push mode is selected

Main Server
  -> task/inventory/robot final decision
  -> GUI status source of truth
```

중요 원칙:

```text
AI / Camera evidence != WMS final decision
```

예를 들어 Camera/Vision Gateway가 `TAG_DETECTED` 또는 `pickup_verified` evidence를 생성해도, task 상태를 실제로 `PICKUP_CONFIRMED`로 바꾸는 것은 Main Server가 담당해야 합니다.

---

## 3. API 경로 제안

### 3.1 VisionEvent evidence ingest

현재 AI Server 쪽 canonical contract는 아래 경로를 사용합니다.

```http
POST /api/v1/vision/events
```

제안:

- 이 경로를 VisionEvent 계열의 canonical ingest endpoint로 유지합니다.
- marker, person, obstacle, item candidate 등 AI evidence event는 이 경로로 보냅니다.
- 중복 방지는 `event_id` 기준으로 합니다.

---

### 3.2 일반 Camera audit/business event

Camera API spec에는 아래 경로가 있습니다.

```http
POST /api/v1/camera/events
```

제안:

- 이 경로는 VisionEvent schema와 다른 일반 카메라 운영 이벤트용으로 분리합니다.
- 예:
  - camera server startup
  - camera stream degraded
  - camera source disconnected
  - operator-visible warning
  - connect test
- 이 경로는 task 상태를 직접 변경하지 않고 audit/event log 용도로만 사용합니다.

즉 역할을 이렇게 나눕니다.

| Endpoint | 용도 | 상태 전이 가능 여부 |
| --- | --- | --- |
| `POST /api/v1/vision/events` | AI VisionEvent evidence | Main 정책 통과 시에만 가능 |
| `POST /api/v1/camera/events` | 일반 camera audit/business event | 직접 상태 전이 없음 |
| `POST /api/v1/vision/lift-roi/evidence` | Lift ROI push evidence 후보 | Main gate 통과 시에만 가능 |

---

### 3.3 Lift ROI evidence

Lift ROI는 두 방식 중 하나를 우선 선택해야 합니다.

#### Option A — Pull-first

```http
Main -> Camera/Vision Gateway
POST {CAMERA_API_BASE}/lift-roi/evaluate
```

장점:

- Main이 task context를 가진 상태에서 필요한 시점에 검증 요청 가능
- task_id/source/operation mismatch 위험이 작음
- Camera/Vision Gateway가 Main task 상태를 몰라도 됨

추천:

- 1차 구현은 Pull-first를 추천합니다.

#### Option B — Push evidence

```http
Camera/Vision Gateway -> Main
POST {MAIN_API_BASE}/vision/lift-roi/evidence
```

필요한 경우:

- Camera/Vision Gateway가 독립적으로 비동기 evidence를 계속 누적해야 하는 경우
- Main이 요청하지 않아도 특정 evidence를 즉시 보고해야 하는 경우
- 여러 source에서 비동기 이벤트가 많이 발생하는 경우

추천:

- MVP에서는 Pull-first를 먼저 확정하고, Push는 필요 시 추가하는 것을 제안합니다.

---

## 4. LiftRoiEvidence schema 제안

현재 Camera API spec의 Lift ROI 예시는 축약되어 있습니다. 실제 계약에는 `docs/contracts/lift-roi-evidence.schema.json`의 전체 필드를 따라야 합니다.

필수 필드 예:

```json
{
  "schema_version": "lift-roi-evidence.v1",
  "evidence_id": "uuid",
  "timestamp": "2026-06-15T10:20:30+09:00",
  "source": "tb3_1_picam",
  "robot_id": "tb3_1",
  "frame_id": "tb3_1_pi_camera_optical_frame",
  "operation": "PICKUP",
  "task_id": "12",
  "image": {
    "width": 640,
    "height": 480
  },
  "roi": {
    "roi_id": "LIFT_ROI",
    "kind": "LIFT",
    "polygon_xy": [[0, 0], [640, 0], [640, 480], [0, 480]]
  },
  "expected_count": 1,
  "stable_frames": 3,
  "count_stable": true,
  "lift_sensor": {
    "lift_up": true,
    "lift_down_complete": null,
    "backoff_complete": null
  },
  "load": {
    "count": 1,
    "empty": false,
    "accepted_items": [],
    "rejected_items": []
  },
  "dropped_item_count": 0,
  "verification": {
    "status": "CONFIRMED",
    "reason": "pickup_verified"
  },
  "policy": {
    "policy_version": "mvp1-lift-roi",
    "load_classes": ["box", "pallet"],
    "min_confidence": 0.5,
    "min_overlap_ratio": 0.6
  },
  "metadata": {
    "model": "opencv/ultralytics/etc",
    "latency_ms": 12.3
  }
}
```

주의:

- `task_id`는 현재 schema 기준 `string | null`입니다. Main에서 integer를 쓰고 싶다면 양쪽 schema 변경이 필요합니다.
- `verification.status`는 현재 schema 기준 다음만 허용합니다.

```text
CONFIRMED | CANDIDATE | FAILED
```

- `ERROR`를 추가하려면 schema 변경이 필요합니다.

---

## 5. 포트/환경변수 제안

현재 문서와 구현의 포트가 다릅니다.

Camera API spec 제안:

```text
Main API: 8080
Camera API: 8090
Camera stream / rosbridge: 9090
```

현재 AI Server 기본값:

```text
AI Server API: 8100
Main Server URL default: 8000
```

제안:

- 실제 통합 포트를 Main 팀과 명시적으로 확정합니다.
- 포트가 아직 예시라면 문서에 “예시값”이라고 표시합니다.
- 최종 env 이름은 아래처럼 정리하는 것을 제안합니다.

```bash
MAIN_API_BASE=http://<main-host>:<main-port>/api/v1
VISION_API_BASE=http://<vision-host>:<vision-port>/api/v1
CAMERA_STREAM_URL=ws://<vision-host>:9090
```

질문:

- Main API 실제 포트는 `8080`인가요, `8000`인가요?
- Camera/Vision Gateway API 포트는 `8090`으로 맞출까요, 현재 AI Server의 `8100`을 유지할까요?
- Browser stream URL은 rosbridge `9090`을 계속 쓸까요, 아니면 Vision Gateway 자체 stream endpoint를 쓸까요?

---

## 6. ROS topic / source registry 제안

현재 topic 이름이 여러 종류로 섞여 있습니다.

문서 후보:

```text
/mission/tb3_1/camera/compressed
/mission/tb3_2/camera/compressed
```

현재 Robot1 live QA:

```text
/camera/image_raw/compressed
```

현재 AI config 후보:

```text
/global_camera/image_raw
/tb3_1/pi_camera/image_raw
/tb3_2/pi_camera/image_raw
```

Vision Gateway 신규 제안:

```text
/sf/cameras/<source>/image/compressed
/sf/vision/<source>/overlay/compressed
/sf/vision/<source>/evidence_json
```

제안:

- source ID는 고정합니다.

```text
global_cam_01
tb3_1_picam
tb3_2_picam
```

- 실제 ROS topic은 `config/vision/sources.yaml` 같은 source registry에서 매핑합니다.

예:

```yaml
sources:
  tb3_1_picam:
    robot_id: tb3_1
    input_topic: /mission/tb3_1/camera/compressed
    input_type: sensor_msgs/msg/CompressedImage
    overlay_topic: /sf/vision/tb3_1_picam/overlay/compressed
    evidence_topic: /sf/vision/tb3_1_picam/evidence_json
```

질문:

- Main/Frontend 쪽에서 기대하는 최종 camera topic 이름은 `/mission/...`인가요?
- 아니면 Vision Gateway가 `/sf/...` namespace로 표준화해서 publish해도 되나요?
- Browser는 raw camera topic을 볼까요, overlay topic을 볼까요, 둘 다 필요할까요?

---

## 7. Safety / Movement 책임 경계 제안

Camera API spec에는 아래 방향이 있습니다.

```text
Camera Server -> Movement Server safety channel -> robot stop/slow
Camera Server -> Main Server /camera/events -> 사후 감사 로그
```

이 문구는 안전상 오해의 여지가 있습니다.

제안:

- Camera/Vision Gateway는 safety evidence 또는 alert를 생성할 수 있습니다.
- 실제 stop/slow 권한은 별도 Movement/Safety Controller가 가져야 합니다.
- Camera/Vision Gateway가 직접 `/cmd_vel`을 publish하거나 Nav2 action을 호출하지 않습니다.
- Movement/Safety Controller가 받을 API/topic이 필요하다면 별도 contract를 정의해야 합니다.

권장 문구:

```text
Camera/Vision Gateway may emit PERSON_INTRUSION or OBSTACLE_DETECTED safety evidence.
Motion stop/slow authority belongs to the Movement/Safety Controller.
Main Server receives the event for audit and operator visibility.
```

질문:

- Movement Server가 safety event를 받는 공식 API/topic이 있나요?
- Camera/Vision Gateway가 직접 stop 명령을 보내야 한다는 요구가 실제로 있나요?
- 만약 있다면, 해당 경로는 누가 승인하고 어떤 fail-safe 조건을 가져야 하나요?

---

## 8. Main Server 팀에 확인할 질문 목록

### 8.1 구현 상태 확인

1. `POST /api/v1/camera/events`는 실제로 구현되어 있나요, 아니면 제안인가요?
2. `CameraEvent` schema와 `EventRepository`는 현재 Main repo에 존재하나요?
3. 존재한다면 request/response schema를 공유해줄 수 있나요?

### 8.2 endpoint 역할 확인

4. `POST /api/v1/vision/events`는 VisionEvent evidence canonical ingest로 유지해도 되나요?
5. `POST /api/v1/camera/events`는 일반 camera audit/business event로 분리하는 데 동의하나요?
6. Lift ROI push endpoint가 필요하다면 경로는 아래로 합의해도 되나요?

```http
POST /api/v1/vision/lift-roi/evidence
```

### 8.3 Lift ROI 방식 확인

7. MVP에서는 Pull-first 방식으로 갈까요?

```http
Main -> Camera/Vision Gateway
POST /api/v1/lift-roi/evaluate
```

8. Push 방식도 MVP에 필요한가요?
9. `task_id` 타입은 string으로 맞출까요, integer로 바꿀까요?
10. `verification.status`에 `ERROR`가 꼭 필요한가요, 아니면 HTTP error / `FAILED`로 충분한가요?

### 8.4 idempotency / 저장 정책 확인

11. VisionEvent 중복 처리는 `event_id` 기준으로 하면 되나요?
12. Lift ROI evidence 중복 처리는 `evidence_id` 기준인가요, `report_id` 기준인가요?
13. 중복 요청 시 Main 응답은 `200 duplicate`로 할까요?
14. evidence 저장 table 또는 inbound report table이 있나요?

### 8.5 source / stream / GUI 확인

15. Main `/api/v1/status`에 Camera source health를 포함할 계획인가요?
16. GUI는 Camera/Vision Gateway `/sources`를 직접 조회하나요, 아니면 Main이 normalize한 source 상태를 조회하나요?
17. Browser stream은 rosbridge `9090`을 직접 보나요?
18. Overlay 영상 topic도 Browser에서 볼 예정인가요?
19. 최종 topic namespace는 `/mission/...`을 유지하나요, `/sf/...`로 표준화하나요?

### 8.6 safety 확인

20. Camera/Vision Gateway가 safety evidence만 보내는 것으로 충분한가요?
21. Movement Server의 safety stop/slow API 또는 ROS topic은 별도로 있나요?
22. Camera/Vision Gateway가 직접 motion command를 보내면 안 된다는 원칙에 동의하나요?

---

## 9. 구현 전 합의가 필요한 결정표

| 항목 | 제안 | Main 팀 확인 필요 |
| --- | --- | --- |
| VisionEvent ingest | `POST /api/v1/vision/events` 유지 | yes |
| Generic camera event | `POST /api/v1/camera/events`는 audit/business event 전용 | yes |
| Lift ROI MVP 방식 | Pull-first | yes |
| Lift ROI push | 필요 시 `POST /api/v1/vision/lift-roi/evidence` | yes |
| task_id type | 현재 schema 기준 string/null | yes |
| verification status | `CONFIRMED/CANDIDATE/FAILED` | yes |
| Camera API port | 8090 또는 8100 중 확정 | yes |
| Main API port | 8080 또는 8000 중 확정 | yes |
| Source IDs | `global_cam_01`, `tb3_1_picam`, `tb3_2_picam` | likely yes |
| ROS topic naming | source registry로 매핑 | yes |
| Safety authority | Movement/Safety Controller 소유 | yes |

---

## 10. 수정 후 권장 구현 레인

계약 합의 후 구현은 아래 순서가 안전합니다.

### Lane 0 — Contract Alignment

- Main endpoint 이름 확정
- port/env 확정
- Lift ROI pull/push 선택
- idempotency 정책 확정
- task_id 타입 확정
- safety authority 문구 확정

### Lane A — Base Refactor

- source registry 추가
- source mapping hardcode 제거
- existing API regression 유지

### Lane B — Stream / Overlay Synthetic

- robot 없이 synthetic frame으로 overlay stream 검증
- frame_seq/timestamp/evidence sync 설계

### Lane C — ROS2 Passive Integration

- compressed image ingest
- overlay/evidence ROS topic publish
- domain bridge allowlist
- no `/cmd_vel`

### Lane D1 — Performance / GUI / WMS Integration

- multi-camera soak
- GUI stream + WMS state 분리 표시
- WMS evidence gate 검증

### Lane D2 — Active Motion, Permission-gated

- 사용자 명시 승인 전까지 진행하지 않음
- Vision Gateway는 motion authority 없음

---

## 11. 최종 요약

Main Server 팀에 전달할 핵심 메시지는 다음입니다.

> Camera/Vision Gateway가 영상과 evidence를 담당하고, Main Server가 task/inventory 최종 판단을 담당하는 방향에는 동의합니다. 다만 구현 전에 `/vision/events`와 `/camera/events`의 역할, Lift ROI pull/push 방식, idempotency key, 포트, topic naming, safety authority를 먼저 합의해야 합니다. 특히 LiftRoiEvidence는 현재 schema와 맞춰야 하며, Camera/Vision Gateway가 robot motion authority를 갖는 것처럼 보이는 문구는 수정이 필요합니다.
