# Vision runtime-control `--git-pull` 반영 실패 의심 기록 (2026-07-02)

## 요약

운영자 PC에서 AI 노트북(`smartfactory-vision.local`)의 low-load Vision runtime을 원격 재시작할 때 `--git-pull` 요청은 API상 accepted/scheduled로 기록되지만, 최신 코드 변경분이 실제 실행 프로세스에 반영되지 않은 것으로 보인다.

현재까지의 결론은 **Vision 구조 문제라기보다 runtime-control의 git pull 성공/실패 가시성 부족 또는 노트북 로컬 git 상태/브랜치 문제 가능성이 높다**는 것이다.

## 관찰 환경

- 운영자 PC repo branch: `feature/ai-server-marker-detection`
- 운영자 PC 최신 원격 HEAD: `46a7fb8 fix(vision): simplify map roi overlay visuals`
- AI 노트북 host: `smartfactory-vision.local`
- AI Server: `http://smartfactory-vision.local:8100`
- Global WebRTC: `http://smartfactory-vision.local:8889/global_cam_01_full/`
- Runtime profile: `lab-gopro-tb3-low-load`

## 관련 커밋

- `d2baf07 feat(vision): add diagnostic map roi overlay`
  - Map ROI diagnostic overlay 추가
  - `VISION_MAP_ROI_*` runtime-control allowlist 추가
- `46a7fb8 fix(vision): simplify map roi overlay visuals`
  - Map ROI stale/age 색상도 cyan으로 고정
  - visual overlay에서 `class_name == "unknown"` 이벤트는 그리지 않도록 수정

## 기대 동작

`46a7fb8`이 노트북에 pull되고 low-load runtime이 재시작되면:

1. Map ROI 폴리곤은 항상 cyan 계열로 표시된다.
2. `unknown` detection 이벤트는 payload/store에는 남을 수 있지만, `/api/v1/vision/overlay/latest/image?source=global_cam_01` 렌더 이미지에는 박스/라벨로 표시되지 않아야 한다.
3. runtime-control `--git-pull` 요청 후 실행 중인 AI Server/overlay renderer가 최신 코드 기준으로 동작해야 한다.

## 실제 증상

### 1. `--git-pull` 요청은 accepted/scheduled로 보임

운영자 PC에서 다음 계열 요청을 보냈고 API는 scheduled 응답을 반환했다.

```bash
AI_SERVER_URL=http://smartfactory-vision.local:8100 \
./scripts/vision/sf_lab.sh api restart-low-load \
  --git-pull \
  --allow-dirty-git \
  --reason "pull visual overlay fixes and apply final roi" \
  GOPRO_STREAM_TARGET_FPS=20 \
  VISION_MAP_ROI_ENABLED=true \
  VISION_MAP_ROI_SOURCE=global_cam_01 \
  VISION_MAP_ROI_MARKER_IDS=11,12 \
  VISION_MAP_ROI_MIN_MARKERS=1 \
  VISION_MAP_ROI_STALE_USABLE_S=180 \
  'VISION_MAP_ROI_POLYGON_NORMALIZED=0.19,0.03;0.765,0.03;0.725,0.94;0.27,0.94'
```

당시 runtime-status의 마지막 pull 요청 예:

```json
{
  "run_id": "ef5fe23073c7",
  "git_pull": true,
  "require_clean_git": false,
  "log_file": "/home/hasam/Desktop/project/SmartFactory/.run/vision/runtime-control/ef5fe23073c7.log",
  "reason": "pull visual overlay fixes and apply final roi"
}
```

### 2. 최신 코드 반영 신호가 보이지 않음

`46a7fb8` 이후에는 visual overlay에서 `unknown` 박스가 사라져야 하지만, 노트북 overlay image에서는 여전히 `unknown 0.53` 같은 박스/라벨이 표시되었다.

확인한 이미지 endpoint:

```text
http://smartfactory-vision.local:8100/api/v1/vision/overlay/latest/image?source=global_cam_01
```

이 증상은 다음 둘 중 하나를 강하게 시사한다.

- 노트북 working tree가 `46a7fb8`까지 실제로 pull되지 않았다.
- pull은 됐지만, 재시작된 프로세스가 pull 이후 코드가 아닌 이전 코드로 실행되었다.

### 3. runtime-status는 helper 성공/실패를 직접 알려주지 않음

현재 `/api/v1/operator/runtime/status`는 `last_request.json`만 읽는다. 즉 다음 정보는 알 수 있다.

- 요청이 API에서 accept 되었는지
- `git_pull=true`였는지
- override param이 무엇이었는지
- log 파일 경로가 무엇인지

하지만 다음 정보는 알 수 없다.

- `git pull --ff-only`가 실제 성공했는지
- pull 전후 branch/HEAD가 무엇인지
- working tree dirty 때문에 pull이 거절됐는지
- helper가 어느 단계에서 실패했는지
- tmux pane에 새 launch command paste가 실제로 성공했는지

따라서 운영자 PC 입장에서는 `scheduled`만 보고 pull 성공으로 오인할 수 있다.

## 현재 확인된 원격 상태 예시

마지막 튜닝 요청은 pull 없이 runtime param만 바꾼 것이다.

```json
{
  "run_id": "c8a84efb95ed",
  "git_pull": false,
  "require_clean_git": true,
  "params": {
    "GOPRO_STREAM_TARGET_FPS": "20",
    "VISION_MAP_ROI_ENABLED": "true",
    "VISION_MAP_ROI_MARKER_IDS": "11,12",
    "VISION_MAP_ROI_MIN_MARKERS": "1",
    "VISION_MAP_ROI_POLYGON_NORMALIZED": "0.18,0.01;0.81,0.01;0.725,0.94;0.27,0.94",
    "VISION_MAP_ROI_SOURCE": "global_cam_01",
    "VISION_MAP_ROI_STALE_USABLE_S": "180"
  }
}
```

이 요청은 폴리곤 위치 조정용이며, 코드 pull 문제를 해결하지 않는다.

## 의심 원인

우선순위 높은 순서:

1. **AI 노트북 repo가 다른 branch에 있음**
   - helper는 `git pull --ff-only`만 실행한다.
   - 현재 branch가 `feature/ai-server-marker-detection`이 아니면 운영자 PC가 push한 커밋을 받지 못할 수 있다.

2. **AI 노트북 working tree가 dirty 상태**
   - `--require-clean-git`일 때는 dirty면 pull/restart를 거절한다.
   - `--allow-dirty-git`이어도 tracked local modification이 있으면 `git pull --ff-only`가 conflict/overwrite 보호로 실패할 수 있다.

3. **helper log를 원격 status에서 볼 수 없음**
   - 실패하더라도 API status에는 `last_request`만 남아 원인 판단이 어렵다.

4. **pull 후 실제 runtime 재시작 검증이 부족함**
   - 현재 status는 재시작 후 실행 중인 프로세스의 git SHA를 노출하지 않는다.
   - API가 어느 git commit에서 실행 중인지 확인할 endpoint가 없다.

5. **SSH 접근 불가로 운영자 PC에서 직접 로그 확인 불가**
   - 확인 시도 결과: `ssh: connect to host smartfactory-vision.local port 22: Connection refused`
   - 따라서 현재는 노트북 로컬 터미널에서 직접 git/log를 확인해야 한다.

## 노트북에서 바로 확인할 명령

AI 노트북에서 실행:

```bash
cd /home/hasam/Desktop/project/SmartFactory

# 1) 현재 branch와 working tree 확인
git status -sb
git branch --show-current
git remote -v

# 2) 현재 HEAD와 원격 feature HEAD 비교
git log --oneline -5
git fetch origin
git rev-parse HEAD
git rev-parse origin/feature/ai-server-marker-detection
git log --oneline --decorate -5 origin/feature/ai-server-marker-detection

# 3) runtime-control helper 로그 확인
ls -lt .run/vision/runtime-control | head -20
tail -200 .run/vision/runtime-control/ef5fe23073c7.log
tail -200 .run/vision/runtime-control/c8a84efb95ed.log
```

## 노트북에서 예상 조치

### branch가 다르면

```bash
cd /home/hasam/Desktop/project/SmartFactory
git switch feature/ai-server-marker-detection
git pull --ff-only origin feature/ai-server-marker-detection
```

### branch는 맞지만 HEAD가 오래됐으면

```bash
cd /home/hasam/Desktop/project/SmartFactory
git pull --ff-only origin feature/ai-server-marker-detection
git log --oneline -3
```

최소 기대 HEAD:

```text
46a7fb8 fix(vision): simplify map roi overlay visuals
```

### dirty working tree 때문에 pull이 실패하면

먼저 어떤 파일이 dirty인지 확인한다.

```bash
git status --short
```

노트북 실험 산출물/캐시라면 제거하거나, 필요한 변경이면 별도 branch/commit/stash로 정리한 뒤 pull한다.

```bash
# 예: 추적되지 않은 실험 파일만 제거할 때는 반드시 목록 확인 후 실행
# git clean -fd <경로>

# 예: 임시 tracked 변경 보존
# git stash push -u -m "laptop local runtime experiments before pull"
```

## 수동 복구 절차

노트북에서 최신 코드 확인 후 low-load runtime 재시작:

```bash
cd /home/hasam/Desktop/project/SmartFactory
git switch feature/ai-server-marker-detection
git pull --ff-only origin feature/ai-server-marker-detection
git log --oneline -3

./scripts/vision/sf_lab.sh down
SF_RUNTIME_CONTROL_ENABLED=true ./scripts/vision/sf_lab.sh low-load
```

그 뒤 운영자 PC에서 runtime param만 다시 적용:

```bash
AI_SERVER_URL=http://smartfactory-vision.local:8100 \
./scripts/vision/sf_lab.sh api restart-low-load \
  --reason "apply map roi tuned params after manual pull" \
  GOPRO_STREAM_TARGET_FPS=20 \
  VISION_MAP_ROI_ENABLED=true \
  VISION_MAP_ROI_SOURCE=global_cam_01 \
  VISION_MAP_ROI_MARKER_IDS=11,12 \
  VISION_MAP_ROI_MIN_MARKERS=1 \
  VISION_MAP_ROI_STALE_USABLE_S=180 \
  'VISION_MAP_ROI_POLYGON_NORMALIZED=0.18,0.01;0.81,0.01;0.725,0.94;0.27,0.94'
```

## 재발 방지 개선안

다음 중 하나 이상을 추가하면 같은 문제가 줄어든다.

1. runtime-control helper가 `last_result.json`을 남기도록 개선
   - `git_branch_before`, `git_head_before`
   - `git_pull_exit_code`, `git_pull_output_tail`
   - `git_branch_after`, `git_head_after`
   - `restart_exit_code`
   - `tmux_target_pane`, `tmux_paste_result`

2. `/api/v1/operator/runtime/status`가 `last_request`뿐 아니라 `last_result`도 반환하도록 개선

3. `/api/v1/health` 또는 별도 debug endpoint에 현재 실행 코드의 git SHA 노출

4. `--git-pull` 동작을 현재 branch 암묵 pull이 아니라 명시 branch pull로 제한
   - 예: `git fetch origin && git merge --ff-only origin/feature/ai-server-marker-detection`
   - 단, 노트북이 다른 branch를 의도적으로 쓰는 경우를 막을 수 있으므로 runtime-control 안전 정책에 반영 필요

## RALPLAN 영향

이 이슈는 현재까지 **3개 API 추가 RALPLAN의 기능 계약 자체를 변경하지 않는다.**

- Map ROI overlay는 diagnostic/튜닝 보조 기능이다.
- Main-facing person hazard/evidence/dropped item API 계약은 이 문제로 바뀌지 않는다.
- 다만 노트북 셋업/원격 운영 편의성 단계에서 `pull 성공 여부를 신뢰할 수 없다`는 운영 리스크가 있으므로, 하드웨어 튜닝 전 runtime-control 가시성 개선 또는 노트북 수동 git 상태 확인이 필요하다.
