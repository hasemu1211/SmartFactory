# SmartFactory scripts 사용법

이 문서는 “무엇을 할 때 어떤 스크립트를 실행하는지”만 정리한 운영자용 안내입니다.
긴 설계 설명은 별도 `docs/` 문서를 보세요.

## 기본 원칙

- 장시간 실행되는 Vision live 프로세스는 tmux `Smartfactory:3:Development` 안에서 실행하세요.
- 평소에는 `sf_lab.sh`만 쓰면 됩니다.
- 하위 profile 디버깅이 필요할 때만 `sf_vision.sh`를 직접 씁니다.

## 가장 많이 쓰는 명령

```bash
# 저부하 실행: GoPro full + tb3_1/tb3_2 PiCam WebRTC, lift_roi WebRTC 끔
./scripts/vision/sf_lab.sh low-load

# 전체 실행: GoPro full+lift_roi + tb3_1/tb3_2 + AI Server + MJPEG fallback + mDNS
./scripts/vision/sf_lab.sh all

# 현재 상태 확인
./scripts/vision/sf_lab.sh status

# Main/브라우저에서 열 URL 확인
./scripts/vision/sf_lab.sh urls

# 종료
./scripts/vision/sf_lab.sh down
```

## 목적별로 무엇을 실행하나

| 하고 싶은 일 | 실행 명령 | 설명 |
|---|---|---|
| 저부하 lab vision 켜기 | `./scripts/vision/sf_lab.sh low-load` | 노트북/약한 PC 권장. GoPro full + tb3_1/tb3_2 PiCam WebRTC를 켜고, lift_roi WebRTC만 끕니다. |
| 전체 lab vision 켜기 | `./scripts/vision/sf_lab.sh all` | lift_roi WebRTC까지 필요할 때. GoPro + PiCam + AI Server + WebRTC/MJPEG fallback을 켭니다. |
| 상태 확인 | `./scripts/vision/sf_lab.sh status` | 살아있는 프로세스, WebRTC/MJPEG 상태, GoPro/PiCam 상태를 봅니다. |
| URL 확인 | `./scripts/vision/sf_lab.sh urls low-load` | 선택한 profile 기준으로 활성 WebRTC URL과 fallback URL을 출력합니다. |
| 종료 | `./scripts/vision/sf_lab.sh down` | Vision 관련 live 프로세스를 내립니다. |
| health 확인 | `./scripts/vision/sf_lab.sh api health` | AI Server health를 확인합니다. |
| stream 계약 확인 | `./scripts/vision/sf_lab.sh api streams` | Main이 읽을 stream discovery JSON을 확인합니다. |
| 증거 API 계획 확인 | `./scripts/vision/sf_lab.sh api evidence-plan PICKUP` | 하드웨어 없이 증거 판단 요청 형태를 봅니다. |
| 증거 API mock 확인 | `./scripts/vision/sf_lab.sh api evidence-mock DROPOFF` | Main DB 변경 없이 mock 응답을 확인합니다. |
| 실행 중 평가 호출 | `./scripts/vision/sf_lab.sh api evaluate-no-frame global_cam_01 lift_roi PICKUP` | 최신 프레임이 없어도 API 응답 형태를 확인합니다. |
| 품질 평가 호출 | `./scripts/vision/sf_lab.sh api evaluate-quality global_cam_01 full` | 현재 영상 품질/평가 응답을 확인합니다. |

## 로봇 Pi camera 준비

Vision PC에서 `sf_lab.sh all`을 켜기 전에, 사용할 로봇 쪽 SSH 터미널에서 카메라 bringup을 켭니다.

```bash
# tb3_1 카메라
ROS_DOMAIN_ID=2 ros2 launch turtlebot3_bringup camera_low_bandwidth.launch.py

# tb3_2 카메라를 쓸 때
ROS_DOMAIN_ID=5 ros2 launch turtlebot3_bringup camera_low_bandwidth.launch.py
```

로봇 Pi에는 위 카메라 bringup 외 추가 WebRTC/AI 프로세스를 올리지 않습니다.

## Main 화면 확인

```text
http://smartfactory-main.local:8088/operate/control
```

Main이 받을 수 있는 주요 URL은 아래 명령으로 확인합니다.

```bash
./scripts/vision/sf_lab.sh urls
./scripts/vision/sf_lab.sh urls low-load
./scripts/vision/sf_lab.sh api streams
```

Main 화면에 `MJPEG·poll`이 보이면 먼저 아래만 확인하세요.

```bash
./scripts/vision/sf_lab.sh status
./scripts/vision/sf_lab.sh urls
./scripts/vision/sf_vision.sh logs gopro-adapter
./scripts/vision/sf_vision.sh logs webrtc-sidecar
```

## 하위 profile을 직접 쓸 때

평소에는 필요 없습니다. profile 확인/디버깅 때만 씁니다.

```bash
# profile 목록
./scripts/vision/sf_vision.sh profiles

# 저부하 WebRTC profile 사전 점검
./scripts/vision/sf_vision.sh check lab-gopro-tb3-low-load

# 전체 WebRTC profile 사전 점검
./scripts/vision/sf_vision.sh check lab-gopro-tb3-ffmpeg-first

# 전체 WebRTC profile 직접 실행
./scripts/vision/sf_vision.sh up lab-gopro-tb3-ffmpeg-first

# 상태/스모크/로그/종료
./scripts/vision/sf_vision.sh status
./scripts/vision/sf_vision.sh smoke
./scripts/vision/sf_vision.sh logs
./scripts/vision/sf_vision.sh down
```

## Make alias

```bash
make vision-lab-all
make vision-lab-status
make vision-lab-urls
make vision-lab-api-plan OPERATION=PICKUP
make vision-lab-down
```

## 기본 profile

| Profile | 언제 쓰나 |
|---|---|
| `lab-gopro-tb3-low-load` | 저부하 권장. GoPro full + tb3_1/tb3_2 PiCam WebRTC를 실행하고, lift_roi WebRTC만 끕니다. |
| `lab-gopro-tb3-ffmpeg-first` | 전체 WebRTC. GoPro full + lift ROI + tb3_1/tb3_2 WebRTC, MJPEG fallback으로 실행. |
| `lab-gopro-tb3` | WebRTC보다 기존 MJPEG 안정 경로를 우선 확인할 때. |
| `tb3-live-webrtc` | GoPro 없이 tb3_1 PiCam만 WebRTC로 확인할 때. |
| `local-smoke` | 하드웨어 없이 API/gateway smoke만 할 때. |

## 저부하 WebRTC URL

```text
http://smartfactory-vision.local:8889/global_cam_01_full/
http://smartfactory-vision.local:8889/tb3_1_picam_full/
http://smartfactory-vision.local:8889/tb3_2_picam_full/
```

## 전체 WebRTC 추가 URL

```text
http://smartfactory-vision.local:8889/global_cam_01_lift_roi/
```

## 기본 MJPEG fallback URL

```text
http://smartfactory-vision.local:8090/api/v1/vision/overlay/stream?source=global_cam_01&view=full&max_fps=30
http://smartfactory-vision.local:8090/api/v1/vision/overlay/stream?source=global_cam_01&view=lift_roi&max_fps=30
http://smartfactory-vision.local:8090/api/v1/vision/overlay/stream?source=tb3_1_picam&view=full&max_fps=30
http://smartfactory-vision.local:8090/api/v1/vision/overlay/stream?source=tb3_2_picam&view=full&max_fps=30
```

## mediamtx / ffmpeg 확인

```bash
./scripts/vision/run_webrtc_sidecar_mediamtx.sh --check
./scripts/vision/run_webrtc_sidecar_mediamtx.sh --status
```

`mediamtx`가 PATH에 없으면 다음처럼 경로를 지정할 수 있습니다.

```bash
export MEDIAMTX_BIN=/absolute/path/to/mediamtx
```
