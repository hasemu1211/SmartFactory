# SmartFactory scripts 안내서 (한국어)

이 디렉토리는 SmartFactory 로컬 개발/운영 보조 스크립트의 진입점입니다. 특히 Main/Vision 연동은 임의 명령보다 이 디렉토리의 스크립트를 우선 사용하세요.
파일시스템 ownership / 용도별 배치 기준: [`../docs/technical/project-filesystem-ownership.md`](../docs/technical/project-filesystem-ownership.md).

## 현재 결론: `smartfactory-vision.local`은 자동 영구 설정이 아님

현재 `smartfactory-vision.local`은 다음 helper 프로세스가 살아있는 동안만 임시로 mDNS 방송됩니다.

```bash
./scripts/vision/publish_vision_mdns_alias.py
```

이 helper는 다음을 하지 않습니다.

- `/etc/hosts` 수정 안 함
- OS hostname 변경 안 함
- 라우터 DHCP reservation 설정 안 함
- 영구 DNS 설정 안 함

따라서 “사용자가 신경 쓰지 않아도 되는 운영 상태”를 만들려면 라우터/DNS 쪽에서 고정해야 합니다.

날짜가 박힌 lab DHCP/DNS handoff 세부값은
[`docs/requests/main-vision-runtime-config-request-2026-06-19.md`](../docs/requests/main-vision-runtime-config-request-2026-06-19.md)를 보세요.
MAC/IP 값은 외부 공개 또는 DHCP/router 변경 후 사용 전에 반드시 재확인하세요.

## 빠른 실행 순서

### 1. 임시 hostname 방송

live 프로세스를 어느 tmux 창/패널에 둘지는 현재 runbook/session evidence를 따르세요. durable README에는 일시적인 pane/window ID를 고정하지 않습니다.

```bash
./scripts/vision/publish_vision_mdns_alias.py
```

동작 확인만 하고 싶으면:

```bash
./scripts/vision/publish_vision_mdns_alias.py --print-only
```

### 2. Main-compatible Vision bundle 실행

```bash
VISION_MODEL_WORKER_ENABLED=false ./scripts/vision/run_d1_vision_multi_source_gateway_bundle.sh
```

이 bundle은 다음을 띄웁니다.

```text
0.0.0.0:8100   AI Server
0.0.0.0:8090   public HTTP/MJPEG Vision Stream Gateway
127.0.0.1:18090 internal tb3_1 overlay bridge
127.0.0.1:18091 internal tb3_2 overlay bridge
```

기본 Main callback 설정은 다음입니다.

```env
MAIN_SERVER_URL=http://smartfactory-main.local:8088
WMS_VISION_EVENTS_PATH=/api/v1/vision/events
WMS_EMIT_ENABLED=false
```

`WMS_EMIT_ENABLED=false`는 안전 기본값입니다. 실제로 VisionEvent를 Main에 POST하려는 경우에만 명시적으로 `true`로 바꾸세요.

### 3. 확인 URL

```bash
curl http://smartfactory-vision.local:8100/api/v1/health
curl http://smartfactory-vision.local:8090/api/v1/vision/bridge/status
curl http://smartfactory-main.local:8088/api/v1/vision/bridge/status
```

로봇/카메라가 없을 때는 서비스가 `200`이어도 source 상태가 `no_frame`, `offline`, `stale`일 수 있습니다. 이것은 정상입니다.

## 스크립트 그룹과 실제 배치

이제 루트 `scripts/`에는 문서만 남깁니다. 실행 가능한 스크립트는 용도별
하위 폴더에 직접 배치되어 있고, 현재 문서/Makefile/systemd 참조도 실제 경로를 직접 가리킵니다.

| 그룹 | 실행 위치 | 예시 |
|---|---|---|
| AI Server | `scripts/ai/` | `run_ai_server.sh`, `setup_ai_server_env.sh`, `setup_ai_server_model_env.sh`, `test_ai_server.sh` |
| D1 Vision / Main 연동 | `scripts/vision/` | `publish_vision_mdns_alias.py`, `run_d1_vision_multi_source_gateway_bundle.sh`, `run_d1_vision_stream_gateway.py`, `smoke_main_dashboard_gateway.sh` |
| 계약/검증 | `scripts/validate/` | `validate_contracts.py`, `validate_deployment_assets.py` |
| 계약 산출물 생성 | `scripts/generate/` | `generate_source_registry_surfaces.py` |
| 보고서/Confluence 산출물 | `scripts/reports/` | `create_sprint3_presentation_pptx.py`, `generate-drawio-architectures.py`, `render-scenario-sequence-diagrams.py` |
| 운영 확인 | `scripts/ops/` | `check-confluence-env.sh` |
| 공용 shell helper | `scripts/lib/` | `vision_bundle_common.sh` |

배치 규칙:

- 새 문서와 자동화에는 용도별 실제 경로를 직접 사용합니다.
- 외부 배포 호환 전환이 필요한 경우가 아니면 루트 실행 shim을 만들지 않습니다.
- 구현 변경은 용도에 맞는 하위 폴더에서 합니다.

## 안전 경계

이 Vision script 세트는 다음을 하지 않아야 합니다.

- `/cmd_vel` publish
- Nav2 action 호출
- teleop 실행
- ROS parameter mutation
- robot-side persistent service 변경
- 전체 DDS/rosbridge graph 노출

Vision은 evidence/advisory만 제공하고, Main/WMS와 Movement/Safety가 최종 상태와 제어를 소유합니다.
