# Vision/Main live AI overlay validation — 2026-06-19 KST

## Summary

On 2026-06-19 KST, the operator validated the current Vision/Main integration with two robot cameras and AI overlay streaming visible on the Main dashboard.

## Operator-confirmed runtime state

- Main dashboard page showed the real-time video panel in grid mode.
- Stream mode was `overlay`.
- Two camera cards were visible:
  - `tb3_1 Camera` / `tb3_1_picam`
  - `tb3_2 Camera` / `tb3_2_picam`
- Both streams displayed AI overlay boxes/labels for `person` detections.
- The visible overlay timestamps were around `13:50:44` and `13:50:45`.
- The dashboard showed `2대`, matching two active camera sources.
- Runtime setup reported by operator:
  - tmux window `3:` had SSH sessions open to both robots.
  - camera launch/bringup was running on both robots.
  - Vision bundle was started with `./scripts/vision/run_d1_vision_multi_source_gateway_bundle.sh`.

## Evidence asset

- Screenshot: `docs/reports/assets/main-dashboard-two-robot-ai-overlay-2026-06-19.png`

## Contract relevance

This confirms the current Main-facing stream contract is working in the lab path:

```text
Robot Pi camera sources
-> ROS/domain camera bridge sidecars
-> AI overlay processing
-> public Vision Stream Gateway :8090
-> Main dashboard real-time video panel
```

Main-facing stream examples:

```text
http://smartfactory-vision.local:8090/api/v1/vision/overlay/stream?source=tb3_1_picam&max_fps=30
http://smartfactory-vision.local:8090/api/v1/vision/overlay/stream?source=tb3_2_picam&max_fps=30
```

## Safety note

This validation confirmed live video/evidence streaming. It does not grant Vision any motion authority. Vision remains evidence/advisory only; Nav/Movement owns robot motion and safety execution.
