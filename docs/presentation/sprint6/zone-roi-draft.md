# Global Cam Zone ROI Draft — 2026-07-03

현재 MapROI 위에 낙하물 감시를 위한 정적 구역 ROI 초안을 잡았다.

## 구역 해석

- 입고구역: A1/A0 주변. `natural_item_location=true`
- 충전구역: A3/A4 주변. 로봇 충전/대기 참고 구역이며, target item 자연 방치 구역은 아님.
- 출고구역: A5/A6 주변. `natural_item_location=true`
- 창고구역: A9/A10 주변 상단/하단. 위/아래 각각 약 30cm 구역으로 시작.
- 동적 파레트 구역: 아직 static JSON에는 없음. Main/ROS robot pose 기반 DynamicCarrierROI로 별도 계산 예정.

## 낙하물 판단 초안

낙하물이 있어도 자연스러운 위치는 다음으로 둔다.

1. 입고구역
2. 출고구역
3. 창고구역 상단/하단
4. active robot의 DynamicCarrierROI / pallet ROI

충전구역은 로봇이 있어도 자연스러운 구역이지만, target item이 떨어져 있어도 정상인 구역으로는 우선 보지 않는다.

## 파일

- config: `config/vision/zone_rois/global_cam_01_lab_draft.json`
- preview: `assets/03-global-zone-roi-draft.jpg`
- marker sample: `assets/03-zone-marker-visibility-current-60.json` (원본: `.run/vision/debug/zone_marker_visibility_current_60.json`)

## 현재 샘플링 메모

2026-07-03 17:58 KST 전후 60회 샘플 기준:

- 안정적으로 보임: A6 `60/60`, A11 `60/60`, A3 `57/60`
- 비교적 자주 보임: A4 `41/60`, A9 `34/60`, A5 `29/60`, A10 `29/60`
- 현재 샘플에서 거의/전혀 안 보임: A0/A1/A12

A0/A1은 현재 화면에서 간헐적이므로 입고구역 ROI는 물리 배치 설명과 현재 화면을 같이 보고 잡은 초안이다. A12는 현재 프레임에 매번 보이지 않아도, 한 번 LOCK된 Map ROI를 유지하는 용도로 쓴다.
