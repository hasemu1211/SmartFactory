# SmartFactory

SmartFactory AI/Vision/ROS 통합 워크스페이스의 로컬 안내서입니다.

English version: [`README.md`](README.md).

## 먼저 볼 문서

- 스크립트/운영자 안내: [`scripts/README.ko.md`](scripts/README.ko.md)
- 영어 스크립트 안내: [`scripts/README.md`](scripts/README.md)
- 파일시스템 ownership / 용도별 배치 기준: [`docs/technical/project-filesystem-ownership.md`](docs/technical/project-filesystem-ownership.md)
- AI Server 안내: [`services/ai-server/README.md`](services/ai-server/README.md)
- ROS perception package 안내: [`ros2/smartfactory_perception_ros/README.md`](ros2/smartfactory_perception_ros/README.md)

## 현재 Main/Vision 계약

- Main callback base: `http://smartfactory-main.local:8088`
- Vision public stream base: `http://smartfactory-vision.local:8090`
- Vision API base: `http://smartfactory-vision.local:8100`
- `smartfactory-vision.local`은 이 repo 안에서는 임시 mDNS helper 기반입니다. 신경 쓰지 않아도 되는 운영 상태를 원하면 router/DNS/hostname 설정이 별도로 필요합니다.
- `WMS_EMIT_ENABLED=false`가 안전 기본값입니다.

## AI/Vision 노트북 빠른 시작

노트북은 유선 LAN이 아니어도 됩니다. **Main PC와 같은 WiFi에 있고 AP/client isolation이 꺼져 있으면** Vision API/stream을 WiFi로 사용할 수 있습니다.

주소 구분:

- `http://127.0.0.1:8100`: AI/Vision 노트북 **자기 자신에서만** 쓰는 로컬 확인 주소입니다.
- `http://<노트북_WiFi_IP>:8100`: Main PC나 다른 장비가 노트북 AI Server에 붙을 때 쓰는 주소입니다.
- `http://smartfactory-vision.local:8100` 또는 `http://smartfactory-ai:8100`: DNS/mDNS/hosts가 준비된 경우의 권장 hostname 주소입니다.

노트북에서 repo를 받은 뒤:

```bash
git checkout feature/ai-server-marker-detection
git pull --ff-only
./scripts/setup/setup_ubuntu24_ai_vision_laptop.sh --with-gopro --with-model
```

API를 Main PC에서 볼 수 있게 켤 때는 `127.0.0.1`이 아니라 `0.0.0.0`으로 바인딩합니다.

```bash
AI_SERVER_HOST=0.0.0.0 \
VISION_MODEL_WORKER_ENABLED=false \
./scripts/ai/run_ai_server.sh
```

노트북에서 로컬 확인:

```bash
curl http://127.0.0.1:8100/api/v1/health
```

Main PC에서 원격 확인:

```bash
curl http://<노트북_WiFi_IP>:8100/api/v1/health
curl http://<노트북_WiFi_IP>:8100/api/v1/vision/monitors
```

자세한 노트북 설치/WiFi/방화벽/포트 절차는 [`docs/setup/ubuntu24-ai-vision-laptop.md`](docs/setup/ubuntu24-ai-vision-laptop.md)를 따릅니다.

## 정리 원칙

폴더는 보기 좋은 이름이 아니라 실제 용도, 호출자, 운영 역할, 참조관계 기준으로 정리합니다. 사용자가 직접 실행하는 root script는 wrapper와 검증 없이 바로 옮기지 않습니다.
