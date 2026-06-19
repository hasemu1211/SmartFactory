# External Server Handoff: Vision endpoint hostname-first 변경 요청

- Date: 2026-06-18 KST
- 작성 범위: Vision/AI Server PC에서 외부 Main/Nav/GUI/운영 서버 개발자에게 전달하는 계약 변경 요청
- 이 PC 범위: Vision/AI Server, Vision Stream Gateway, 문서/검증 스크립트
- 이 PC 밖 범위: Main Server, Nav/Movement Server, 다른 운영 서버 설정/코드
- Canonical Confluence: `API` page v70 — hostname-first Vision endpoint contract 반영 완료

## 1. 변경 요약

Vision stream/API endpoint 계약이 고정 IP 중심에서 **hostname-first** 형식으로 바뀌었습니다.

기존처럼 `192.168.x.x` classroom DHCP IP를 Main/GUI/다른 서버에 hard-code하지 말고, 아래 hostname을 기본 endpoint로 사용해 주세요.

```bash
VISION_API_BASE_URL=http://smartfactory-vision.local:8100
VISION_STREAM_BASE_URL=http://smartfactory-vision.local:8090
LMS_VISION_STREAM_BASE_URL=http://smartfactory-vision.local:8090
```

핵심 유지 사항:

- 영상 stream은 계속 단일 HTTP/MJPEG gateway `:8090`입니다.
- 여러 카메라는 port가 아니라 `source` query parameter로 구분합니다.
- AI API는 `:8100`입니다.
- ROS2/DDS/ROS_DOMAIN_ID/internal bridge port는 Main-facing 계약이 아닙니다.
- Vision은 evidence/advisory만 제공하며 직접 motion authority를 갖지 않습니다.

## 2. Main Server / GUI에서 바꿔야 할 point

Main/GUI는 browser에 Vision PC IP를 직접 노출하지 않고, 기존처럼 Main-relative proxy endpoint를 유지하면 됩니다.

Browser/HTML 요청 예:

```text
GET /api/v1/vision/overlay/stream?source=tb3_1_picam&max_fps=30
GET /api/v1/vision/frame/stream?source=tb3_2_picam&max_fps=30
GET /api/v1/vision/bridge/status
```

Main upstream 설정만 hostname-first로 바꿔 주세요.

```bash
VISION_STREAM_BASE_URL=http://smartfactory-vision.local:8090
LMS_VISION_STREAM_BASE_URL=http://smartfactory-vision.local:8090
```

Semantic evidence/API polling 또는 health check를 쓰는 경우:

```bash
VISION_API_BASE_URL=http://smartfactory-vision.local:8100
```

예시 upstream 호출:

```text
GET ${VISION_STREAM_BASE_URL}/api/v1/vision/overlay/stream?source=tb3_1_picam&max_fps=30
GET ${VISION_STREAM_BASE_URL}/api/v1/vision/bridge/status
GET ${VISION_API_BASE_URL}/api/v1/health
GET ${VISION_API_BASE_URL}/api/v1/detections/latest?source=tb3_1_picam&limit=10
```

## 3. Explicit fallback 원칙

`smartfactory-vision.local`이 Main Server PC에서 resolve되지 않거나 health check가 실패할 때만 명시적 fallback을 사용합니다.

```bash
VISION_API_FALLBACK_BASE_URL=http://<operator-configured-vision-lan-ip>:8100
VISION_STREAM_FALLBACK_BASE_URL=http://<operator-configured-vision-lan-ip>:8090
```

주의:

- fallback IP를 Main 코드에 hard-code하지 마세요.
- Vision PC가 출력한 detected LAN IP는 운영자가 env/config에 넣는 **fallback evidence**일 뿐입니다.
- 서버가 임의로 같은 subnet IP를 스캔하거나 추측하지 마세요.
- `192.168.10.63`은 과거 smoke 시점의 값이며 current durable contract가 아닙니다.

## 4. 권장 health/fallback 동작

Main/다른 서버는 endpoint 후보를 다음 순서로 확인하는 것을 권장합니다.

1. hostname-first 후보 확인
   - `GET ${VISION_API_BASE_URL}/api/v1/health`
   - `GET ${VISION_STREAM_BASE_URL}/api/v1/vision/bridge/status`
2. hostname resolution 또는 health 실패 시, 명시적으로 설정된 fallback만 확인
   - `GET ${VISION_API_FALLBACK_BASE_URL}/api/v1/health`
   - `GET ${VISION_STREAM_FALLBACK_BASE_URL}/api/v1/vision/bridge/status`
3. status/log에 현재 active endpoint와 fallback reason을 노출
   - `hostname_unresolved`
   - `health_timeout`
   - `status_non_2xx`
   - `fallback_not_configured`

## 5. Source IDs

현재 Main-facing stream source:

```text
tb3_1_picam
tb3_2_picam
```

미래 확장 후보는 별도 source-registry/ADR 이후 반영합니다.

```text
global_cam_01
global_rgbd_01
global_depth_01
```

## 6. Vision PC 쪽 검증 명령

Vision/AI Server PC에서는 다음 명령으로 현재 권장 endpoint와 fallback evidence를 출력합니다.

```bash
make vision-config
```

Main dashboard/proxy와 함께 report-only smoke를 남길 때:

```bash
MAIN_DASHBOARD_URL=http://<main-host>:8088/dashboard/overview \
VISION_STREAM_FALLBACK_BASE_URL=http://<operator-configured-vision-lan-ip>:8090 \
VISION_API_FALLBACK_BASE_URL=http://<operator-configured-vision-lan-ip>:8100 \
scripts/vision/smoke_main_dashboard_gateway.sh
```

이 smoke script는 `.omx/reports`에 결과를 남기며, DNS/IP/hosts/route/ROS/robot motion/Main config를 변경하지 않습니다.

## 7. Safety boundary

- Vision Gateway는 read-only stream/evidence/advisory surface입니다.
- `/cmd_vel`, Nav2 action, teleop, parameter mutation, whole-graph rosbridge를 제공하지 않습니다.
- Main/WMS가 task·inventory·DB truth를 소유합니다.
- Nav/Movement가 motion·safety execution truth를 소유합니다.
- 실로봇 검증은 staged validation으로만 진행합니다.

## 8. 요청 사항 체크리스트

외부 Main/Nav/다른 서버 담당자는 다음을 확인해 주세요.

- [ ] `smartfactory-vision.local`이 해당 서버 PC에서 resolve되는지 확인
- [ ] Main/GUI upstream base URL을 hostname-first로 변경
- [ ] 필요한 경우 fallback env/config를 명시적으로만 설정
- [ ] Main status/log에 active endpoint와 fallback reason 노출
- [ ] `192.168.10.63` 같은 과거 DHCP IP hard-code 제거
- [ ] Browser는 Vision host/IP를 직접 알지 않고 Main-relative proxy URL만 사용
