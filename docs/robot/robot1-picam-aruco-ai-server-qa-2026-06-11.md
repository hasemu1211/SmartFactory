# Robot1 PiCam → AI Server ArUco QA 기록 — 2026-06-11

## 요약

2026-06-11 Asia/Seoul에 Robot1 Pi Camera의 compressed ROS2 이미지 스트림을 SmartFactory AI Server까지 연결해 ArUco 검출 이벤트가 생성되는지 실기 검증했다.

검증 결론:

```text
Robot1 PiCam
  -> /camera/image_raw/compressed
  -> smartfactory_perception_ros image_snapshot_client
  -> AI Server POST /api/v1/detect/image
  -> GET /api/v1/detections/latest
  -> ARUCO_4X4_50_0 event 확인
```

결과는 **성공**이다.

## 범위와 안전 기준

대상:

- Robot1: `192.168.10.75`
- Robot2: 사용 중이라 접근하지 않음
- Global camera: 아직 준비되지 않아 제외
- WMS/Main emit: `emit=false`로 제외
- Robot movement: 없음

이번 QA에서 허용한 로봇 쪽 작업:

- Robot1 SSH 접속
- 상태 확인 명령
- 필요 시 `ros2 launch turtlebot3_bringup camera.launch.py` 실행/중지/재시작

실제로는 `/camera/image_raw/compressed`가 이미 정상이라 **Robot1 camera launch를 재시작하지 않았다**.

이번 QA에서 하지 않은 작업:

- 로봇 파일 수정 없음
- 로봇 `.bashrc`, `.envrc`, ROS/DDS 설정 수정 없음
- 패키지 설치/삭제 없음
- systemd/reboot/shutdown/network 변경 없음
- Robot2 접근 없음
- `/cmd_vel`, `/motor_power` 제어 없음

## 사전 검증 결과

AI Server가 꺼져 있으면 SmartFactory repo root에서 먼저 실행한다.

```bash
cd /home/codelab/Desktop/Project/SmartFactory
./scripts/ai/run_ai_server.sh
```

AI Server 상태:

```bash
curl -fsS http://127.0.0.1:8100/api/v1/health
```

정상 응답 확인:

```text
status=ok
contract_version=vision-event.v1
sources=[global_cam_01, tb3_1_picam, tb3_2_picam]
```

Robot1 compressed topic 상태:

```bash
ros2 topic info /camera/image_raw/compressed -v
```

확인 결과:

```text
Type: sensor_msgs/msg/CompressedImage
Publisher count: 1
Node name: camera
Node namespace: /
Reliability: RELIABLE
Durability: VOLATILE
```

수신률:

```bash
timeout 8 ros2 topic hz /camera/image_raw/compressed
```

확인 결과:

```text
average rate: about 30 Hz
```

비교 참고:

- `/camera/image_raw`: 약 13 Hz
- `/camera/image_raw/compressed`: 약 30 Hz

따라서 Robot PiCam 경로는 compressed transport를 우선 사용한다.

## 사용한 OpenCV 라이브 확인 도구

위치:

```text
/home/codelab/opencv_test/src
```

안전하게 사용 가능한 스크립트:

```text
camera_viewer.py   # 화면 확인만 수행
aruco_detector.py  # 화면 확인 + ArUco ID 표시만 수행
```

실행 예:

```bash
cd /home/codelab/opencv_test
source /opt/ros/jazzy/setup.bash
source /home/codelab/turtlebot3_ws/install/setup.bash
source /home/codelab/venv/venv/bin/activate
python3 src/aruco_detector.py
```

`aruco_detector.py`는 `/camera/image_raw/compressed`를 구독하고 OpenCV 창 `ArUco Detector`에 영상과 감지 ID를 표시한다.

주의: 이번 QA에서는 아래 스크립트를 사용하지 않는다.

```text
aruco_robot_control.py
aruco_marker4_follower.py
```

이 두 스크립트는 `/cmd_vel`, `/motor_power` 등 로봇 제어에 영향을 줄 수 있으므로 단순 시각 QA에는 부적합하다.

## 사용자 마커 표시 절차

1. 사용자가 폰에 ArUco 이미지를 크게 띄운다.
2. `ArUco Detector` 창에서 마커가 보이도록 위치를 맞춘다.
3. 마커 네 귀퉁이가 모두 보이게 한다.
4. 화면 밝기를 높이고, 반사가 심하면 각도를 살짝 조정한다.
5. 너무 가까워서 잘리면 조금 뒤로 뺀다.
6. detector 로그나 창에서 `ID: 0`이 안정적으로 표시되는지 확인한다.

실제 로그에서 확인한 viewer 감지:

```text
[aruco_detector_node]: 감지된 마커 ID: 0
```

## AI Server adapter 실행 절차

마커가 OpenCV viewer에서 안정적으로 잡힌 뒤, 중앙 PC에서 adapter를 실행한다.

```bash
cd /home/codelab/Desktop/Project/SmartFactory
source /opt/ros/jazzy/setup.bash
source /home/codelab/turtlebot3_ws/install/setup.bash

ros2 run smartfactory_perception_ros image_snapshot_client --ros-args \
  -p source_id:=tb3_1_picam \
  -p image_topic:=/camera/image_raw/compressed \
  -p image_transport:=compressed \
  -p ai_server_url:=http://127.0.0.1:8100 \
  -p snapshot_period_sec:=0.5 \
  -p request_timeout_sec:=1.0 \
  -p emit:=false
```

이번 검증에서는 `timeout 12`로 약 12초 동안 실행했다.

마커 표시 구간:

```text
MARKER_WINDOW_START: 2026-06-11T12:14:15+09:00
MARKER_WINDOW_END:   2026-06-11T12:14:28+09:00
```

## AI Server 검출 결과

조회 명령:

```bash
curl -fsS 'http://127.0.0.1:8100/api/v1/detections/latest?source=tb3_1_picam&limit=10'
```

검증 결과:

- 유효 이벤트 수: 10개
- 모든 유효 이벤트 timestamp가 마커 표시 구간 안에 있음
- `source`: `tb3_1_picam`
- `robot_id`: `tb3_1`
- `class_name`: `aruco_marker`
- `marker_id`: `ARUCO_4X4_50_0`
- `frame_id`: `tb3_1_pi_camera_optical_frame`
- `wms_hint`: `TAG_DETECTED`
- `metadata.image_width`: `640`
- `metadata.image_height`: `480`
- bbox가 이미지 범위 안에 있음

대표 이벤트:

```json
{
  "timestamp": "2026-06-11T12:14:27.701600+09:00",
  "source": "tb3_1_picam",
  "robot_id": "tb3_1",
  "class_name": "aruco_marker",
  "marker_id": "ARUCO_4X4_50_0",
  "bbox_xyxy": [192.0, 187.0, 306.0, 299.0],
  "wms_hint": "TAG_DETECTED",
  "metadata": {
    "model": "opencv-aruco-4x4-50",
    "image_width": 640,
    "image_height": 480,
    "latency_ms": 1.766
  }
}
```

로컬 QA artifact:

```text
.omx/reports/robot1-picam-aruco-qa-20260611_121455.json
```

## 성공 판정 기준

이번 절차는 아래 기준을 모두 만족하면 성공으로 본다.

- `/camera/image_raw/compressed`가 `sensor_msgs/msg/CompressedImage`로 보인다.
- publisher count가 1 이상이다.
- topic hz가 약 30 Hz 수준으로 수신된다.
- AI Server `/api/v1/health`가 `status=ok`를 반환한다.
- adapter가 `source_id=tb3_1_picam`, `image_transport=compressed`, `emit=false`로 실행된다.
- AI Server 로그에 `POST /api/v1/detect/image` HTTP 200이 찍힌다.
- latest detections에 마커 표시 구간 내 `aruco_marker` 이벤트가 생성된다.
- bbox가 이벤트의 `metadata.image_width` / `metadata.image_height` 범위 안에 있다.

## 실패 시 점검 순서

로봇 설정을 바꾸기 전에 아래 순서로 확인한다.

1. OpenCV viewer에서 마커가 실제 화면 안에 있는지 확인한다.
2. 폰 밝기를 올린다.
3. 마커 네 귀퉁이가 잘리지 않도록 거리를 조정한다.
4. 화면 반사가 심하면 각도를 바꾼다.
5. `/camera/image_raw/compressed` topic info/hz를 다시 확인한다.
6. AI Server `/api/v1/health`를 확인한다.
7. AI Server 로그에서 POST 200 여부를 확인한다.
8. 그래도 실패하면 compressed snapshot을 저장해 실제 프레임을 시각 확인한다.

snapshot 저장 예:

```bash
cd /home/codelab/Desktop/Project/SmartFactory
python3 .omx/tmp/capture_ros_compressed_image_once.py \
  --topic /camera/image_raw/compressed \
  --out .omx/reports/robot1-picam-debug.png \
  --timeout 8
```

## 다음 작업

1. Robot2가 사용 가능해지면 동일 절차로 `tb3_2_picam`을 검증한다.
2. Robot1/Robot2를 동시에 운용하려면 camera topic namespace/remap 전략을 별도 설계한다.
3. namespace/remap, 로봇 파일 수정, 환경 설정 수정은 공유 로봇에 영향을 주므로 사용자 허가 후 진행한다.
4. global camera가 준비되면 동일한 adapter 방식으로 `global_cam_01`을 추가 검증한다.
5. WMS/Main emit은 현재 `emit=false`로 검증했으므로, 실제 운영 전 별도 contract/장애 처리 정책을 확인한다.
