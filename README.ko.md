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
- `smartfactory-vision.local`은 이 repo 안에서는 임시 mDNS helper 기반입니다. 신경 쓰지 않아도 되는 운영 상태를 원하면 router/DNS/hostname 설정이 별도로 필요합니다.
- `WMS_EMIT_ENABLED=false`가 안전 기본값입니다.

## 정리 원칙

폴더는 보기 좋은 이름이 아니라 실제 용도, 호출자, 운영 역할, 참조관계 기준으로 정리합니다. 사용자가 직접 실행하는 root script는 wrapper와 검증 없이 바로 옮기지 않습니다.
