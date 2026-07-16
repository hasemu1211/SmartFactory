# Vision lift-load evidence API smoke test

- Date: 2026-07-06
- Scope: 노트북 AI Server에서 `global_cam_01` 스트림 프레임을 이용해 pick/drop 적재 증거 API가 최소 계약대로 동작하는지 확인한다.
- Endpoint: `POST /api/v1/vision/evidence/lift-load/evaluate`
- Status: laptop hardware smoke checklist

## 0. 이 테스트가 확인하는 것

이 API는 Main이 PICK/DROP 경계에서 1회 호출하는 증거 API다.

- 입력: Main의 `robot_id`, `task_id`, `command_id`, `operation`, 기대 item marker, 대상 ZoneROI.
- 처리: AI Server가 현재 `global_cam_01` latest frame burst에서 ArUco item marker를 찾는다.
- 출력: Main이 바로 판단할 수 있는 compact JSON.
- 하지 않는 것: 로봇 정지/이동 명령, DB write, inventory truth 변경, bbox/polygon/raw detection 반환.

MVP 기본 정책:

- `burst_frames=5`
- `min_pass_frames=1`
- 즉 5프레임 중 expected ArUco marker가 지정 ZoneROI 안에서 1프레임이라도 잡히면 `PASS` 후보가 된다. 단, 같은 burst에서 extra item marker/count가 보이면 `FAIL`로 fail-closed 처리한다.
- `event.confidence`는 관측 비율이다. 예: 1/5면 `0.2`, 5/5면 `1.0`.

## 1. 실행 준비

노트북에서 최신 코드 반영 후 low-load 실행:

```bash
cd ~/SmartFactory
git pull --ff-only origin feature/ai-server-marker-detection
./scripts/vision/sf_lab.sh down
./scripts/vision/sf_lab.sh low-load
```

API base URL:

```bash
# 노트북에서 직접 테스트할 때
export AI=http://127.0.0.1:8100

# Main PC / 운영자 PC에서 테스트할 때
export AI=http://smartfactory-vision.local:8100
```

Global cam WebRTC 확인:

```text
http://smartfactory-vision.local:8889/global_cam_01_full/
```

기대 화면:

- global cam 영상이 보인다.
- MapROI와 ZoneROI overlay가 보인다.
- item으로 쓸 ArUco marker `20~49`가 화면에서 육안으로 보인다.

## 2. Preflight

```bash
curl -sS "$AI/api/v1/health" | jq '.status, .sources?'
```

ZoneROI overlay metadata 확인:

```bash
curl -sS "$AI/api/v1/vision/overlay/metadata?source=global_cam_01&view=full&limit=50" \
  | jq '.events[]? | select(.class_name=="zone_roi") | {class_name, metadata}'
```

`zone_roi`가 나오면 API가 쓸 zone config가 로드된 상태로 보면 된다.

## 3. PASS smoke test

ArUco item marker `20`을 `inbound_static_item_zone` 안에 놓고 실행한다.

```bash
curl -sS -X POST "$AI/api/v1/vision/evidence/lift-load/evaluate" \
  -H 'Content-Type: application/json' \
  -d '{
    "source": "global_cam_01",
    "robot_id": "tb3_1",
    "task_id": "manual-lift-api-001",
    "command_id": "pick-001",
    "operation": "PICK_UP",
    "expected_item_id": "aruco-20-test-item",
    "expected_marker_id": 20,
    "expected_item_count": 1,
    "vision_zone_id": "inbound_static_item_zone",
    "burst_frames": 5,
    "min_pass_frames": 1,
    "sample_interval_ms": 80
  }' | jq .
```

성공 기대:

```json
{
  "schema_version": "vision-lift-load-evaluate.v1",
  "monitor_id": "lift_evidence",
  "source": "global_cam_01",
  "robot_id": "tb3_1",
  "operation": "PICKUP",
  "vision_zone_id": "inbound_static_item_zone",
  "result": "PASS",
  "reason_code": "EXPECTED_ITEM_COUNT_MATCH_AND_STABLE"
}
```

추가 확인 포인트:

```bash
# 위 응답을 result.json에 저장했다면
jq '{result, reason_code, event_type: .event.event_type, confidence: .event.confidence, data: .event.data_json}' result.json
```

- `event.event_type`은 `ITEM_PICKED`.
- `event.data_json.detected_marker_id`는 `ARUCO_4X4_50_20`.
- `event.data_json.accepted_frames >= 1`이면 정상.
- `event.data_json.total_frames`는 실제 burst에서 확보한 최신 프레임 수이므로 현장 상태에 따라 `1~5`가 될 수 있다.

## 4. DROP_OFF smoke test

같은 marker를 출고/창고 등 자연 item zone에 놓고 `DROP_OFF`로 호출한다.

예: 출고구역:

```bash
curl -sS -X POST "$AI/api/v1/vision/evidence/lift-load/evaluate" \
  -H 'Content-Type: application/json' \
  -d '{
    "source": "global_cam_01",
    "robot_id": "tb3_1",
    "task_id": "manual-lift-api-002",
    "command_id": "drop-001",
    "operation": "DROP_OFF",
    "expected_item_id": "aruco-20-test-item",
    "expected_marker_id": 20,
    "expected_item_count": 1,
    "vision_zone_id": "outbound_static_item_zone"
  }' | jq .
```

성공 기대:

- `result=PASS`
- `operation=DROPOFF`
- `event.event_type=ITEM_PLACED`

## 5. location_id alias test

Main이 최종적으로 `location_id`를 쓰려면 alias 합의가 필요하다. 현재 draft config에는 아래 alias만 있다.

| Main-style `location_id` | AI `vision_zone_id` |
| --- | --- |
| `inbound` | `inbound_static_item_zone` |
| `outbound` | `outbound_static_item_zone` |
| `storage_1` | `storage_upper_static_item_zone` |
| `storage_2` | `storage_lower_static_item_zone` |

`vision_zone_id` 대신 `location_id`로 테스트:

```bash
curl -sS -X POST "$AI/api/v1/vision/evidence/lift-load/evaluate" \
  -H 'Content-Type: application/json' \
  -d '{
    "robot_id": "tb3_1",
    "operation": "PICK_UP",
    "expected_marker_id": 20,
    "expected_item_count": 1,
    "location_id": "inbound"
  }' | jq .
```

기대:

- marker가 inbound zone에서 잡히면 `PASS`.
- 응답의 `vision_zone_id`는 `inbound_static_item_zone`.
- `event.data_json.zone_resolution_source`는 `location_aliases`.

## 6. Negative / fail-closed tests

### 6.1 marker가 없거나 다른 marker를 기대할 때

Marker `20`을 두고 `expected_marker_id=21`로 호출한다.

```bash
curl -sS -X POST "$AI/api/v1/vision/evidence/lift-load/evaluate" \
  -H 'Content-Type: application/json' \
  -d '{
    "robot_id": "tb3_1",
    "operation": "PICK_UP",
    "expected_marker_id": 21,
    "expected_item_count": 1,
    "vision_zone_id": "inbound_static_item_zone"
  }' | jq '{result, reason_code, event: .event.data_json}'
```

기대:

- 일반적으로 `FAIL / EXPECTED_ITEM_COUNT_MISMATCH`.
- 프레임 자체가 없거나 stale이면 `NO_DECISION` 계열이 먼저 나올 수 있다.

### 6.2 item 정상 위치가 아닌 zone

충전구역은 item 정상 방치 구역이 아니므로 정책상 판단하지 않는다.

```bash
curl -sS -X POST "$AI/api/v1/vision/evidence/lift-load/evaluate" \
  -H 'Content-Type: application/json' \
  -d '{
    "robot_id": "tb3_1",
    "operation": "PICK_UP",
    "expected_marker_id": 20,
    "expected_item_count": 1,
    "vision_zone_id": "charging_reference_zone"
  }' | jq '{result, reason_code}'
```

기대:

```json
{
  "result": "NO_DECISION",
  "reason_code": "POLICY_NOT_APPLICABLE"
}
```

### 6.3 map/zone marker를 item으로 요청하면 거절

`0~19`는 map/zone marker로 예약되어 있으므로 item marker로 쓰면 안 된다.

```bash
curl -sS -X POST "$AI/api/v1/vision/evidence/lift-load/evaluate" \
  -H 'Content-Type: application/json' \
  -d '{
    "robot_id": "tb3_1",
    "operation": "PICK_UP",
    "expected_marker_id": 6,
    "expected_item_count": 1,
    "vision_zone_id": "inbound_static_item_zone"
  }' | jq .
```

기대: HTTP `400`, detail에 `20..49` 예약 범위 관련 메시지.

## 7. 결과 기록 양식

| time | marker_id | zone/location | operation | result | reason_code | confidence | accepted/total | note |
| --- | ---: | --- | --- | --- | --- | ---: | --- | --- |
|  | 20 | inbound_static_item_zone | PICK_UP |  |  |  |  |  |
|  | 20 | outbound_static_item_zone | DROP_OFF |  |  |  |  |  |

## 8. 문제 해석 quick guide

| 증상 | 우선 해석 |
| --- | --- |
| `NO_DECISION / SOURCE_STALE` | global cam latest frame이 안 들어오거나 너무 오래됨. GoPro/low-load부터 확인. |
| `NO_DECISION / POLICY_NOT_APPLICABLE` | zone id가 없거나, alias 미매핑이거나, natural item zone이 아님. |
| `FAIL / EXPECTED_ITEM_COUNT_MISMATCH` | 프레임은 들어왔지만 expected marker/count가 조건과 맞지 않음. |
| `PASS`인데 confidence가 낮음 | 5프레임 중 일부만 잡힘. MVP는 extra item이 없는 경우 1프레임 hit면 PASS지만, confidence는 증거 강도 참고값. |
| HTTP `400` | source/robot/marker 범위 같은 명시 계약 위반. |
| HTTP `422` | JSON schema 위반, 필수값 누락, 알 수 없는 extra field 등. |

## 9. 2026-07-06 laptop live smoke result

- Runtime: `sf_lab.sh low-load`
- AI base URL: `http://127.0.0.1:8100`
- Source: `global_cam_01`
- API under test: `POST /api/v1/vision/evidence/lift-load/evaluate`
- Evidence files: `.run/vision/lift-load-api-smoke/*20260706_153103*`, `.run/vision/lift-load-api-smoke/*20260706_153334*`

### 9.1 Preflight

AI Server health returned `status=ok` and `model_status=loaded`.
The global camera overlay metadata exposed all expected ZoneROI entries:

- `inbound_static_item_zone`
- `outbound_static_item_zone`
- `storage_upper_static_item_zone`
- `storage_lower_static_item_zone`
- `charging_reference_zone`

During this run, `charging_reference_zone` was confirmed as:

```text
natural_item_location=false
role=robot_charging_reference_zone
```

### 9.2 Outbound dual-marker negative observation

Physical/live setup: marker `27` and marker `29` were both visible around the outbound area.
The test called the API with:

```json
{
  "operation": "DROP_OFF",
  "expected_marker_id": 29,
  "expected_item_count": 1,
  "vision_zone_id": "outbound_static_item_zone",
  "burst_frames": 5,
  "min_pass_frames": 1
}
```

Observed over 5 calls:

| case | PASS | FAIL | common detected markers | note |
| --- | ---: | ---: | --- | --- |
| direct `vision_zone_id=outbound_static_item_zone` | 3 | 2 | `ARUCO_4X4_50_27`, `ARUCO_4X4_50_29` | PASS occurred when at least one burst frame counted only the expected item. |

Representative PASS:

```text
result=PASS
reason_code=EXPECTED_ITEM_COUNT_MATCH_AND_STABLE
accepted_frames=1~2 / 5
observed_count=1
detected_marker_ids=[ARUCO_4X4_50_27, ARUCO_4X4_50_29]
```

Representative FAIL:

```text
result=FAIL
reason_code=EXPECTED_ITEM_COUNT_MISMATCH
accepted_frames=0 / 5
observed_count=2
detected_marker_ids=[ARUCO_4X4_50_27, ARUCO_4X4_50_29]
```

Interpretation: the API can see both item candidates, but the MVP policy `min_pass_frames=1` can still PASS if any sampled frame satisfies the expected count. Therefore this test is not a stable fail-closed dual-item negative under the current policy.

### 9.3 `location_id=outbound` alias observation

The same live condition was tested with `location_id` instead of direct `vision_zone_id`:

```json
{
  "operation": "DROP_OFF",
  "expected_marker_id": 29,
  "expected_item_count": 1,
  "location_id": "outbound",
  "burst_frames": 5,
  "min_pass_frames": 1
}
```

Observed over 5 calls:

| case | PASS | FAIL | resolved zone | zone resolution source |
| --- | ---: | ---: | --- | --- |
| `location_id=outbound` | 3 | 2 | `outbound_static_item_zone` | `location_aliases` |

Conclusion: alias resolution works correctly. The PASS/FAIL split matches the direct-zone test, so the instability is caused by burst/count policy, not by `location_id` mapping.

### 9.4 Charging zone policy test

The non-item/reference zone was tested with:

```json
{
  "operation": "PICK_UP",
  "expected_marker_id": 29,
  "expected_item_count": 1,
  "vision_zone_id": "charging_reference_zone"
}
```

Observed over 3 calls:

| result | count | reason_code | command_satisfying |
| --- | ---: | --- | --- |
| `NO_DECISION` | 3 | `POLICY_NOT_APPLICABLE` | `false` |

Conclusion: `charging_reference_zone` correctly fails closed as a non-natural item location. It is not treated as item pickup/dropoff evidence.

### 9.5 Live smoke conclusion

Confirmed:

- The lift-load evidence endpoint is reachable in low-load runtime.
- `location_id=outbound` resolves to `outbound_static_item_zone` through explicit aliases.
- The charging/reference zone is excluded from normal item evidence.
- The API returns compact Main-consumable results without motion commands or inventory writes.

Risk / policy finding:

- Under `min_pass_frames=1`, a dual-marker zone can produce mixed PASS/FAIL results across repeated calls.
- If Main requires strict single-item safety, the next policy iteration should treat any non-expected accepted item marker in the requested ZoneROI during the burst as `FAIL` or `UNCERTAIN`, even if one frame satisfies the expected marker/count condition.

Optional remaining validation, not required for the current smoke goal:

- Unknown `location_id` should return `NO_DECISION/POLICY_NOT_APPLICABLE`.
- Reserved marker ids `0..19` should return HTTP `400`.
- Invalid `source` or `robot_id` should return validation errors.

## 10. Code review follow-up for 9.2 dual-marker finding

Review finding:

- Severity: HIGH for evidence correctness, because the API could return `PASS` when an expected marker appeared in at least one burst frame even though another item marker was also observed in the same requested ZoneROI during the burst.
- Scope: lift-load evidence policy only. No Main/ROS/WebRTC/DB contract change is required.
- Constraint kept: the MVP still allows `burst_frames=5`, `min_pass_frames=1` for a single clearly observed expected item.

Fix direction:

- Keep the one-frame PASS threshold for the normal single-item case.
- Add a burst-level fail-closed guard: if any sampled frame observes more item markers than `expected_item_count`, the result is `FAIL / EXPECTED_ITEM_COUNT_MISMATCH` even if another frame matched the expected marker/count.
- Reuse the existing reason code and compact response shape, so Main does not need a new enum or parser change.

Expected behavior after the fix:

| live condition | expected result |
| --- | --- |
| only expected marker `29` appears in outbound zone in at least 1/5 frames | `PASS` |
| marker `27` and `29` both appear in outbound zone during the burst while `expected_marker_id=29`, `expected_item_count=1` | `FAIL / EXPECTED_ITEM_COUNT_MISMATCH` |
| marker is in `charging_reference_zone` | `NO_DECISION / POLICY_NOT_APPLICABLE` |

Regression coverage added:

- Unit policy test for `per_frame_item_counts=[1,1,2,1,1]`, `min_pass_frames=1` now expects `FAIL`.
- Existing API tests still cover single-frame PASS, wrong marker FAIL, mixed markers in one frame FAIL, non-natural zone NO_DECISION, and reserved marker HTTP 400.
