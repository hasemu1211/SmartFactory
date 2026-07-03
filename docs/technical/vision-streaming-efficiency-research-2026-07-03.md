# SmartFactory Vision 스트리밍 경로 효율화 리서치 — low-load 기준

- 작성일: 2026-07-03
- 로컬 기준 프로젝트: `/home/codelab/Desktop/Project/SmartFactory`
- 운용 기준: `./scripts/vision/sf_lab.sh low-load` → `lab-gopro-tb3-low-load`
- 목적: 로봇 PiCam + 글로벌캠 스트리밍을 **낮은 프로세스 부하**, **낮은 지연**, **버벅임 적음**, **품질 유지** 기준으로 비교하고 drive 개발 쪽이 참고할 의사결정 근거를 남긴다.
- 현재 하드웨어 상태: `./scripts/vision/sf_lab.sh check low-load` 기준 GoPro/global cam USB는 `not detected`. 따라서 글로벌캠은 현재 live 측정이 아니라 config/code/과거 runtime evidence 기반 분석이다.
- 검증 세션: `RESEARCH/vision_streaming_efficiency_20260703/` (`validate_ledger.py` 통과, verified=6)

## 1. 결론 요약

1. **현재 `low-load`의 공개 WebRTC 1차 경로는 MJPEG-derived가 아니다.**
   - `global_cam_01/full`, `tb3_1_picam/full`, `tb3_2_picam/full`은 MediaMTX path를 만들고, Vision PC의 compositor가 H264/RTSP로 publish하는 구조다.
   - MJPEG `:8090` overlay/frame stream은 fallback/diagnostic URL로 남아 있다.

2. **“UDP로 바꾸면 효율적”이 아니라 “어떤 codec을 UDP에 싣느냐”가 핵심이다.**
   - `H264 RTP/RTSP/MPEG-TS over UDP/TCP`처럼 inter-frame video codec을 쓰면 효율/품질/브라우저 스트리밍에 유리하다.
   - `MJPEG/JPEG frame over HTTP/UDP`는 각 프레임을 독립 JPEG로 보내는 성격이라 대역폭·화질 효율에서 불리하고, 네트워크/CPU 흔들림 시 버벅임이 커질 수 있다.

3. **로봇 안정성이 우선이면 현재 low-load 방향이 가장 안전한 기본값이다.**
   - 로봇 Pi는 기존 camera bringup만 수행하고, Vision PC가 AI/overlay/H264 encode/MediaMTX를 담당한다.
   - 로봇 쪽에 GStreamer H264 송출을 올리면 Vision PC 부하는 줄 수 있지만, 로봇 CPU/열/네트워크/DDS/Nav2 안정성 리스크를 새로 만든다. 이는 실험 브랜치에서 A/B 계측 후 승격해야 한다.

4. **글로벌캠은 현재 연결되어 있지 않아 live 판단은 보류다.**
   - low-load profile은 global full만 WebRTC로 공개하고 lift_roi WebRTC를 꺼서 load를 줄인다.
   - 과거 증거상 GoPro adapter와 AI server CPU가 큰 비중을 차지했다. 다음 최적화 후보는 “MediaMTX-first direct H264/TS” 또는 “clean media + Main canvas overlay”이지만, 현재 public contract가 burned-in overlay라서 바로 바꾸면 Main 쪽 변경/검증이 필요하다.

## 2. 현재 `low-load` 실제 경로

### 2.1 low-load가 켜는 스트림

`sf_lab.sh`는 `low-load|lowload|lite`를 `lab-gopro-tb3-low-load`로 매핑한다 (`scripts/vision/sf_lab.sh:70-75`, `:192-194`, `:519`). 해당 profile 설명은 다음과 같다.

- GoPro/global cam full WebRTC on
- `tb3_1_picam/full`, `tb3_2_picam/full` WebRTC on
- `global_cam_01/lift_roi` WebRTC off
- MJPEG fallback 및 evidence API helper는 유지
- robot-side camera launch는 manual/safety-owned (`config/vision/profiles/lab-gopro-tb3-low-load.env:1-9`)

`./scripts/vision/sf_lab.sh urls low-load` 기준 active WebRTC URL:

```text
http://smartfactory-vision.local:8889/global_cam_01_full/
http://smartfactory-vision.local:8889/global_cam_01_full/whep
http://smartfactory-vision.local:8889/tb3_1_picam_full/
http://smartfactory-vision.local:8889/tb3_1_picam_full/whep
http://smartfactory-vision.local:8889/tb3_2_picam_full/
http://smartfactory-vision.local:8889/tb3_2_picam_full/whep
```

Disabled WebRTC:

```text
global_cam_01/lift_roi
```

### 2.2 로봇 PiCam 현재 경로

```text
Robot Pi camera_ros
  -> ROS /camera/image_raw/compressed (domain 2 or 5)
  -> Vision PC ROS gateway (latest-frame, keep-last/drop-stale)
  -> AI Server frame/process + latest frame store
  -> run_latest_frame_compositor.py burns overlay at media FPS
  -> ffmpeg libx264 zerolatency -> RTSP 127.0.0.1:18554/<path>
  -> MediaMTX -> WebRTC/WHEP :8889
  -> Main/browser
```

근거:

- low-load profile source topics: `/camera/image_raw/compressed`, domains 2/5 (`lab-gopro-tb3-low-load.env:36-49`).
- ROS gateway는 passive sidecar이며 motion/control/Nav2를 만들지 않는다 (`vision_frame_gateway.py:66-72`).
- image QoS depth 1, async pipeline, latest message 저장/중복 skip/replaced work 방식이다 (`vision_frame_gateway.py:91-120`, `:218-243`, `:326-356`).
- compressed image가 이미 JPEG/PNG면 bytes를 유지해 불필요한 decode/re-encode를 피한다 (`image_snapshot_client.py:84-95`).
- PiCam compositor는 AI polling cadence와 media output cadence를 분리한다 (`run_latest_frame_compositor.py:160-161`).
- public RTSP/H264 publish는 `RawVideoRtspPublisher`가 raw BGR frame을 ffmpeg `libx264`, `-tune zerolatency`, GOP, `-bf 0`, RTSP/TCP로 보낸다 (`burned_overlay_compositor.py:360-443`).

### 2.3 글로벌캠 현재 low-load 경로

현재 global cam은 연결되어 있지 않지만 profile/code상 경로는 다음이다.

```text
GoPro/global cam TS UDP input udp://0.0.0.0:8554
  -> run_gopro_smart_roi_adapter.py latest capture
  -> AI monitor 5fps, media stream target 20fps
  -> burned overlay full compositor only (lift_roi WebRTC disabled)
  -> ffmpeg libx264 zerolatency -> RTSP 127.0.0.1:18554/global_cam_01_full
  -> MediaMTX -> WebRTC/WHEP :8889
  -> Main/browser
```

근거:

- low-load profile: `GOPRO_INPUT=udp://0.0.0.0:8554`, `GOPRO_STREAM_TARGET_FPS=20`, `GOPRO_AI_MONITOR_FPS=5`, `GOPRO_PUBLISH_WEBRTC=true`, `GOPRO_PUBLISH_ROI_WEBRTC=false`, full output `960x540`, bitrate `1600k`, GOP `10` (`lab-gopro-tb3-low-load.env:51-87`).
- GoPro adapter arg help도 “WebRTC compositor output FPS; AI processing still uses --target-fps”로 media/AI cadence를 분리한다 (`run_gopro_smart_roi_adapter.py:705-714`).
- compositor publish는 full/ROI를 RTSP URL로 publish하되 low-load에서는 ROI publish가 disabled다 (`run_gopro_smart_roi_adapter.py:560-574`, `:741-754`).

### 2.4 MediaMTX sidecar 역할

현재 low-load의 sidecar는 public paths에 대해 **receiver/server** 역할이다.

```text
Vision PC compositor publisher -> RTSP localhost 18554 -> MediaMTX path source=publisher
MediaMTX -> WebRTC browser/WHEP :8889, ICE UDP :8189
```

근거:

- `.run/vision/webrtc-sidecar/mediamtx.yml`: RTSP `127.0.0.1:18554`, WebRTC `:8889`, ICE UDP `:8189`, paths `source: publisher`.
- `--print-config`: 각 stream의 `transport_origin=vision_pc_compositor_publisher`, `mediamtx_source=publisher`, metrics path 지정.
- sidecar docs: recommended lab profile에서 sidecar는 receiver-only이고, public WebRTC path는 Vision-PC compositor가 H264/RTSP로 publish한다. `raw_frame_compositor_h264_webrtc`가 current primary, `http_mjpeg_gateway`는 fallback, `mjpeg_overlay_h264_transcode_webrtc`는 legacy/diagnostic/rollback이다 (`docs/setup/webrtc-mediamtx-sidecar.md:76-83`).

## 3. 경로별 효율·품질 비교

| 후보 경로 | 프로세스 부하 위치 | 지연/버벅임 | 품질 | overlay | 운영 리스크 | 판정 |
|---|---|---|---|---|---|---|
| A. 현재 low-load: Robot compressed image / GoPro input -> Vision-PC compositor H264 -> MediaMTX WebRTC | Vision PC가 AI/overlay/H264 encode 담당. Robot Pi 추가 부담 작음 | media FPS와 AI FPS 분리 가능. fixed canvas/H264 zerolatency로 브라우저 안정성 좋음 | PiCam은 원본 JPEG 한계 + H264 재인코딩 손실, global은 profile상 960x540/1600k | burned-in overlay 보장 | Vision PC CPU 필요. global cam live 미검증 | **현재 추천 기본값** |
| B. Robot Pi hardware H264 -> RTSP/RTP/MPEG-TS -> MediaMTX -> WebRTC | Robot Pi가 capture/encode/network 송출 담당. Vision PC encode 감소 가능 | source-native H264면 낮은 지연 가능 | JPEG 경유보다 유리할 가능성 | clean이면 Main canvas overlay 필요. burned-in 유지하려면 Vision PC compositor 재개입 | Nav2/SLAM과 CPU/열/네트워크 경합 가능. 실측 필요 | **실험 후보** |
| C. MJPEG overlay -> ffmpeg H264 -> MediaMTX WebRTC | Vision PC HTTP/JPEG decode + H264 encode | overlay/AI cadence에 묶일 수 있고 HTTP multipart churn 있음 | JPEG->H264 이중 손실 | burned-in overlay | 과거 log에서 반복 restart 흔적 | **fallback/diagnostic만** |
| D. Browser direct MJPEG fallback | AI/gateway가 JPEG multipart 제공, 브라우저 decode | 단순하지만 대역폭/CPU/네트워크 흔들림에 취약 | 같은 bitrate 대비 H264보다 불리 | overlay endpoint면 burned-in | 디버깅은 쉬움, 스케일 낮음 | **최후 fallback** |
| E. Raw ROS/base64/WebSocket/rosbridge image | ROS/web bridge CPU·bandwidth 큼 | JSON/base64 overhead, stale frame 위험 | raw면 품질은 유지되나 네트워크 비효율 | 별도 처리 필요 | 전체 ROS graph 노출/보안/제어 위험 | **피해야 함** |

## 4. “로봇 UDP 브링업 -> WebRTC”에 대한 판단

### 4.1 UDP 자체는 답이 아니다

UDP는 transport일 뿐이다. 효율은 아래 조합에서 결정된다.

- 좋은 방향: `camera -> H264 hardware encode -> RTP/RTSP/MPEG-TS -> MediaMTX -> WebRTC`
- 나쁜/제한적 방향: `camera -> JPEG/MJPEG frame -> UDP/HTTP -> browser/transcode`

MediaMTX는 RTSP, WebRTC, MPEG-TS, RTP 등 다양한 protocol publish/read와 protocol conversion을 지원한다. GStreamer도 RTSP client, MPEG-TS over UDP, WHIP/WebRTC publish가 가능하고, MediaMTX docs는 GStreamer publish 방식 중 RTSP client를 권장한다.

### 4.2 현재 로봇에서 가능한 실험 근거

SSH read-only probe에서 확인된 사항:

- robot: Ubuntu 24.04.4 aarch64, ROS Jazzy.
- current `RMW_IMPLEMENTATION=rmw_fastrtps_cpp`, `ROS_DOMAIN_ID=2`.
- 현재 probe 시점에는 camera bringup이 실행 중이 아니어서 `/camera/image_raw/compressed` live hz는 측정 불가.
- `/dev/video11`에 H264/MJPG encode capability가 있고, GStreamer 1.24.2와 `v4l2h264enc`, `rtph264pay`, `libcamerasrc`가 있었다.
- `webrtcbin`은 확인되지 않았고, robot에 `ffmpeg` binary는 없었다.
- `camera_ros`는 libcamera/V4L2/Raspberry Pi camera를 지원하고 compressed topic을 제공한다.

따라서 “robot H264 direct publish”는 가능성이 있지만 현재 production 기본값으로 승격하기 전에 다음을 측정해야 한다.

```text
Robot GStreamer prototype:
libcamerasrc / camera source
  -> v4l2h264enc or equivalent H264 encoder
  -> h264parse
  -> rtph264pay / mpegtsmux / rtspclientsink
  -> Vision PC MediaMTX
  -> WebRTC
```

필수 검증:

- Nav2/SLAM/localization stack 동시 실행 중 robot CPU, load average, throttling, temperature.
- Wi-Fi/LAN packet loss와 bitrate 안정성.
- camera process가 장애 날 때 ROS/DDS/cmd_vel/Nav2에 영향이 없는지.
- Main이 burned-in overlay를 계속 요구하면 clean H264에 canvas overlay를 입히거나 Vision PC compositor를 유지해야 한다.

### 4.3 MediaMTX rpiCamera 직접 소스는 보류

MediaMTX는 Raspberry Pi camera native source를 제공하며 low-latency/high-quality streaming에 매력적이다. 다만 공식 docs는 Raspberry Pi OS Trixie/Bookworm/Bullseye 조건을 명시한다. 현재 robot probe는 Ubuntu 24.04 aarch64였으므로, 지금은 바로 적용 권장보다 별도 compatibility spike가 맞다.

## 5. 글로벌캠 경로 판단

현재 글로벌캠이 연결되어 있지 않으므로 live CPU/FPS/latency를 새로 계측하지 않았다. config 기준 low-load 최적화는 이미 다음을 한다.

- `global_cam_01/full`만 WebRTC 공개.
- `global_cam_01/lift_roi` WebRTC off로 crop/encode work 절감.
- global media target 20fps, AI monitor 5fps.
- full output 960x540, 1600k, GOP 10.
- high-quality evidence capture는 streaming과 별도.

과거 `.omx/context/gopro-mediamtx-first-direct-media-20260629T012530Z.md`에는 live profile에서 GoPro adapter와 AI server CPU가 큰 비중이었다는 기록이 있다. 그러므로 다음 최적화 우선순위는 다음이다.

1. **global cam 연결 후 현 low-load baseline 재측정**
   - adapter CPU, AI server CPU, compositor metrics, WebRTC stats를 먼저 찍는다.
2. **MediaMTX-first direct H264/TS 실험**
   - GoPro UDP/TS source를 MediaMTX가 먼저 소유하고, adapter는 MediaMTX RTSP를 읽는 구조를 실험한다.
   - 목적: GoPro UDP input을 여러 프로세스가 경쟁하지 않게 하고, public clean media path의 재사용성을 높인다.
3. **burned overlay contract 유지 여부 결정**
   - Main이 반드시 video pixels에 overlay가 burn-in 되어야 한다면 Vision PC compositor는 계속 필요하다.
   - Main이 canvas overlay를 안정적으로 처리할 수 있으면 clean H264 direct WebRTC가 CPU/품질 면에서 더 유리할 수 있다.

## 6. 권장 의사결정

### 6.1 당장 유지할 기본값

- demo/drive 개발 기준은 계속 `./scripts/vision/sf_lab.sh low-load`.
- low-load에서는 WebRTC primary를 현재 compositor publisher로 유지.
- MJPEG URL은 fallback/diagnostic으로만 설명.
- global cam 연결 전에는 global 경로의 성능 결론을 확정하지 않는다.

### 6.2 새로 조사/구현할 실험 후보

#### 후보 1 — Robot hardware H264 direct publish A/B

목표: PiCam 경로에서 JPEG source + Vision-PC H264 encode 대비 latency/quality/CPU가 실제로 좋아지는지 확인.

비교군:

- A: current low-load PiCam path.
- B: robot GStreamer H264 -> MediaMTX -> WebRTC clean/direct path.
- C: B + Vision PC overlay compositor, 또는 B + Main canvas overlay.

승격 조건:

- robot navigation/localization CPU headroom이 안전하게 남는다.
- p95 glass-to-glass latency와 freeze/stutter가 A보다 개선된다.
- WebRTC browser stats에서 sustained frame drop/freeze spike가 줄어든다.
- 품질이 현재보다 같거나 좋다.
- 장애 시 current low-load로 즉시 rollback 가능하다.

#### 후보 2 — Global MediaMTX-first direct media

목표: GoPro adapter가 UDP source를 단독 소유하고 public path가 MJPEG/AI gateway에 묶이는 구조를 줄인다.

비교군:

- A: current low-load global full compositor.
- B: GoPro TS/RTSP -> MediaMTX direct clean WebRTC.
- C: B + overlay compositor or Main canvas overlay.

주의:

- current low-load는 global cam 미연결 상태라 baseline부터 새로 찍어야 한다.
- GoPro input 소유권 충돌 (`udp://0.0.0.0:8554` bind 경쟁)을 피해야 한다.

#### 후보 3 — Browser WebRTC stats collector 추가

현재 판단은 compositor metrics와 process CPU에 치우친다. 사용자가 말한 “지연 적음, 버벅임 없음, 영상 품질”을 정량화하려면 browser에서 `RTCPeerConnection.getStats()`를 수집해야 한다.

수집 항목 예:

- `framesDecoded`, `framesDropped`, `framesPerSecond`
- `jitterBufferDelay`, `jitterBufferEmittedCount`
- `freezeCount` 또는 total freeze duration 계열 구현별 값
- `keyFramesDecoded`
- inbound bitrate, packet loss, RTT 후보

## 7. 계측 프로토콜

### 7.1 공통 baseline

```bash
./scripts/vision/sf_lab.sh check low-load
./scripts/vision/sf_lab.sh urls low-load
./scripts/vision/sf_lab.sh low-load
./scripts/vision/sf_lab.sh status
./scripts/vision/run_webrtc_sidecar_mediamtx.sh --print-config
```

### 7.2 Vision PC process 부하

```bash
pidstat -durh -p ALL 1
ps -eo pid,ppid,pcpu,pmem,comm,args | grep -E 'uvicorn|gopro|compositor|ffmpeg|mediamtx'
```

확인 대상:

- AI server / uvicorn
- `run_gopro_smart_roi_adapter.py`
- `run_latest_frame_compositor.py`
- ffmpeg publisher
- mediamtx

### 7.3 compositor metrics

```bash
cat .run/vision/compositor-metrics/*.json
```

주요 필드:

- `target_fps`
- `output_fps_estimate`
- `stale_frames`
- `repeated_frames`
- `dropped_frames`
- `ffmpeg_restarts`
- `updated_at_epoch_s` freshness

### 7.4 ROS/robot side

로봇에서 camera bringup 실행 상태에서:

```bash
ros2 topic hz /camera/image_raw/compressed
ros2 topic bw /camera/image_raw/compressed
ps -eo pid,pcpu,pmem,comm,args | grep -E 'camera|gstreamer|gst|ros2'
vcgencmd measure_temp  # 가능할 때만
```

robot H264 실험 때 추가:

```bash
gst-inspect-1.0 v4l2h264enc
GST_DEBUG=2 gst-launch-1.0 ...
```

### 7.5 end-to-end latency

가장 신뢰할 수 있는 방법:

1. 카메라 시야에 millisecond stopwatch 또는 LED blink source를 둔다.
2. 브라우저 표시 화면을 같은 카메라/캡처로 촬영한다.
3. source timestamp와 display timestamp 차이를 p50/p95로 계산한다.

대체 방법:

- frame sequence/timestamp overlay를 video에 burn-in하고 browser capture timestamp와 비교한다.

## 8. low-load 튜닝 가이드

### 약한 Vision PC/laptop에서 버벅이면

1. global full FPS: 20 → 15.
2. global full output: 960x540 → 854x480 또는 640x360.
3. bitrate: 1600k → 1200k 또는 900k.
4. AI monitor: 5fps → 3fps.
5. lift_roi WebRTC는 계속 off.
6. AI FPS를 올려 video smoothness를 해결하려 하지 않는다. media FPS와 AI FPS는 분리된 budget이다.

### 품질이 부족하면

1. bitrate를 먼저 올리되 CPU/packet loss를 같이 본다.
2. PiCam source resolution을 320x240 → 640x480로 올리는 실험은 가능하지만, robot CPU/network/DDS 영향을 먼저 계측한다.
3. H264 direct path를 실험해 JPEG→H264 이중 손실을 줄일 수 있는지 본다.
4. fixed even canvas를 유지한다. H264/yuv420p와 WebRTC reader 안정성에 유리하다.

## 9. 하지 말아야 할 것

- raw ROS image를 browser로 직접 보내거나 rosbridge whole graph를 공개하지 않는다.
- `/cmd_vel`, Nav2 action, ROS parameter mutation을 streaming stack에 섞지 않는다.
- “UDP”라는 이유만으로 robot-side 송출을 production에 승격하지 않는다.
- MJPEG overlay → H264 transcode를 다시 primary로 홍보하지 않는다.
- global cam이 연결되지 않은 상태에서 global live 부하/품질 결론을 확정하지 않는다.

## 10. 참고 출처

### Local evidence

- `./scripts/vision/sf_lab.sh check low-load` — profile, streams, GoPro 미검출, ports, source topics 확인.
- `./scripts/vision/sf_lab.sh urls low-load` — active/disabled WebRTC와 MJPEG fallback URL 확인.
- `config/vision/profiles/lab-gopro-tb3-low-load.env` — low-load budget/source/sidecar 설정.
- `scripts/vision/run_webrtc_sidecar_mediamtx.sh --print-config` — `vision_pc_compositor_publisher` 확인.
- `docs/setup/webrtc-mediamtx-sidecar.md` — current primary와 fallback/legacy 경로 설명.
- `ros2/smartfactory_perception_ros/.../vision_frame_gateway.py` — passive latest-frame gateway, no motion/control.
- `scripts/vision/burned_overlay_compositor.py` — H264 RTSP publisher, fixed canvas, metrics.
- SSH/tmux read-only robot probe — Ubuntu 24.04 aarch64, ROS Jazzy, `/dev/video11` H264/MJPG, GStreamer `v4l2h264enc`, camera not currently publishing.

### External references

- MediaMTX Introduction: <https://mediamtx.org/docs/kickoff/introduction>
- MediaMTX WebRTC-specific features: <https://mediamtx.org/docs/features/webrtc-specific-features>
- MediaMTX GStreamer publish: <https://mediamtx.org/docs/publish/gstreamer>
- MediaMTX Raspberry Pi Cameras: <https://mediamtx.org/docs/publish/raspberry-pi-cameras>
- MDN WebRTC codecs: <https://developer.mozilla.org/en-US/docs/Web/Media/Guides/Formats/WebRTC_codecs>
- RFC 7742 WebRTC Video Processing and Codec Requirements: <https://www.rfc-editor.org/rfc/rfc7742.html>
- GStreamer `rtph264pay`: <https://gstreamer.freedesktop.org/documentation/rtp/rtph264pay.html>
- GStreamer `x264enc`: <https://gstreamer.freedesktop.org/documentation/x264/index.html>
- camera_ros upstream: <https://github.com/christianrauch/camera_ros>
- ROS Index `compressed_image_transport`: <https://index.ros.org/p/compressed_image_transport/>
- Clearpath camera compression: <https://docs.clearpathrobotics.com/docs/ros/config/camera_compression/>
