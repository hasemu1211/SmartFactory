# Lane B visual QA artifact — 2026-06-15

Generated from API-served overlay image endpoints using `POST /api/v1/vision/synthetic/frame` and `GET /api/v1/vision/overlay/latest/image`.

Files:

- `fresh_overlay.jpg`: fresh evidence overlay.
- `stale_overlay.jpg`: stale evidence overlay with full-width amber warning band.
- `fresh_vs_stale_overlay_comparison.jpg`: side-by-side visual QA image.

Sampled pixel check at top-right header area, BGR order:

- fresh header pixel: `[255, 255, 254]`
- stale header pixel: `[0, 165, 254]`
- Euclidean difference: `270.42`

Expected visual QA result: stale overlay has a clearly visible amber header band, the warning text fits the synthetic 160px frame as `STALE FRAME`, compact bottom labels fit small debug frames, and metadata reports `visual_state=stale`.

Stale metadata excerpt:

```json
{'source': 'tb3_1_picam', 'frame_seq': 2, 'frame_timestamp': '2026-06-15T17:27:12.021510+09:00', 'evidence_timestamp': '2026-06-15T17:27:12.021817+09:00', 'overlay_timestamp': '2026-06-15T17:27:12.022262+09:00', 'latency_ms': 0.269, 'event_count': 1, 'stale': True, 'visual_state': 'stale', 'image': {'width': 160, 'height': 160}, 'content_type': 'image/jpeg'}
```

Validation commands:

```bash
./scripts/test_ai_server.sh -q tests/test_api.py tests/test_overlay.py tests/test_contract_boundaries.py
./scripts/test_ai_server.sh -q
```

Current result: `122 passed, 1 warning`; contract fixtures behaved as expected.
