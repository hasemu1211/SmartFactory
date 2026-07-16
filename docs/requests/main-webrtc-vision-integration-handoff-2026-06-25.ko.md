# Main 전달본 — Vision WebRTC + MJPEG fallback 연동 요청

- 작성일: 2026-06-25 KST
- Main 화면: `http://smartfactory-main.local:8088/operate/control`
- Vision host: `smartfactory-vision.local`
- Vision API: `http://smartfactory-vision.local:8100`
- Vision MJPEG gateway: `http://smartfactory-vision.local:8090`
- WebRTC sidecar: `http://smartfactory-vision.local:8889`

## 요청 요약

Main dashboard는 live video에 대해 DB 저장/상태변경을 하지 말고, media transport만 선택해 주세요.

1. 기존 MJPEG 경로는 유지합니다.
2. WebRTC가 online이면 WebRTC를 우선 사용합니다.
3. WebRTC가 unavailable/offline이면 MJPEG로 fallback합니다.
4. evidence/evaluation REST는 live video transport와 별개로 유지합니다.

## Main 쪽 필수 source allowlist

Main proxy/connector가 Vision discovery를 대신 호출한다면 아래 source를 모두 허용해야 합니다.

```text
global_cam_01
tb3_1_picam
tb3_2_picam
```

2026-06-25 현재 확인 결과:

- `GET http://smartfactory-main.local:8088/operate/control` → `200 OK`
- `GET http://smartfactory-main.local:8088/api/v1/vision/streams?source=tb3_1_picam` → `200 OK`
- `GET http://smartfactory-main.local:8088/api/v1/vision/bridge/status` → `200 OK`
- `GET http://smartfactory-main.local:8088/api/v1/vision/streams?source=global_cam_01` → `404 {"detail":"unknown camera source"}`

따라서 Main 쪽에는 최소한 `global_cam_01` source 등록/allowlist 추가가 필요합니다.

## 현재 Vision runtime 검증 상태

`lab-gopro-tb3-webrtc` profile 기준입니다.

| source/view | 현재 상태 | WebRTC path | fallback |
|---|---:|---|---|
| `global_cam_01/full` | online | `global_cam_01_full` | MJPEG |
| `global_cam_01/lift_roi` | online | `global_cam_01_lift_roi` | MJPEG |
| `tb3_1_picam/full` | online | `tb3_1_picam_full` | MJPEG |
| `tb3_2_picam/full` | configured, 현재 no frame | `tb3_2_picam_full` | MJPEG |

`tb3_2_picam`은 현재 2번 로봇 카메라를 사용하지 않아서 offline/fallback 상태입니다. 나중에 `ROS_DOMAIN_ID=5`에서 같은 카메라 bringup을 하면 같은 계약으로 online 전환됩니다.

## Main runtime config

hostname 우선으로 설정해 주세요.

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

## Main dashboard transport 선택 순서

각 camera tile은 먼저 discovery를 호출합니다.

```http
GET {VISION_API_BASE_URL}/api/v1/vision/streams?source={source_id}
```

대상 source/view:

```text
global_cam_01/full
global_cam_01/lift_roi
tb3_1_picam/full
tb3_2_picam/full
```

WebRTC를 쓰려면 offer endpoint를 호출하고, 응답의 `selected_transport`가 `webrtc`일 때만 WebRTC를 선택합니다.

```http
POST {VISION_API_BASE_URL}/api/v1/vision/streams/{source_id}/webrtc/offer?view={view}
```

예상 응답 예시:

```json
{
  "source": "tb3_1_picam",
  "view": "full",
  "selected_transport": "webrtc",
  "reason": "sidecar_path_online",
  "sidecar": {
    "path_id": "tb3_1_picam_full",
    "whep_url": "http://smartfactory-vision.local:8889/tb3_1_picam_full/whep",
    "browser_url": "http://smartfactory-vision.local:8889/tb3_1_picam_full",
    "path_runtime_health": "online"
  },
  "fallback": {
    "kind": "mjpeg",
    "url": "http://smartfactory-vision.local:8090/api/v1/vision/overlay/stream?source=tb3_1_picam&view=full&max_fps=30"
  }
}
```

규칙:

1. `selected_transport == "webrtc"`이면 `sidecar.whep_url`을 WebRTC player에 사용합니다.
2. WHEP player 구현 전이면 `sidecar.browser_url`은 operator/demo embed 용도로만 사용할 수 있습니다.
3. `selected_transport != "webrtc"`이거나 offer 실패 시 `fallback.url` MJPEG를 사용합니다.
4. live video transport 선택은 DB write/evidence truth mutation을 하지 않습니다.

## MJPEG fallback 경로

항상 유지해야 하는 안정 경로입니다.

```http
GET {VISION_STREAM_BASE_URL}/api/v1/vision/overlay/stream?source={source_id}&view={view}&max_fps=30
```

예:

```text
http://smartfactory-vision.local:8090/api/v1/vision/overlay/stream?source=global_cam_01&view=full&max_fps=30
http://smartfactory-vision.local:8090/api/v1/vision/overlay/stream?source=global_cam_01&view=lift_roi&max_fps=30
http://smartfactory-vision.local:8090/api/v1/vision/overlay/stream?source=tb3_1_picam&view=full&max_fps=30
http://smartfactory-vision.local:8090/api/v1/vision/overlay/stream?source=tb3_2_picam&view=full&max_fps=30
```

## Media-only 안전 경계

Vision WebRTC/MJPEG API는 media-only입니다.

- DB write 없음
- evidence truth mutation 없음
- `/cmd_vel` publish 없음
- Nav2 action call 없음
- ROS parameter mutation 없음
- full rosbridge graph exposure 없음

offer 응답의 `side_effects`도 이 경계를 명시합니다.

## Evidence/evaluation API는 별도

task/evidence 판단이 필요할 때만 별도로 호출합니다. live video rendering 경로와 섞지 않습니다.

```http
POST {VISION_API_BASE_URL}/api/v1/evidence/evaluate
POST {VISION_API_BASE_URL}/api/v1/vision/evidence/lift-load/evaluate
# Internal/compat only when explicitly testing AI Server internals:
# POST {VISION_API_BASE_URL}/api/v1/lift-roi/evaluate
# POST {VISION_API_BASE_URL}/api/v1/lift-roi/evaluate-image
```

Main은 task id, DB 저장, inventory truth, UI 상태전이의 owner입니다. Vision은 판단 근거와 PASS/FAIL/UNCERTAIN 평가 payload를 제공합니다.

## Main 팀 acceptance check

Main 수정 후 아래를 확인해 주세요.

```bash
curl http://smartfactory-vision.local:8100/api/v1/health
curl 'http://smartfactory-vision.local:8100/api/v1/vision/streams?source=global_cam_01'
curl 'http://smartfactory-vision.local:8100/api/v1/vision/streams?source=tb3_1_picam'
curl http://smartfactory-vision.local:8090/api/v1/vision/bridge/status

curl 'http://smartfactory-main.local:8088/api/v1/vision/streams?source=global_cam_01'
curl 'http://smartfactory-main.local:8088/api/v1/vision/streams?source=tb3_1_picam'
curl 'http://smartfactory-main.local:8088/api/v1/vision/bridge/status'
```

성공 기준:

- `/operate/control`이 camera tile을 표시한다.
- `global_cam_01`, `tb3_1_picam`, `tb3_2_picam` source를 Main이 거절하지 않는다.
- WebRTC path가 online이면 WebRTC 우선.
- WebRTC path가 offline이면 MJPEG fallback.
- video component가 DB/evidence truth/robot control을 직접 변경하지 않는다.
