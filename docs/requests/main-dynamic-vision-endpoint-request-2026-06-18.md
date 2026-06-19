# Main 요청: Vision endpoint hostname-first + explicit fallback

- Date: 2026-06-18 KST
- Owner surface: Main Server / dashboard Vision proxy configuration
- Related Vision contract: single HTTP/MJPEG Vision Stream Gateway `:8090`, AI API `:8100`
- Safety boundary: Vision evidence/advisory only; no `/cmd_vel`, Nav2 action, teleop, parameter mutation, or whole-graph bridge

## 요청 요약

Main-facing Vision endpoint를 고정 IP가 아니라 hostname-first 후보로 처리해 주세요.

```bash
VISION_API_BASE_URL=http://smartfactory-vision.local:8100
VISION_STREAM_BASE_URL=http://smartfactory-vision.local:8090
LMS_VISION_STREAM_BASE_URL=http://smartfactory-vision.local:8090
```

`smartfactory-vision.local`이 Main Server PC에서 resolve되지 않거나 health check가 실패할 때만 명시적 fallback을 사용합니다.

```bash
VISION_API_FALLBACK_BASE_URL=http://<detected-or-operator-configured-vision-lan-ip>:8100
VISION_STREAM_FALLBACK_BASE_URL=http://<detected-or-operator-configured-vision-lan-ip>:8090
```

Main은 IP를 추측하거나 `192.168.10.63` 같은 classroom-specific 값을 hard-code하지 않습니다.

## 배경 증거

2026-06-18 live smoke에서 다음을 확인했습니다.

- Vision PC DHCP 주소는 `192.168.10.59`였습니다.
- Main dashboard는 `http://192.168.10.66:8088/dashboard/overview`에서 reachable이었습니다.
- Main proxy는 기존 stale 설정 `192.168.10.63`으로 Vision upstream을 보려 해서 timeout/504가 발생했습니다.
- `192.168.10.63`은 다른 ASRock 장비의 MAC으로 응답했으므로 Vision PC가 그 주소를 alias/reservation으로 가져가는 것은 안전하지 않습니다.

## Main fallback semantics 제안

1. Startup 또는 proxy 최초 사용 전에 hostname-first 후보를 probe합니다.
   - `GET ${VISION_API_BASE_URL}/api/v1/health`
   - `GET ${VISION_STREAM_BASE_URL}/api/v1/vision/bridge/status`
2. hostname resolution 또는 health가 실패하면 명시적으로 설정된 fallback만 사용합니다.
3. Main status/debug endpoint 또는 log에는 다음을 노출합니다.
   - active `vision_api_base_url`
   - active `vision_stream_base_url`
   - fallback 사용 여부
   - fallback 이유: `hostname_unresolved`, `health_timeout`, `status_non_2xx` 등
4. Dashboard HTML은 계속 Main-relative URL을 사용합니다.
   - 예: `/api/v1/vision/overlay/stream?source=tb3_1_picam&max_fps=30`
   - Browser가 Vision PC host/IP를 직접 알 필요는 없습니다.

## Vision 쪽에서 제공하는 검증 도구

Vision repo는 다음을 제공합니다.

```bash
make vision-config
scripts/vision/smoke_main_dashboard_gateway.sh
```

`make vision-config`는 hostname-first 권장 URL과 detected LAN fallback evidence를 출력합니다.  
`smoke_main_dashboard_gateway.sh`는 report-only로 hostname resolution, Vision status/health, explicit fallback, Main dashboard/proxy 결과를 `.omx/reports`에 저장합니다.

예시:

```bash
MAIN_DASHBOARD_URL=http://<main-host>:8088/dashboard/overview \
VISION_STREAM_FALLBACK_BASE_URL=http://<detected-vision-lan-ip>:8090 \
VISION_API_FALLBACK_BASE_URL=http://<detected-vision-lan-ip>:8100 \
scripts/vision/smoke_main_dashboard_gateway.sh
```

## 비범위 / 안전 경계

- Vision은 Main DB, task, inventory truth를 쓰지 않습니다.
- Vision은 Nav/Movement 명령을 직접 실행하지 않습니다.
- ROS/rosbridge/DDS/domain bridge는 내부 sidecar/operator/prototype 경계입니다.
- 이 요청은 Main proxy endpoint 후보 선택과 status visibility만 다룹니다.
