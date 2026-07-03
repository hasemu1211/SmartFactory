# Sprint 6 발표 원천 소스 모음

이번 폴더는 최종 발표자료가 아니라, 발표 슬라이드를 만들 때 가져다 쓸 **캡처 이미지 / 쉬운 설명 / 검증 로그 원천자료**입니다.

## 바로 볼 파일

- `live-capture.html` — 실시간 캡처용 웹페이지
- `sprint6-source-notes.md` — 이번 주 작업을 쉬운 말로 정리한 발표 메모
- `capture-log-summary.md` — 실제 tb3_1 person detection API 로그 요약
- `zone-roi-draft.md` — Global Cam 정적 구역 ROI 초안과 낙하물 판단 기준

## 대표 이미지

- `assets/01-tb3_1-person-detection-overlay.jpg` — PiCam 사람 감지 overlay
- `assets/01-tb3_1-person-camera-frame.jpg` — PiCam 원본 프레임
- `assets/02-global-map-roi-locked.jpg` — Global Cam Map ROI + ArUco LOCK overlay
- `assets/03-global-zone-roi-draft.jpg` — 입고/출고/창고/충전 구역 ROI 초안 overlay

## 실시간 캡처 URL

AI 노트북/SF runtime이 켜져 있을 때:

```text
http://smartfactory-vision.local:8889/tb3_1_picam_full/
http://smartfactory-vision.local:8889/global_cam_01_full/
http://smartfactory-vision.local:8100/api/v1/vision/hazards/person/latest?robot_id=tb3_1
```

이 PC에서 캡처용 페이지 서버를 켜려면:

```bash
cd /home/codelab/Desktop/Project/SmartFactory
python3 docs/presentation/sprint6/serve_live_capture.py
```

브라우저:

```text
http://127.0.0.1:9876/live-capture.html
```

주의: `live-capture.html`의 JSON 패널은 `/proxy`를 사용하므로 일반
`python3 -m http.server`가 아니라 `serve_live_capture.py`로 띄워야 한다.
