# Main → Vision handoff — callback port mismatch (`:8000` vs `:8088`)

- Date: 2026-06-19 KST
- From: Main/LMS side
- Re: follow-up to `main-vision-runtime-config-request-2026-06-19.md`
- Main host: `smartfactory-main.local` (LAN IPv4 `192.168.10.66`, iface `enp3s0`)

## TL;DR

Vision 측 요청(Vision upstream을 `smartfactory-vision.local`로 교체)은 **Main에서 처리 완료**했고, Main→Vision 프록시(`:8090`/`:8100`)는 정상 동작한다. 다만 점검 중 **반대 방향(Vision→Main) 포트 불일치**를 발견했다. AI 서버가 Main을 `:8000`으로 알고 있는데 Main은 `:8088`에만 떠 있어, **Vision이 Main으로 보내는 evidence/event 콜백은 전부 연결 실패**한다. 이 값은 Vision 측 설정이라 Main에서 고칠 수 없다. **Vision 측에서 `main_server_url`을 `:8088`로 변경 요청한다.**

## Main 측 완료 사항 (요청서 대응)

`.env` / 코드 반영 완료, Main 재시작·검증 완료.

```env
LMS_VISION_API_BASE_URL=http://smartfactory-vision.local:8100
LMS_VISION_STREAM_BASE_URL=http://smartfactory-vision.local:8090
LMS_VISION_API_FALLBACK_BASE_URL=http://192.168.10.59:8100
LMS_VISION_STREAM_FALLBACK_BASE_URL=http://192.168.10.59:8090
```

- 호스트명(.local) 우선, 해석/연결 실패(URLError) 시 IP 폴백으로 1회 재시도하도록 프록시 로직 구현.
- upstream이 HTTP 상태를 주면(이름해석 성공) 폴백하지 않고 그대로 전달.
- 검증: `external-config`에 placeholder 사라짐 / `vision/bridge/status` 프록시 200 / `overlay/stream` MJPEG 헤더 정상.
- 참고: Main이 읽는 env 키는 **`LMS_` 접두사** (`LMS_VISION_API_BASE_URL` 등). 요청서의 `VISION_API_BASE_URL`이 아님.

## 발견한 불일치 (Vision 측 조치 필요)

| 점검 | 결과 |
|---|---|
| Main 자기 광고 주소 (`LMS_PUBLIC_BASE_URL`) | `http://smartfactory-main.local:8088` (정상) |
| Main 머신 `:8000` 리스너 | 없음 (Main은 `:8088`만 LISTEN) |
| `http://smartfactory-main.local:8088/health` | HTTP 200 |
| `http://smartfactory-main.local:8000/health` | 연결 실패 (Couldn't connect) |
| AI 서버 `/api/v1/health` → `main_server_url` | `http://smartfactory-main.local:8000` ← 잘못된 포트 |

### 영향

- Main→Vision (이미지/상태 pull 프록시): **정상**.
- Vision→Main (evidence/event 콜백 push): **실패**. AI 서버가 `:8000`으로 POST하면 Main에 도달하지 못한다.
- Main은 Vision에게 콜백 URL을 push하지 않는다(pull 전용 프록시). 따라서 `main_server_url`은 **Vision 측 정적 설정**이며 Main에서 원격으로 못 고친다.

## 요청 사항 (Vision 측)

Vision/AI 서버 설정의 Main 콜백 주소를 실제 포트로 변경:

```text
main_server_url: http://smartfactory-main.local:8000  ->  http://smartfactory-main.local:8088
```

`smartfactory-main.local`이 Vision PC에서 해석되지 않으면 IPv4 직접 사용도 가능:

```text
http://192.168.10.66:8088
```

> 운영 합의상 Main을 `:8000`으로 옮기는 대안도 있으나, `LMS_PUBLIC_BASE_URL`·프론트엔드·문서가 모두 `:8088` 기준이므로 **Vision 측을 `:8088`로 맞추는 것을 권장**한다.

## 검증 (Vision 변경 후, Vision PC 또는 같은 LAN에서)

```bash
# 1) AI 서버가 보고하는 main_server_url이 :8088인지
curl http://smartfactory-vision.local:8100/api/v1/health
#    -> "main_server_url": "http://smartfactory-main.local:8088"

# 2) Main 콜백 엔드포인트 도달 확인
curl http://smartfactory-main.local:8088/health        # 200
curl http://smartfactory-main.local:8000/health        # 연결 실패가 정상(Main은 8000 안 씀)

# 3) Vision->Main evidence/event 콜백 실제 1건 전송 후 Main 로그/DB 수신 확인
```

기대 결과: AI 서버 `main_server_url`이 `:8088`로 표시되고, Vision→Main 콜백이 Main에 정상 도달한다.

## 비고

- 네트워크 안정화(라우터 DHCP 예약 `a0:ad:9f:bd:63:1b → 192.168.10.59`)는 별건으로 여전히 권장. 임시 tmux mDNS 퍼블리셔는 운영 설정이 아님.
- 이 메모는 `main-vision-runtime-config-request-2026-06-19.md`의 후속이다.
