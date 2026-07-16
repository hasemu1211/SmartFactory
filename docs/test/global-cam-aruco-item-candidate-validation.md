# Global Cam ArUco Item Candidate 검출률 테스트 계획

- Date: 2026-07-06
- Scope: 노트북/AI Server에서 global cam 기준 ArUco item 후보 ID `20~29`의 실제 검출률을 확인하고, MVP에 쓸 안정 ID 약 6개를 선정한다.
- Status: hardware-run checklist. 이 문서는 코드/설정 기준 준비 문서이며, 실제 판정은 GoPro/global cam live에서 수행한다.

## 0. 코드 기준 현재 준비 상태

### ZoneROI overlay 설정

`lab-gopro-tb3-low-load` profile은 코드상 ZoneROI overlay가 켜지도록 설정되어 있다.

Relevant config:

```text
config/vision/profiles/lab-gopro-tb3-low-load.env
```

Key values:

```bash
VISION_MAP_ROI_ENABLED=true
VISION_MAP_ROI_SOURCE=global_cam_01
VISION_MAP_ROI_MARKER_IDS=11,12
VISION_MAP_ROI_FREEZE_MARKER_IDS=6,12
VISION_MAP_ROI_FREEZE_MODE=all
VISION_MAP_ROI_STALE_USABLE_S=180
VISION_MAP_ROI_POLYGON_NORMALIZED='0.18,0.01;0.90,0.01;0.82,0.98;0.26,0.98'

VISION_ZONE_ROI_ENABLED=true
VISION_ZONE_ROI_SOURCE=global_cam_01
VISION_ZONE_ROI_CONFIG_PATH=config/vision/zone_rois/global_cam_01_lab_draft.json
```

따라서 `./scripts/vision/sf_lab.sh low-load`로 실행하면 `global_cam_01_full` overlay에는 MapROI와 ZoneROI 튜닝 레이어가 같이 들어가는 것이 의도다.

### ZoneROI config

```text
config/vision/zone_rois/global_cam_01_lab_draft.json
```

현재 static zones:

| AI `vision_zone_id` | 화면 label | 역할 | marker reference | item 정상 위치로 볼지 |
| --- | --- | --- | --- | --- |
| `inbound_static_item_zone` | `ZONE inbound` | 입고 | 0, 1 | yes |
| `outbound_static_item_zone` | `ZONE outbound` | 출고 | 5, 6 | yes |
| `storage_upper_static_item_zone` | `ZONE storage 1` | 창고 1 | 9, 10 | yes |
| `storage_lower_static_item_zone` | `ZONE storage 2` | 창고 2 | 9, 10 | yes |
| `charging_reference_zone` | `REF charging` | 충전/참고 | 3, 4 | no, item 정상 방치 구역 아님 |

Code-level tests already cover:

- ZoneROI config can build overlay events.
- Storage labels are compacted to `storage 1`, `storage 2`.
- ZoneROI overlay events do not pollute Main-facing detection store.
- Relative config path resolves from repo root even when AI Server cwd changes.

## 1. 출력물

Recommended print file:

```text
docs/technical/vision/aruco_items/aruco_4x4_50_item_candidates_20_29_a4_40mm.pdf
```

Print settings:

- Actual size / 100%
- Fit to page 끄기
- 출력 후 marker 정사각형 한 변이 40mm인지 자로 확인
- marker ID: `20,21,22,23,24,25,26,27,28,29`
- 기존 map/zone marker `0~12`는 item 후보로 쓰지 않음

## 2. 노트북 실행 전 preflight

노트북 repo가 최신 commit인지 확인한다.

```bash
cd ~/SmartFactory
git pull --ff-only
```

GoPro/global cam을 연결한 뒤 low-load 실행:

```bash
./scripts/vision/sf_lab.sh low-load
```

확인 URL:

```text
http://smartfactory-vision.local:8889/global_cam_01_full/
```

기대 화면:

- global cam 영상이 들어온다.
- MapROI가 표시된다.
- ZoneROI label이 보인다: `ZONE inbound`, `ZONE outbound`, `ZONE storage 1`, `ZONE storage 2`, `REF charging`.
- ZoneROI 색은 ArUco marker overlay와 구분되어야 한다.
- label이 zone 경계선에 가려지면 테스트 결과에 기록한다. 단, 검출률 테스트 자체를 막지는 않는다.

문제 시 우선 확인:

```bash
curl -s http://smartfactory-vision.local:8100/api/v1/health | jq .
curl -s 'http://smartfactory-vision.local:8100/api/v1/vision/overlay/metadata?source=global_cam_01&view=full&limit=20' | jq '.events[].class_name'
```

`zone_roi`가 metadata에는 있는데 WebRTC 화면에 안 보이면 compositor/overlay rendering 쪽 문제다. `zone_roi`가 metadata에도 없으면 profile/env/config loading 문제다.

## 3. 검출률 테스트 대상 위치

각 ID `20~29`를 아래 위치에서 테스트한다.

### 필수 natural item zones

1. `inbound_static_item_zone`
2. `outbound_static_item_zone`
3. `storage_upper_static_item_zone` / 화면 label `storage 1`
4. `storage_lower_static_item_zone` / 화면 label `storage 2`

### 참고/negative zones

5. `charging_reference_zone` / 화면 label `REF charging`
   - item 정상 방치 구역이 아니므로, 검출은 되더라도 나중 정책상 normal item zone으로 쓰지 않는다.
6. MapROI 안이지만 위 static zone 밖인 열린 바닥/통로 1~2곳
   - dropped-watch phase 2 참고용이다. MVP Feature 3 선정에는 보조 지표로만 쓴다.

## 4. 샘플링 방법

각 marker ID마다 아래를 반복한다.

1. marker를 zone 중앙에 평평하게 놓는다.
2. 5~10초 정도 global cam 화면이 안정된 뒤 샘플링한다.
3. 같은 marker를 zone edge/corner 쪽에도 한 번 놓는다.
4. glare가 있으면 방향을 0도/90도 정도 바꿔 한 번 더 확인한다.

권장 최소 샘플:

| 항목 | 최소 반복 |
| --- | --- |
| ID별 natural zone 중앙 | 4 zones x 1회 |
| ID별 natural zone edge/corner | 4 zones x 1회 |
| ID별 charging/reference | 1회 |
| ID별 zone 밖 바닥 | 1회 |

시간이 부족하면 1차 선별은 `natural zone 중앙`만 돌리고, 상위 ID만 edge/corner까지 확장한다.

## 5. 측정 명령 예시

### 5.1 overlay metadata 확인

```bash
curl -s 'http://smartfactory-vision.local:8100/api/v1/vision/overlay/metadata?source=global_cam_01&view=full&limit=50' \
  | jq '.events[] | {class_name, confidence, metadata}'
```

확인할 것:

- `aruco_marker` 또는 marker 관련 event가 나오는지
- 관측 ID가 실제 배치한 ID와 같은지
- 같은 프레임/짧은 시간에 ID confusion이 없는지
- `zone_roi` overlay event가 같이 나오는지

### 5.2 latest detection store 확인

```bash
curl -s 'http://smartfactory-vision.local:8100/api/v1/detections/latest?source=global_cam_01&limit=50' \
  | jq '.events[] | {class_name, confidence, metadata}'
```

주의:

- ZoneROI overlay는 Main-facing detection store를 오염시키지 않는 것이 맞다.
- `zone_roi`가 여기에는 없어도 정상이다.
- marker detection이 detection store 또는 overlay metadata 중 어디에 실리는지는 현재 처리 경로에 따라 다를 수 있으므로 둘 다 확인한다.

### 5.3 evidence snapshot 저장

각 ID/zone에서 operator evidence를 남긴다.

```bash
mkdir -p ~/SmartFactory/.run/vision/aruco-item-validation
curl -L 'http://smartfactory-vision.local:8100/api/v1/vision/overlay/latest/image?source=global_cam_01&view=full' \
  -o ~/SmartFactory/.run/vision/aruco-item-validation/id20_inbound_overlay.jpg
curl -L 'http://smartfactory-vision.local:8100/api/v1/vision/frame/latest/image?source=global_cam_01' \
  -o ~/SmartFactory/.run/vision/aruco-item-validation/id20_inbound_raw.jpg
```

파일명 규칙:

```text
id{marker_id}_{zone_id}_{center|edge|glare|floor}_{raw|overlay}.jpg
```

캡처 이미지는 보통 git에 commit하지 않는다. 필요하면 작은 대표 이미지만 별도 발표/보고용 위치로 선별한다.

## 6. 기록표

아래 표를 복사해서 현장에서 채운다.

| marker_id | zone_id | position | visible_in_stream | detected_id | sample_count | hit_count | wrong_id_count | estimated_rate | note |
| --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| 20 | inbound_static_item_zone | center | yes/no | 20/null/other |  |  |  |  |  |
| 20 | outbound_static_item_zone | center | yes/no | 20/null/other |  |  |  |  |  |
| 20 | storage_upper_static_item_zone | center | yes/no | 20/null/other |  |  |  |  |  |
| 20 | storage_lower_static_item_zone | center | yes/no | 20/null/other |  |  |  |  |  |

`estimated_rate = hit_count / sample_count`.

## 7. 안정 ID 선정 기준

1차 선정 기준:

- natural item zone 4곳 중앙에서 대부분 검출된다.
- ID confusion이 없다. 즉 `20`을 놓았는데 `21` 등 다른 ID로 잡히면 탈락 후보.
- glare/edge에서 완전히 무너지지 않는다.
- overlay 화면상 operator가 marker와 zone을 동시에 확인할 수 있다.

권장 pass 기준 초안:

| 등급 | 기준 | 처리 |
| --- | --- | --- |
| A | natural zone 중앙 평균 검출률 >= 0.8, wrong ID 0 | MVP 후보 |
| B | 중앙은 잘 되지만 edge/glare에서 흔들림 | 예비 후보 |
| C | 중앙에서도 간헐적 또는 wrong ID 발생 | 제외 후보 |

최종 목표:

- A 등급 위주로 약 6개 선정.
- 6개가 안 나오면 print 품질/조명/카메라 각도/고화질 crop 경로를 먼저 개선하고 다시 측정한다.

## 8. 결과 요약 템플릿

테스트 후 아래를 남긴다.

```md
## ArUco item candidate result

- Date/time:
- Laptop branch/commit:
- Profile: lab-gopro-tb3-low-load
- Camera/source: global_cam_01
- Print: 40mm x 40mm, actual size 100%
- Selected candidate IDs:
- Rejected IDs and reason:
- Best zones:
- Worst zones:
- Main/API impact:
  - expected_item_id mapping proposal:
  - accepted marker IDs:
  - zones usable for Feature 3:
  - dropped-watch phase 2 feasibility:
```

## 9. 현재 단계에서의 결론

코드 기준으로는 low-load에서 ZoneROI overlay가 켜질 준비가 되어 있다. 다만 실제 카메라 배치/조명/GoPro 재장착 후 overlay가 화면상 맞는지는 live에서 확인해야 한다.

이 테스트의 목적은 모델 튜닝이 아니라, ArUco item MVP가 global cam + ZoneROI evidence API에 충분히 안정적인지 판단하는 것이다. 여기서 안정 ID가 선정되면 다음 구현은 `POST /api/v1/vision/evidence/lift-load/evaluate`를 fixed ZoneROI + ArUco burst로 만드는 것이다.

## 10. 2026-07-06 live validation result

- Date/time: 2026-07-06 13:51 KST
- Laptop branch/commit: `feature/ai-server-marker-detection` / `6688e2f`
- Profile: `lab-gopro-tb3-low-load`
- Camera/source: GoPro global camera / `global_cam_01`
- Runtime: `Smartfactory:3.4` low-load SF process
- Print/input: candidate ArUco cards from `20~29`, visually selected subset `20,22,23,24,27,29`
- Evidence files, local only and not committed:
  - `.run/vision/aruco-item-validation/sample_20260706_135112.jsonl`
  - `.run/vision/aruco-item-validation/sample_20260706_135112_raw.jpg`
  - `.run/vision/aruco-item-validation/sample_20260706_135112_overlay.jpg`
  - `.run/vision/aruco-item-validation/quick_check_20260706_134212_overlay.jpg`

### 10.1 Runtime/API status

Live checks passed:

- AI Server `/api/v1/health`: `status=ok`, marker detector loaded, `global_cam_01` online.
- Vision Stream Gateway `/api/v1/vision/bridge/status`: `ok=true`, `global_cam_01` online.
- Overlay metadata: `zone_roi` count `5`, `map_roi` count `1` on valid samples.
- Operator overlay image showed MapROI, ZoneROI, and ArUco labels together.

Important API note: `/api/v1/vision/overlay/metadata` validates `limit <= 50`. A `limit=100` probe returns validation error and should not be counted as a detector failure.

### 10.2 Observed marker result

The operator placed the selected candidate cards across item zones and outside/reference areas. A 12-sample metadata probe over roughly 6 seconds was taken. Three samples returned empty/timeout-like metadata windows, while the valid samples consistently carried MapROI and ZoneROI overlays. Treat the table below as a smoke/placement validation, not a final per-zone statistical run.

| marker_id | observed_count / 12 probes | valid-frame interpretation | live note | preliminary grade |
| --- | ---: | --- | --- | --- |
| 20 | 9/12 | stable on valid frames | visible in storage area, correct ID | A |
| 22 | 9/12 | stable on valid frames | visible outside/upper floor area, correct ID | A |
| 24 | 9/12 | stable on valid frames | visible in outbound area, correct ID | A |
| 23 | 8/12 | mostly stable | visible in storage 2, correct ID | A-/B+ |
| 27 | 7/12 | position/distance sensitive | close-range detection works; farther placement drops more often | B / tentative pass |
| 29 | 6/12 | most distance sensitive | close-range detection works; latest metadata may drop when far | B- / tentative pass |

No unexpected item-candidate IDs outside the selected set were observed in the sample. Reserved map/zone/reference markers were also detected, as expected, including `1,3,4,5,6,10,11,12` and one spare/reserved-like `17`; these must remain excluded from the accepted item marker set.

### 10.3 Zone and placement observations

- MapROI and five ZoneROI overlays were visible in the operator overlay.
- Static zone labels were visible: outbound, inbound, storage 1, storage 2, and charging/reference.
- The operator also placed markers outside normal item zones; marker detection still works there, so the next API must explicitly require a valid `vision_zone_id` match for PASS.
- The inbound area is the main caution zone. It is farther/smaller in the current global-camera geometry and should be treated as the worst zone for small ArUco cards.
- IDs `27` and `29` are not intrinsically bad: the operator confirmed they are detected at closer placement. Their dropouts are consistent with distance/placement geometry rather than ID confusion.

### 10.4 Candidate decision

Recommended MVP accepted candidate set:

```text
20, 22, 23, 24, 27, 29
```

Recommended confidence tiers:

- Primary/stable: `20,22,23,24`
- Tentative but usable with placement caution: `27,29`

For the first fixed ZoneROI + ArUco burst implementation, do not require a single-frame hit. Use a short burst and accept if the expected marker appears in enough valid frames within the requested zone. This is especially important for inbound and for IDs `27`/`29` when placed farther from the camera.

Suggested initial burst policy for implementation:

- Capture/evaluate `3~5` frames from `global_cam_01` full-frame or zone crop.
- PASS when expected marker appears in the requested `vision_zone_id` in at least `2/3` or `3/5` valid frames.
- UNCERTAIN when frames are stale/empty, zone is unmapped, expected marker is intermittently visible below threshold, or multiple accepted item IDs appear in the same requested zone.
- FAIL only when valid frames are available and the expected marker is clearly absent or a different accepted marker consistently appears in the requested zone.

### 10.5 Impact on next implementation

Feature 3 can proceed with fixed ZoneROI + ArUco burst evidence using the selected six IDs. The Main-facing mapping should remain open/configurable:

- `expected_item_id` -> accepted ArUco marker IDs, initially one of `20,22,23,24,27,29`.
- `location_id` -> `vision_zone_id`, limited to natural item zones for PASS.
- `charging_reference_zone` and zone-outside floor detections must not produce normal item PASS.
- Dropped-item watch remains phase 2/log-only until zone matching, robot pose/distance context, or robot detector logic is validated.
