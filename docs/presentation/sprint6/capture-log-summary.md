# Sprint 6 Vision 캡처 로그 요약

생성 시각: 2026-07-03 KST

## AI Server 상태

- status: `ok`
- model_status: `loaded`
- source_summary: `{'configured': 3, 'online': 2, 'stale': 0, 'disabled': 0, 'offline': 1}`
- sources: `global_cam_01, tb3_1_picam, tb3_2_picam`

## tb3_1 PiCam overlay metadata

- source: `tb3_1_picam`
- frame_seq: `2824`
- overlay 상태: `fresh`
- overlay lag frames: `0`
- event_count: `1`
- latest class: `person`
- latest confidence: `0.9226573705673218`
- latest model: `ultralytics-detect:/home/codelab/yolo_test/yolov8n.pt`

## Main-facing person hazard API 결과

- result: `ADVISORY`
- reason_code: `HUMAN_DETECTED`
- event_type: `HUMAN_DETECTED`
- robot_id: `tb3_1`
- task_id: `601`
- severity: `CRITICAL`
- confidence: `0.921348512172699`
- trusted: `False`
- 제어 명령: AI Server는 없음. Main이 HOLD/E-stop 최종 판단.
