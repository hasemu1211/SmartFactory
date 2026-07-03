# 좁은 공간 주행용 ROS2/Nav2 Drive 기술조사 — TurtleBot3급 리프트 AMR

작성일: 2026-07-03 KST  
대상: SmartFactory drive / Nav-Movement 개발  
범위: TurtleBot3 Burger급 소형 2륜 차동 로봇 + 전방 리프트/하중부가 있는 실내 데모 AMR의 **저지연 통신, 좌표/맵 정확도, 실제 점유영역, 좁은 통로 안전주행** 설계·튜닝 항목.

> 핵심 결론: cm 단위 여유가 없는 주행은 “DDS를 하나로 바꾸는 것”만으로 해결되지 않는다. 반드시 `측정된 footprint + 오차 예산 + 고품질 map/localization + local costmap/controller/safety stop`를 하나의 폐루프로 맞춰야 한다. DDS/RMW는 그중 **지연·발견 노이즈를 줄이는 기반 작업**이다.

---

## 1. 현재 로봇/프로젝트에서 확인된 단서

- SSH된 로봇 터미널(`Smartfactory:2.3`)에서 2026-07-03 기준 로봇은 Ubuntu 24.04.4 LTS, Raspberry Pi aarch64 커널, ROS 2 Jazzy 환경으로 관찰됐다. 환경값은 `RMW_IMPLEMENTATION=rmw_fastrtps_cpp`, `ROS_AUTOMATIC_DISCOVERY_RANGE=SUBNET`, `ROS_DOMAIN_ID=2`, `ROS_STATIC_PEERS=192.168.30.5;192.168.10.57;192.168.0.160`, `TURTLEBOT3_MODEL=burger`였다. [src_019]
- 로봇 쪽 설치 패키지 probe에서는 `rmw_fastrtps_cpp`/Fast DDS 계열과 `turtlebot3_msgs`만 보였고, 홈에는 `~/turtlebot3_ws`, `~/camera_ws`가 있었다. 즉 Nav2는 로봇 SBC보다 Nav/Movement PC 쪽에서 운용될 가능성이 높다. [src_019]
- 이전 launch 로그상 base bringup은 `turtlebot3_bringup robot.launch.py`로 OpenCR/Dynamixel/IMU/odom을 올리고, LiDAR는 `single_coin_d4_node`가 `/dev/tb3_lidar`를 사용했다. Pi camera는 IMX219이며 `camera_low_bandwidth.launch.py`에서 320x240 XRGB stream을 올렸지만 camera calibration yaml이 없어 warning/error가 있었다. [src_019]
- SmartFactory 아키텍처상 motion authority는 Nav/Movement Server가 갖고, Vision은 advisory/evidence로 분리되어야 한다. `/cmd_vel`, Nav2 action, whole-graph DDS, `/tf`, `/rosout`는 vision contract에 노출하지 않는 경계가 이미 문서화되어 있다. [src_020] [src_022]
- 기능 요구사항은 TurtleBot3 Burger 2대가 ROS2/Nav2 목표지점으로 이동하고, 사전 생성된 SLAM Toolbox map + Nav2 localization으로 데모 주행하는 것이다. [src_021]
- 공식 TurtleBot3 Burger 사양은 작지만 이미 폭이 약 178 mm이고, 최대 병진 속도는 0.22 m/s 수준이다. 리프트/하중부가 전방에 붙으면 실제 footprint는 기본 Burger보다 길고 비대칭이 된다. [src_017] [src_018]

---

## 2. 성공 기준: “cm clearance”는 오차 예산으로 먼저 판정

좁은 공간에서 안전하게 “막힘없이” 지나가려면 파라미터값보다 먼저 다음 부등식이 만족되어야 한다.

```text
한쪽 여유폭 >
  localization 95% 오차
+ map/grid quantization 오차
+ footprint 측정/장착 오차
+ controller tracking 오차
+ 센서 장애물 검출 오차
+ 정책상 safety margin
```

Nav2 costmap의 `resolution`은 cell 크기이며, 작게 잡을수록 장애물 디테일은 좋아지지만 계산량이 증가한다고 문서화되어 있다. 기본 예제는 0.05 m를 흔히 쓰지만, cm 단위 여유를 논하려면 local costmap은 0.02~0.03 m부터 실측 A/B가 필요하다. [src_005] [src_013]

**drive팀 판정 규칙:** 통로 폭과 로봇 최외곽 footprint를 실측한 뒤, 위 오차 예산이 한쪽 여유폭의 60~70%를 넘으면 “파라미터 튜닝”이 아니라 **속도 제한, route centerline, docking/marker 보조, 추가 근접센서, 물리 가이드**가 필요하다고 봐야 한다.

---

## 3. 우선 변경/검증해야 할 레이어별 항목

### A. 물리 footprint / URDF / TF

1. **`robot_radius` 금지, polygon footprint 사용.** 리프트가 전방에 달린 로봇은 원형 근사가 위험하다. Nav2 costmap은 `footprint` polygon을 받을 수 있고, `~/footprint` topic으로 robot shape 변경도 반영할 수 있다. 문서 예시도 부착 manipulator나 pallet 때문에 footprint가 바뀌는 경우를 언급한다. [src_005]
2. **리프트 상태별 footprint를 분리한다.** 최소 `lift_down_empty`, `lift_up_loaded`, `lift_down_loaded` 3개 polygon을 실측하고, 주행 모드 전환 시 dynamic footprint를 publish한다. collision monitor polygon도 동일한 상태 모델을 따라야 한다. [src_005] [src_010]
3. **TF tree를 엄격히 고정한다.** Nav2는 `map=>odom`, `odom=>base_link`, `base_link=>sensor` transform을 요구한다. LiDAR/camera/lift 센서 extrinsic이 틀리면 장애물과 footprint가 서로 다른 좌표계에서 어긋난다. [src_014]
4. **Pi camera calibration부터 해결한다.** 현재 로그에 IMX219 calibration yaml 없음이 보인다. docking/marker/lift ROI를 active control에 쓰려면 `camera_info`와 optical frame이 실제 캘리브레이션 파일로 고정되어야 한다. [src_019] [src_023]

### B. DDS/RMW/ROS graph: “싱글방식”의 실제 의미

1. **한 robot-domain 안에서는 RMW를 하나로 고정한다.** 현재 로봇은 Fast DDS(`rmw_fastrtps_cpp`)다. ROS 2는 `RMW_IMPLEMENTATION`으로 RMW를 선택하며, 다른 RMW로 바꿀 때는 ROS daemon이 이전 RMW로 떠 있으면 CLI와 graph가 꼬일 수 있어 `ros2 daemon stop`이 필요하다. [src_003]
2. **멀티캐스트 discovery 범위를 줄인다.** 현재 `ROS_AUTOMATIC_DISCOVERY_RANGE=SUBNET`은 같은 subnet 노드를 자동 발견한다. ROS 2는 `LOCALHOST`와 `ROS_STATIC_PEERS` 조합으로 localhost + 지정 peer만 발견하게 할 수 있다. Nav PC↔Robot 구조에서는 `LOCALHOST + ROS_STATIC_PEERS=<NavPC/RobotIP>`가 노이즈/ghost participant를 줄이는 기본안이다. [src_002]
3. **Fast DDS 유지 vs CycloneDDS 전환은 A/B로 결정한다.** ROS 2는 Fast DDS, Cyclone DDS 등 여러 DDS/RMW를 지원하고 default는 Fast DDS다. “Cyclone이 무조건 빠르다”가 아니라, 현재 네트워크/CPU/토픽 수에서 discovery 안정성, topic latency, packet loss를 계측해 결정해야 한다. [src_004]
4. **QoS는 토픽별로 다르게 둔다.** ROS 2 sensor data profile은 최신 샘플 적시성이 중요해 best-effort + 작은 queue를 사용한다. 반대로 map/static data는 late joiner가 받아야 하므로 transient local/reliable 계열이 맞다. QoS mismatch는 publisher/subscriber 연결 자체를 막을 수 있으므로 `ros2 topic info -v`를 배포 체크에 넣는다. [src_001]
5. **명령 토픽은 stale command가 더 위험하다.** `/cmd_vel`은 queue를 깊게 쌓지 말고, `TwistStamped` 또는 driver watchdog/lifespan 정책으로 오래된 명령을 버리는 구조가 필요하다. Nav2 Collision Monitor의 최신 문서는 `TwistStamped` 사용 전환과 action-level velocity filtering을 다룬다. [src_010]

### C. Map / SLAM / localization

1. **맵 생성은 느린 속도 + loop closure 품질 중심.** SLAM Toolbox는 2D SLAM, pose-graph 저장/재사용, localization mode, synchronous/asynchronous mapping을 제공한다. 좁은 통로 맵은 한 번 빠르게 스캔하는 것보다 정지/저속 주행으로 loop closure와 벽 직선성이 맞는지 검수해야 한다. [src_015]
2. **AMCL update threshold를 기본값 그대로 두면 좁은 공간엔 둔하다.** Nav2 AMCL 기본 예시의 `update_min_d`는 0.25 m, `update_min_a`는 0.2 rad다. cm clearance 주행에서는 2~5 cm 이동/수도 단위 회전에서도 laser update가 반영되도록 낮춰 A/B 해야 한다. [src_007]
3. **wheel odom + IMU fusion을 별도 layer로 둔다.** robot_localization은 wheel odom/IMU 등 여러 `Odometry`, `Imu`, pose/twist covariance 입력을 EKF/UKF로 fuse해 locally smooth odometry를 만들고 `/tf`의 `odom=>base_link`도 publish할 수 있다. [src_016]
4. **정밀 docking/진입부는 AMCL만 믿지 말고 marker/fixture를 추가한다.** 좁은 구간 진입 전 “전역 map pose”를 “국소 marker pose”로 보정하는 구조가 안전하다. SmartFactory에는 이미 ArUco docking template와 `stable_frames`, `stale_timeout_ms`, low-speed active caps가 있다. [src_023]

### D. Costmap / obstacle model

1. **local costmap 해상도부터 낮춘다.** 시작값: local `resolution: 0.02~0.03`, `update_frequency: 10~15 Hz`, `publish_frequency: 2~5 Hz`, local window 1.5~2.5 m. global은 `resolution: 0.03~0.05`, `update_frequency: 1~3 Hz` 정도부터 CPU를 보며 시작한다. Nav2는 해상도 감소가 정확도/계산량 trade-off임을 명시한다. [src_005]
2. **inflation은 “큰 값=안전”이 아니다.** Inflation layer는 lethal obstacle 주변 비용을 올리고 inscribed radius 안쪽을 lethal로 처리한다. 너무 큰 inflation은 좁은 통로 전체를 막고, 너무 작은 inflation은 벽을 스치게 한다. 오차 예산 기반으로 `inflation_radius`와 `cost_scaling_factor`를 통로별로 나눠야 한다. [src_006]
3. **obstacle layer range를 센서 실측으로 제한한다.** Obstacle layer는 2D raycasting으로 LaserScan/PointCloud2를 costmap에 반영하고, `obstacle_max_range`, `raytrace_max_range`, marking/clearing을 쓴다. 전방 리프트·하중이 LiDAR를 가리거나 낮은 장애물을 못 보는 구간은 costmap만으로 안전을 보장하지 않는다. [src_010] [src_013]
4. **keepout/speed zone을 map policy로 둔다.** Nav2 최근 bringup은 keepout, speed zones, route planning 데모를 포함한다. 좁은 통로/선반/팔레트 구간은 global planner가 자유공간 전체를 탐색하게 하기보다 centerline route + speed zone + no-go zone으로 제한하는 것이 drive팀 디버깅에 유리하다. [src_026]

### E. Planner / controller

1. **기본 후보는 RPP + Rotation Shim.** Regulated Pure Pursuit는 service/industrial robot 요구를 겨냥해 곡률·장애물 근접에 따라 속도를 낮추고 path tracking을 안정화한다. 차동 TurtleBot이 좁은 통로에 진입할 때는 RPP를 1차 후보로 둔다. [src_008]
2. **RPP 시작 파라미터 예시.** 좁은 구간 mode에서는 `max_linear_vel: 0.03~0.10`, `max_angular_vel: 0.3~0.8`, `lookahead_dist: 0.15~0.35`, `use_velocity_scaled_lookahead_dist: true`, `min_lookahead_dist: 0.10~0.20`, `max_lookahead_dist: 0.35~0.50`, `max_allowed_time_to_collision_up_to_carrot: 0.5~1.0`부터 주행 로그로 조정한다. RPP docs의 기본 max linear는 0.5 m/s라 TurtleBot3 Burger 공식 최대 0.22 m/s보다 크므로 반드시 robot-specific cap을 둔다. [src_008] [src_017]
3. **controller server 주기를 올리되 missed loop를 계측한다.** Nav2 Controller Server의 기본 `controller_frequency`는 20 Hz이고 `use_realtime_priority` 옵션이 있다. Raspberry Pi에서 30~50 Hz를 목표로 하되, CPU가 못 버티면 latency가 아니라 jitter가 증가하므로 `/cmd_vel` period histogram으로 확인한다. [src_011]
4. **velocity smoother를 controller보다 높게 둔다.** Nav2 velocity smoother는 controller command를 acceleration/deadband 제약으로 smoothing하고 더 높은 rate로 interpolation할 수 있다. 50~100 Hz로 두고 base driver watchdog과 함께 stale command를 제거한다. [src_012]
5. **MPPI는 Nav PC x86에서만 2차 후보.** MPPI는 predictive sampling controller이고 modest Intel i5에서 100+ Hz 측정 사례가 문서화되어 있지만, Raspberry Pi에서 narrow mode realtime loop를 보장한다고 가정하면 안 된다. [src_024]
6. **Smac planner/route graph로 통로 중심선을 강제한다.** Smac Hybrid-A*는 cost-aware Hybrid-A* global planner이고, 좁은 구간은 자유공간에서 “최단경로”보다 centerline waypoint/route graph가 더 안정적이다. [src_025] [src_026]

### F. Safety layer

1. **Collision Monitor는 Nav2 아래 최후 필터로 둔다.** Nav2 Collision Monitor는 costmap/planner를 우회해 sensor data로 emergency-stop 수준의 collision avoidance를 수행한다. drive stack에서 controller output과 base driver 사이에 둬야 한다. [src_009]
2. **리프트 전방 polygon을 별도 stop/slowdown zone으로 둔다.** Collision Monitor는 polygon/circle zone과 `stop`, `slowdown`, `limit`, `approach` action을 제공하고, velocity polygon으로 전진/후진/회전별 polygon을 바꿀 수 있다. 전방 리프트가 실제 최전방이면 base footprint와 별도 `front_lift_stop`, `front_lift_slow` polygon이 필요하다. [src_010]
3. **narrow mode behavior tree를 분리한다.** 좁은 aisle 진입 전: speed zone 적용 → footprint state 고정 → localization covariance/AMCL score 확인 → traffic lock 획득 → controller mode 전환 → 통로 내부 재계획 제한 → 막히면 stop/backout/retry. BT Navigator는 복합 navigation behavior를 구성하는 Nav2 계층이다. [src_020] [src_026]
4. **AI/person detection은 advisory-only.** SmartFactory contract상 Vision은 motion authority가 아니므로, person/obstacle 후보는 Main/Nav 상태와 Collision Monitor/costmap 정책에 입력되는 advisory로만 둔다. [src_022]

---

## 4. 권장 ROS/DDS 환경 프로파일

### 단일 robot-domain 기본안

```bash
# 모든 robot/nav 관련 shell과 service에 동일 적용
export ROS_DISTRO=jazzy
export ROS_DOMAIN_ID=2              # robot별 분리: tb3_1=2, tb3_2=5 등
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
export ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
export ROS_STATIC_PEERS='192.168.30.5;192.168.30.101'
export FASTRTPS_DEFAULT_PROFILES_FILE=$HOME/.ros/fastdds_ghost_fix.xml
```

- 현재 로봇은 `SUBNET`이라 discovery 범위가 넓다. 우선 `LOCALHOST + static peers`로 줄이고, `/rosout`, `/parameter_events`, 카메라/scan latency를 비교한다. [src_002] [src_019]
- CycloneDDS로 바꾸려면 robot/nav PC 모두 `rmw_cyclonedds_cpp` 설치 여부를 확인하고, 모든 shell/service/env를 동시에 바꾼 뒤 `ros2 daemon stop`을 수행한다. [src_003]

### QoS 기준

| Topic group | 권장 QoS | 이유 |
|---|---|---|
| `/scan`, camera/image, obstacle sensor | best_effort, volatile, keep_last 1~3 | 최신 sensor sample이 중요하고 queue 누적은 latency로 바뀜. [src_001] |
| `/map`, `/tf_static`, static metadata | reliable + transient_local, depth 1 | late joiner가 마지막 map/static transform을 받아야 함. [src_001] |
| `/tf`, `/odom`, `/amcl_pose` | keep_last small, reliability는 실제 publisher와 호환 | QoS mismatch가 연결 실패를 만들 수 있어 `topic info -v`로 확인. [src_001] |
| `/cmd_vel` / `/cmd_vel_nav` | small queue, stale-drop watchdog, 가능하면 stamped | 오래된 velocity가 실행되는 것이 packet drop보다 위험함. [src_010] |

---

## 5. Nav2 narrow-mode starter YAML 조각

> 아래는 바로 production 적용값이 아니라 **실측 A/B 시작점**이다. 로봇 footprint, map resolution, CPU, LiDAR rate에 따라 조정한다.

```yaml
local_costmap:
  local_costmap:
    ros__parameters:
      global_frame: odom
      robot_base_frame: base_link
      rolling_window: true
      width: 2.0
      height: 2.0
      resolution: 0.02
      update_frequency: 12.0
      publish_frequency: 3.0
      transform_tolerance: 0.10
      footprint_padding: 0.005
      footprint: "[[0.16,0.11],[0.16,-0.11],[-0.11,-0.11],[-0.11,0.11]]"  # 실측으로 대체
      plugins: ["obstacle_layer", "inflation_layer"]
      obstacle_layer:
        plugin: "nav2_costmap_2d::ObstacleLayer"
        enabled: true
        observation_sources: scan
        scan:
          topic: /scan
          data_type: "LaserScan"
          marking: true
          clearing: true
          obstacle_max_range: 1.5
          raytrace_max_range: 2.0
          obstacle_min_range: 0.02
      inflation_layer:
        plugin: "nav2_costmap_2d::InflationLayer"
        inflation_radius: 0.06        # 오차 예산 + 통로 폭으로 재계산
        cost_scaling_factor: 8.0

amcl:
  ros__parameters:
    min_particles: 500
    max_particles: 2000
    update_min_d: 0.03
    update_min_a: 0.03
    transform_tolerance: 0.10
    laser_model_type: "likelihood_field"

controller_server:
  ros__parameters:
    controller_frequency: 30.0
    costmap_update_timeout: 0.15
    use_realtime_priority: true
    controller_plugins: ["FollowPath"]
    FollowPath:
      plugin: "nav2_regulated_pure_pursuit_controller::RegulatedPurePursuitController"
      max_linear_vel: 0.08
      max_angular_vel: 0.6
      max_linear_accel: 0.20
      max_linear_decel: -0.25
      lookahead_dist: 0.25
      use_velocity_scaled_lookahead_dist: true
      min_lookahead_dist: 0.12
      max_lookahead_dist: 0.40
      lookahead_time: 1.0
      use_collision_detection: true
      max_allowed_time_to_collision_up_to_carrot: 0.8

velocity_smoother:
  ros__parameters:
    smoothing_frequency: 60.0
    feedback: "CLOSED_LOOP"
    max_velocity: [0.08, 0.0, 0.6]
    min_velocity: [-0.03, 0.0, -0.6]
    max_accel: [0.20, 0.0, 1.0]
    max_decel: [-0.25, 0.0, -1.0]

collision_monitor:
  ros__parameters:
    base_frame_id: base_link
    odom_frame_id: odom
    cmd_vel_in_topic: cmd_vel_nav
    cmd_vel_out_topic: cmd_vel
    polygons: ["front_lift_stop", "front_lift_slow"]
    front_lift_stop:
      type: polygon
      points: "[[0.34,0.12],[0.34,-0.12],[0.08,-0.12],[0.08,0.12]]"
      action_type: stop
      min_points: 2
      trigger_consecutive_points: 1
      release_consecutive_points: 2
    front_lift_slow:
      type: polygon
      points: "[[0.55,0.18],[0.55,-0.18],[0.10,-0.18],[0.10,0.18]]"
      action_type: slowdown
      slowdown_ratio: 0.35
      min_points: 2
```

---

## 6. 검증 계획과 KPI

### 필수 계측

1. `ros2 topic hz /scan /odom /tf /cmd_vel`, `ros2 topic bw`를 각 mode에서 기록한다. [src_001]
2. `ros2 topic info -v`로 sensor/cmd/map/tf QoS mismatch를 배포 전에 확인한다. [src_001]
3. `/tf` 지연: `map=>odom`, `odom=>base_link`, `base_link=>scan/camera` transform lookup 실패율과 age histogram을 기록한다. [src_014]
4. `ros2 bag record -s mcap /scan /odom /tf /tf_static /amcl_pose /cmd_vel /local_costmap/costmap`로 narrow aisle bag을 남긴다.
5. AprilTag/ArUco 또는 줄자 기준점을 두고 localization error를 측정한다. docking template에는 이미 marker size, stable frame, stale timeout, low-speed caps가 있다. [src_023]

### KPI 초안

| KPI | 목표 시작값 | 실패 시 조치 |
|---|---:|---|
| `/scan` 실제 rate jitter p95 | 센서 nominal의 ±15% 이내 | QoS/depth, CPU, DDS discovery 감소 |
| `/odom`/filtered rate | 30~50 Hz | EKF/base driver rate 조정 |
| Controller loop miss | 1% 미만 | frequency 낮춤, realtime priority, CPU 격리 |
| TF lookup failure | 0 또는 rare | frame id/clock/tolerance 조정 |
| 좁은 통로 lateral RMS | 한쪽 여유폭의 1/3 이하 | speed/lookahead/AMCL/route centerline 조정 |
| stale cmd_vel 실행 | 0 | watchdog/lifespan/TwistStamped 적용 |
| collision monitor false stop | demo 허용 수준 이하 | polygon/min_points/release hysteresis 조정 |

---

## 7. drive팀 실행 순서

1. **실측 패킷 만들기:** 리프트 포함 외곽 치수, wheel separation/radius, LiDAR/camera/lift sensor pose, 통로 폭, 바닥 마찰, 최대 하중을 표준 양식으로 기록한다.
2. **TF/URDF/footprint 고정:** polygon footprint와 dynamic footprint publisher를 만들고 RViz에서 footprint가 실제 리프트 끝과 맞는지 확인한다.
3. **통신 baseline:** 현재 Fast DDS에서 `SUBNET`과 `LOCALHOST+ROS_STATIC_PEERS`를 비교한다. CycloneDDS 전환은 그 다음 A/B로만 한다.
4. **맵 생성:** SLAM Toolbox로 0.02~0.03 m map 후보와 0.05 m map 후보를 만들고 벽 직선성/폭 오차를 줄자로 검증한다.
5. **localization:** AMCL low-threshold profile과 EKF odom profile을 만들고 marker 기준 pose error를 측정한다.
6. **narrow-mode Nav2 profile:** RPP + velocity smoother + collision monitor를 별도 namespace/profile로 만들어 일반 구간과 좁은 구간을 분리한다.
7. **route policy:** 좁은 통로는 free planner보다 semantic waypoint/route graph/centerline을 우선한다. WMS semantic waypoint와 실제 map 좌표 연결 요구사항과도 맞다. [src_021] [src_026]
8. **safety gate:** Vision/person hazard는 advisory로만 두고, motion stop은 Collision Monitor/base watchdog/Nav behavior가 담당한다. [src_009] [src_022]
9. **bag 기반 회귀:** 통로 성공/실패 bag을 저장하고, 동일 bag replay에서 costmap/controller decision이 재현되는지 테스트한다.

---

## 8. 결론

가장 먼저 바꿀 것은 “DDS 종류”가 아니라 **주행 오차 예산을 만족하는 stack 구성**이다. 현재는 Fast DDS + SUBNET discovery + static peers 구성이므로, 우선 discovery range를 좁히고 QoS/queue/stale command를 정리한다. 동시에 리프트 포함 polygon footprint, local costmap 2~3 cm, AMCL/EKF 저지연 pose, RPP narrow profile, Collision Monitor 전방 polygon을 묶어 별도 narrow-mode로 만들어야 한다. 그 후 Fast DDS와 CycloneDDS는 동일 bag/동일 route에서 latency/jitter/graph 안정성으로 비교하면 된다.

## Sources

- [src_001] ROS 2 Documentation, “Quality of Service settings,” raw documentation source, accessed 2026-07-03. https://raw.githubusercontent.com/ros2/ros2_documentation/rolling/source/Concepts/Intermediate/About-Quality-of-Service-Settings.rst
- [src_002] ROS 2 Documentation, “Improved Dynamic Discovery,” raw documentation source, accessed 2026-07-03. https://raw.githubusercontent.com/ros2/ros2_documentation/rolling/source/Tutorials/Advanced/Improved-Dynamic-Discovery.rst
- [src_003] ROS 2 Documentation, “Working with multiple ROS 2 middleware implementations,” accessed 2026-07-03. https://raw.githubusercontent.com/ros2/ros2_documentation/rolling/source/How-To-Guides/Working-with-multiple-RMW-implementations.rst
- [src_004] ROS 2 Documentation, “RMW implementations,” accessed 2026-07-03. https://raw.githubusercontent.com/ros2/ros2_documentation/rolling/source/Installation/RMW-Implementations.rst
- [src_005] Open Navigation LLC, “Costmap 2D,” Nav2 documentation, accessed 2026-07-03. https://docs.nav2.org/configuration/packages/configuring-costmaps.html
- [src_006] Open Navigation LLC, “Inflation Layer Parameters,” Nav2 documentation, accessed 2026-07-03. https://docs.nav2.org/configuration/packages/costmap-plugins/inflation.html
- [src_007] Open Navigation LLC, “AMCL,” Nav2 documentation, accessed 2026-07-03. https://docs.nav2.org/configuration/packages/configuring-amcl.html
- [src_008] Open Navigation LLC, “Regulated Pure Pursuit,” Nav2 documentation, accessed 2026-07-03. https://docs.nav2.org/configuration/packages/configuring-regulated-pp.html
- [src_009] Open Navigation LLC, “Collision Monitor,” Nav2 documentation, accessed 2026-07-03. https://docs.nav2.org/configuration/packages/configuring-collision-monitor.html
- [src_010] Open Navigation LLC, “Collision Monitor Node,” Nav2 documentation, accessed 2026-07-03. https://docs.nav2.org/configuration/packages/collision_monitor/configuring-collision-monitor-node.html
- [src_011] Open Navigation LLC, “Controller Server,” Nav2 documentation, accessed 2026-07-03. https://docs.nav2.org/configuration/packages/configuring-controller-server.html
- [src_012] Open Navigation LLC, “Velocity Smoother,” Nav2 documentation, accessed 2026-07-03. https://docs.nav2.org/configuration/packages/configuring-velocity-smoother.html
- [src_013] Open Navigation LLC, “Mapping and Localization,” Nav2 setup guide, accessed 2026-07-03. https://docs.nav2.org/setup_guides/sensors/mapping_localization.html
- [src_014] Open Navigation LLC, “Setting Up Transformations,” Nav2 setup guide, accessed 2026-07-03. https://docs.nav2.org/setup_guides/transformation/setup_transforms.html
- [src_015] Steve Macenski / maintainers, “SLAM Toolbox,” GitHub README, accessed 2026-07-03. https://github.com/SteveMacenski/slam_toolbox
- [src_016] Open Navigation LLC, “Smoothing Odometry using Robot Localization,” Nav2 setup guide, accessed 2026-07-03. https://docs.nav2.org/setup_guides/odom/setup_robot_localization.html
- [src_017] ROBOTIS, “TurtleBot3 Features / Hardware Specifications,” accessed 2026-07-03. https://emanual.robotis.com/docs/en/platform/turtlebot3/features/
- [src_018] ROBOTIS, “TurtleBot3 product page,” accessed 2026-07-03. https://en.robotis.com/model/page.php?co_id=prd_turtlebot3
- [src_019] Local tmux SSH robot probe, `Smartfactory:2.3`, 2026-07-03.
- [src_020] SmartFactory local architecture spec, `docs/confluence/architecture/paperbanana/smartfactory-architecture-spec.md`.
- [src_021] SmartFactory local requirements, `docs/requirements/system-functional-requirements.md`.
- [src_022] SmartFactory local safety boundary, `docs/contracts/source-registry-v2-evidence-contract-migration-plan-2026-06-18.md`.
- [src_023] SmartFactory local docking tuning template, `config/perception/docking_tuning.example.yaml`.
- [src_024] Open Navigation LLC, “Model Predictive Path Integral Controller,” Nav2 documentation, accessed 2026-07-03. https://docs.nav2.org/configuration/packages/configuring-mppic.html
- [src_025] Open Navigation LLC, “Smac Hybrid-A* Planner,” Nav2 documentation, accessed 2026-07-03. https://docs.nav2.org/configuration/packages/smac/configuring-smac-hybrid.html
- [src_026] Open Navigation LLC, “Jazzy to Kilted,” Nav2 migration notes, accessed 2026-07-03. https://docs.nav2.org/migration/Jazzy.html
