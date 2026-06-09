# SmartFactory AI Vision Pipeline Research

- 작성일: 2026-06-02
- 대상 프로젝트: 데모용 SmartFactory AMR-WMS 통합 시스템
- 대상 하드웨어: TurtleBot3 Burger 2대, 중앙 PC, LDS-03 LiDAR, 전역 카메라 1대, 로봇별 Pi Camera 1대, 전방 리프트/포크 예정
- 2026-06-09 구현 확정: 로봇에는 depth camera/RealSense D435를 장착하지 않는다. MVP1 비전 입력은 `global_cam_01`, `tb3_1_picam`, `tb3_2_picam`으로 고정한다. D435/depth/PointCloud2 내용은 배경 조사 또는 미래 옵션으로만 본다.
- NotebookLM: `SmartFactory AI Vision Pipeline Research — TurtleBot3 D435 YOLO ROS2` / `3440ab4c-5039-4a17-84f7-41dcd9ba7d66`

## 0. 계약 문서 우선순위

이 문서는 기술조사/배경자료다. 구현 시 API 경로, 필드명, enum, 검증 규칙은 `docs/contracts/vision-event.schema.json` 및 `docs/contracts/ai-server-api.md`를 우선한다. 이 문서에 남아 있는 `/vision-events`, `tag_id`, `wms_interpretation`, `recommended_action`, D435/depth 예시는 2026-06-09 확정 이후 MVP1 canonical contract가 아니다.

## 1. 프로젝트 맥락 인식

현재 문서 기준 프로젝트는 **데모용 SmartFactory AMR-WMS 통합 시스템**이다. 중앙 PC가 WMS-lite, GUI, DB, Vision, PyTorch/YOLO, ROS2 관제 로직을 담당하고, TurtleBot3 SBC는 최소 bringup·센서·구동·통신에 집중하는 구조가 이미 정리되어 있다.

핵심 설계 원칙은 다음과 같다.

1. **WMS-lite가 단일 진실 공급원**이다. 물품, 슬롯, 로봇, 작업, 이벤트 상태 전이는 WMS-lite가 결정한다.
2. **LiDAR/Nav2가 주행 안전의 주된 계층**이다. AI 비전은 사람/박스/낙하물 후보를 감지하고 설명·로그·예외 근거를 제공하지만, 안전 인증 제어처럼 표현하면 안 된다.
3. **OpenCV/AprilTag/QR은 ID와 위치 검증**, YOLO 계열은 사람/박스/낙하물 후보 감지로 분리한다.
4. **GUI는 Evidence over magic** 원칙을 따라 Vision Detail Drawer와 Robot Status Evidence에 감지 근거를 보여준다.

이번 사용자 추가 요구사항은 기존 초안과 잘 맞는다.

- 사람/장애물 인식 및 회피
- 떨어진 물건 또는 박스 후보 인식 후 WMS 이벤트 전달
- 도킹 위치 추정 보조: AprilTag/ArUco/QR 기반 권장
- RealSense D435 활용 가능성 검토(배경 조사; 2026-06-09 기준 MVP1 로봇 장착 제외)
- 최신 YOLO 발전형/SOTA와 실무 구현 가능성 비교

## 2. 우선 결론

### 2.1 우선순위에 대한 의견

사용자가 제시한 **ROS 통합성 > 실시간성 > 정확도** 순서는 이 프로젝트에 적합하다. 이유는 다음과 같다.

- 로봇 데모는 모델 mAP보다 **ROS topic/action, TF, Nav2, WMS 이벤트 연결이 끊기지 않는 것**이 먼저다.
- TurtleBot3 Burger와 Wi-Fi 환경에서는 카메라 스트림, depth, YOLO 추론, Nav2가 동시에 돌아갈 때 병목이 쉽게 생긴다.
- 실제 안전·회피는 LiDAR/Nav2 costmap이 담당해야 하므로, AI 모델은 고정밀 SOTA보다 **낮은 지연·낮은 false event·설명 가능한 이벤트화**가 더 중요하다.

권장 우선순위는 다음처럼 조금 더 세분화한다.

1. ROS2/Nav2/TF 안정성
2. 실시간성 및 네트워크 대역폭
3. 낮은 false positive/false negative를 위한 이벤트 필터링
4. 모델 정확도
5. 최신 SOTA 실험

### 2.2 추천 모델 선택

| 목적 | 1차 추천 | 2차/실험 | 이유 |
| --- | --- | --- | --- |
| MVP 실시간 사람/박스 후보 감지 | Ultralytics YOLO26n 또는 YOLO11n/s | YOLOv12n, YOLOv13n | YOLO26은 2026년 Ultralytics 최신 라인이고 edge/CPU 최적화를 강조한다. YOLO11은 성숙도가 높다. |
| 박스/낙하물 커스텀 감지 | YOLO26n/s fine-tune 또는 YOLO11n/s fine-tune | YOLOv13 fine-tune | 박스/낙하물은 COCO class만으로 부족할 수 있어 소량 데이터 fine-tune이 필요하다. |
| depth 기반 물체 거리 추정 | YOLO-seg + D435 depth ROI | Pi Camera known-size/AprilTag/homography 근사 | D435가 있으면 안정적이고, Pi Camera만 있으면 제한적 거리·위치 추정만 가능하다. |
| open-vocabulary 조사/라벨링 보조 | YOLOE-26, YOLO-World, Grounding DINO | 수동 검수 후 YOLO fine-tune | 실시간 제어보다 unknown item 조사와 데이터셋 준비에 적합하다. |
| 실시간 detector 비교 | RT-DETRv2 | TensorRT/ONNX 최적화 | DETR 계열은 end-to-end 구조가 강점이나, 데모 구현은 ROS/Ultralytics 생태계가 더 빠르다. |

## 3. 최신 모델/기술 동향 요약

### 3.1 YOLO26

Ultralytics 문서 기준 YOLO26은 2026-01-14 공개된 최신 Ultralytics YOLO 라인이다. 핵심은 다음과 같다.

- end-to-end NMS-free inference
- DFL 제거로 export/edge 호환성 단순화
- CPU inference 최대 43% 개선 주장
- detection, segmentation, semantic segmentation, pose, OBB 등 통합 태스크 지원
- nano 모델 기준 COCO mAP 40.9, CPU ONNX 약 38.9 ms, T4 TensorRT 약 1.7 ms로 문서화됨

프로젝트 적용 의견:

- 중앙 PC가 GPU를 갖고 있으면 `yolo26s.pt`까지 실험 가능하다.
- CPU만 안정적으로 쓸 계획이면 `yolo26n.pt`, 입력 320~640, frame skipping 구조가 현실적이다.
- YOLO26은 최신이라 논문 기반 검증은 약하지만, Ultralytics ROS quickstart 예제와 통합이 쉽다.

### 3.2 YOLO11

YOLO11은 2024년 공개되었고, detection/segmentation/pose/OBB 등 여러 태스크 지원과 edge/cloud 배포를 강조한다. 최신성은 YOLO26보다 낮지만, 커뮤니티 자료와 안정성이 더 좋을 수 있다.

프로젝트 적용 의견:

- 첫 구현은 YOLO11n/s로 성공 경로를 확보하고, 이후 YOLO26으로 교체하는 전략도 안전하다.
- ROS2 래퍼를 직접 만들면 모델 교체는 `YOLO("...")` 한 줄 수준으로 유지할 수 있다.

### 3.3 YOLOv10/v12/v13 연구 라인

- YOLOv10은 NMS-free end-to-end YOLO의 중요한 전환점이다.
- YOLOv12는 attention-centric 구조로 실시간 detector 성능을 끌어올린 연구다.
- YOLOv13은 hypergraph 기반 상관 강화로 YOLO11/YOLOv12 대비 mAP 개선을 주장한다.

프로젝트 적용 의견:

- 논문/SOTA 감시는 YOLOv12, YOLOv13을 포함해야 한다.
- 다만 MVP 구현에서는 논문 최신성보다 `pip install`, ROS message 변환, export, 디버깅 자료가 많은 쪽이 더 중요하다.

### 3.4 RT-DETR/RT-DETRv2

RT-DETRv2는 real-time detection transformer 계열이며, DETR의 deployment 제약을 줄이고 훈련 전략을 개선하려는 연구다.

프로젝트 적용 의견:

- 조사 대상에는 포함한다.
- 그러나 MVP는 Ultralytics YOLO 계열이 더 빠르게 ROS 이벤트 파이프라인화 가능하다.
- RT-DETRv2는 성능 비교/발표 SOTA 슬라이드용 또는 중장기 실험 후보가 적합하다.

### 3.5 YOLOE, YOLO-World, Grounding DINO

이 계열은 open-vocabulary/object grounding에 강하다.

프로젝트 적용 의견:

- “unknown item”, “새로운 물체 유형”, “라벨링 보조”에는 매우 유용하다.
- 실시간 주행 제어 path에는 넣지 않는다.
- 추천 사용법: 오프라인으로 데이터 라벨 후보 생성 → 사람이 검수 → YOLO26/YOLO11 custom model fine-tune.

## 4. RealSense D435를 TurtleBot3 Burger에 부착할 수 있는가?

결론: **물리적으로는 가능성이 높다. 단, 전원/USB3/무게중심/네트워크 대역폭 때문에 MVP에서는 고정형 또는 한 대 로봇에만 제한적으로 쓰는 것을 권장한다.**

근거:

- TurtleBot3 Burger 공식 사양은 최대 payload 15 kg, 본체 약 1 kg이다.
- D435는 90 mm × 25 mm × 25 mm의 작은 폼팩터이고, 1/4-20 UNC 및 M3 장착 포인트가 있다.
- D435는 USB-C 3.1 Gen 1, RGB 1920×1080@30fps, depth up to 1280×720@90fps를 제공한다.

실무상 주의:

1. Burger payload 수치가 충분하더라도 전방 리프트/포크, 카메라, 브라켓, 케이블을 앞쪽에 몰면 무게중심이 앞으로 쏠린다.
2. D435 raw depth+RGB 스트림을 로봇 SBC에서 중앙 PC로 Wi-Fi 송신하면 병목이 된다.
3. Raspberry Pi 계열에서 RealSense를 최고 해상도/프레임으로 운용하면 CPU/USB/전원 문제가 생길 수 있다.
4. 전방 리프트와 같이 쓰려면 카메라 시야가 포크에 가리지 않도록 LiDAR보다 낮거나 높은 위치, 약간 상향/하향 tilt를 실험해야 한다.

권장 배치:

| 단계 | D435 배치 | 이유 |
| --- | --- | --- |
| MVP 안정형 | 중앙 PC에 직접 연결한 고정형 D435 또는 USB 연장 가능한 고정 위치 | depth/YOLO 실험이 쉽고 네트워크 부담이 낮다. |
| MVP+ | Robot1에만 D435 장착, 640×480×15/30fps, pointcloud off 기본 | 한 대에서만 depth event를 검증한다. |
| 고급 | D435 pointcloud를 Nav2 voxel/obstacle layer에 선택적으로 투입 | 3D 장애물 반영 가능하지만 TF/대역폭/노이즈 튜닝 난이도가 높다. |

## 5. Pi Camera만 사용할 때 가능한 수준

결론: **Pi Camera만으로 Level 0~2는 충분히 가능하고, Level 3은 제한적으로 가능하며, Level 4는 비추천/불가능에 가깝다.** 따라서 D435 없이도 데모의 핵심 흐름인 인식 → WMS 이벤트 → 로봇 이동 → 슬롯/도킹 검증 → 예외 처리는 구현할 수 있다.

| 단계 | Pi Camera 단독 가능 여부 | 가능한 기능 | 한계 |
| --- | --- | --- | --- |
| Level 0 | 가능 | QR/AprilTag/ArUco로 item/slot/dock ID 확인 | 조명, 초점, 태그 크기와 카메라 캘리브레이션 필요 |
| Level 1 | 가능 | YOLO26n/YOLO11n으로 사람, 박스, 낙하물 후보 2D 감지 | 일반 물체의 정확한 거리·3D 위치는 알 수 없음 |
| Level 2 | 가능 | LiDAR/Nav2 장애물 상태와 YOLO evidence를 WMS/GUI에서 결합 | 실제 정지·회피는 LiDAR/Nav2가 담당해야 함 |
| Level 3 | 제한적 가능 | AprilTag pose, 물체 실제 크기 기반 거리 근사, 고정 카메라 homography로 바닥 좌표 근사 | 카메라가 움직이거나 물체 높이가 달라지면 오차가 커짐 |
| Level 4 | 비추천/거의 불가 | 없음 또는 매우 제한적 | depth/PointCloud2가 없어 Nav2 voxel/3D costmap 융합 불가 |
| Level 5 | 조사/보조 가능 | YOLOE/Grounding DINO류로 라벨링 후보 생성, unknown item 조사 | 실시간 주행 제어용으로는 부적합 |

Pi Camera 구성에서 추천하는 데모 범위는 다음과 같다.

1. **AprilTag/QR 기반 ID 검증**: 슬롯, 물품, 도킹 지점에 태그를 붙이고 WMS에 `TAG_DETECTED`, `SLOT_VERIFIED`, `DOCK_TARGET_VISIBLE` 이벤트를 보낸다.
2. **YOLO 기반 후보 감지**: `person`, `box`, `dropped_item_candidate`를 2D bbox로 감지하되, item ID 확정은 태그가 읽혔을 때만 수행한다.
3. **LiDAR/Nav2 기반 회피**: Pi Camera가 사람 후보를 감지해도 직접 `/cmd_vel`을 제어하지 않고, LiDAR/Nav2 상태와 결합해 GUI/WMS evidence로 표시한다.
4. **도킹 보조**: Nav2가 도킹 전방 waypoint까지 이동하고, 마지막 짧은 구간은 Pi Camera가 본 AprilTag pose로 정렬한다.

Pi Camera만으로 어려운 항목은 다음과 같다.

- 일반 물체까지의 안정적인 depth 측정
- 떨어진 물건의 정확한 3D 위치 계산
- 포크/리프트와 물체 사이의 깊이 정렬
- 낮은 장애물/높은 장애물을 Nav2 3D costmap에 직접 반영
- 박스가 바닥/선반/리프트 중 어디에 있는지 안정적으로 구분

## 6. 권장 데이터 파이프라인

### 6.1 전체 구조

```text
Camera / LiDAR
  ├─ /scan                                      # LDS-03 LiDAR, Nav2 권위 센서
  ├─ /global_camera/image_raw                   # 전역 RGB 카메라 1대
  ├─ /global_camera/camera_info
  ├─ /tb3_1/pi_camera/image_raw                 # Robot1 Pi Camera
  ├─ /tb3_1/pi_camera/camera_info
  ├─ /tb3_2/pi_camera/image_raw                 # Robot2 Pi Camera
  └─ /tb3_2/pi_camera/camera_info

ROS2 perception preprocessing
  ├─ image_proc / camera calibration
  ├─ apriltag_ros / ArUco / QR detector
  └─ ROI crop / resize / frame skipping

AI inference
  ├─ YOLO26n or YOLO11n/s detection
  ├─ optional segmentation for 2D mask/overlay only
  └─ ByteTrack/BoT-SORT for temporal stability

Event fusion
  ├─ confidence threshold
  ├─ N-frame confirmation
  ├─ ROI / zone rule
  ├─ tag pose / homography / known-size sanity check
  └─ duplicate event suppression

WMS-lite ingest
  ├─ POST /vision-events
  ├─ item/slot/task/robot/event state transition
  └─ WebSocket broadcast to GUI

GUI
  ├─ Robot Status Evidence Summary
  ├─ Vision Detail Drawer
  └─ Debug Log Drawer
```

### 6.2 VisionEvent 권장 스키마

```json
{
  "event_id": "uuid",
  "timestamp": "2026-06-02T17:00:00+09:00",
  "source": "global_cam_01 | tb3_1_picam | tb3_2_picam",
  "robot_id": "tb3_1",
  "frame_id": "camera_color_optical_frame",
  "event_kind": "CANDIDATE | CONFIRMED | CLEARED | STALE",
  "class_name": "person | box | dropped_item | pallet | unknown",
  "track_id": 12,
  "confidence": 0.83,
  "bbox_xyxy": [120, 80, 260, 210],
  "mask_ref": null,
  "depth_median_m": null,
  "map_pose_estimate": null,
  "roi_id": "STORAGE_A01_ROI",
  "tag_id": "TAG_A01",
  "wms_interpretation": "BOX_CANDIDATE_AT_SLOT",
  "recommended_action": "VERIFY_TAG | WAIT_OBSTACLE_CLEAR | MANUAL_CONFIRM"
}
```

### 6.3 이벤트 확정 정책

초기값 제안:

| 이벤트 | 확정 조건 | WMS 처리 |
| --- | --- | --- |
| PERSON_DETECTED | confidence ≥ 0.55, 3프레임 이상, 로봇 경로 ROI와 겹침 | `DYNAMIC_OBSTACLE` 후보. Nav2/LiDAR 상태와 결합해서 표시 |
| BOX_CANDIDATE | confidence ≥ 0.60, 5프레임 이상, 슬롯/바닥 ROI 내부 | item 후보. 태그 없으면 item ID 확정 금지 |
| DROPPED_ITEM_CANDIDATE | 바닥 ROI + 새 track + 일정 시간 정지 | `ITEM_DROPPED_CANDIDATE`, 수동 확인 또는 재검증 task 생성 |
| TAG_DETECTED | AprilTag/QR decoded + pose valid | item/slot/dock ID 검증 이벤트 |
| VISION_STALE | 카메라 프레임 또는 event N초 이상 없음 | 관련 slot/zone `STALE` 또는 `UNKNOWN` |

핵심: YOLO 감지는 후보이고, **ID 확정은 QR/AprilTag/WMS 정책으로 처리**해야 한다.

## 7. 작업별 설계

### 7.1 사람/장애물 인식 및 회피

권장 설계:

1. 즉시 회피/정지는 LiDAR `/scan` + Nav2 obstacle layer/local costmap이 담당한다.
2. YOLO person detection은 GUI Evidence와 WMS event에 사용한다.
3. WMS는 Nav2 feedback, robot velocity, person candidate를 결합해 `OBSTACLE_BLOCKED`, `WAITING`, `REROUTING`, `RESUMED` 이벤트를 기록한다.

나쁜 설계:

- YOLO person만 보고 `/cmd_vel`을 직접 막는 구조.
- AI가 주행 안전을 단독 책임지는 것처럼 발표하는 구조.

### 7.2 떨어진 물건/박스 후보 인식 후 WMS 전달

권장 설계:

1. 전역 카메라 1대 또는 로봇별 Pi Camera에서 YOLO detection/segmentation.
2. ByteTrack으로 track_id 유지.
3. 바닥 ROI에서 일정 시간 정지한 객체를 dropped item candidate로 분류.
4. depth가 없으므로 전역 카메라 homography, tag pose, known-size 근사만 사용하고 정확한 3D 위치라고 표현하지 않는다.
5. WMS에 `ITEM_DROPPED_CANDIDATE` 이벤트를 전송하고 GUI에서 수동 확인/복구 task를 제공한다.

주의:

- COCO pretrained에는 프로젝트의 “떨어진 물건” 클래스가 없다. 초반에는 `box`, `bottle`, `backpack`, `unknown_object` 등 후보로 표현하고, 이후 직접 데이터셋을 만든다.

### 7.3 WMS item identity

실무적으로는 객체검출이 아니라 **tag identity + WMS state**가 정답이다.

권장:

- item/slot/dock에 QR 또는 AprilTag 부착.
- YOLO는 “박스가 보인다”까지만 말한다.
- QR/AprilTag가 읽히면 item_id/slot_id 확정.
- YOLO box는 있는데 tag가 없으면 `ITEM_TAG_UNREADABLE` 또는 `UNKNOWN_ITEM`으로 처리.

### 7.4 도킹 위치 추정 보조

권장:

- 도킹 스테이션 또는 리프트 target에 AprilTag를 붙인다.
- 로봇 전면 Pi Camera가 tag를 본다.
- `apriltag_ros`가 tag id와 pose/TF를 publish한다.
- Nav2는 dock 전방 waypoint까지 이동하고, 마지막 0.3~0.8 m는 tag pose 기반 미세정렬한다.

초기 파라미터 제안:

- tag family: `36h11`
- tag size: 실제 출력 크기 정확히 측정
- 카메라 calibration 필수
- tag 중심이 포크/리프트 기준축과 맞도록 설치

## 8. 난이도 단계별 로드맵

### Level 0 — 결정론적 비전 이벤트 MVP

- 고정 웹캠 또는 Pi Camera 한 대
- OpenCV QR 또는 AprilTag 검출
- WMS `/vision-events` ingest
- GUI Vision Detail Drawer에 ROI/tag/confidence 표시

성공 기준:

- item/slot/dock tag를 읽고 WMS 이벤트가 남는다.
- AI 없이도 Normal Flow, Slot Verify, Dock Verify demo가 가능하다.

### Level 1 — YOLO 후보 감지

- YOLO26n 또는 YOLO11n/s로 `person`, `box-like object` 감지
- frame skipping, ROI crop, confidence threshold
- WMS에는 `CANDIDATE` 이벤트만 전달

성공 기준:

- 사람이 지나가면 GUI에 `PERSON_DETECTED_CANDIDATE`가 보인다.
- 박스 후보가 보이면 `BOX_CANDIDATE`가 보이지만 item ID는 확정하지 않는다.

### Level 2 — Nav2 예외 흐름 연결

- LiDAR/Nav2 obstacle layer로 실제 정지/대기/재계획
- YOLO person event와 Nav2 blocked feedback을 WMS에서 결합
- GUI에 “AI evidence + Nav2 action” 분리 표시

성공 기준:

- 경로에 장애물이 있으면 로봇 상태가 WAITING/REROUTING으로 바뀐다.
- 이벤트 로그가 “LiDAR/Nav2가 주행 제어, YOLO가 근거 표시”를 설명한다.

### Level 3 — 거리/위치 추정: Pi Camera 제한형 또는 D435 확장형

- Pi Camera만 쓸 경우: AprilTag pose, 물체 실제 크기 기반 거리 근사, 고정 카메라 homography로 바닥 좌표를 근사한다.
- D435를 쓸 경우: RGB+depth aligned stream, YOLO-seg 또는 bbox depth median으로 더 안정적인 거리 추정을 수행한다.
- WMS에는 `DISTANCE_ESTIMATED`, `DROPPED_ITEM_CANDIDATE`, `VISION_STALE` 같은 이벤트를 보낸다.

성공 기준:

- Pi Camera 구성에서는 tag/dock/slot 중심의 제한적 위치 보정이 가능하다.
- D435 구성에서는 낙하물 후보의 거리 또는 map 근사 위치를 WMS 이벤트로 보낸다.

### Level 4 — Depth/PointCloud와 Nav2 costmap 융합

- D435 PointCloud2를 Nav2 obstacle/voxel layer에 추가
- TF, extrinsics, pointcloud filtering, voxel tuning
- LiDAR가 놓치는 낮거나 높은 장애물 보조

성공 기준:

- depth obstacle이 local costmap에 반영된다.
- false obstacle/noise를 RViz에서 튜닝할 수 있다.

난이도 높음: Wi-Fi, CPU, USB3, TF, depth noise, voxel parameter를 동시에 잡아야 한다.

### Level 5 — SOTA/open-world 고도화

- YOLOE/YOLO-World/Grounding DINO로 unknown item 라벨링 보조
- YOLOv13/RT-DETRv2 성능 비교
- custom dataset + active learning
- 2대 로봇 협업 이벤트와 WMS recovery policy 고도화

성공 기준:

- 새 물품 유형을 빠르게 추가할 수 있다.
- 최신 SOTA 조사와 실제 데모 구현 경계를 명확히 설명한다.

## 9. 추천 데모 구현안

최소 성공 경로:

1. **카메라 구성**: 전역 카메라 1대(`global_cam_01`) + Robot1/Robot2 Pi Camera 각 1대(`tb3_1_picam`, `tb3_2_picam`)
2. **ID 인식**: QR/AprilTag/ArUco
3. **AI 모델**: YOLO26n 또는 YOLO11n
4. **장애물 제어**: LDS-03 LiDAR/Nav2 only
5. **WMS 이벤트**: VisionEvent schema로 FastAPI ingest
6. **GUI**: Vision Detail Drawer와 Debug Log Drawer

추천 확장:

1. 전역 카메라 + 로봇별 Pi Camera + AprilTag/QR/ArUco + YOLO 후보 감지로 Level 0~2를 먼저 완성
2. depth/PointCloud2 경로는 MVP1에서 제외하고, 위치 추정은 전역 카메라 homography 또는 Pi Camera tag pose로 제한한다.
3. custom dataset으로 box/dropped_item fine-tune
4. 도킹은 YOLO가 아니라 Pi Camera의 AprilTag/ArUco pose로 구현

2대 TurtleBot3 운용은 다음처럼 나누는 것이 현실적이다.

| 로봇 | 권장 역할 | 비전 구성 |
| --- | --- | --- |
| Robot1 | 이동 중 근접 태그/도킹/물품 검증 | Pi Camera + QR/AprilTag/ArUco + YOLO 후보 감지 |
| Robot2 | 동일 구성의 반복 검증 및 2대 운용 흐름 | Pi Camera + QR/AprilTag/ArUco + YOLO 후보 감지 |
| 전역 카메라 | 슬롯/구역/장애물 후보 overview | Global RGB camera 1대 + ROI/homography 기반 2D 근사 |

두 로봇 모두 depth camera 없이 동일한 Pi Camera 기반 검증 경로를 사용하고, 전역 카메라가 슬롯/구역 overview를 보완한다.

## 10. 하드웨어/성능 운용 가이드

| 항목 | 권장 초기값 |
| --- | --- |
| YOLO 입력 크기 | 320 또는 640 |
| detector FPS | 5~15 FPS부터 시작 |
| GUI overlay FPS | control state보다 낮아도 됨 |
| Pi Camera RGB | 640×480, 10~15fps부터 시작 |
| robot-mounted camera stream | compressed image transport 고려 |
| WMS event rate | 같은 track은 1~2초 debounce |
| person confirmation | 3 frames 이상 |
| dropped item confirmation | 5 frames 이상 + 위치 정지 |

## 11. 리스크와 완화책

| 리스크 | 영향 | 완화책 |
| --- | --- | --- |
| YOLO false positive | WMS 상태 오염 | CANDIDATE/CONFIRMED 분리, N-frame 확인, ROI 제한 |
| 태그 미검출 | item/slot 확정 실패 | tag 크기 확대, 조명, 카메라 calibration, 재시도 flow |
| AI 역할 과장 | 발표 신뢰도 저하 | LiDAR/Nav2가 주행 제어를 담당하고, 비전은 인식 evidence를 제공한다는 점을 명확히 표시 |
| 최신 모델 설치 문제 | 일정 지연 | YOLO11 fallback, 작은 모델부터 벤치마크 |

## 12. 다음 조사/구현 체크리스트

- [ ] 중앙 PC GPU 유무 확인
- [ ] TurtleBot3 정확한 SBC/Raspberry Pi 버전 확인
- [x] 2026-06-09 결정: MVP1은 전역 카메라 1대 + 로봇별 Pi Camera 1대, 로봇 depth camera/D435 제외. Level 0~2 우선 구현.
- [ ] dock/slot/item marker 크기와 위치 결정
- [ ] VisionEvent API schema 확정
- [ ] AI Server Python 환경 고정: `uv`/`.venv`, lockfile, `.env.example`, package pinning
- [ ] Git repository/branch 전략 확정: contract-first merge, feature branches, integration branch
- [ ] confidence/N-frame/stale timeout 정책 확정
- [ ] YOLO26 vs YOLO11 작은 모델 벤치마크
- [ ] custom dataset 수집 계획 수립: person, box, dropped_item, slot occupancy, fork/lift pose

## 13. 주요 참고 소스

- Ultralytics YOLO26 Docs: https://docs.ultralytics.com/models/yolo26/
- Ultralytics YOLO11 Docs: https://docs.ultralytics.com/models/yolo11/
- Ultralytics ROS Quickstart: https://docs.ultralytics.com/guides/ros-quickstart/
- YOLOv10 paper: https://arxiv.org/abs/2405.14458
- YOLOv12 paper: https://arxiv.org/abs/2502.12524
- YOLOv13 paper: https://arxiv.org/abs/2506.17733
- RT-DETRv2 paper: https://arxiv.org/abs/2407.17140
- YOLO-World paper: https://arxiv.org/abs/2401.17270
- YOLOE Docs: https://docs.ultralytics.com/models/yoloe/
- Grounding DINO paper: https://arxiv.org/abs/2303.05499
- apriltag_ros Jazzy docs: https://docs.ros.org/en/jazzy/p/apriltag_ros/index.html
- ROS image_pipeline docs: https://docs.ros.org/en/ros2_packages/rolling/api/image_pipeline/
- RealSense D435 product page: https://www.realsenseai.com/products/stereo-depth-camera-d435/
- realsense-ros wrapper: https://github.com/realsenseai/realsense-ros
- TurtleBot3 official features/spec: https://emanual.robotis.com/docs/en/platform/turtlebot3/features/
- Nav2 mapping/localization and costmap guide: https://docs.nav2.org/setup_guides/sensors/mapping_localization.html
- Nav2 transformations guide: https://docs.nav2.org/setup_guides/transformation/setup_transforms.html
- Nav2 docking server docs: https://docs.nav2.org/configuration/packages/configuring-docking-server.html
- Nav2 voxel layer docs: https://docs.nav2.org/configuration/packages/costmap-plugins/voxel.html
- Open Navigation docking repository: https://github.com/open-navigation/opennav_docking
- SLAM Toolbox Jazzy docs: https://docs.ros.org/en/ros2_packages/jazzy/api/slam_toolbox/
