"""Lift ROI evidence API tests."""

import json

from api_test_helpers import InstanceMask, blank_png_bytes, client, get_settings, main_module, np

def test_lift_roi_evaluate_returns_contract_valid_pickup_evidence():
    response = client.post(
        "/api/v1/lift-roi/evaluate",
        json={
            "source": "tb3_1_picam",
            "operation": "PICKUP",
            "task_id": "TASK-IN-0001",
            "image": {"width": 200, "height": 160},
            "roi": {
                "roi_id": "TB3_1_LIFT_ROI",
                "kind": "LIFT",
                "polygon_xy": [[50, 40], [150, 40], [150, 120], [50, 120]],
            },
            "expected_count": 1,
            "stable_frames": 3,
            "count_stable": True,
            "lift_sensor": {
                "lift_up": True,
                "lift_down_complete": None,
                "backoff_complete": None,
            },
            "candidates": [
                {
                    "class_name": "box",
                    "bbox_xyxy": [60, 50, 90, 90],
                    "confidence": 0.91,
                    "track_id": "box-1",
                }
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["schema_version"] == "lift-roi-evidence.v1"
    assert body["source"] == "tb3_1_picam"
    assert body["robot_id"] == "tb3_1"
    assert body["frame_id"] == "tb3_1_pi_camera_optical_frame"
    assert body["load"]["count"] == 1
    assert body["load"]["empty"] is False
    assert body["load"]["accepted_items"][0]["evidence_type"] == "bbox"
    assert body["verification"] == {"status": "CONFIRMED", "reason": "pickup_verified"}
    assert body["policy"]["load_classes"] == ["box", "pallet"]
    assert body["metadata"]["model"] == "provided-bbox"

def test_lift_roi_evaluate_accepts_instance_mask_polygon_without_model_choice():
    response = client.post(
        "/api/v1/lift-roi/evaluate",
        json={
            "source": "global_cam_01",
            "operation": "DROPOFF",
            "task_id": "TASK-OUT-0001",
            "image": {"width": 200, "height": 160},
            "roi": {
                "roi_id": "OUTBOUND_SLOT_A_ROI",
                "kind": "TARGET_SLOT",
                "polygon_xy": [[50, 40], [150, 40], [150, 120], [50, 120]],
            },
            "expected_count": 1,
            "stable_frames": 2,
            "count_stable": True,
            "lift_sensor": {
                "lift_up": None,
                "lift_down_complete": True,
                "backoff_complete": True,
            },
            "candidates": [
                {
                    "class_name": "pallet",
                    "bbox_xyxy": [0, 0, 190, 150],
                    "confidence": 0.87,
                    "track_id": 12,
                    "evidence_type": "instance_mask",
                    "mask_polygon_xy": [[80, 60], [130, 60], [130, 100], [80, 100]],
                }
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    item = body["load"]["accepted_items"][0]
    assert body["robot_id"] is None
    assert item["evidence_type"] == "instance_mask"
    assert item["mask_area_px"] > 0
    assert item["overlap_ratio"] == 1.0
    assert body["verification"]["reason"] == "dropoff_vision_verified"
    assert body["metadata"]["model"] == "provided-instance-mask"

def test_lift_roi_evaluate_keeps_contract_valid_for_non_load_rejections():
    response = client.post(
        "/api/v1/lift-roi/evaluate",
        json={
            "source": "tb3_2_picam",
            "operation": "MONITOR",
            "image": {"width": 200, "height": 160},
            "roi": {
                "roi_id": "TB3_2_LIFT_ROI",
                "kind": "LIFT",
                "polygon_xy": [[50, 40], [150, 40], [150, 120], [50, 120]],
            },
            "stable_frames": 1,
            "count_stable": False,
            "lift_sensor": {
                "lift_up": None,
                "lift_down_complete": None,
                "backoff_complete": None,
            },
            "candidates": [
                {
                    "class_name": "person",
                    "bbox_xyxy": [60, 50, 90, 90],
                    "confidence": 0.8,
                }
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    rejected = body["load"]["rejected_items"][0]
    assert body["load"]["count"] == 0
    assert rejected["class_name"] == "unknown"
    assert rejected["reason"] == "class_not_load"
    assert body["verification"] == {"status": "CANDIDATE", "reason": "monitor_only"}

def test_lift_roi_evaluate_rejects_bad_source_and_incomplete_instance_mask():
    bad_source = client.post(
        "/api/v1/lift-roi/evaluate",
        json={
            "source": "bad_cam",
            "operation": "MONITOR",
            "image": {"width": 200, "height": 160},
            "roi": {
                "roi_id": "LIFT_ROI",
                "kind": "LIFT",
                "polygon_xy": [[50, 40], [150, 40], [150, 120], [50, 120]],
            },
        },
    )
    assert bad_source.status_code == 400

    missing_mask = client.post(
        "/api/v1/lift-roi/evaluate",
        json={
            "source": "tb3_1_picam",
            "operation": "MONITOR",
            "image": {"width": 200, "height": 160},
            "roi": {
                "roi_id": "LIFT_ROI",
                "kind": "LIFT",
                "polygon_xy": [[50, 40], [150, 40], [150, 120], [50, 120]],
            },
            "candidates": [
                {
                    "class_name": "box",
                    "bbox_xyxy": [60, 50, 90, 90],
                    "confidence": 0.91,
                    "evidence_type": "instance_mask",
                }
            ],
        },
    )
    assert missing_mask.status_code == 400
    assert "mask_polygon_xy is required" in missing_mask.json()["error"]["message"]

def test_lift_roi_pickup_gate_blocks_lift_success_when_vision_count_is_insufficient():
    response = client.post(
        "/api/v1/lift-roi/evaluate",
        json={
            "source": "tb3_1_picam",
            "operation": "PICKUP",
            "task_id": "TASK-IN-UNSAFE",
            "image": {"width": 200, "height": 160},
            "roi": {
                "roi_id": "TB3_1_LIFT_ROI",
                "kind": "LIFT",
                "polygon_xy": [[50, 40], [150, 40], [150, 120], [50, 120]],
            },
            "expected_count": 2,
            "stable_frames": 3,
            "count_stable": True,
            "lift_sensor": {
                "lift_up": True,
                "lift_down_complete": None,
                "backoff_complete": None,
            },
            "candidates": [
                {
                    "class_name": "box",
                    "bbox_xyxy": [60, 50, 90, 90],
                    "confidence": 0.91,
                }
            ],
        },
    )

    assert response.status_code == 200
    verification = response.json()["verification"]
    assert verification["status"] == "CANDIDATE"
    assert verification["reason"] == "load_count_mismatch"

def test_lift_roi_evaluate_image_fails_closed_when_model_is_not_configured(monkeypatch):
    settings = get_settings()
    main_module._parse_vision_model_source_config.cache_clear()
    monkeypatch.setattr(settings, "vision_model_worker_enabled", True)
    monkeypatch.setattr(settings, "vision_model_path", "")
    monkeypatch.setattr(settings, "vision_model_source_config_json", "")

    response = client.post(
        "/api/v1/lift-roi/evaluate-image",
        data={
            "source": "tb3_1_picam",
            "operation": "MONITOR",
            "roi_json": '{"roi_id":"TB3_1_LIFT_ROI","kind":"LIFT","polygon_xy":[[50,40],[150,40],[150,120],[50,120]]}',
        },
        files={"image": ("frame.png", blank_png_bytes(width=200, height=160), "image/png")},
    )

    assert response.status_code == 503
    assert "vision model path is not configured" in response.json()["error"]["message"]

def test_lift_roi_evaluate_image_uses_segmentation_mask_when_model_is_available(monkeypatch):
    class FakeSegmenter:
        detector_name = "fake-seg"

        def detect(self, image):
            mask = np.zeros(image.shape[:2], dtype=bool)
            mask[60:100, 80:130] = True
            return (
                InstanceMask(
                    class_name="box",
                    bbox_xyxy=(10.0, 10.0, 190.0, 150.0),
                    confidence=0.93,
                    mask=mask,
                    track_id="seg-1",
                    detector=self.detector_name,
                ),
            )

    settings = get_settings()
    main_module._parse_vision_model_source_config.cache_clear()
    monkeypatch.setattr(settings, "vision_model_worker_enabled", True)
    monkeypatch.setattr(settings, "vision_model_path", "fake-default-seg.pt")
    monkeypatch.setattr(settings, "vision_model_task", "segment")
    monkeypatch.setattr(main_module, "_get_lift_roi_segmenter", lambda **_: FakeSegmenter())

    response = client.post(
        "/api/v1/lift-roi/evaluate-image",
        data={
            "source": "tb3_1_picam",
            "operation": "PICKUP",
            "task_id": "TASK-IN-SEG",
            "expected_count": "1",
            "stable_frames": "3",
            "count_stable": "true",
            "lift_up": "true",
            "roi_json": '{"roi_id":"TB3_1_LIFT_ROI","kind":"LIFT","polygon_xy":[[50,40],[150,40],[150,120],[50,120]]}',
        },
        files={"image": ("frame.png", blank_png_bytes(width=200, height=160), "image/png")},
    )

    assert response.status_code == 200
    body = response.json()
    item = body["load"]["accepted_items"][0]
    assert item["evidence_type"] == "instance_mask"
    assert item["mask_area_px"] == 2000
    assert item["overlap_ratio"] == 1.0
    assert body["verification"] == {"status": "CONFIRMED", "reason": "pickup_verified"}
    assert body["metadata"]["model"] == "fake-seg"


def test_lift_roi_evaluate_image_routes_global_source_to_segment_model(monkeypatch):
    settings = get_settings()
    main_module._parse_vision_model_source_config.cache_clear()
    monkeypatch.setattr(settings, "vision_model_worker_enabled", True)
    monkeypatch.setattr(settings, "vision_model_path", "fallback-picam-det.pt")
    monkeypatch.setattr(settings, "vision_model_task", "detect")
    monkeypatch.setattr(settings, "vision_model_imgsz", 320)
    monkeypatch.setattr(settings, "vision_model_class_map_json", '{"person":"person"}')
    monkeypatch.setattr(
        settings,
        "vision_model_source_config_json",
        json.dumps(
            {
                "global_cam_01": {
                    "model_path": "global-pallet-seg.pt",
                    "task": "segment",
                    "imgsz": 640,
                    "class_map": {"pallet": "pallet", "box": "box"},
                },
                "tb3_1_picam": {
                    "model_path": "picam-person-det.pt",
                    "task": "detect",
                    "imgsz": 320,
                    "class_map": {"person": "person"},
                },
            }
        ),
    )
    calls = []

    class FakeSegmenter:
        detector_name = "fake-global-pallet-seg"

        def detect(self, image):
            calls.append({"image_shape": image.shape})
            mask = np.zeros(image.shape[:2], dtype=bool)
            mask[60:100, 80:130] = True
            return (
                InstanceMask(
                    class_name="pallet",
                    bbox_xyxy=(10.0, 10.0, 190.0, 150.0),
                    confidence=0.93,
                    mask=mask,
                    track_id="seg-1",
                    detector=self.detector_name,
                ),
            )

    def fake_model_factory(**kwargs):
        calls.append(kwargs)
        return FakeSegmenter()

    monkeypatch.setattr(main_module, "_get_lift_roi_segmenter", fake_model_factory)

    response = client.post(
        "/api/v1/lift-roi/evaluate-image",
        data={
            "source": "global_cam_01",
            "operation": "PICKUP",
            "task_id": "TASK-GLOBAL-SEG",
            "expected_count": "1",
            "stable_frames": "3",
            "count_stable": "true",
            "lift_up": "true",
            "roi_json": '{"roi_id":"GLOBAL_LIFT_ROI","kind":"LIFT","polygon_xy":[[50,40],[150,40],[150,120],[50,120]]}',
        },
        files={"image": ("frame.png", blank_png_bytes(width=200, height=160), "image/png")},
    )

    assert response.status_code == 200
    assert calls[0]["model_path"] == "global-pallet-seg.pt"
    assert calls[0]["task"] == "segment"
    assert calls[0]["image_size"] == 640
    assert calls[0]["class_map_json"] == '{"box": "box", "pallet": "pallet"}'
    body = response.json()
    assert body["load"]["accepted_items"][0]["class_name"] == "pallet"
    assert body["metadata"]["model"] == "fake-global-pallet-seg"
