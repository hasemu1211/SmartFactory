# 좁은 공간 주행 검증·튜닝 프로토콜 — TurtleBot3급 리프트 AMR

작성일: 2026-07-03 KST  
대상: SmartFactory drive / Nav-Movement 개발  
연계 문서: `docs/technical/narrow-space-ros2-nav2-drive-research-2026-07-03.md` [src_001]

> 결론: 이전 문서는 “무엇을 바꿀지”를 정리했고, 이 문서는 “어떤 순서로 측정하고, 어떤 지표가 나빠지면 무엇을 조정할지”를 정리한다. 좁은 공간 주행은 파라미터 세트 하나로 끝내면 안 되고, **같은 route·같은 bag·같은 하중·같은 footprint 상태에서 한 번에 한 변수만 바꾸는 실험 프로토콜**로 관리해야 한다.

---

## 0. 이번 추가 조사에서 발견한 더 봐야 할 지점

이전 조사만으로 1차 구현 방향은 충분하지만, “안전하고 부드럽고 강건한 주행”까지 가려면 아래 항목은 별도 실험으로 남겨야 한다.

1. **실측 latency/jitter budget**: `/scan → local costmap → controller → velocity smoother → collision monitor → base driver` 체인의 p50/p95/p99 지연을 bag·topic statistics·tracing으로 분리해야 한다. ROS 2 Topic Statistics는 subscription 측에서 message age와 period를 측정하고 평균/최대/최소/표준편차/sample count를 제공한다. [src_003] [src_004]
2. **현재 로봇의 계측 가능성 차이**: SSH probe 기준 로봇에는 `rosbag2-storage-mcap`, `tf2-tools`, `statistics-msgs`, `libstatistics-collector`, `tracetools`가 설치되어 있지만 `ros2 trace` CLI는 현재 없다. 따라서 바로 가능한 계측은 `ros2 bag`, `ros2 topic`, `tf2_tools/tf2_monitor`이고, 정밀 callback tracing은 `ros-jazzy-ros2trace` 등 추가 설치 후로 분리해야 한다. [src_002]
3. **bag 기반 회귀 체계**: ROS 2 bag은 topic/service/action 데이터를 기록해 재생·검사할 수 있고, rosbag2는 ROS 2 통신 record/playback 도구다. 즉 좁은 통로 성공/실패 주행은 사람이 기억하지 말고 MCAP bag + 분석 리포트로 남겨야 한다. [src_007] [src_008]
4. **recovery 정책 제한**: Nav2 기본 BT는 복구를 위해 costmap clearing, spinning, waiting, backing up 등을 쓸 수 있다. 좁은 통로에서는 spin/back-up이 충돌을 유발할 수 있으므로 narrow-mode BT를 분리해야 한다. [src_021] [src_022]
5. **route/speed/keepout 정책화**: 좁은 통로는 자유공간 최단경로보다 route graph, preferred lane, keepout/speed zone을 쓰는 쪽이 디버깅과 재현성이 높다. Nav2는 keepout filter, speed filter, route server를 제공한다. [src_018] [src_019] [src_020]

---

## 1. 현재 로봇에서 확인된 baseline

SSH pane `Smartfactory:2.3`에서 2026-07-03에 확인한 상태는 다음과 같다. [src_002]

- OS/kernel: Ubuntu 24.04.4 LTS, aarch64, Raspberry Pi 계열 커널 `6.8.0-1057-raspi`, `PREEMPT_DYNAMIC`.
- CPU/RAM: 4 cores, 약 3.6 GiB RAM.
- ROS: Jazzy, `RMW_IMPLEMENTATION=rmw_fastrtps_cpp`, `ROS_DOMAIN_ID=2`, `ROS_AUTOMATIC_DISCOVERY_RANGE=SUBNET`, `ROS_STATIC_PEERS=192.168.30.5;192.168.10.57;192.168.0.160`.
- Fast DDS profile: participant lease 8 s, announcement 2 s.
- 설치 확인: `ros-jazzy-rosbag2-storage-mcap`, `ros-jazzy-tf2-tools`, `ros-jazzy-statistics-msgs`, `ros-jazzy-libstatistics-collector`, `ros-jazzy-tracetools`.
- 미확인/부재: `ros2 trace` CLI subcommand는 현재 없음.
- ROS graph: probe 시점에는 `/parameter_events`, `/rosout`만 보여 실제 bringup은 실행 중이 아니었다.
- time sync: system clock synchronized yes, NTP active, RTC 없음.

이 baseline 때문에 첫 실험은 **패키지 설치 없이 가능한 계측**부터 시작한다. 이후 tracing이나 CycloneDDS 설치/전환은 실험 2단계로 둔다.

---

## 2. 원칙: 좁은 공간 튜닝은 “속도”가 아니라 “오차 예산” 문제

좁은 공간 주행 pass/fail은 아래 식을 통과해야 한다. [src_001]

```text
한쪽 실제 여유폭
  > localization 오차 p95
  + map/grid 오차
  + footprint 실측 오차
  + controller tracking 오차 p95
  + braking/stop distance
  + 센서 사각/검출 오차
  + 정책 safety margin
```

따라서 drive팀은 매 실험마다 다음 값들을 같이 기록한다.

| 구분 | 기록값 |
|---|---|
| 물리 | 통로 폭, 바닥 상태, 리프트 up/down, 적재 유무/무게, 실제 polygon footprint |
| 맵 | map 해상도, 벽/통로 폭 실측 오차, inflation 설정 |
| localization | AMCL pose, odom/filtered, marker 기준 pose error, covariance/score 가능 시 |
| control | controller frequency, `/cmd_vel` period, accel/decel/jerk, stop count |
| safety | collision monitor polygon state, false stop, missed stop, source timeout |
| comms | RMW, discovery range, QoS, topic period/age, TF age |

---

## 3. 계측 레이어

### 3.1 항상 남길 read-only snapshot

실험 시작 전후로 같은 명령을 남긴다. 목적은 “어떤 설정에서 성공/실패했는지”를 재현 가능하게 만드는 것이다.

```bash
mkdir -p ~/narrow_logs/$(date +%Y%m%d_%H%M%S)
LOG=~/narrow_logs/$(date +%Y%m%d_%H%M%S)

{
  date
  hostname
