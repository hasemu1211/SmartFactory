# Main 서버 전달 브리핑 — global_cam_01 WebRTC/MJPEG 노출 확인 요청

- 작성일: 2026-06-26 KST
- 대상 화면: `http://smartfactory-main.local:8088/operate/control`
- Vision host: `smartfactory-vision.local`
- Vision API: `http://smartfactory-vision.local:8100`
- Vision MJPEG gateway: `http://smartfactory-vision.local:8090`
- WebRTC sidecar(MediaMTX): `http://smartfactory-vision.local:8889`
- 주요 source/view:
  - `global_cam_01/full`
  - `global_cam_01/lift_roi`
  - `tb3_1_picam/full`
  - `tb3_2_picam/full` (2번 로봇 카메라가 없으면 offline/fallback 가능)

## 1. 결론 요약

현재 관측된 “Pi 카메라는 보이는데 global cam은 Main 화면에서 못 봄” 현상은 세 가지 가능성을 분리해서 봐야 합니다.

1. **Vision을 `lab-gopro-tb3` 프로필로 실행했다면 실제 WebRTC sidecar는 켜지지 않습니다.**
   - 이 프로필은 `VISION_WEBRTC_ENABLED=true`이지만 `SF_VISION_WEBRTC_SIDECAR_ENABLED=false`입니다.
   - 즉 WebRTC discovery/offer API는 존재하지만, 실제 WebRTC path가 없어서 offer 응답은 의도적으로 MJPEG fallback을 선택합니다.
   - global cam까지 WebRTC로 확인하려면 Vision 쪽은 `./scripts/vision/sf_vision.sh up lab-gopro-tb3-webrtc` 프로필이 필요합니다.

2. **Main 쪽이 `global_cam_01` source를 allowlist/proxy/UI camera list에 아직 등록하지 않았을 가능성이 큽니다.**
   - 기존 Main 화면은 `tb3_1_picam`, `tb3_2_picam` 같은 Pi camera 경로만 알고 있을 수 있습니다.
   - `global_cam_01`은 legacy robot camera topic이 아니라 Vision API source로 discovery해야 합니다.
   - 이전 전달본 기준으로 Main proxy에서 `global_cam_01`이 `404 unknown camera source`로 거절된 기록이 있습니다. 이 경우 Vision이 정상이어도 Main 화면에는 global cam 카드가 뜨지 않습니다.

3. **Vision 쪽 live source/path 문제도 배제하면 안 됩니다.**
   - GoPro/adapter가 `global_cam_01` 프레임을 AI Server에 넣고 있어야 합니다.
   - WebRTC sidecar가 켜져 있어도 MediaMTX path `global_cam_01_full` 또는 `global_cam_01_lift_roi`가 online이어야 WebRTC가 선택됩니다.
   - path가 missing/offline이면 Main은 MJPEG fallback으로 보여야 합니다.

따라서 Main 서버 개발자에게 요청할 핵심은 **`global_cam_01` source 등록 + discovery 기반 transport 선택 + WebRTC 실패 시 MJPEG fallback 유지**입니다.

## 2. Vision 프로필 차이

### `lab-gopro-tb3`

```text
SF_VISION_GOPRO_ENABLED=true
VISION_WEBRTC_ENABLED=true
SF_VISION_WEBRTC_SIDECAR_ENABLED=false
VISION_WEBRTC_SIDECAR_WHEP_URL_TEMPLATE=<empty>
VISION_WEBRTC_SIDECAR_BROWSER_URL_TEMPLATE=<empty>
```

의미:

- GoPro/global cam ingest와 MJPEG fallback 경로는 사용합니다.
- WebRTC discovery/offer endpoint는 있지만 실제 MediaMTX sidecar URL이 없으므로 WebRTC offer는 `selected_transport=mjpeg`, `reason=sidecar_not_configured`가 정상 동작입니다.

### `lab-gopro-tb3-webrtc`

```text
SF_VISION_GOPRO_ENABLED=true
VISION_WEBRTC_ENABLED=true
SF_VISION_WEBRTC_SIDECAR_ENABLED=true
VISION_WEBRTC_SIDECAR_WHEP_URL_TEMPLATE=http://smartfactory-vision.local:8889/{source}_{view}/whep
VISION_WEBRTC_SIDECAR_BROWSER_URL_TEMPLATE=http://smartfactory-vision.local:8889/{source}_{view}
VISION_WEBRTC_SIDECAR_STREAMS=global_cam_01/full,global_cam_01/lift_roi,tb3_1_picam/full,tb3_2_picam/full
```

의미:

- MediaMTX sidecar가 Vision MJPEG overlay stream을 받아 RTSP/WebRTC path로 재송출합니다.
- WebRTC 후보 path:
  - `http://smartfactory-vision.local:8889/global_cam_01_full`
  - `http://smartfactory-vision.local:8889/global_cam_01_full/whep`
  - `http://smartfactory-vision.local:8889/global_cam_01_lift_roi`
  - `http://smartfactory-vision.local:8889/global_cam_01_lift_roi/whep`
  - `http://smartfactory-vision.local:8889/tb3_1_picam_full`
  - `http://smartfactory-vision.local:8889/tb3_1_picam_full/whep`

## 3. Main 서버에서 필요한 변경/확인

### 3.1 source allowlist / camera registry

Main 서버가 Vision proxy 또는 UI camera registry를 가지고 있다면 아래 source를 모두 허용해 주세요.

```text
global_cam_01
tb3_1_picam
tb3_2_picam
```

특히 `global_cam_01`은 robot id가 없고, legacy `/mission/tb3_*` camera topic도 없습니다. Main 화면이 robot camera list만 순회하면 global cam은 표시되지 않습니다.

### 3.2 runtime config

Main 서버가 직접 Vision에 접근하거나 proxy한다면 hostname-first 설정을 사용해 주세요.

```env
VISION_API_BASE_URL=http://smartfactory-vision.local:8100
VISION_STREAM_BASE_URL=http://smartfactory-vision.local:8090
LMS_VISION_STREAM_BASE_URL=http://smartfactory-vision.local:8090
```

hostname 해석이 실패할 때만 명시 fallback을 사용합니다.

```env
VISION_API_FALLBACK_BASE_URL=http://192.168.10.59:8100
VISION_STREAM_FALLBACK_BASE_URL=http://192.168.10.59:8090
LMS_VISION_STREAM_FALLBACK_BASE_URL=http://192.168.10.59:8090
```

### 3.3 dashboard transport 선택 규칙

각 camera tile은 먼저 discovery를 호출합니다.

```http
GET {VISION_API_BASE_URL}/api/v1/vision/streams?source={source_id}
```

WebRTC를 우선하려면 offer endpoint를 호출합니다.

```http
POST {VISION_API_BASE_URL}/api/v1/vision/streams/{source_id}/webrtc/offer?view={view}
Content-Type: application/json

{"type":"offer","sdp":"...browser offer..."}
```

선택 규칙:

1. 응답의 `selected_transport == "webrtc"`이고 `sidecar.path_runtime_health == "online"`이면 WebRTC를 사용합니다.
2. WHEP player가 있으면 `sidecar.whep_url`을 사용합니다.
3. WHEP 구현 전이면 operator/demo 용도로 `sidecar.browser_url`을 iframe/embed할 수 있습니다.
4. `selected_transport != "webrtc"`, offer 실패, path missing/offline/unhealthy이면 반드시 MJPEG fallback을 사용합니다.
5. live video transport 선택은 DB write, evidence truth mutation, robot control publish를 하지 않습니다.

예상 WebRTC 성공 응답 형태:

```json
{
  "source": "global_cam_01",
  "view": "full",
  "status": "sidecar_configured",
  "reason": "sidecar_path_online",
  "selected_transport": "webrtc",
  "sidecar": {
    "path_id": "global_cam_01_full",
    "path_runtime_health": "online",
    "whep_url": "http://smartfactory-vision.local:8889/global_cam_01_full/whep",
    "browser_url": "http://smartfactory-vision.local:8889/global_cam_01_full"
  },
  "fallback": {
    "kind": "mjpeg",
    "url": "http://smartfactory-vision.local:8090/api/v1/vision/overlay/stream?source=global_cam_01&view=full&max_fps=30"
  }
}
```

### 3.4 MJPEG fallback은 항상 유지

WebRTC가 아직 안 붙어도 이 경로로 global cam이 떠야 합니다.

```http
GET {VISION_STREAM_BASE_URL}/api/v1/vision/overlay/stream?source=global_cam_01&view=full&max_fps=30
GET {VISION_STREAM_BASE_URL}/api/v1/vision/overlay/stream?source=global_cam_01&view=lift_roi&max_fps=30
GET {VISION_STREAM_BASE_URL}/api/v1/vision/overlay/stream?source=tb3_1_picam&view=full&max_fps=30
```

Main proxy를 거친다면 아래 proxy도 `global_cam_01`을 거절하지 않아야 합니다.

```http
GET  /api/v1/vision/streams?source=global_cam_01
POST /api/v1/vision/streams/global_cam_01/webrtc/offer?view=full
GET  /api/v1/vision/overlay/stream?source=global_cam_01&view=full&max_fps=30
```

## 4. 원인 판별용 체크리스트

아래는 operator 또는 Main 개발자가 같은 LAN에서 실행할 수 있는 체크입니다.

### 4.1 Vision direct health

```bash
curl http://smartfactory-vision.local:8100/api/v1/health
curl http://smartfactory-vision.local:8090/api/v1/vision/bridge/status
```

성공 기준:

- 둘 다 HTTP 200
- bridge status에 `global_cam_01`, `tb3_1_picam` source가 보임

### 4.2 global cam discovery

```bash
curl 'http://smartfactory-vision.local:8100/api/v1/vision/streams?source=global_cam_01' | jq .
```

확인할 필드:

- `sources[0].source == "global_cam_01"`
- `sources[0].available_views`에 `full`, `lift_roi` 포함
- `sources[0].stream_transports[]`에 `kind=mjpeg`와 `kind=webrtc` 모두 존재

### 4.3 global cam WebRTC offer

```bash
curl -X POST \
  'http://smartfactory-vision.local:8100/api/v1/vision/streams/global_cam_01/webrtc/offer?view=full' \
  -H 'Content-Type: application/json' \
  -d '{"type":"offer","sdp":"v=0"}' | jq .
```

응답 해석:

| 응답 | 의미 | 담당 |
|---|---|---|
| `selected_transport=webrtc`, `reason=sidecar_path_online` | Vision WebRTC path 정상. Main은 WebRTC 또는 browser_url을 표시해야 함 | Main 표시/플레이어 확인 |
| `selected_transport=mjpeg`, `reason=sidecar_not_configured` | Vision이 `lab-gopro-tb3` 프로필이거나 sidecar URL 미설정 | Vision 실행 프로필 확인 |
| `selected_transport=mjpeg`, `reason=sidecar_health_unhealthy` | MediaMTX listener/port 문제 | Vision sidecar 확인 |
| `selected_transport=mjpeg`, `reason=sidecar_path_missing` 또는 `sidecar_path_offline` | MediaMTX는 있으나 해당 source/view publisher가 online 아님 | Vision GoPro/overlay stream 확인 |
| Vision direct는 정상인데 Main proxy가 `404 unknown camera source` | Main이 `global_cam_01`을 allowlist하지 않음 | Main 수정 필요 |
| Vision direct는 정상인데 browser에서 8889 접근 실패 | DNS/LAN/CORS/browser direct network 문제 | Main/network 확인 |

### 4.4 MJPEG fallback 직접 열기

브라우저에서 아래 URL이 보여야 합니다.

```text
http://smartfactory-vision.local:8090/api/v1/vision/overlay/view?source=global_cam_01&view=full
http://smartfactory-vision.local:8090/api/v1/vision/overlay/view?source=global_cam_01&view=lift_roi
```

또는 stream URL:

```text
http://smartfactory-vision.local:8090/api/v1/vision/overlay/stream?source=global_cam_01&view=full&max_fps=30
http://smartfactory-vision.local:8090/api/v1/vision/overlay/stream?source=global_cam_01&view=lift_roi&max_fps=30
```

### 4.5 Main proxy 확인

```bash
curl 'http://smartfactory-main.local:8088/api/v1/vision/streams?source=global_cam_01'
curl 'http://smartfactory-main.local:8088/api/v1/vision/streams?source=tb3_1_picam'
curl 'http://smartfactory-main.local:8088/api/v1/vision/bridge/status'
```

성공 기준:

- `global_cam_01`이 404/unknown source로 거절되지 않음
- `/operate/control`에 global cam tile 또는 selectable source가 표시됨
- WebRTC 실패 시에도 MJPEG fallback으로 영상 표시

## 5. Vision operator 쪽 준비사항

WebRTC까지 확인할 때는 아래 준비가 필요합니다.

```bash
./scripts/vision/run_webrtc_sidecar_mediamtx.sh --check
./scripts/vision/sf_vision.sh up lab-gopro-tb3-webrtc
```

필수 조건:

- `mediamtx`가 PATH에 있거나 `MEDIAMTX_BIN=/absolute/path/to/mediamtx` 설정
- `ffmpeg` 설치
- GoPro stream이 Vision PC UDP `:8554`로 들어옴
- robot Pi camera가 필요하면 robot side에서 별도 bringup:

```bash
ROS_DOMAIN_ID=2 ros2 launch turtlebot3_bringup camera_low_bandwidth.launch.py
```

운영 중 상태 확인:

```bash
./scripts/vision/sf_vision.sh status
./scripts/vision/sf_vision.sh smoke
./scripts/vision/run_webrtc_sidecar_mediamtx.sh --status
```

## 6. Main 개발자에게 요청하는 acceptance criteria

1. `global_cam_01` source를 Main proxy/UI camera registry에서 허용한다.
2. `/operate/control`에서 `global_cam_01/full` 또는 `global_cam_01/lift_roi`를 표시할 수 있다.
3. Main은 `GET /api/v1/vision/streams?source=global_cam_01` discovery 결과를 읽는다.
4. WebRTC는 offer 응답의 `selected_transport == "webrtc"`일 때만 사용한다.
5. WebRTC가 unconfigured/offline/missing/unhealthy이면 `fallback.url` MJPEG를 사용한다.
6. Pi camera 전용 legacy topic/allowlist에 의존하지 않는다.
7. live video transport 선택은 DB write, evidence truth mutation, `/cmd_vel`, Nav2, ROS parameter mutation을 하지 않는다.

## 7. Repo evidence

- `config/vision/profiles/lab-gopro-tb3.env`
  - `SF_VISION_GOPRO_ENABLED=true`
  - `VISION_WEBRTC_ENABLED=true`
  - sidecar enable 값이 없어서 기본값 `false`
  - 설명도 `MJPEG fallback + WebRTC discovery`
- `config/vision/profiles/lab-gopro-tb3-webrtc.env`
  - `SF_VISION_WEBRTC_SIDECAR_ENABLED=true`
  - `VISION_WEBRTC_SIDECAR_WHEP_URL_TEMPLATE=http://smartfactory-vision.local:8889/{source}_{view}/whep`
  - `VISION_WEBRTC_SIDECAR_STREAMS=global_cam_01/full,global_cam_01/lift_roi,tb3_1_picam/full,tb3_2_picam/full`
- `scripts/vision/sf_vision.sh`
  - sidecar template이 없으면 “WebRTC offer intentionally selects MJPEG fallback”이라고 출력
  - `up` 실행 순서: mDNS → bundle → GoPro → WebRTC sidecar
- `services/ai-server/app/api/vision.py`
  - WebRTC offer는 sidecar health와 MediaMTX path online을 확인한 뒤에만 `selected_transport=webrtc`를 반환
  - 그렇지 않으면 `selected_transport=mjpeg` fallback 반환
- `scripts/vision/run_webrtc_sidecar_mediamtx.sh`
  - MediaMTX path는 `{source}_{view}` 형식으로 생성
  - 예: `global_cam_01/full` → `global_cam_01_full`
- `config/vision/sources.yaml`
  - `global_cam_01`은 enabled source이며 views는 `full`, `lift_roi`, `pallet_zoom`
  - `tb3_1_picam`, `tb3_2_picam`은 robot Pi camera source
