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
  uname -a
  lsb_release -ds 2>/dev/null || true
  printenv | grep -E '^(ROS|RMW|CYCLONE|FAST|DDS|TURTLEBOT)' | sort
  ros2 node list
  ros2 topic list
  ros2 doctor --report 2>/dev/null || true
} | tee "$LOG/env_graph.txt"

ros2 topic info /scan -v 2>&1 | tee "$LOG/qos_scan.txt"
ros2 topic info /odom -v 2>&1 | tee "$LOG/qos_odom.txt"
ros2 topic info /tf -v 2>&1 | tee "$LOG/qos_tf.txt"
ros2 topic info /cmd_vel -v 2>&1 | tee "$LOG/qos_cmd_vel.txt"
```

QoS는 ROS 2에서 reliability, durability, deadline, lifespan 같은 정책 조합으로 동작하고, publisher/subscriber profile이 호환되지 않으면 메시지가 전달되지 않을 수 있다. 특히 `lifespan`은 publish부터 receive까지 오래된 메시지를 stale/expired로 간주해 버리는 정책이므로 명령·센서 지연 분석에 중요하다. [src_010]

### 3.2 MCAP bag capture

로봇에 MCAP storage plugin이 설치되어 있으므로 지금 바로 가능하다. ROS 2 공식 문서는 `ros2 bag record`가 여러 topic/service/action 데이터를 저장하고, 기록 후 `ros2 bag info`와 `ros2 bag play`로 검사·재생할 수 있다고 설명한다. [src_007]

권장 topic set:

```bash
ros2 bag record -s mcap -o narrow_$(date +%Y%m%d_%H%M%S) \
  /scan \
  /odom \
  /tf \
  /tf_static \
  /amcl_pose \
  /particlecloud \
  /cmd_vel \
  /cmd_vel_nav \
  /cmd_vel_smoothed \
  /local_costmap/costmap \
  /local_costmap/published_footprint \
  /global_costmap/costmap \
  /behavior_tree_log \
  /collision_monitor_state \
  /statistics
```

없는 topic은 실험 구성에 맞게 제외한다. 고대역 camera raw는 기본 bag에서 제외하고, 별도 실험에서만 10~30초 구간으로 분리한다.

### 3.3 Topic Statistics

Topic Statistics는 subscription 측에서 message age/period를 moving window로 계산하고 `/statistics` 같은 topic에 `statistics_msgs/msg/MetricsMessage`를 publish할 수 있다. [src_003] [src_004]

사용 전략:

- drive팀 custom monitor node를 하나 만들어 `/scan`, `/odom`, `/cmd_vel*`, `/amcl_pose` subscription에 topic statistics를 켠다.
- bag에는 `/statistics`를 항상 포함한다.
- message age가 NaN이면 해당 message header timestamp가 비어 있거나 계산 불가라는 뜻이므로, driver timestamp 정책도 함께 점검한다. [src_003]

### 3.4 TF age / transform stability

TF 도구는 transform 숫자 확인, tree 시각화, rate/delay 확인에 쓴다. `tf2_echo`는 특정 transform의 numeric value를 보고, `view_frames`는 TF tree와 average rate, buffer length, most recent transform delay 같은 시간 통계를 PDF로 만든다. [src_009]

```bash
ros2 run tf2_tools view_frames
ros2 run tf2_ros tf2_monitor map base_link
ros2 run tf2_ros tf2_monitor odom base_link
ros2 run tf2_ros tf2_echo base_link base_scan
```

판정:

- `map→odom`, `odom→base_link`, `base_link→base_scan/camera` 중 하나라도 끊기면 navigation 튜닝 전에 TF부터 고친다.
- `most recent transform` delay가 controller period보다 크거나 출렁이면 speed/controller 튜닝보다 timestamp/clock/source rate를 먼저 본다.

### 3.5 ros2_tracing — 2단계 정밀 계측

`ros2_tracing` provides ROS2 core tracing instrumentation plus CLI/launch tools and currently uses LTTng/Linux. [src_005] [src_006]

현재 로봇에는 `tracetools`는 있으나 `ros2 trace` CLI가 없으므로, 패키지 설치 권한이 생기면 아래를 후보로 둔다.

```bash
sudo apt-get install ros-jazzy-ros2trace ros-jazzy-tracetools-analysis babeltrace
ros2 run tracetools status
ros2 trace --session-name narrow_nav --list
# 별도 terminal에서 bringup/nav 실행 후 stop
babeltrace ~/.ros/tracing/narrow_nav | less
```

주의:

- tracing은 시작 시점 metadata가 중요하므로 가능하면 launch 전에 켠다. [src_005]
- continuous tracing은 디스크 부하가 생길 수 있으므로 snapshot/dual-session은 추후 장시간 현장 디버깅용으로 검토한다. [src_005]

---

## 4. 테스트 사다리

좁은 공간 주행은 바로 좁은 통로에서 시작하지 않는다. 각 단계 pass 후 다음 단계로 간다.

| 단계 | 환경 | 허용 동작 | pass 기준 |
|---|---|---|---|
| L0 Config | 로봇 정지/bringup 없음 | yaml/URDF/footprint review | footprint 좌표와 리프트 실측치 일치 |
| L1 Passive | bringup + sensor only | `/cmd_vel` 금지, topic/TF/bag만 | scan/odom/tf/camera rate 안정, QoS mismatch 없음 |
| L2 Raised wheels | 바퀴 공중 | low cmd replay 가능 | stale cmd 없음, watchdog stop 동작 |
| L3 Open floor | 넓은 공간 | 저속 직선/회전 | path tracking RMS와 cmd jitter baseline 확보 |
| L4 Wide aisle | 충분히 넓은 임시 통로 | narrow profile 적용 | collision monitor false stop 과다 없음 |
| L5 Step-down aisle | 폭을 5 cm 단위로 축소 | 동일 route 반복 | clearance margin이 오차 예산보다 큼 |
| L6 Lift/load | 리프트/하중 포함 | loaded footprint | 회전 sweep, braking distance 재검증 |
| L7 Disturbance | 사람/박스/부분 막힘 | stop/slow/backout | risky recovery 없이 fail-safe |

SmartFactory의 기존 docking runbook도 passive → static calibration → low-speed active로 나눠 `/cmd_vel` publish를 명시적으로 gated step으로 둔다. narrow drive 실험도 같은 안전 철학을 따른다. [src_023] [src_024]

---

## 5. A/B 실험 매트릭스

### 공통 규칙

- 한 run에서 바꾸는 변수는 하나만 둔다.
- 같은 시작 pose, 같은 route, 같은 하중, 같은 lift state, 같은 통로 폭을 유지한다.
- 각 설정은 최소 5회 반복한다. 단, 충돌/near-miss는 1회만 발생해도 해당 설정은 fail로 정지한다.
- 결과는 `bag + env_graph.txt + metrics.csv + operator notes` 묶음으로 저장한다.

### E0. Baseline capture

목적: 현재 Fast DDS + SUBNET + 기존 bringup에서 topic/TF/control 상태를 기록한다. [src_002] [src_011]

측정:

- `/scan`, `/odom`, `/tf`, `/cmd_vel` hz/bw.
- TF tree PDF.
- 60초 stationary bag, 60초 open-floor straight bag.

pass:

- scan/odom topic이 nominal rate에서 큰 drop 없이 유지.
- TF lookup failure 없음.
- `/cmd_vel` 정지 후 base driver가 계속 움직이지 않음.

### E1. Discovery scope A/B

ROS 2는 기본적으로 같은 subnet의 node를 자동 발견하며, `ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST`와 `ROS_STATIC_PEERS`로 발견 범위를 제어할 수 있다. [src_011]

비교:

1. Fast DDS + `SUBNET`.
2. Fast DDS + `LOCALHOST` + static peers.
3. 필요 시 `OFF` + static-only 검토.

측정:

- bringup 후 graph 안정화 시간.
- ghost participant/끊긴 topic 발생 여부.
- `/scan` message period p95/p99.
- CPU/network 변화.

판정:

- 같은 기능이면 `LOCALHOST + static peers`가 기본 후보.
- 통신이 불안정하면 static peer IP, firewall, multicast, domain id부터 확인하고 RMW 교체는 E8로 미룬다.

### E2. QoS/depth/lifespan/stale command

QoS 정책은 best-effort/reliable, keep_last depth, transient_local/volatile, deadline, lifespan 등을 포함한다. `lifespan`은 오래된 메시지가 수신되지 않도록 하는 stale-drop 장치로 쓸 수 있다. [src_010]

실험:

- `/scan`: best_effort + keep_last 1~3 vs reliable.
- `/cmd_vel*`: queue depth 1~3, driver watchdog, 가능하면 TwistStamped path.
- `/map`, `/tf_static`: reliable/transient_local 유지.

측정:

- message age p95/p99.
- stale command execution count.
- topic info QoS compatibility.

판정:

- sensor는 drop보다 queue latency가 더 위험하면 best_effort/shallow queue 우선.
- command는 오래된 명령 실행이 0이어야 한다.

### E3. Map/costmap/inflation

Nav2 tuning guide는 비원형 로봇에서는 실제 geometric footprint를 주는 것이 tighter space planning과 collision checking에 중요하다고 설명한다. [src_017]

비교:

- local costmap resolution: 0.05 / 0.03 / 0.02 m.
- inflation radius/cost scaling 조합.
- footprint padding: 0 / 0.005 / 0.01 m.

측정:

- narrow aisle에서 path blocked 비율.
- wall clearance minimum.
- costmap update cycle time.
- false obstacle / clearing delay.

판정:

- 통로가 costmap상 막히면 inflation을 줄이는 것이 아니라 map width, footprint, inflation, route centerline, 실제 여유폭을 함께 본다.
- CPU가 부족하면 0.02 m를 고집하지 말고 local window와 update_frequency를 줄인다.

### E4. Localization / odom fusion

측정:

- marker/줄자 기준 lateral error, yaw error.
- AMCL update threshold A/B.
- odom drift over 1 m straight, 90도 회전, loaded/unloaded.
- TF age와 `map→odom` jump.

판정:

- 좁은 구간 진입 전 pose error p95가 한쪽 여유폭의 1/3을 넘으면 Nav2 parameter 튜닝보다 marker correction/docking mode/route constraint가 우선이다.

### E5. Controller / smoother

Nav2 Controller Server의 기본 `controller_frequency`는 20 Hz이고 `use_realtime_priority`는 controller thread priority를 높여 missed loop를 줄이기 위한 옵션이다. [src_013] Velocity Smoother는 Nav2 velocity command를 accel/deadband 제약으로 smoothing하고 controller보다 높은 rate로 interpolation할 수 있다. [src_014]

비교:

- controller_frequency: 20 / 30 / 40 Hz.
- RPP lookahead: 짧음/중간/김.
- max linear: 0.03 / 0.05 / 0.08 m/s.
- smoothing_frequency: 30 / 60 / 80 Hz.

측정:

- lateral RMS, max lateral error.
- angular oscillation count.
- cmd_vel period jitter.
- jerk proxy: `Δcmd_vel / Δt`와 `Δangular_z / Δt`.
- stop-and-go count.

판정:

- controller frequency를 올렸는데 jitter가 커지면 낮춘다.
- 부드러움은 최고속도보다 accel/decel/jerk와 lookahead가 좌우한다.
- 회전 진입이 덜컥거리면 Rotation Shim 또는 route heading alignment를 분리해 본다.

### E6. Collision Monitor envelope

Collision Monitor는 costmap/planner를 우회해 sensor data로 emergency-stop 수준 collision prevention을 수행한다. [src_015] Collision Monitor Node는 polygon/circle/velocity polygon zone과 stop/slowdown/limit/approach 모델을 제공하며, source timeout 시 정지시키는 설정도 있다. [src_016]

비교:

- front_lift_stop polygon 크기.
- front_lift_slow polygon 크기와 slowdown ratio.
- min_points 1/2/3.
- release_consecutive_points hysteresis.
- velocity polygon: 전진/후진/회전별 zone.

측정:

- obstacle insertion 후 stop distance.
- false stop rate.
- missed obstacle count.
- source timeout stop 동작.

판정:

- stop zone은 실제 brake distance + sensor age + controller period를 포함해야 한다.
- false stop은 min_points/release hysteresis로 줄이되, missed stop이 생기면 무조건 보수적으로 되돌린다.

### E7. Route / keepout / speed zone

Keepout Filter는 robot이 들어가면 안 되는 zone과 preferred lane을 costmap filter로 표현할 수 있고, Speed Filter는 map에 표시된 restriction area에서 최대속도를 제한한다. [src_018] [src_019] Route Server는 predefined navigation graph로 route를 계산해 freespace planning을 대체하거나 보강한다. [src_020]

실험:

- 좁은 aisle centerline route graph 생성.
- aisle 내부 speed zone 적용.
- 선반/리프트 충돌 위험 영역 keepout mask 적용.
- global replanning 제한/허용 비교.

측정:

- aisle entry alignment 성공률.
- 통로 내부 path deviation.
- recovery 발생 횟수.
- route graph 이탈 횟수.

판정:

- 좁은 통로는 자유공간 탐색보다 route-following이 우선이다.
- 통로 내부에서 global replan이 lateral jump를 만들면 replan rate/context를 줄인다.

### E8. RMW A/B — 마지막에 한다

ROS 2는 `RMW_IMPLEMENTATION`으로 Fast DDS, Cyclone DDS 등 구현을 선택할 수 있고, 기본 RMW vendor는 Fast DDS다. [src_012]

비교:

1. Fast DDS current.
2. Fast DDS + discovery constrained.
3. CycloneDDS + equivalent peer/interface settings.

측정:

- graph discovery time.
- message age/period p95/p99.
- lost graph/topic incidents.
- CPU/RAM.
- bag replay consistency.

판정:

- RMW 교체는 latency p95/p99 또는 discovery 안정성에서 이득이 있을 때만 채택한다.
- RMW를 바꿨으면 모든 shell/service에서 동일 env를 쓰고, ROS daemon을 재시작한다. [src_012]

---

## 6. Pass/Fail 게이트 초안

아래 숫자는 production 보증값이 아니라 **lab tuning 시작 기준**이다. 실제 통로 폭/속도/센서 rate를 넣어 조정한다.

| 게이트 | 시작 기준 | fail이면 |
|---|---:|---|
| TF lookup failure | 0 | frame/timestamp/clock부터 수정 |
| `/scan` period p95 | nominal period의 1.5배 이하 | QoS/depth/CPU/DDS/driver 확인 |
| `/odom` or filtered odom | 30 Hz 이상 권장 | EKF/base driver rate 확인 |
| cmd_vel stale execution | 0 | depth/lifespan/watchdog/TwistStamped 검토 |
| controller missed loop | 1% 미만 목표 | frequency 낮춤, realtime priority, CPU 부하 분리 |
| lateral RMS | 한쪽 여유폭의 1/3 이하 | speed/lookahead/localization/route 수정 |
| min clearance | 정책 margin보다 큼 | footprint/inflation/route/speed 재조정 |
| collision monitor missed stop | 0 | stop polygon 확대, source timeout 단축 |
| false stop | 반복 demo 가능한 수준 | min_points/release hysteresis 조정 |
| risky recovery in aisle | 0 | narrow BT에서 spin/back-up 금지 또는 조건부화 |

---

## 7. Narrow-mode BT / recovery 정책

BT Navigator는 NavigateToPose/NavigateThroughPoses 같은 task interface를 behavior tree로 구현해 복잡한 navigation behavior와 recovery를 지정할 수 있다. [src_021] 기본 NavigateToPose tree는 replanning과 여러 recovery를 제공하지만, 좁은 통로에서는 recoveries를 그대로 쓰면 위험하다. [src_022]

권장 narrow-mode 상태:

```text
Outside aisle
  -> align_to_entry_pose
  -> enter_narrow_mode
      - speed filter active
      - collision monitor narrow polygons active
      - controller = RPP_narrow
      - planner/route = aisle centerline
      - recovery = wait/stop/relocalize only
  -> traverse aisle
  -> exit_narrow_mode
```

금지/주의:

- aisle 내부 blind spin 금지.
- 후진 recovery는 뒤쪽 clearance와 rear sensor가 검증된 경우만 허용.
- costmap clearing은 sensor dropout을 숨길 수 있으므로 반복 clearing 후 주행 재개 금지.
- localization low confidence면 stop 후 operator/relocalization flow.

---

## 8. 분석 산출물 형식

각 실험 run은 다음 디렉터리 구조로 남긴다.

```text
narrow_runs/YYYYMMDD_HHMMSS_<experiment_id>/
├── env_graph.txt
├── qos_scan.txt
├── qos_odom.txt
├── qos_tf.txt
├── qos_cmd_vel.txt
├── frames.pdf
├── run.mcap
├── metrics.csv
├── operator_notes.md
└── verdict.md
```

`metrics.csv` 최소 컬럼:

```csv
run_id,experiment,robot_id,lift_state,load_state,aisle_width_m,map_resolution_m,rmw,discovery,controller,controller_hz,smoother_hz,max_linear_mps,scan_period_p95_ms,odom_period_p95_ms,tf_age_p95_ms,cmd_period_p95_ms,lateral_rms_m,lateral_max_m,min_clearance_m,stop_count,false_stop_count,missed_stop_count,recovery_count,verdict
```

---

## 9. Drive팀 실행 순서

1. **L1 passive baseline**: 현재 Fast DDS/SUBNET 상태에서 60초 stationary bag과 TF PDF를 만든다.
2. **측정 스크립트 작성**: bag에서 topic period, cmd jerk, lateral error, stop count를 계산하는 offline analyzer를 만든다.
3. **E1 discovery 축소**: `LOCALHOST + ROS_STATIC_PEERS`로 바꾼 상태를 기존 baseline과 비교한다.
4. **footprint/map 고정**: 리프트 포함 polygon과 route centerline 없이는 controller tuning에 들어가지 않는다.
5. **E3~E5 반복**: costmap → localization → controller/smoother 순서로 튜닝한다.
6. **E6 safety envelope**: collision monitor false/missed stop을 통과시킨다.
7. **E7 route policy**: 좁은 aisle은 route/speed/keepout을 적용한다.
8. **E8 RMW A/B**: 마지막에만 CycloneDDS 또는 다른 RMW를 비교한다.
9. **narrow-mode release gate**: 같은 bag/route에서 5회 이상 성공, near-miss 0, stale cmd 0, risky recovery 0일 때만 demo profile로 승격한다.

---

## 10. 바로 할 수 있는 다음 작업

- [ ] Robot bringup 중 `ros2 topic list`, `ros2 topic info -v`, `view_frames`, 60초 MCAP bag capture.
- [ ] `ros2 bag list storage` 결과에 `mcap`이 있으므로 MCAP 저장을 기본으로 사용. [src_002] [src_007]
- [ ] `/statistics`가 없으면 drive monitor node에서 Topic Statistics를 켜도록 구현. [src_003] [src_004]
- [ ] `ros2 trace`가 없으므로 정밀 tracing은 설치 승인 후 별도 runbook으로 분리. [src_002] [src_005]
- [ ] 기존 docking passive/active guardrail과 같은 방식으로 `/cmd_vel` publish는 명시 permission gate를 유지. [src_023]

---

## Sources

- [src_001] SmartFactory local research, `docs/technical/narrow-space-ros2-nav2-drive-research-2026-07-03.md`.
- [src_002] Local tmux SSH robot probe, `Smartfactory:2.3`, 2026-07-03 KST.
- [src_003] ROS 2 Documentation, “Topic Statistics,” raw documentation source, accessed 2026-07-03. https://raw.githubusercontent.com/ros2/ros2_documentation/rolling/source/Concepts/Intermediate/About-Topic-Statistics.rst
- [src_004] ROS 2 Documentation, “Enabling topic statistics (C++),” raw documentation source, accessed 2026-07-03. https://raw.githubusercontent.com/ros2/ros2_documentation/rolling/source/Tutorials/Advanced/Topic-Statistics-Tutorial/Topic-Statistics-Tutorial.rst
- [src_005] ros2/ros2_tracing, “Tracing tools for ROS 2,” GitHub README, accessed 2026-07-03. https://github.com/ros2/ros2_tracing
- [src_006] ROS 2 Documentation, “How to use ros2_tracing to trace and analyze an application,” raw documentation source, accessed 2026-07-03. https://raw.githubusercontent.com/ros2/ros2_documentation/rolling/source/Tutorials/Advanced/ROS2-Tracing-Trace-and-Analyze.rst
- [src_007] ROS 2 Documentation, “Recording and playing back data,” raw documentation source, accessed 2026-07-03. https://raw.githubusercontent.com/ros2/ros2_documentation/rolling/source/Tutorials/Beginner-CLI-Tools/Recording-And-Playing-Back-Data/Recording-And-Playing-Back-Data.rst
- [src_008] ros2/rosbag2, “Rosbag2,” GitHub README, accessed 2026-07-03. https://github.com/ros2/rosbag2
- [src_009] ROS 2 geometry2, “tf2_ros Command Line Tools,” raw documentation source, accessed 2026-07-03. https://raw.githubusercontent.com/ros2/geometry2/rolling/tf2_ros/doc/cli_tools.rst
- [src_010] ROS 2 Documentation, “Quality of Service settings,” raw documentation source, accessed 2026-07-03. https://raw.githubusercontent.com/ros2/ros2_documentation/rolling/source/Concepts/Intermediate/About-Quality-of-Service-Settings.rst
- [src_011] ROS 2 Documentation, “Improved Dynamic Discovery,” raw documentation source, accessed 2026-07-03. https://raw.githubusercontent.com/ros2/ros2_documentation/rolling/source/Tutorials/Advanced/Improved-Dynamic-Discovery.rst
- [src_012] ROS 2 Documentation, “Working with multiple ROS 2 middleware implementations,” raw documentation source, accessed 2026-07-03. https://raw.githubusercontent.com/ros2/ros2_documentation/rolling/source/How-To-Guides/Working-with-multiple-RMW-implementations.rst
- [src_013] Open Navigation LLC, “Controller Server,” Nav2 documentation, accessed 2026-07-03. https://docs.nav2.org/configuration/packages/configuring-controller-server.html
- [src_014] Open Navigation LLC, “Velocity Smoother,” Nav2 documentation, accessed 2026-07-03. https://docs.nav2.org/configuration/packages/configuring-velocity-smoother.html
- [src_015] Open Navigation LLC, “Collision Monitor,” Nav2 documentation, accessed 2026-07-03. https://docs.nav2.org/configuration/packages/configuring-collision-monitor.html
- [src_016] Open Navigation LLC, “Collision Monitor Node,” Nav2 documentation, accessed 2026-07-03. https://docs.nav2.org/configuration/packages/collision_monitor/configuring-collision-monitor-node.html
- [src_017] Open Navigation LLC, “Tuning Guide,” Nav2 documentation, accessed 2026-07-03. https://docs.nav2.org/tuning/index.html
- [src_018] Open Navigation LLC, “Navigating with Keepout Zones,” Nav2 tutorial, accessed 2026-07-03. https://docs.nav2.org/tutorials/docs/navigation2_with_keepout_filter.html
- [src_019] Open Navigation LLC, “Navigating with Speed Limits,” Nav2 tutorial, accessed 2026-07-03. https://docs.nav2.org/tutorials/docs/navigation2_with_speed_filter.html
- [src_020] Open Navigation LLC, “Route Server,” Nav2 documentation, accessed 2026-07-03. https://docs.nav2.org/configuration/packages/configuring-route-server.html
- [src_021] Open Navigation LLC, “Behavior-Tree Navigator,” Nav2 documentation, accessed 2026-07-03. https://docs.nav2.org/configuration/packages/configuring-bt-navigator.html
- [src_022] Open Navigation LLC, “Detailed Behavior Tree Walkthrough,” Nav2 documentation, accessed 2026-07-03. https://docs.nav2.org/behavior_trees/overview/detailed_behavior_tree_walkthrough.html
- [src_023] SmartFactory local runbook, `docs/robot/docking-tuning-runbook.md`.
- [src_024] SmartFactory local template, `config/perception/docking_tuning.example.yaml`.
