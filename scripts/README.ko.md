# SmartFactory scripts 안내서 (한국어)

이 디렉토리는 SmartFactory 로컬 개발/운영 보조 스크립트의 진입점입니다. 특히 Main/Vision 연동은 임의 명령보다 이 디렉토리의 스크립트를 우선 사용하세요.

## 현재 결론: `smartfactory-vision.local`은 자동 영구 설정이 아님

현재 `smartfactory-vision.local`은 다음 helper 프로세스가 살아있는 동안만 임시로 mDNS 방송됩니다.

```bash
./scripts/publish_vision_mdns_alias.py
```

이 helper는 다음을 하지 않습니다.

- `/etc/hosts` 수정 안 함
- OS hostname 변경 안 함
- 라우터 DHCP reservation 설정 안 함
- 영구 DNS 설정 안 함

따라서 “사용자가 신경 쓰지 않아도 되는 운영 상태”를 만들려면 라우터/DNS 쪽에서 고정해야 합니다.

```text
Vision PC MAC: a0:ad:9f:bd:63:1b
권장 이름: smartfactory-vision.local
현재 lab IP: 192.168.10.59
```

## 빠른 실행 순서

### 1. 임시 hostname 방송

tmux window `3:Development` 안에서 실행하는 것을 권장합니다.

```bash
./scripts/publish_vision_mdns_alias.py
```

동작 확인만 하고 싶으면:

```bash
./scripts/publish_vision_mdns_alias.py --print-only
```

### 2. Main-compatible Vision bundle 실행

```bash
VISION_MODEL_WORKER_ENABLED=false ./scripts/run_d1_vision_multi_source_gateway_bundle.sh
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

## 스크립트 그룹

### AI Server

| 파일 | 용도 |
|---|---|
| `setup_ai_server_env.sh` | AI Server Python venv 생성/갱신 |
| `setup_ai_server_model_env.sh` | YOLO/Torch 등 모델 런타임 환경 보조 |
| `run_ai_server.sh` | AI Server 단독 실행 (`:8100`) |
| `test_ai_server.sh` | AI Server 테스트 실행 |

### D1 Vision / Main 연동

| 파일 | 용도 |
|---|---|
| `publish_vision_mdns_alias.py` | 임시 `smartfactory-vision.local` mDNS A record 방송 |
| `run_d1_vision_multi_source_gateway_bundle.sh` | 현재 권장 Main-compatible multi-source bundle |
| `run_d1_vision_stream_gateway.py` | ROS-free public HTTP/MJPEG source mux (`:8090`) |
| `run_d1_vision_bundle.sh` | 단일 source/이전 디버그 bundle |
| `run_d1_vision_domain_sidecar.sh` | 추가 source/domain sidecar |
| `smoke_main_dashboard_gateway.sh` | Main/Vision report-only smoke check |

### 계약/검증/생성

| 파일 | 용도 |
|---|---|
| `validate_contracts.py` | 계약/schema 검증 |
| `generate_source_registry_surfaces.py` | source registry 기반 fixture/OpenAPI snapshot 생성 |
| `validate_deployment_assets.py` | Docker/systemd 배포 자산 검증 |
| `test_run_d1_vision_stream_gateway.py` | stream gateway 관련 pytest |

### 기타 산출물/보고서 생성

| 파일 | 용도 |
|---|---|
| `check-confluence-env.sh` | Confluence env 확인 |
| `prepare_docking_tuning_session.sh` | docking tuning 세션 준비 |
| `generate-drawio-architectures.py` | draw.io architecture 산출물 생성 |
| `render-scenario-sequence-diagrams.py` | scenario sequence diagram 생성 |
| `create_sprint3_presentation_pptx.py` | 발표자료 pptx 생성 |

## 폴더 정리 판단

현재는 루트의 여러 스크립트가 다음에서 직접 참조됩니다.

- `Makefile`
- `services/ai-server/tests/*`
- `docs/contracts/*`
- `docs/runbooks/*`
- `entry.md`

그래서 지금 바로 `scripts/vision/`, `scripts/ai/`, `scripts/validation/` 같은 하위 폴더로 이동하면 참조가 대량으로 깨질 수 있습니다.

### 권장 단계

#### 1단계: 문서상 분류만 먼저 유지

현재 `scripts/README.md`와 이 문서에서 용도별 그룹을 명확히 합니다. 실제 파일 이동은 하지 않습니다.

#### 2단계: stable root entrypoint 유지

사용자가 직접 치는 명령과 Makefile 대상은 루트에 유지합니다.

```text
run_d1_vision_multi_source_gateway_bundle.sh
publish_vision_mdns_alias.py
smoke_main_dashboard_gateway.sh
run_ai_server.sh
test_ai_server.sh
setup_ai_server_env.sh
validate_contracts.py
validate_deployment_assets.py
generate_source_registry_surfaces.py
```

#### 3단계: 이동이 필요하면 wrapper 방식

예를 들어 내부 구현을 나중에 `scripts/vision/`으로 옮기더라도, 기존 루트 파일은 wrapper로 남깁니다.

```bash
#!/usr/bin/env bash
exec "$(dirname "$0")/vision/run_d1_vision_multi_source_gateway_bundle.sh" "$@"
```

이렇게 해야 기존 문서/Makefile/테스트/운영 습관을 깨지 않습니다.

#### 4단계: 저위험 파일부터 이동 후보

직접 운영 entrypoint가 아닌 산출물 생성 스크립트가 우선 후보입니다.

```text
scripts/reports/create_sprint3_presentation_pptx.py
scripts/reports/generate-drawio-architectures.py
scripts/reports/render-scenario-sequence-diagrams.py
```

단, 이동 시에도 기존 경로 wrapper 또는 문서 업데이트가 필요합니다.

## 안전 경계

이 Vision script 세트는 다음을 하지 않아야 합니다.

- `/cmd_vel` publish
- Nav2 action 호출
- teleop 실행
- ROS parameter mutation
- robot-side persistent service 변경
- 전체 DDS/rosbridge graph 노출

Vision은 evidence/advisory만 제공하고, Main/WMS와 Movement/Safety가 최종 상태와 제어를 소유합니다.
