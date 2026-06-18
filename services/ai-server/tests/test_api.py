from fastapi.testclient import TestClient
import pytest
import cv2
import numpy as np

import app.main as main_module
from app.config import get_settings
from app.main import app
from app.vision_interfaces import DetectionBox, InstanceMask
from generated_fixtures import aruco_png_bytes, blank_png_bytes

client = TestClient(app)


def expected_ros_overlay_publish_qos_policy() -> dict:
    return {
        "reliability": "BEST_EFFORT",
        "history": "KEEP_LAST",
        "depth": 1,
        "durability": "VOLATILE",
    }


def expected_ros_overlay_publish_policy() -> dict:
    return {
        "message_type": "sensor_msgs/msg/CompressedImage",
        "encoding": "jpeg",
        "publish_when": "publish_payload_preview.payload_available_true",
        "drop_when": ["no_frame", "no_overlay", "overlay_lag"],
        "max_publish_fps": 10,
        "queue_policy": "keep_last_1_drop_old_overlay",
        "include_stale_warning_band": True,
        "publish_lagging_overlay": False,
        "publish_control_topics": False,
        "http_handlers_may_publish": False,
    }


def expected_ros_evidence_event_publish_policy() -> dict:
    return {
        "topic": "/sf/vision/events",
        "message_type": "smartfactory_msgs/msg/VisionEvent or JSON bridge payload",
        "schema_version": "vision-event.v1",
        "qos_profile": {
            "reliability": "RELIABLE",
            "history": "KEEP_LAST",
            "depth": 10,
            "durability": "VOLATILE",
        },
        "publish_when": "worker_tick_or_detector_emits_schema_valid_vision_event",
        "dedup_key": "event_id",
        "source_of_truth": "Main/WMS remains authoritative; Vision publishes evidence only",
        "publish_control_topics": False,
        "http_handlers_may_publish": False,
        "payload_contains_image_bytes": False,
    }


def source_definition(source: str):
    return get_settings().source_registry.get(source)


def expected_ros_ingest_runtime_plan(source: str) -> dict:
    definition = source_definition(source)
    return {
        "node_name": "smartfactory_vision_gateway",
        "executor": "MultiThreadedExecutor",
        "spin_location": "background_thread",
        "source_registry_path": str(get_settings().vision_sources_registry_path),
        "physical_input_topic": definition.physical_input.topic,
        "physical_input_message_type": definition.physical_input.message_type,
        "physical_input_content_type": definition.physical_input.content_type,
        "physical_input_transport": definition.physical_input.preferred_transport,
        "subscription_callback": "registry_source_image_message_to_latest_frame_store_put",
        "ingest_adapter": "_store_latest_frame_from_bytes",
        "ingest_adapter_contract": {
            "input": "registry source plus encoded image bytes plus content_type from HTTP or future ROS callback",
            "output": "StoredFrame in LatestFrameStore",
            "updates_source_health": True,
            "runs_detection_inline": False,
            "renders_overlay_inline": False,
            "safe_for_http_handlers": True,
            "raw_image_requires_callback_encoding": True,
        },
        "shared_state": "LatestFrameStore",
        "shared_state_guard": "threading.Lock inside frame store",
        "http_handler_role": "read_latest_state_only_never_spin_ros2",
        "backpressure": "overwrite_latest_frame_per_source",
        "target_frame_store_source": source,
        "startup_owner": "process_startup_or_launch_file_not_http_request",
        "shutdown_owner": "process_signal_handler_or_lifespan_cleanup",
    }


def expected_ros_ingest_readiness(source: str, *, topic_configured: bool = True) -> dict:
    definition = source_definition(source)
    return {
        "readiness_state": "contract_ready" if topic_configured else "missing_physical_topic",
        "physical_input_topic_configured": topic_configured,
        "physical_input_message_type": definition.physical_input.message_type,
        "physical_input_content_type": definition.physical_input.content_type,
        "physical_input_transport": definition.physical_input.preferred_transport,
        "runtime_subscriber_active": False,
        "http_debug_ingest_path": "/api/v1/vision/frame",
        "required_qos_profile": {
            "reliability": "BEST_EFFORT",
            "history": "KEEP_LAST",
            "depth": 1,
        },
        "frame_drop_policy": {
            "cache": "latest_only",
            "drop_stale_frames": True,
            "stale_after_s": get_settings().source_stale_after_s,
            "offline_after_s": get_settings().source_offline_after_s,
            "backpressure": "overwrite_latest_frame_per_source",
        },
        "runtime_plan": expected_ros_ingest_runtime_plan(source),
        "reason": (
            "source registry has a physical ROS image topic; Lane C can attach a background subscriber"
            if topic_configured
            else "no physical ROS image topic is configured for this source"
        ),
    }


def expected_ros_publish_runtime_plan(source: str) -> dict:
    return {
        "node_name": "smartfactory_vision_gateway",
        "executor": "MultiThreadedExecutor",
        "spin_location": "background_thread",
        "publisher_callback": "read_latest_overlay_then_publish_compressed_image_when_ready",
        "publish_adapter": "_overlay_publish_payload_preview_for_source",
        "publish_adapter_contract": {
            "input": "source plus latest frame and overlay cache state",
            "output": "publishable compressed overlay metadata when overlay is ready",
            "reads_latest_overlay_cache": True,
            "requires_frame_overlay_seq_match": True,
            "publishes_lagging_overlay": False,
            "publishes_control_topics": False,
            "safe_for_http_handlers": True,
        },
        "shared_state": "LatestEvidenceCache plus overlay image cache",
        "shared_state_guard": "threading.Lock around overlay image cache",
        "publish_topic": f"/sf/vision/sources/{source}/overlay/compressed",
        "publish_message_type": "sensor_msgs/msg/CompressedImage",
        "publish_qos_profile": expected_ros_overlay_publish_qos_policy(),
        "publish_policy": expected_ros_overlay_publish_policy(),
        "publish_condition": "overlay_ready_true_and_latest_overlay_frame_seq_matches_latest_frame_seq",
        "stale_behavior": "publish_ready_stale_overlay_with_visual_warning_band",
        "lag_behavior": "do_not_publish_lagging_overlay",
        "http_handler_role": "read_latest_state_only_never_publish_ros2",
        "control_publish_allowed": False,
        "startup_owner": "process_startup_or_launch_file_not_http_request",
        "shutdown_owner": "process_signal_handler_or_lifespan_cleanup",
    }


def expected_ros_topic_exposure_policy() -> dict:
    return {
        "policy": "explicit_allowlist_only",
        "rosbridge_exposes_all_topics": False,
        "browser_primary_transport": "rosbridge",
        "allowed_message_types": [
            "sensor_msgs/msg/CompressedImage",
            "smartfactory_msgs/msg/VisionEvent or JSON bridge payload",
        ],
        "forbidden_topic_globs": [
            "/cmd_vel",
            "*/cmd_vel",
            "/navigate_to_pose",
            "/follow_path",
            "/parameter_events",
            "/rosout",
            "/tf",
            "/tf_static",
        ],
        "forbidden_capabilities": [
            "motion_command_publish",
            "nav2_action_call",
            "parameter_mutation",
            "raw_dds_forwarding",
        ],
        "client_publish_allowed": False,
        "server_publish_control_allowed": False,
        "auth_required_when_exposed_beyond_private_network": True,
        "notes": [
            "Expose only camera/overlay/evidence topics needed by GUI.",
            "Do not expose all DDS topics through rosbridge.",
            "Motion and parameter mutation remain outside Vision Gateway.",
        ],
    }


def expected_source_topic_exposure(source: str) -> dict:
    robot_topic = {
        "tb3_1_picam": "/mission/tb3_1/camera/compressed",
        "tb3_2_picam": "/mission/tb3_2/camera/compressed",
    }.get(source)
    physical_topic = source_definition(source).physical_input.topic
    browser_topics = [
        item
        for item in (
            robot_topic,
            f"/sf/vision/sources/{source}/image/compressed",
            f"/sf/vision/sources/{source}/overlay/compressed",
        )
        if item is not None
    ]
    return {
        "allowed_browser_topics": browser_topics,
        "allowed_ingest_topics": [physical_topic],
        "allowed_publish_topics": [
            f"/sf/vision/sources/{source}/image/compressed",
            f"/sf/vision/sources/{source}/overlay/compressed",
            "/sf/vision/events",
        ],
        "client_publish_allowed": False,
        "control_topics_allowed": [],
        "forbidden_topic_globs": expected_ros_topic_exposure_policy()["forbidden_topic_globs"],
    }


def expected_rosbridge_subscription_hints(source: str) -> dict:
    return {
        "allowed_browser_topics": expected_source_topic_exposure(source)[
            "allowed_browser_topics"
        ],
        "recommended_image_topic": f"/sf/vision/sources/{source}/image/compressed",
        "recommended_overlay_topic": f"/sf/vision/sources/{source}/overlay/compressed",
        "legacy_browser_topic": {
            "tb3_1_picam": "/mission/tb3_1/camera/compressed",
            "tb3_2_picam": "/mission/tb3_2/camera/compressed",
        }.get(source),
        "client_publish_allowed": False,
        "control_topics_allowed": [],
    }


def expected_topic_exposure_summary(sources: list[str]) -> dict:
    exposures = [expected_source_topic_exposure(source) for source in sources]
    browser_topics = {
        topic for exposure in exposures for topic in exposure["allowed_browser_topics"]
    }
    ingest_topics = {
        topic for exposure in exposures for topic in exposure["allowed_ingest_topics"]
    }
    publish_topics = {
        topic for exposure in exposures for topic in exposure["allowed_publish_topics"]
    }
    control_topics = {
        topic for exposure in exposures for topic in exposure["control_topics_allowed"]
    }
    policy = expected_ros_topic_exposure_policy()
    return {
        "sources_total": len(sources),
        "allowed_browser_topic_count": len(browser_topics),
        "allowed_ingest_topic_count": len(ingest_topics),
        "allowed_publish_topic_count": len(publish_topics),
        "control_topic_allowed_count": len(control_topics),
        "client_publish_allowed_source_count": sum(
            1 for exposure in exposures if exposure["client_publish_allowed"]
        ),
        "forbidden_topic_glob_count": len(policy["forbidden_topic_globs"]),
        "forbidden_capability_count": len(policy["forbidden_capabilities"]),
        "explicit_allowlist_only": True,
        "rosbridge_exposes_all_topics": False,
        "server_publish_control_allowed": False,
        "policy_status": "safe",
        "policy_violation_count": 0,
        "policy_violations": [],
    }


def test_health_exposes_canonical_sources():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["schema_version"] == "vision-event.v1"
    assert body["sources"] == ["global_cam_01", "tb3_1_picam", "tb3_2_picam"]
    assert body["event_retention"]["max_size"] == 200


def test_sources_include_robot_mapping():
    main_module.source_health.reset()
    response = client.get("/api/v1/sources")
    assert response.status_code == 200
    sources = {item["source"]: item for item in response.json()["sources"]}
    assert sources["global_cam_01"]["robot_id"] is None
    assert sources["tb3_1_picam"]["robot_id"] == "tb3_1"
    assert sources["tb3_2_picam"]["robot_id"] == "tb3_2"
    assert sources["tb3_1_picam"]["status"] == "offline"
    assert sources["tb3_1_picam"]["last_frame_at"] is None
    assert sources["tb3_1_picam"]["last_event_at"] is None
    assert sources["tb3_1_picam"]["frame_count"] == 0
    assert sources["tb3_1_picam"]["event_count"] == 0


def test_detect_image_updates_source_health_for_blank_frame():
    main_module.source_health.reset()

    response = client.post(
        "/api/v1/detect/image",
        data={"source": "tb3_1_picam"},
        files={"image": ("frame.png", blank_png_bytes(), "image/png")},
    )

    assert response.status_code == 200
    sources_response = client.get("/api/v1/sources")
    sources = {item["source"]: item for item in sources_response.json()["sources"]}
    tb3_1 = sources["tb3_1_picam"]
    assert tb3_1["status"] == "online"
    assert tb3_1["last_frame_at"] is not None
    assert tb3_1["last_frame_age_s"] is not None
    assert tb3_1["last_event_at"] is None
    assert tb3_1["frame_count"] == 1
    assert tb3_1["event_count"] == 0

    health = client.get("/api/v1/health").json()["source_summary"]
    assert health["configured"] == 3
    assert health["online"] == 1
    assert health["offline"] == 2


def test_detect_image_updates_source_health_for_marker_event():
    main_module.source_health.reset()

    response = client.post(
        "/api/v1/detect/image",
        data={"source": "tb3_1_picam"},
        files={"image": ("aruco.png", aruco_png_bytes(), "image/png")},
    )

    assert response.status_code == 200
    event = response.json()["events"][0]
    sources = {item["source"]: item for item in client.get("/api/v1/sources").json()["sources"]}
    tb3_1 = sources["tb3_1_picam"]
    assert tb3_1["status"] == "online"
    assert tb3_1["frame_count"] == 1
    assert tb3_1["event_count"] == 1
    assert tb3_1["last_event_at"] == event["timestamp"]
    assert tb3_1["last_event_id"] == event["event_id"]
    assert tb3_1["last_event_kind"] == "CONFIRMED"
    assert tb3_1["last_marker_id"] == "ARUCO_4X4_50_7"


def test_detect_image_returns_empty_events_for_frame_without_markers():
    response = client.post(
        "/api/v1/detect/image",
        data={"source": "tb3_1_picam"},
        files={"image": ("frame.png", blank_png_bytes(), "image/png")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "tb3_1_picam"
    assert body["emitted"] is False
    assert body["emit_disabled"] is False
    assert body["emit_results"] == []
    assert body["events"] == []


def test_detect_image_returns_contract_valid_marker_event():
    response = client.post(
        "/api/v1/detect/image",
        data={"source": "tb3_1_picam"},
        files={"image": ("aruco.png", aruco_png_bytes(), "image/png")},
    )
    assert response.status_code == 200
    events = response.json()["events"]
    assert len(events) == 1
    event = events[0]
    assert event["schema_version"] == "vision-event.v1"
    assert event["event_kind"] == "CONFIRMED"
    assert event["class_name"] == "aruco_marker"
    assert event["marker_id"] == "ARUCO_4X4_50_7"
    assert event["source"] == "tb3_1_picam"
    assert event["robot_id"] == "tb3_1"
    assert event["depth_median_m"] is None


def test_detect_image_emit_flag_is_disabled_by_default(monkeypatch):
    async def fail_if_called(*_, **__):
        raise AssertionError("WMS emit should not be called when disabled")

    monkeypatch.setattr(main_module, "emit_vision_events", fail_if_called)
    response = client.post(
        "/api/v1/detect/image",
        data={"source": "tb3_2_picam", "emit": "true"},
        files={"image": ("aruco.png", aruco_png_bytes(9), "image/png")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "tb3_2_picam"
    assert body["emitted"] is False
    assert body["emit_disabled"] is True
    assert body["emit_results"] == []
    assert len(body["events"]) == 1
    assert body["events"][0]["source"] == "tb3_2_picam"


def test_detect_image_emits_to_wms_when_enabled(monkeypatch):
    monkeypatch.setenv("WMS_EMIT_ENABLED", "true")
    get_settings.cache_clear()

    async def fake_emit(events, *, settings):
        assert settings.wms_emit_enabled is True
        return [
            {
                "event_id": event["event_id"],
                "attempted": True,
                "ok": True,
                "status_code": 202,
                "error": None,
                "response": {
                    "accepted": True,
                    "duplicate": False,
                    "wms_processing_status": "queued",
                },
            }
            for event in events
        ]

    monkeypatch.setattr(main_module, "emit_vision_events", fake_emit)
    try:
        response = client.post(
            "/api/v1/detect/image",
            data={"source": "tb3_1_picam", "emit": "true"},
            files={"image": ("aruco.png", aruco_png_bytes(11), "image/png")},
        )
    finally:
        get_settings.cache_clear()

    assert response.status_code == 200
    body = response.json()
    assert body["emitted"] is True
    assert body["emit_disabled"] is False
    assert len(body["events"]) == 1
    assert len(body["emit_results"]) == 1
    assert body["emit_results"][0]["event_id"] == body["events"][0]["event_id"]
    assert body["emit_results"][0]["status_code"] == 202


def test_detect_image_reports_wms_failure_without_failing_detection(monkeypatch):
    monkeypatch.setenv("WMS_EMIT_ENABLED", "true")
    get_settings.cache_clear()

    async def fake_emit(events, *, settings):
        return [
            {
                "event_id": event["event_id"],
                "attempted": True,
                "ok": False,
                "status_code": 503,
                "error": "WMS ingest returned HTTP 503",
                "response": None,
            }
            for event in events
        ]

    monkeypatch.setattr(main_module, "emit_vision_events", fake_emit)
    try:
        response = client.post(
            "/api/v1/detect/image",
            data={"source": "tb3_1_picam", "emit": "true"},
            files={"image": ("aruco.png", aruco_png_bytes(12), "image/png")},
        )
    finally:
        get_settings.cache_clear()

    assert response.status_code == 200
    body = response.json()
    assert body["emitted"] is False
    assert len(body["events"]) == 1
    assert body["emit_results"][0]["ok"] is False
    assert body["emit_results"][0]["status_code"] == 503


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


def test_lift_roi_evaluate_image_fails_closed_when_model_is_not_configured():
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






def test_detect_image_can_emit_aruco_pose_from_named_profile():
    response = client.post(
        "/api/v1/detect/image",
        data={"source": "tb3_1_picam", "pose_profile": "tb3_1_lab_marker_7"},
        files={"image": ("aruco.png", aruco_png_bytes(), "image/png")},
    )

    assert response.status_code == 200
    pose = response.json()["events"][0]["pose_estimate"]
    assert pose is not None
    assert pose["method"] == "ARUCO_POSE"
    assert abs(pose["x"]) < 0.02
    assert 0.45 < pose["y"] < 0.60


def test_detect_image_rejects_pose_profile_with_manual_calibration_mix():
    response = client.post(
        "/api/v1/detect/image",
        data={
            "source": "tb3_1_picam",
            "pose_profile": "tb3_1_lab_marker_7",
            "marker_size_m": "0.08",
        },
        files={"image": ("aruco.png", aruco_png_bytes(), "image/png")},
    )

    assert response.status_code == 400
    assert "pose_profile cannot be combined" in response.json()["error"]["message"]


def test_detect_image_unknown_pose_profile_is_bad_request():
    response = client.post(
        "/api/v1/detect/image",
        data={"source": "tb3_1_picam", "pose_profile": "missing_profile"},
        files={"image": ("aruco.png", aruco_png_bytes(), "image/png")},
    )

    assert response.status_code == 400
    assert "unknown pose_profile" in response.json()["error"]["message"]


def test_detect_image_pose_profile_marker_mismatch_keeps_pose_null():
    response = client.post(
        "/api/v1/detect/image",
        data={"source": "tb3_1_picam", "pose_profile": "tb3_1_picam_marker_0_placeholder"},
        files={"image": ("aruco.png", aruco_png_bytes(), "image/png")},
    )

    assert response.status_code == 200
    assert response.json()["events"][0]["marker_id"] == "ARUCO_4X4_50_7"
    assert response.json()["events"][0]["pose_estimate"] is None


def test_detect_image_can_emit_optional_aruco_pose_estimate():
    response = client.post(
        "/api/v1/detect/image",
        data={
            "source": "tb3_1_picam",
            "marker_size_m": "0.08",
            "camera_fx": "600",
            "camera_fy": "600",
            "camera_cx": "80",
            "camera_cy": "80",
            "camera_dist_coeffs": "0,0,0,0,0",
        },
        files={"image": ("aruco.png", aruco_png_bytes(), "image/png")},
    )

    assert response.status_code == 200
    events = response.json()["events"]
    assert len(events) == 1
    pose = events[0]["pose_estimate"]
    assert pose is not None
    assert pose["method"] == "ARUCO_POSE"
    assert abs(pose["x"]) < 0.02
    assert 0.45 < pose["y"] < 0.60
    assert abs(pose["yaw"]) < 0.10
    assert 0.0 <= pose["confidence"] <= 1.0


def test_detect_image_rejects_partial_aruco_pose_calibration():
    response = client.post(
        "/api/v1/detect/image",
        data={"source": "tb3_1_picam", "marker_size_m": "0.08"},
        files={"image": ("aruco.png", aruco_png_bytes(), "image/png")},
    )

    assert response.status_code == 400
    assert "ArUco pose requires" in response.json()["error"]["message"]


def test_detect_image_rejects_invalid_pose_numbers():
    response = client.post(
        "/api/v1/detect/image",
        data={
            "source": "tb3_1_picam",
            "marker_size_m": "-0.08",
            "camera_fx": "600",
            "camera_fy": "600",
            "camera_cx": "80",
            "camera_cy": "80",
        },
        files={"image": ("aruco.png", aruco_png_bytes(), "image/png")},
    )

    assert response.status_code == 400
    assert response.json()["error"]["message"] == "marker_size_m must be positive"


def test_invalid_image_rejected():
    response = client.post(
        "/api/v1/detect/image",
        data={"source": "tb3_1_picam"},
        files={"image": ("frame.jpg", b"fake-image-bytes", "image/jpeg")},
    )
    assert response.status_code == 400


def test_latest_detections_can_filter_by_source():
    client.post(
        "/api/v1/detect/image",
        data={"source": "global_cam_01"},
        files={"image": ("aruco.png", aruco_png_bytes(8), "image/png")},
    )
    response = client.get(
        "/api/v1/detections/latest", params={"source": "global_cam_01", "limit": 5}
    )
    assert response.status_code == 200
    events = response.json()["events"]
    assert events
    assert all(event["source"] == "global_cam_01" for event in events)


def test_unknown_source_rejected():
    response = client.post(
        "/api/v1/detect/image",
        data={"source": "bad_cam"},
        files={
            "image": ("frame.png", blank_png_bytes(width=32, height=32), "image/png")
        },
    )
    assert response.status_code == 400


def test_detect_image_populates_overlay_metadata_and_image():
    main_module.source_health.reset()
    main_module.frame_store.reset()
    main_module.overlay_cache.reset()
    with main_module._overlay_images_lock:
        main_module._overlay_images.clear()

    response = client.post(
        "/api/v1/detect/image",
        data={"source": "tb3_1_picam"},
        files={"image": ("aruco.png", aruco_png_bytes(), "image/png")},
    )

    assert response.status_code == 200
    overlay_response = client.get("/api/v1/vision/overlay/latest", params={"source": "tb3_1_picam"})
    assert overlay_response.status_code == 200
    overlay_body = overlay_response.json()
    assert overlay_body["requested_source"] == "tb3_1_picam"
    assert overlay_body["sync"] == {
        "latest_frame_seq": 1,
        "latest_overlay_frame_seq": 1,
        "overlay_lag_frames": 0,
        "overlay_visual_state": "fresh",
    }
    overlay = overlay_body["overlay"]
    assert overlay["source"] == "tb3_1_picam"
    assert overlay["frame_seq"] == 1
    assert overlay["frame_timestamp"] is not None
    assert overlay["evidence_timestamp"] == response.json()["events"][0]["timestamp"]
    assert overlay["event_count"] == 1
    assert overlay["stale"] is False

    image_response = client.get(
        "/api/v1/vision/overlay/latest/image",
        params={"source": "tb3_1_picam"},
    )
    assert image_response.status_code == 200
    assert image_response.headers["content-type"] == "image/jpeg"
    assert image_response.content.startswith(b"\xff\xd8")



def test_overlay_latest_reports_sync_lag_after_newer_raw_frame():
    main_module.source_health.reset()
    main_module.frame_store.reset()
    main_module.overlay_cache.reset()
    with main_module._overlay_images_lock:
        main_module._overlay_images.clear()

    first = client.post(
        "/api/v1/vision/synthetic/frame",
        json={"source": "tb3_2_picam", "marker_id": 7},
    )
    assert first.status_code == 200
    decoded = main_module.generate_synthetic_aruco_frame(marker_id=8)
    frame = main_module.frame_store.put_decoded(source="tb3_2_picam", image_bgr=decoded)
    main_module.source_health.record_frame("tb3_2_picam", at=main_module._now_dt())
    assert frame.frame_seq == 2

    response = client.get("/api/v1/vision/overlay/latest", params={"source": "tb3_2_picam"})

    assert response.status_code == 200
    body = response.json()
    assert body["requested_source"] == "tb3_2_picam"
    assert body["overlay"]["frame_seq"] == 1
    assert body["sync"] == {
        "latest_frame_seq": 2,
        "latest_overlay_frame_seq": 1,
        "overlay_lag_frames": 1,
        "overlay_visual_state": "fresh",
    }

def test_overlay_latest_returns_404_before_any_frame():
    main_module.frame_store.reset()
    main_module.overlay_cache.reset()
    with main_module._overlay_images_lock:
        main_module._overlay_images.clear()

    response = client.get("/api/v1/vision/overlay/latest", params={"source": "tb3_1_picam"})

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_vision_streams_declares_rosbridge_primary_and_debug_fallback():
    main_module.store.reset()
    main_module.source_health.reset()
    main_module.frame_store.reset()
    main_module.overlay_cache.reset()
    with main_module._overlay_images_lock:
        main_module._overlay_images.clear()

    response = client.get("/api/v1/vision/streams")

    assert response.status_code == 200
    body = response.json()
    assert body["requested_source"] is None
    assert body["summary"]["sources_total"] == 3
    assert body["summary"]["ros_ingest_contract_ready_count"] == 3
    assert body["summary"]["ros_ingest_runtime_subscriber_active_count"] == 0
    assert body["summary"]["ros_ingest_status_counts"] == {"contract_ready": 3}
    assert body["summary"]["ros_publish_ready_count"] == 0
    assert body["summary"]["ros_publish_payload_available_count"] == 0
    assert body["summary"]["ros_publish_payload_blocked_count"] == 3
    assert body["summary"]["ros_publish_status_counts"] == {"no_frame": 3}
    assert body["summary"]["evidence_event_publish_ready_count"] == 0
    assert body["primary_stream_plane"] == "rosbridge"
    assert body["debug_only"] is True
    assert body["motion_command_allowed"] is False
    assert body["control_topics_published"] == []
    assert body["topic_exposure_policy"] == expected_ros_topic_exposure_policy()
    assert body["topic_exposure_summary"] == expected_topic_exposure_summary(
        ["global_cam_01", "tb3_1_picam", "tb3_2_picam"]
    )
    assert body["topic_exposure_summary"]["policy_status"] == "safe"
    assert body["runtime_policy"] == {
        "ros2_started_by_http_request": False,
        "recommended_executor": "MultiThreadedExecutor",
        "http_handlers_must_spin_ros2_executor": False,
        "threading_model": "ROS2 executor outside FastAPI request handlers with lock-protected latest-frame handoff",
    }
    assert body["debug_fallback"]["mjpeg_path_template"] == "/api/v1/vision/stream/{source}.mjpeg"
    assert body["debug_fallback"]["mjpeg_max_fps_default"] == 10
    assert body["debug_fallback"]["mjpeg_max_fps_limit"] == 30
    assert body["debug_fallback"]["frame_metadata_path"] == "/api/v1/vision/frame/latest?source={source}"
    assert body["debug_fallback"]["frame_image_path"] == "/api/v1/vision/frame/latest/image?source={source}"
    assert body["debug_fallback"]["ros_handoff_path"] == "/api/v1/vision/ros/topics"
    assert {item["source"] for item in body["sources"]} == {
        "global_cam_01",
        "tb3_1_picam",
        "tb3_2_picam",
    }





def test_vision_streams_can_filter_one_source_and_rejects_unknown_source():
    main_module.store.reset()
    main_module.source_health.reset()
    main_module.frame_store.reset()
    main_module.overlay_cache.reset()
    with main_module._overlay_images_lock:
        main_module._overlay_images.clear()

    response = client.get("/api/v1/vision/streams", params={"source": "tb3_1_picam"})

    assert response.status_code == 200
    body = response.json()
    assert body["requested_source"] == "tb3_1_picam"
    assert body["summary"]["sources_total"] == 1
    assert body["summary"]["with_frame_count"] == 0
    assert body["summary"]["with_overlay_count"] == 0
    assert body["summary"]["ros_ingest_contract_ready_count"] == 1
    assert body["summary"]["ros_ingest_runtime_subscriber_active_count"] == 0
    assert body["summary"]["ros_ingest_status_counts"] == {"contract_ready": 1}
    assert body["summary"]["ros_publish_ready_count"] == 0
    assert body["summary"]["ros_publish_payload_available_count"] == 0
    assert body["summary"]["ros_publish_payload_blocked_count"] == 1
    assert body["summary"]["ros_publish_status_counts"] == {"no_frame": 1}
    assert body["summary"]["evidence_event_publish_ready_count"] == 0
    assert body["primary_stream_plane"] == "rosbridge"
    assert body["debug_only"] is True
    assert body["motion_command_allowed"] is False
    assert body["control_topics_published"] == []
    assert [item["source"] for item in body["sources"]] == ["tb3_1_picam"]
    source = body["sources"][0]
    assert source["mjpeg_path"] == "/api/v1/vision/stream/tb3_1_picam.mjpeg"
    assert source["frame_metadata_path"] == "/api/v1/vision/frame/latest?source=tb3_1_picam"
    assert source["overlay_metadata_path"] == "/api/v1/vision/overlay/latest?source=tb3_1_picam"
    assert source["metrics_path"] == "/api/v1/metrics?source=tb3_1_picam"
    assert source["ros_handoff_path"] == "/api/v1/vision/ros/topics"
    assert source["ros_handoff_source_path"] == "/api/v1/vision/ros/topics?source=tb3_1_picam"
    assert body["topic_exposure_summary"] == expected_topic_exposure_summary(["tb3_1_picam"])
    assert body["runtime_policy"]["ros2_started_by_http_request"] is False
    assert body["runtime_policy"]["http_handlers_must_spin_ros2_executor"] is False
    assert source["topic_exposure"] == expected_source_topic_exposure("tb3_1_picam")
    assert source["rosbridge_subscription_hints"] == expected_rosbridge_subscription_hints(
        "tb3_1_picam"
    )
    assert source["ros_ingest_readiness"] == expected_ros_ingest_readiness("tb3_1_picam")
    assert source["ros_publish_readiness"]["readiness_state"] == "no_frame"
    assert source["ros_publish_readiness"]["overlay_ready"] is False
    assert source["ros_publish_readiness"]["publish_payload_preview"] == {
        "payload_available": False,
        "topic": "/sf/vision/sources/tb3_1_picam/overlay/compressed",
        "message_type": "sensor_msgs/msg/CompressedImage",
        "frame_seq": None,
        "content_type": None,
        "size_bytes": 0,
        "reason": "no latest frame has been ingested",
    }
    assert source["ros_publish_readiness"]["runtime_plan"] == (
        expected_ros_publish_runtime_plan("tb3_1_picam")
    )
    assert source["evidence_event_publish_readiness"] == {
        "event_available": False,
        "publish_ready": False,
        "topic": "/sf/vision/events",
        "message_type": "smartfactory_msgs/msg/VisionEvent or JSON bridge payload",
        "schema_version": None,
        "latest_event_id": None,
        "latest_event_kind": None,
        "latest_event_timestamp": None,
        "dedup_key": "event_id",
        "payload_contains_image_bytes": False,
        "policy": expected_ros_evidence_event_publish_policy(),
        "reason": "no VisionEvent is available for this source",
    }

    bad = client.get("/api/v1/vision/streams", params={"source": "bad_cam"})
    assert bad.status_code == 400
    assert bad.json()["error"]["code"] == "BAD_REQUEST"



def test_vision_streams_reports_frame_overlay_lag_status():
    main_module.store.reset()
    main_module.source_health.reset()
    main_module.frame_store.reset()
    main_module.overlay_cache.reset()
    with main_module._overlay_images_lock:
        main_module._overlay_images.clear()

    ingest = client.post(
        "/api/v1/vision/frame",
        data={"source": "tb3_1_picam"},
        files={"image": ("aruco.png", aruco_png_bytes(), "image/png")},
    )
    assert ingest.status_code == 200

    before_tick = client.get("/api/v1/vision/streams", params={"source": "tb3_1_picam"})
    assert before_tick.status_code == 200
    source_before = before_tick.json()["sources"][0]
    assert source_before["latest_frame_seq"] == 1
    assert source_before["latest_overlay_frame_seq"] is None
    assert source_before["overlay_lag_frames"] is None
    assert source_before["overlay_visual_state"] is None
    assert before_tick.json()["summary"]["with_frame_count"] == 1
    assert before_tick.json()["summary"]["with_overlay_count"] == 0
    assert before_tick.json()["summary"]["overlay_lag_count"] == 0
    assert before_tick.json()["summary"]["ros_ingest_contract_ready_count"] == 1
    assert before_tick.json()["summary"]["ros_ingest_runtime_subscriber_active_count"] == 0
    assert before_tick.json()["summary"]["ros_ingest_status_counts"] == {"contract_ready": 1}
    assert source_before["ros_ingest_readiness"]["readiness_state"] == "contract_ready"
    assert source_before["ros_ingest_readiness"]["runtime_subscriber_active"] is False
    assert before_tick.json()["summary"]["ros_publish_ready_count"] == 0
    assert before_tick.json()["summary"]["ros_publish_payload_available_count"] == 0
    assert before_tick.json()["summary"]["ros_publish_payload_blocked_count"] == 1
    assert before_tick.json()["summary"]["ros_publish_status_counts"] == {"no_overlay": 1}
    assert source_before["ros_publish_readiness"]["readiness_state"] == "no_overlay"
    assert source_before["ros_publish_readiness"]["overlay_ready"] is False
    assert source_before["ros_publish_readiness"]["publish_payload_preview"]["payload_available"] is False

    tick = client.post("/api/v1/vision/worker/tick", json={"source": "tb3_1_picam"})
    assert tick.status_code == 200

    synced = client.get("/api/v1/vision/streams", params={"source": "tb3_1_picam"})
    assert synced.status_code == 200
    source_synced = synced.json()["sources"][0]
    assert source_synced["latest_frame_seq"] == 1
    assert source_synced["latest_overlay_frame_seq"] == 1
    assert source_synced["overlay_lag_frames"] == 0
    assert source_synced["overlay_visual_state"] == "fresh"
    assert synced.json()["summary"]["with_frame_count"] == 1
    assert synced.json()["summary"]["with_overlay_count"] == 1
    assert synced.json()["summary"]["synced_overlay_count"] == 1
    assert synced.json()["summary"]["ros_publish_ready_count"] == 1
    assert synced.json()["summary"]["ros_publish_payload_available_count"] == 1
    assert synced.json()["summary"]["ros_publish_payload_blocked_count"] == 0
    assert synced.json()["summary"]["ros_publish_status_counts"] == {"ready_fresh": 1}
    assert synced.json()["summary"]["evidence_event_publish_ready_count"] == 1
    assert source_synced["ros_publish_readiness"]["readiness_state"] == "ready_fresh"
    assert source_synced["ros_publish_readiness"]["overlay_ready"] is True
    assert source_synced["ros_publish_readiness"]["publish_payload_preview"]["payload_available"] is True
    assert source_synced["ros_publish_readiness"]["publish_payload_preview"]["topic"] == (
        "/sf/vision/sources/tb3_1_picam/overlay/compressed"
    )
    assert source_synced["ros_publish_readiness"]["runtime_plan"] == (
        expected_ros_publish_runtime_plan("tb3_1_picam")
    )
    assert source_synced["evidence_event_publish_readiness"]["publish_ready"] is True
    assert source_synced["evidence_event_publish_readiness"]["schema_version"] == "vision-event.v1"

    newer = client.post(
        "/api/v1/vision/frame",
        data={"source": "tb3_1_picam"},
        files={"image": ("aruco.png", aruco_png_bytes(), "image/png")},
    )
    assert newer.status_code == 200

    lagging = client.get("/api/v1/vision/streams", params={"source": "tb3_1_picam"})
    assert lagging.status_code == 200
    source_lagging = lagging.json()["sources"][0]
    assert source_lagging["latest_frame_seq"] == 2
    assert source_lagging["latest_overlay_frame_seq"] == 1
    assert source_lagging["overlay_lag_frames"] == 1
    assert source_lagging["overlay_visual_state"] == "fresh"
    assert lagging.json()["summary"]["overlay_lag_count"] == 1
    assert lagging.json()["summary"]["synced_overlay_count"] == 0
    assert lagging.json()["summary"]["ros_publish_ready_count"] == 0
    assert lagging.json()["summary"]["ros_publish_payload_available_count"] == 0
    assert lagging.json()["summary"]["ros_publish_payload_blocked_count"] == 1
    assert lagging.json()["summary"]["ros_publish_status_counts"] == {"overlay_lag": 1}
    assert source_lagging["ros_publish_readiness"]["readiness_state"] == "overlay_lag"
    assert source_lagging["ros_publish_readiness"]["overlay_ready"] is False
    assert source_lagging["ros_publish_readiness"]["publish_payload_preview"]["payload_available"] is False
    assert lagging.json()["summary"]["evidence_event_publish_ready_count"] == 1


def test_vision_ros_topics_declares_safe_domain_bridge_handoff_matrix():
    main_module.store.reset()
    main_module.frame_store.reset()
    main_module.overlay_cache.reset()
    with main_module._overlay_images_lock:
        main_module._overlay_images.clear()

    response = client.get("/api/v1/vision/ros/topics")

    assert response.status_code == 200
    body = response.json()
    assert body["primary_stream_plane"] == "rosbridge"
    assert body["debug_only"] is True
    assert body["motion_command_allowed"] is False
    assert body["control_topics_published"] == []
    assert body["topic_exposure_policy"] == expected_ros_topic_exposure_policy()
    assert body["topic_exposure_policy"]["client_publish_allowed"] is False
    assert "/cmd_vel" in body["topic_exposure_policy"]["forbidden_topic_globs"]
    assert body["topic_exposure_summary"] == expected_topic_exposure_summary(
        ["global_cam_01", "tb3_1_picam", "tb3_2_picam"]
    )
    assert body["topic_exposure_summary"]["control_topic_allowed_count"] == 0
    assert body["topic_exposure_summary"]["rosbridge_exposes_all_topics"] is False
    assert body["topic_exposure_summary"]["policy_status"] == "safe"
    assert body["topic_exposure_summary"]["policy_violation_count"] == 0
    assert body["topic_exposure_summary"]["policy_violations"] == []
    assert body["image_ingest_qos"] == {
        "reliability": "BEST_EFFORT",
        "history": "KEEP_LAST",
        "depth": 1,
    }
    assert body["frame_drop_policy"]["cache"] == "latest_only"
    assert body["frame_drop_policy"]["drop_stale_frames"] is True
    assert body["overlay_publish_qos"] == expected_ros_overlay_publish_qos_policy()
    assert body["overlay_publish_policy"] == expected_ros_overlay_publish_policy()
    assert body["overlay_publish_policy"]["publish_control_topics"] is False
    assert body["overlay_publish_policy"]["http_handlers_may_publish"] is False
    assert body["evidence_event_publish_policy"] == expected_ros_evidence_event_publish_policy()
    assert body["evidence_event_publish_policy"]["publish_control_topics"] is False
    assert body["evidence_event_publish_policy"]["payload_contains_image_bytes"] is False
    assert body["runtime_policy"]["ros2_started_by_http_request"] is False
    assert body["runtime_policy"]["http_handlers_must_spin_ros2_executor"] is False
    assert body["ingest_readiness_summary"] == {
        "sources_total": 3,
        "contract_ready_count": 3,
        "missing_physical_topic_count": 0,
        "runtime_subscriber_active_count": 0,
        "status_counts": {"contract_ready": 3, "missing_physical_topic": 0},
    }
    assert body["publish_readiness_summary"]["sources_total"] == 3
    assert body["publish_readiness_summary"]["no_frame_count"] == 3
    assert body["publish_readiness_summary"]["overlay_ready_count"] == 0
    assert body["publish_readiness_summary"]["publish_payload_available_count"] == 0
    assert body["publish_readiness_summary"]["publish_payload_blocked_count"] == 3
    assert body["evidence_event_publish_readiness_summary"] == {
        "sources_total": 3,
        "publish_ready_count": 0,
        "no_event_count": 3,
    }
    assert "keep existing /mission" in body["migration_policy"]
    by_source = {item["source"]: item for item in body["sources"]}
    assert set(by_source) == {"global_cam_01", "tb3_1_picam", "tb3_2_picam"}
    assert by_source["tb3_1_picam"]["physical_input_topic"] == source_definition("tb3_1_picam").physical_input.topic
    assert by_source["tb3_1_picam"]["physical_input_message_type"] == source_definition("tb3_1_picam").physical_input.message_type
    assert by_source["tb3_1_picam"]["physical_input_content_type"] == source_definition("tb3_1_picam").physical_input.content_type
    assert by_source["tb3_1_picam"]["physical_input_transport"] == source_definition("tb3_1_picam").physical_input.preferred_transport
    assert by_source["tb3_1_picam"]["legacy_browser_topic"] == "/mission/tb3_1/camera/compressed"
    assert by_source["tb3_1_picam"]["legacy_browser_message_type"] == "sensor_msgs/msg/CompressedImage"
    assert by_source["tb3_1_picam"]["normalized_image_topic"] == (
        "/sf/vision/sources/tb3_1_picam/image/compressed"
    )
    assert by_source["tb3_1_picam"]["normalized_overlay_topic"] == (
        "/sf/vision/sources/tb3_1_picam/overlay/compressed"
    )
    assert by_source["tb3_1_picam"]["normalized_image_message_type"] == "sensor_msgs/msg/CompressedImage"
    assert by_source["tb3_1_picam"]["normalized_overlay_message_type"] == "sensor_msgs/msg/CompressedImage"
    assert by_source["tb3_1_picam"]["evidence_event_topic"] == "/sf/vision/events"
    assert by_source["tb3_1_picam"]["evidence_event_publish_policy"] == body[
        "evidence_event_publish_policy"
    ]
    assert by_source["tb3_1_picam"]["evidence_event_publish_policy"]["dedup_key"] == "event_id"
    assert by_source["tb3_1_picam"]["evidence_event_publish_readiness"] == {
        "event_available": False,
        "publish_ready": False,
        "topic": "/sf/vision/events",
        "message_type": "smartfactory_msgs/msg/VisionEvent or JSON bridge payload",
        "schema_version": None,
        "latest_event_id": None,
        "latest_event_kind": None,
        "latest_event_timestamp": None,
        "dedup_key": "event_id",
        "payload_contains_image_bytes": False,
        "policy": expected_ros_evidence_event_publish_policy(),
        "reason": "no VisionEvent is available for this source",
    }
    assert by_source["tb3_1_picam"]["topic_exposure"] == expected_source_topic_exposure("tb3_1_picam")
    assert by_source["tb3_1_picam"]["topic_exposure"]["client_publish_allowed"] is False
    assert by_source["tb3_1_picam"]["topic_exposure"]["control_topics_allowed"] == []
    assert by_source["tb3_1_picam"]["qos_profile"] == body["image_ingest_qos"]
    assert by_source["tb3_1_picam"]["frame_drop_policy"] == body["frame_drop_policy"]
    assert by_source["tb3_1_picam"]["overlay_publish_qos"] == body["overlay_publish_qos"]
    assert by_source["tb3_1_picam"]["overlay_publish_policy"] == body["overlay_publish_policy"]
    assert by_source["tb3_1_picam"]["ingest_readiness"] == expected_ros_ingest_readiness("tb3_1_picam")
    assert by_source["tb3_1_picam"]["publish_readiness"]["readiness_state"] == "no_frame"
    assert by_source["tb3_1_picam"]["publish_readiness"]["overlay_ready"] is False
    assert by_source["tb3_1_picam"]["publish_readiness"]["runtime_plan"] == (
        expected_ros_publish_runtime_plan("tb3_1_picam")
    )
    assert by_source["tb3_1_picam"]["publish_readiness"]["runtime_plan"]["control_publish_allowed"] is False
    assert by_source["global_cam_01"]["legacy_browser_topic"] is None
    assert by_source["global_cam_01"]["legacy_browser_message_type"] is None
    assert by_source["global_cam_01"]["topic_exposure"] == expected_source_topic_exposure("global_cam_01")
    assert "/mission" not in " ".join(by_source["global_cam_01"]["topic_exposure"]["allowed_browser_topics"])
    assert all(item["ingest_status"] == "planned" for item in body["sources"])
    assert all(item["overlay_publish_status"] == "planned" for item in body["sources"])




def test_ros_ingest_readiness_marks_missing_physical_topic_without_starting_ros2():
    readiness = main_module._ros_ingest_readiness("tb3_1_picam", None)

    assert readiness["readiness_state"] == "missing_physical_topic"
    assert readiness["physical_input_topic_configured"] is False
    assert readiness["runtime_subscriber_active"] is False
    assert readiness["http_debug_ingest_path"] == "/api/v1/vision/frame"
    assert readiness["required_qos_profile"] == {
        "reliability": "BEST_EFFORT",
        "history": "KEEP_LAST",
        "depth": 1,
    }
    assert readiness == expected_ros_ingest_readiness("tb3_1_picam", topic_configured=False)
    assert readiness["runtime_plan"]["spin_location"] == "background_thread"
    assert readiness["runtime_plan"]["http_handler_role"] == "read_latest_state_only_never_spin_ros2"


def test_vision_ros_topics_can_filter_one_source_and_rejects_unknown_source():
    main_module.store.reset()
    main_module.frame_store.reset()
    main_module.overlay_cache.reset()
    with main_module._overlay_images_lock:
        main_module._overlay_images.clear()

    response = client.get("/api/v1/vision/ros/topics", params={"source": "tb3_2_picam"})

    assert response.status_code == 200
    body = response.json()
    assert body["requested_source"] == "tb3_2_picam"
    assert body["ingest_readiness_summary"]["sources_total"] == 1
    assert body["ingest_readiness_summary"]["contract_ready_count"] == 1
    assert body["publish_readiness_summary"]["sources_total"] == 1
    assert body["publish_readiness_summary"]["no_frame_count"] == 1
    assert body["publish_readiness_summary"]["publish_payload_available_count"] == 0
    assert body["publish_readiness_summary"]["publish_payload_blocked_count"] == 1
    assert body["evidence_event_publish_readiness_summary"] == {
        "sources_total": 1,
        "publish_ready_count": 0,
        "no_event_count": 1,
    }
    assert [item["source"] for item in body["sources"]] == ["tb3_2_picam"]
    assert body["sources"][0]["legacy_browser_topic"] == "/mission/tb3_2/camera/compressed"
    assert body["topic_exposure_policy"] == expected_ros_topic_exposure_policy()
    assert body["topic_exposure_summary"] == expected_topic_exposure_summary(["tb3_2_picam"])
    assert body["sources"][0]["topic_exposure"] == expected_source_topic_exposure("tb3_2_picam")
    assert body["control_topics_published"] == []
    assert body["motion_command_allowed"] is False

    bad = client.get("/api/v1/vision/ros/topics", params={"source": "bad_cam"})
    assert bad.status_code == 400
    assert bad.json()["error"]["code"] == "BAD_REQUEST"


def test_vision_ros_topics_reports_publish_readiness_transitions():
    main_module.store.reset()
    main_module.source_health.reset()
    main_module.frame_store.reset()
    main_module.overlay_cache.reset()
    with main_module._overlay_images_lock:
        main_module._overlay_images.clear()

    ingest = client.post(
        "/api/v1/vision/frame",
        data={"source": "tb3_1_picam"},
        files={"image": ("aruco.png", aruco_png_bytes(), "image/png")},
    )
    assert ingest.status_code == 200

    before_tick = client.get("/api/v1/vision/ros/topics")
    assert before_tick.status_code == 200
    source_before = {item["source"]: item for item in before_tick.json()["sources"]}["tb3_1_picam"]
    assert source_before["publish_readiness"]["readiness_state"] == "no_overlay"
    assert source_before["publish_readiness"]["latest_frame_seq"] == 1
    assert source_before["publish_readiness"]["latest_overlay_frame_seq"] is None
    assert source_before["publish_readiness"]["publish_payload_preview"]["payload_available"] is False

    tick = client.post("/api/v1/vision/worker/tick", json={"source": "tb3_1_picam"})
    assert tick.status_code == 200

    ready = client.get("/api/v1/vision/ros/topics")
    assert ready.status_code == 200
    ready_body = ready.json()
    source_ready = {item["source"]: item for item in ready_body["sources"]}["tb3_1_picam"]
    assert source_ready["publish_readiness"]["readiness_state"] == "ready_fresh"
    assert source_ready["publish_readiness"]["overlay_ready"] is True
    assert source_ready["publish_readiness"]["latest_frame_seq"] == 1
    assert source_ready["publish_readiness"]["latest_overlay_frame_seq"] == 1
    assert source_ready["publish_readiness"]["publish_payload_preview"]["payload_available"] is True
    assert source_ready["publish_readiness"]["publish_payload_preview"]["topic"] == (
        "/sf/vision/sources/tb3_1_picam/overlay/compressed"
    )
    assert source_ready["publish_readiness"]["runtime_plan"] == (
        expected_ros_publish_runtime_plan("tb3_1_picam")
    )
    assert ready_body["publish_readiness_summary"]["overlay_ready_count"] == 1
    assert ready_body["publish_readiness_summary"]["publish_payload_available_count"] == 1
    assert ready_body["publish_readiness_summary"]["publish_payload_blocked_count"] == 2
    assert ready_body["evidence_event_publish_readiness_summary"]["publish_ready_count"] == 1
    assert source_ready["evidence_event_publish_readiness"]["publish_ready"] is True
    assert source_ready["evidence_event_publish_readiness"]["latest_event_kind"] == "CONFIRMED"
    assert source_ready["evidence_event_publish_readiness"]["schema_version"] == "vision-event.v1"

    newer_frame = client.post(
        "/api/v1/vision/frame",
        data={"source": "tb3_1_picam"},
        files={"image": ("aruco.png", aruco_png_bytes(), "image/png")},
    )
    assert newer_frame.status_code == 200

    lagging = client.get("/api/v1/vision/ros/topics")
    assert lagging.status_code == 200
    lagging_body = lagging.json()
    source_lagging = {item["source"]: item for item in lagging_body["sources"]}["tb3_1_picam"]
    assert source_lagging["publish_readiness"]["readiness_state"] == "overlay_lag"
    assert source_lagging["publish_readiness"]["overlay_ready"] is False
    assert source_lagging["publish_readiness"]["latest_frame_seq"] == 2
    assert source_lagging["publish_readiness"]["latest_overlay_frame_seq"] == 1
    assert source_lagging["publish_readiness"]["publish_payload_preview"]["payload_available"] is False
    assert source_lagging["publish_readiness"]["runtime_plan"]["lag_behavior"] == (
        "do_not_publish_lagging_overlay"
    )
    assert lagging_body["publish_readiness_summary"]["overlay_lag_count"] == 1
    assert lagging_body["publish_readiness_summary"]["publish_payload_available_count"] == 0




def test_worker_tick_includes_pretrained_model_candidates_for_ros_overlay(monkeypatch):
    main_module.store.reset()
    main_module.source_health.reset()
    main_module.metrics.reset()
    main_module.frame_store.reset()
    main_module.overlay_cache.reset()
    with main_module._overlay_images_lock:
        main_module._overlay_images.clear()
    main_module._parse_vision_model_class_map.cache_clear()

    settings = get_settings()
    monkeypatch.setattr(settings, "vision_model_worker_enabled", True)
    monkeypatch.setattr(settings, "vision_model_path", "yolov8n.pt")
    monkeypatch.setattr(settings, "vision_model_task", "detect")
    monkeypatch.setattr(settings, "vision_model_class_map_json", '{"bottle":"box","person":"person"}')
    monkeypatch.setattr(settings, "vision_model_unmapped_class", "unknown")

    class FakePretrainedModel:
        detector_name = "fake-yolov8n"

        def detect(self, image):
            assert image.shape[:2] == (160, 200)
            return (
                DetectionBox(
                    class_name="bottle",
                    bbox_xyxy=(20.0, 30.0, 80.0, 120.0),
                    confidence=0.88,
                    detector=self.detector_name,
                ),
            )

    monkeypatch.setattr(main_module, "_get_lift_roi_segmenter", lambda **_: FakePretrainedModel())

    ingest = client.post(
        "/api/v1/vision/frame",
        data={"source": "tb3_1_picam"},
        files={"image": ("frame.png", blank_png_bytes(width=200, height=160), "image/png")},
    )
    assert ingest.status_code == 200

    tick = client.post("/api/v1/vision/worker/tick", json={"source": "tb3_1_picam"})

    assert tick.status_code == 200
    body = tick.json()
    assert body["summary"]["event_count_total"] == 1
    assert body["results"][0]["overlay"]["event_count"] == 1

    latest = client.get("/api/v1/detections/latest", params={"source": "tb3_1_picam", "limit": 1})
    event = latest.json()["events"][0]
    assert event["event_kind"] == "CANDIDATE"
    assert event["class_name"] == "box"
    assert event["wms_hint"] == "ITEM_CANDIDATE"
    assert event["metadata"]["model"] == "fake-yolov8n"

    ros = client.get("/api/v1/vision/ros/topics", params={"source": "tb3_1_picam"})
    assert ros.status_code == 200
    source = ros.json()["sources"][0]
    assert source["publish_readiness"]["readiness_state"] == "ready_fresh"
    assert source["publish_readiness"]["publish_payload_preview"]["topic"] == (
        "/sf/vision/sources/tb3_1_picam/overlay/compressed"
    )
    assert source["evidence_event_publish_readiness"]["publish_ready"] is True


def test_lane_b_robot_free_e2e_surfaces_stay_consistent_across_stream_debug_ros_and_metrics():
    main_module.store.reset()
    main_module.source_health.reset()
    main_module.metrics.reset()
    main_module.frame_store.reset()
    main_module.overlay_cache.reset()
    with main_module._overlay_images_lock:
        main_module._overlay_images.clear()

    source = "tb3_1_picam"

    initial_stream = client.get("/api/v1/vision/streams", params={"source": source})
    assert initial_stream.status_code == 200
    assert initial_stream.json()["debug_only"] is True
    assert initial_stream.json()["motion_command_allowed"] is False
    assert initial_stream.json()["control_topics_published"] == []
    assert initial_stream.json()["runtime_policy"]["ros2_started_by_http_request"] is False
    assert initial_stream.json()["summary"]["ros_ingest_contract_ready_count"] == 1
    assert initial_stream.json()["summary"]["ros_publish_status_counts"] == {"no_frame": 1}

    ingest = client.post(
        "/api/v1/vision/frame",
        data={"source": source},
        files={"image": ("aruco.png", aruco_png_bytes(), "image/png")},
    )
    assert ingest.status_code == 200
    assert ingest.json()["processed"] is False
    assert ingest.json()["ingest_context"]["ros_callback_compatible"] is True
    assert ingest.json()["frame"]["frame_seq"] == 1

    pending = client.get("/api/v1/vision/worker/status", params={"source": source})
    assert pending.status_code == 200
    assert pending.json()["summary"]["pending_count"] == 1
    assert pending.json()["summary"]["status_counts"]["processed"] == 1

    before_tick = client.get("/api/v1/vision/streams", params={"source": source})
    assert before_tick.status_code == 200
    before_body = before_tick.json()
    before_source = before_body["sources"][0]
    assert before_body["summary"]["with_frame_count"] == 1
    assert before_body["summary"]["with_overlay_count"] == 0
    assert before_body["summary"]["ros_publish_status_counts"] == {"no_overlay": 1}
    assert before_source["latest_frame_seq"] == 1
    assert before_source["latest_overlay_frame_seq"] is None
    assert before_source["ros_publish_readiness"]["readiness_state"] == "no_overlay"
    assert before_source["evidence_event_publish_readiness"]["publish_ready"] is False

    tick = client.post("/api/v1/vision/worker/tick", json={"source": source})
    assert tick.status_code == 200
    assert tick.json()["summary"]["status_counts"]["processed"] == 1
    assert tick.json()["summary"]["event_count_total"] == 1
    assert tick.json()["results"][0]["overlay"]["frame_seq"] == 1

    latest_events = client.get("/api/v1/detections/latest", params={"source": source, "limit": 1})
    assert latest_events.status_code == 200
    assert latest_events.json()["events"][0]["schema_version"] == "vision-event.v1"
    assert latest_events.json()["events"][0]["source"] == source

    frame_image = client.get("/api/v1/vision/frame/latest/image", params={"source": source})
    overlay = client.get("/api/v1/vision/overlay/latest", params={"source": source})
    overlay_image = client.get("/api/v1/vision/overlay/latest/image", params={"source": source})
    assert frame_image.status_code == 200
    assert frame_image.headers["content-type"] == "image/png"
    assert frame_image.content.startswith(b"\x89PNG")
    assert overlay.status_code == 200
    assert overlay.json()["overlay"]["frame_seq"] == 1
    assert overlay.json()["overlay"]["event_count"] == 1
    assert overlay_image.status_code == 200
    assert overlay_image.content.startswith(b"\xff\xd8")

    stream = client.get("/api/v1/vision/streams", params={"source": source})
    debug = client.get("/api/v1/vision/debug/sources", params={"source": source})
    ros = client.get("/api/v1/vision/ros/topics", params={"source": source})
    metrics_response = client.get("/api/v1/metrics", params={"source": source})
    assert stream.status_code == debug.status_code == ros.status_code == metrics_response.status_code == 200

    stream_body = stream.json()
    debug_body = debug.json()
    ros_body = ros.json()
    metrics_body = metrics_response.json()
    stream_source = stream_body["sources"][0]
    debug_source = debug_body["sources"][0]
    ros_source = ros_body["sources"][0]

    assert stream_body["primary_stream_plane"] == ros_body["primary_stream_plane"] == "rosbridge"
    assert stream_body["debug_only"] is True
    assert ros_body["debug_only"] is True
    assert stream_body["motion_command_allowed"] is False
    assert ros_body["motion_command_allowed"] is False
    assert stream_body["control_topics_published"] == ros_body["control_topics_published"] == []
    assert stream_body["runtime_policy"] == ros_body["runtime_policy"]
    assert stream_body["topic_exposure_summary"] == ros_body["topic_exposure_summary"]
    assert debug_body["topic_exposure_summary"] == ros_body["topic_exposure_summary"]

    assert stream_source["latest_frame_seq"] == debug_source["latest_frame"]["frame_seq"] == 1
    assert stream_source["latest_overlay_frame_seq"] == debug_source["latest_overlay"]["frame_seq"] == 1
    assert stream_source["overlay_lag_frames"] == debug_source["overlay_lag_frames"] == 0
    assert stream_source["ros_ingest_readiness"] == debug_source["ros_ingest_readiness"]
    assert stream_source["ros_ingest_readiness"] == ros_source["ingest_readiness"]
    def without_frame_age(readiness: dict) -> dict:
        return {key: value for key, value in readiness.items() if key != "frame_age_s"}

    assert without_frame_age(stream_source["ros_publish_readiness"]) == without_frame_age(
        debug_source["ros_publish_readiness"]
    )
    assert without_frame_age(stream_source["ros_publish_readiness"]) == without_frame_age(
        ros_source["publish_readiness"]
    )
    assert stream_source["evidence_event_publish_readiness"] == debug_source[
        "evidence_event_publish_readiness"
    ]
    assert stream_source["evidence_event_publish_readiness"] == ros_source[
        "evidence_event_publish_readiness"
    ]

    assert stream_body["summary"]["ros_publish_payload_available_count"] == 1
    assert debug_body["summary"]["ros_publish_payload_available_count"] == 1
    assert ros_body["publish_readiness_summary"]["publish_payload_available_count"] == 1
    assert stream_body["summary"]["evidence_event_publish_ready_count"] == 1
    assert debug_body["summary"]["evidence_event_publish_ready_count"] == 1
    assert ros_body["evidence_event_publish_readiness_summary"]["publish_ready_count"] == 1
    assert metrics_body["metrics"]["worker"]["tick_total"] == {"processed": 1}
    assert metrics_body["frame_store"]["frame_seq_by_source"] == {source: 1}

    newer_frame = client.post(
        "/api/v1/vision/frame",
        data={"source": source},
        files={"image": ("aruco.png", aruco_png_bytes(), "image/png")},
    )
    assert newer_frame.status_code == 200
    assert newer_frame.json()["frame"]["frame_seq"] == 2

    lag_stream = client.get("/api/v1/vision/streams", params={"source": source})
    lag_debug = client.get("/api/v1/vision/debug/sources", params={"source": source})
    lag_ros = client.get("/api/v1/vision/ros/topics", params={"source": source})
    assert lag_stream.status_code == lag_debug.status_code == lag_ros.status_code == 200
    lag_stream_source = lag_stream.json()["sources"][0]
    lag_debug_source = lag_debug.json()["sources"][0]
    lag_ros_source = lag_ros.json()["sources"][0]
    assert lag_stream_source["latest_frame_seq"] == lag_debug_source["latest_frame"]["frame_seq"] == 2
    assert lag_stream_source["latest_overlay_frame_seq"] == lag_debug_source["latest_overlay"]["frame_seq"] == 1
    assert lag_stream_source["overlay_lag_frames"] == lag_debug_source["overlay_lag_frames"] == 1
    assert lag_stream_source["ros_publish_readiness"]["readiness_state"] == "overlay_lag"
    assert lag_debug_source["ros_publish_readiness"]["readiness_state"] == "overlay_lag"
    assert lag_ros_source["publish_readiness"]["readiness_state"] == "overlay_lag"
    assert lag_stream.json()["summary"]["ros_publish_payload_available_count"] == 0
    assert lag_debug.json()["summary"]["ros_publish_payload_available_count"] == 0
    assert lag_ros.json()["publish_readiness_summary"]["publish_payload_available_count"] == 0




def test_lane_b_multi_source_e2e_keeps_frame_overlay_event_and_metrics_isolated():
    main_module.store.reset()
    main_module.source_health.reset()
    main_module.metrics.reset()
    main_module.frame_store.reset()
    main_module.overlay_cache.reset()
    with main_module._overlay_images_lock:
        main_module._overlay_images.clear()

    processed_source = "tb3_1_picam"
    waiting_source = "tb3_2_picam"

    first = client.post(
        "/api/v1/vision/frame",
        data={"source": processed_source},
        files={"image": ("tb3_1.png", aruco_png_bytes(), "image/png")},
    )
    second = client.post(
        "/api/v1/vision/frame",
        data={"source": waiting_source},
        files={"image": ("tb3_2.png", aruco_png_bytes(), "image/png")},
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["frame"]["frame_seq"] == 1
    assert second.json()["frame"]["frame_seq"] == 1

    tick_one = client.post("/api/v1/vision/worker/tick", json={"source": processed_source})
    assert tick_one.status_code == 200
    assert tick_one.json()["summary"]["status_counts"]["processed"] == 1
    assert tick_one.json()["results"][0]["source"] == processed_source
    assert tick_one.json()["results"][0]["overlay"]["frame_seq"] == 1

    stream = client.get("/api/v1/vision/streams")
    debug = client.get("/api/v1/vision/debug/sources")
    ros = client.get("/api/v1/vision/ros/topics")
    assert stream.status_code == debug.status_code == ros.status_code == 200

    stream_body = stream.json()
    debug_body = debug.json()
    ros_body = ros.json()
    stream_by_source = {item["source"]: item for item in stream_body["sources"]}
    debug_by_source = {item["source"]: item for item in debug_body["sources"]}
    ros_by_source = {item["source"]: item for item in ros_body["sources"]}

    assert stream_body["summary"]["sources_total"] == 3
    assert stream_body["summary"]["with_frame_count"] == 2
    assert stream_body["summary"]["with_overlay_count"] == 1
    assert stream_body["summary"]["ros_publish_payload_available_count"] == 1
    assert stream_body["summary"]["ros_publish_payload_blocked_count"] == 2
    assert stream_body["summary"]["evidence_event_publish_ready_count"] == 1
    assert stream_body["summary"]["ros_publish_status_counts"] == {
        "no_frame": 1,
        "no_overlay": 1,
        "ready_fresh": 1,
    }
    assert debug_body["summary"]["with_frame_count"] == 2
    assert debug_body["summary"]["with_overlay_count"] == 1
    assert debug_body["summary"]["ros_publish_payload_available_count"] == 1
    assert debug_body["summary"]["evidence_event_publish_ready_count"] == 1
    assert ros_body["publish_readiness_summary"]["publish_payload_available_count"] == 1
    assert ros_body["publish_readiness_summary"]["publish_payload_blocked_count"] == 2
    assert ros_body["evidence_event_publish_readiness_summary"]["publish_ready_count"] == 1

    processed_stream = stream_by_source[processed_source]
    processed_debug = debug_by_source[processed_source]
    processed_ros = ros_by_source[processed_source]
    waiting_stream = stream_by_source[waiting_source]
    waiting_debug = debug_by_source[waiting_source]
    waiting_ros = ros_by_source[waiting_source]
    empty_stream = stream_by_source["global_cam_01"]

    assert processed_stream["latest_frame_seq"] == processed_debug["latest_frame"]["frame_seq"] == 1
    assert processed_stream["latest_overlay_frame_seq"] == processed_debug["latest_overlay"]["frame_seq"] == 1
    assert processed_stream["ros_publish_readiness"]["readiness_state"] == "ready_fresh"
    assert processed_debug["ros_publish_readiness"]["readiness_state"] == "ready_fresh"
    assert processed_ros["publish_readiness"]["readiness_state"] == "ready_fresh"
    assert processed_stream["evidence_event_publish_readiness"]["publish_ready"] is True
    assert processed_debug["evidence_event_publish_readiness"]["publish_ready"] is True
    assert processed_ros["evidence_event_publish_readiness"]["publish_ready"] is True

    assert waiting_stream["latest_frame_seq"] == waiting_debug["latest_frame"]["frame_seq"] == 1
    assert waiting_stream["latest_overlay_frame_seq"] is None
    assert waiting_debug["latest_overlay"] is None
    assert waiting_stream["ros_publish_readiness"]["readiness_state"] == "no_overlay"
    assert waiting_debug["ros_publish_readiness"]["readiness_state"] == "no_overlay"
    assert waiting_ros["publish_readiness"]["readiness_state"] == "no_overlay"
    assert waiting_stream["evidence_event_publish_readiness"]["publish_ready"] is False
    assert waiting_debug["evidence_event_publish_readiness"]["publish_ready"] is False
    assert waiting_ros["evidence_event_publish_readiness"]["publish_ready"] is False

    assert empty_stream["has_frame"] is False
    assert empty_stream["has_overlay"] is False
    assert empty_stream["ros_publish_readiness"]["readiness_state"] == "no_frame"
    assert empty_stream["evidence_event_publish_readiness"]["publish_ready"] is False

    processed_metrics = client.get("/api/v1/metrics", params={"source": processed_source})
    waiting_metrics = client.get("/api/v1/metrics", params={"source": waiting_source})
    assert processed_metrics.status_code == 200
    assert waiting_metrics.status_code == 200
    assert processed_metrics.json()["metrics"]["worker"]["tick_total"] == {"processed": 1}
    assert waiting_metrics.json()["metrics"]["worker"]["tick_total"] == {}
    assert processed_metrics.json()["frame_store"]["frame_seq_by_source"] == {processed_source: 1}
    assert waiting_metrics.json()["frame_store"]["frame_seq_by_source"] == {waiting_source: 1}

    tick_waiting = client.post("/api/v1/vision/worker/tick", json={"source": waiting_source})
    assert tick_waiting.status_code == 200
    assert tick_waiting.json()["summary"]["status_counts"]["processed"] == 1
    final_ros = client.get("/api/v1/vision/ros/topics")
    assert final_ros.status_code == 200
    assert final_ros.json()["publish_readiness_summary"]["publish_payload_available_count"] == 2
    assert final_ros.json()["evidence_event_publish_readiness_summary"]["publish_ready_count"] == 2


def test_lane_b_multi_source_latest_only_backpressure_drops_old_frames_per_source():
    main_module.store.reset()
    main_module.source_health.reset()
    main_module.metrics.reset()
    main_module.frame_store.reset()
    main_module.overlay_cache.reset()
    with main_module._overlay_images_lock:
        main_module._overlay_images.clear()

    first_source = "tb3_1_picam"
    second_source = "tb3_2_picam"

    for expected_seq in (1, 2, 3):
        response = client.post(
            "/api/v1/vision/frame",
            data={"source": first_source},
            files={"image": (f"{first_source}-{expected_seq}.png", aruco_png_bytes(), "image/png")},
        )
        assert response.status_code == 200
        assert response.json()["frame"]["frame_seq"] == expected_seq

    for expected_seq in (1, 2):
        response = client.post(
            "/api/v1/vision/frame",
            data={"source": second_source},
            files={"image": (f"{second_source}-{expected_seq}.png", aruco_png_bytes(), "image/png")},
        )
        assert response.status_code == 200
        assert response.json()["frame"]["frame_seq"] == expected_seq

    all_metrics_before = client.get("/api/v1/metrics")
    first_metrics_before = client.get("/api/v1/metrics", params={"source": first_source})
    second_metrics_before = client.get("/api/v1/metrics", params={"source": second_source})
    assert all_metrics_before.status_code == 200
    assert first_metrics_before.status_code == 200
    assert second_metrics_before.status_code == 200
    assert all_metrics_before.json()["frame_store"]["sources_with_frames"] == 2
    assert all_metrics_before.json()["frame_store"]["frame_seq_by_source"] == {
        first_source: 3,
        second_source: 2,
    }
    assert all_metrics_before.json()["frame_store"]["dropped_frames_by_source"] == {
        first_source: 2,
        second_source: 1,
    }
    assert all_metrics_before.json()["frame_store"]["dropped_frames_total"] == 3
    assert first_metrics_before.json()["frame_store"]["frame_seq_by_source"] == {first_source: 3}
    assert first_metrics_before.json()["frame_store"]["dropped_frames_by_source"] == {
        first_source: 2
    }
    assert first_metrics_before.json()["frame_store"]["dropped_frames_total"] == 2
    assert second_metrics_before.json()["frame_store"]["frame_seq_by_source"] == {second_source: 2}
    assert second_metrics_before.json()["frame_store"]["dropped_frames_by_source"] == {
        second_source: 1
    }
    assert second_metrics_before.json()["frame_store"]["dropped_frames_total"] == 1

    before_tick = client.get("/api/v1/vision/streams")
    assert before_tick.status_code == 200
    before_body = before_tick.json()
    assert before_body["summary"]["with_frame_count"] == 2
    assert before_body["summary"]["with_overlay_count"] == 0
    assert before_body["summary"]["ros_publish_status_counts"] == {
        "no_frame": 1,
        "no_overlay": 2,
    }
    assert before_body["summary"]["ros_publish_payload_available_count"] == 0

    tick = client.post("/api/v1/vision/worker/tick", json={})
    assert tick.status_code == 200
    tick_body = tick.json()
    assert tick_body["summary"]["status_counts"]["processed"] == 2
    assert tick_body["summary"]["status_counts"]["no_frame"] == 1
    assert tick_body["summary"]["event_count_total"] == 2
    tick_by_source = {item["source"]: item for item in tick_body["results"]}
    assert tick_by_source[first_source]["frame_seq"] == 3
    assert tick_by_source[first_source]["overlay"]["frame_seq"] == 3
    assert tick_by_source[second_source]["frame_seq"] == 2
    assert tick_by_source[second_source]["overlay"]["frame_seq"] == 2
    assert tick_by_source["global_cam_01"]["status"] == "no_frame"

    stream = client.get("/api/v1/vision/streams")
    debug = client.get("/api/v1/vision/debug/sources")
    ros = client.get("/api/v1/vision/ros/topics")
    assert stream.status_code == debug.status_code == ros.status_code == 200
    stream_body = stream.json()
    debug_body = debug.json()
    ros_body = ros.json()
    stream_by_source = {item["source"]: item for item in stream_body["sources"]}
    debug_by_source = {item["source"]: item for item in debug_body["sources"]}
    ros_by_source = {item["source"]: item for item in ros_body["sources"]}

    assert stream_body["summary"]["ros_publish_payload_available_count"] == 2
    assert stream_body["summary"]["evidence_event_publish_ready_count"] == 2
    assert debug_body["summary"]["ros_publish_payload_available_count"] == 2
    assert debug_body["summary"]["evidence_event_publish_ready_count"] == 2
    assert ros_body["publish_readiness_summary"]["publish_payload_available_count"] == 2
    assert ros_body["evidence_event_publish_readiness_summary"]["publish_ready_count"] == 2
    assert stream_body["summary"]["ros_publish_status_counts"] == {
        "no_frame": 1,
        "ready_fresh": 2,
    }

    for source, expected_seq in ((first_source, 3), (second_source, 2)):
        assert stream_by_source[source]["latest_frame_seq"] == expected_seq
        assert stream_by_source[source]["latest_overlay_frame_seq"] == expected_seq
        assert debug_by_source[source]["latest_frame"]["frame_seq"] == expected_seq
        assert debug_by_source[source]["latest_overlay"]["frame_seq"] == expected_seq
        assert stream_by_source[source]["ros_publish_readiness"]["readiness_state"] == "ready_fresh"
        assert debug_by_source[source]["ros_publish_readiness"]["readiness_state"] == "ready_fresh"
        assert ros_by_source[source]["publish_readiness"]["readiness_state"] == "ready_fresh"
        assert stream_by_source[source]["evidence_event_publish_readiness"]["publish_ready"] is True
        assert debug_by_source[source]["evidence_event_publish_readiness"]["publish_ready"] is True
        assert ros_by_source[source]["evidence_event_publish_readiness"]["publish_ready"] is True

    assert stream_by_source["global_cam_01"]["ros_publish_readiness"]["readiness_state"] == "no_frame"

    newer_first = client.post(
        "/api/v1/vision/frame",
        data={"source": first_source},
        files={"image": ("tb3_1-newer.png", aruco_png_bytes(), "image/png")},
    )
    assert newer_first.status_code == 200
    assert newer_first.json()["frame"]["frame_seq"] == 4

    lag_stream = client.get("/api/v1/vision/streams")
    lag_metrics = client.get("/api/v1/metrics", params={"source": first_source})
    assert lag_stream.status_code == 200
    assert lag_metrics.status_code == 200
    lag_body = lag_stream.json()
    lag_by_source = {item["source"]: item for item in lag_body["sources"]}
    assert lag_metrics.json()["frame_store"]["frame_seq_by_source"] == {first_source: 4}
    assert lag_metrics.json()["frame_store"]["dropped_frames_by_source"] == {first_source: 3}
    assert lag_metrics.json()["frame_store"]["dropped_frames_total"] == 3
    assert lag_by_source[first_source]["latest_frame_seq"] == 4
    assert lag_by_source[first_source]["latest_overlay_frame_seq"] == 3
    assert lag_by_source[first_source]["overlay_lag_frames"] == 1
    assert lag_by_source[first_source]["ros_publish_readiness"]["readiness_state"] == "overlay_lag"
    assert lag_by_source[first_source]["ros_publish_readiness"]["publish_payload_preview"][
        "payload_available"
    ] is False
    assert lag_by_source[second_source]["latest_frame_seq"] == 2
    assert lag_by_source[second_source]["latest_overlay_frame_seq"] == 2
    assert lag_by_source[second_source]["ros_publish_readiness"]["readiness_state"] == "ready_fresh"
    assert lag_body["summary"]["ros_publish_payload_available_count"] == 1
    assert lag_body["summary"]["ros_publish_payload_blocked_count"] == 2
    assert lag_body["summary"]["ros_publish_status_counts"] == {
        "no_frame": 1,
        "overlay_lag": 1,
        "ready_fresh": 1,
    }


def test_lane_b_worker_tick_is_idempotent_and_does_not_duplicate_evidence_events():
    main_module.store.reset()
    main_module.source_health.reset()
    main_module.metrics.reset()
    main_module.frame_store.reset()
    main_module.overlay_cache.reset()
    with main_module._overlay_images_lock:
        main_module._overlay_images.clear()

    sources = ("tb3_1_picam", "tb3_2_picam")
    for source in sources:
        response = client.post(
            "/api/v1/vision/frame",
            data={"source": source},
            files={"image": (f"{source}.png", aruco_png_bytes(), "image/png")},
        )
        assert response.status_code == 200
        assert response.json()["frame"]["frame_seq"] == 1

    first_tick = client.post("/api/v1/vision/worker/tick", json={})
    assert first_tick.status_code == 200
    first_body = first_tick.json()
    assert first_body["summary"]["status_counts"]["processed"] == 2
    assert first_body["summary"]["status_counts"]["no_frame"] == 1
    assert first_body["summary"]["event_count_total"] == 2
    assert first_body["summary"]["new_event_count_total"] == 2
    assert first_body["summary"]["reused_event_count_total"] == 0
    first_by_source = {item["source"]: item for item in first_body["results"]}
    for source in sources:
        assert first_by_source[source]["status"] == "processed"
        assert first_by_source[source]["evidence_action"] == "created"
        assert first_by_source[source]["new_event_count"] == 1
        assert first_by_source[source]["overlay"]["frame_seq"] == 1

    events_after_first = client.get("/api/v1/detections/latest", params={"limit": 10})
    metrics_after_first = client.get("/api/v1/metrics")
    assert events_after_first.status_code == 200
    assert metrics_after_first.status_code == 200
    first_events = events_after_first.json()["events"]
    first_event_ids = {event["event_id"] for event in first_events}
    assert len(first_events) == 2
    assert {event["source"] for event in first_events} == set(sources)
    assert metrics_after_first.json()["event_store"]["current_size"] == 2

    second_tick = client.post("/api/v1/vision/worker/tick", json={})
    assert second_tick.status_code == 200
    second_body = second_tick.json()
    assert second_body["summary"]["status_counts"]["processed"] == 0
    assert second_body["summary"]["status_counts"]["skipped"] == 2
    assert second_body["summary"]["status_counts"]["no_frame"] == 1
    # event_count_total still describes the events represented by the tick
    # response, while new_event_count_total is the idempotency guard.
    assert second_body["summary"]["event_count_total"] == 2
    assert second_body["summary"]["new_event_count_total"] == 0
    assert second_body["summary"]["reused_event_count_total"] == 2
    second_by_source = {item["source"]: item for item in second_body["results"]}
    for source in sources:
        assert second_by_source[source]["status"] == "skipped"
        assert second_by_source[source]["evidence_action"] == "reused"
        assert second_by_source[source]["new_event_count"] == 0
        assert second_by_source[source]["overlay"]["frame_seq"] == 1

    events_after_second = client.get("/api/v1/detections/latest", params={"limit": 10})
    metrics_after_second = client.get("/api/v1/metrics")
    stream_after_second = client.get("/api/v1/vision/streams")
    ros_after_second = client.get("/api/v1/vision/ros/topics")
    assert events_after_second.status_code == 200
    assert metrics_after_second.status_code == 200
    assert stream_after_second.status_code == 200
    assert ros_after_second.status_code == 200
    second_events = events_after_second.json()["events"]
    assert {event["event_id"] for event in second_events} == first_event_ids
    assert metrics_after_second.json()["event_store"]["current_size"] == 2
    assert metrics_after_second.json()["metrics"]["worker"]["tick_total"] == {
        "no_frame": 2,
        "processed": 2,
        "skipped": 2,
    }
    assert stream_after_second.json()["summary"]["ros_publish_payload_available_count"] == 2
    assert stream_after_second.json()["summary"]["evidence_event_publish_ready_count"] == 2
    assert ros_after_second.json()["publish_readiness_summary"][
        "publish_payload_available_count"
    ] == 2
    assert ros_after_second.json()["evidence_event_publish_readiness_summary"][
        "publish_ready_count"
    ] == 2


def test_frame_ingest_stores_raw_frame_without_processing_then_worker_tick_processes():
    main_module.source_health.reset()
    main_module.frame_store.reset()
    main_module.overlay_cache.reset()
    with main_module._overlay_images_lock:
        main_module._overlay_images.clear()

    ingest = client.post(
        "/api/v1/vision/frame",
        data={"source": "tb3_1_picam"},
        files={"image": ("aruco.png", aruco_png_bytes(), "image/png")},
    )

    assert ingest.status_code == 200
    body = ingest.json()
    assert body["source"] == "tb3_1_picam"
    assert body["processed"] is False
    assert body["overlay"] is None
    assert body["ingest_context"] == {
        "transport": "http_debug",
        "topic": None,
        "stored_in_latest_frame_cache": True,
        "processed_inline": False,
        "source_health_updated": True,
        "ros_callback_compatible": True,
    }
    assert body["worker_tick_path"] == "/api/v1/vision/worker/tick"
    assert body["frame"]["frame_seq"] == 1
    assert body["frame"]["content_type"] == "image/png"
    assert body["frame"]["size_bytes"] > 0

    overlay_before_tick = client.get(
        "/api/v1/vision/overlay/latest",
        params={"source": "tb3_1_picam"},
    )
    assert overlay_before_tick.status_code == 404

    tick = client.post(
        "/api/v1/vision/worker/tick",
        json={"source": "tb3_1_picam"},
    )
    assert tick.status_code == 200
    tick_result = tick.json()["results"][0]
    assert tick_result["status"] == "processed"
    assert tick_result["frame_seq"] == 1
    assert tick_result["event_count"] == 1
    assert tick_result["overlay"]["frame_seq"] == 1


def test_frame_process_ingests_and_updates_overlay_in_one_request():
    main_module.store.reset()
    main_module.source_health.reset()
    main_module.frame_store.reset()
    main_module.overlay_cache.reset()
    with main_module._overlay_images_lock:
        main_module._overlay_images.clear()

    response = client.post(
        "/api/v1/vision/frame/process",
        data={"source": "tb3_1_picam", "force": "true", "stale": "false"},
        files={"image": ("aruco.png", aruco_png_bytes(), "image/png")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "tb3_1_picam"
    assert body["processed"] is True
    assert body["status"] == "processed"
    assert body["frame_seq"] == 1
    assert body["frame"]["frame_seq"] == 1
    assert body["overlay"]["frame_seq"] == 1
    assert body["event_count"] >= 1
    assert body["new_event_count"] == body["event_count"]
    assert body["ingest_context"] == {
        "transport": "http_debug",
        "topic": None,
        "stored_in_latest_frame_cache": True,
        "processed_inline": True,
        "source_health_updated": True,
        "ros_callback_compatible": True,
    }

    latest_overlay = client.get(
        "/api/v1/vision/overlay/latest",
        params={"source": "tb3_1_picam"},
    )
    assert latest_overlay.status_code == 200
    assert latest_overlay.json()["overlay"]["frame_seq"] == 1

    latest_image = client.get(
        "/api/v1/vision/overlay/latest/image",
        params={"source": "tb3_1_picam"},
    )
    assert latest_image.status_code == 200
    assert latest_image.headers["content-type"] == "image/jpeg"
    assert latest_image.content.startswith(b"\xff\xd8")


def test_store_latest_frame_from_bytes_is_ros_callback_ready_without_processing():
    main_module.source_health.reset()
    main_module.frame_store.reset()
    main_module.overlay_cache.reset()

    frame = main_module._store_latest_frame_from_bytes(
        source="tb3_2_picam",
        payload=aruco_png_bytes(),
        content_type="image/png",
    )

    assert frame.source == "tb3_2_picam"
    assert frame.frame_seq == 1
    assert frame.content_type == "image/png"
    assert main_module.overlay_cache.latest("tb3_2_picam") is None
    health = main_module.source_health.snapshot(
        "tb3_2_picam",
        now=main_module._now_dt(),
        stale_after_s=get_settings().source_stale_after_s,
        offline_after_s=get_settings().source_offline_after_s,
    )
    assert health.frame_count == 1
    assert health.event_count == 0

    with pytest.raises(ValueError, match="decodable image"):
        main_module._store_latest_frame_from_bytes(
            source="tb3_2_picam",
            payload=b"not-an-image",
            content_type="text/plain",
        )


def test_frame_ingest_rejects_bad_image_and_unknown_source():
    bad_image = client.post(
        "/api/v1/vision/frame",
        data={"source": "tb3_2_picam"},
        files={"image": ("bad.txt", b"not-an-image", "text/plain")},
    )
    bad_source = client.post(
        "/api/v1/vision/frame",
        data={"source": "bad_cam"},
        files={"image": ("aruco.png", aruco_png_bytes(), "image/png")},
    )

    assert bad_image.status_code == 400
    assert bad_image.json()["error"]["code"] == "BAD_REQUEST"
    assert bad_source.status_code == 400
    assert bad_source.json()["error"]["code"] == "BAD_REQUEST"


def test_latest_frame_metadata_and_image_follow_synthetic_ingest():
    main_module.source_health.reset()
    main_module.frame_store.reset()
    main_module.overlay_cache.reset()
    with main_module._overlay_images_lock:
        main_module._overlay_images.clear()

    ingest = client.post(
        "/api/v1/vision/synthetic/frame",
        json={"source": "tb3_1_picam", "marker_id": 7},
    )
    assert ingest.status_code == 200

    metadata_response = client.get(
        "/api/v1/vision/frame/latest",
        params={"source": "tb3_1_picam"},
    )
    assert metadata_response.status_code == 200
    frame = metadata_response.json()["frame"]
    assert frame["source"] == "tb3_1_picam"
    assert frame["frame_seq"] == 1
    assert frame["content_type"] == "image/jpeg"
    assert frame["size_bytes"] > 0
    assert frame["image"]["width"] > 0
    assert frame["image"]["height"] > 0

    image_response = client.get(
        "/api/v1/vision/frame/latest/image",
        params={"source": "tb3_1_picam"},
    )
    assert image_response.status_code == 200
    assert image_response.headers["content-type"] == "image/jpeg"
    assert image_response.content.startswith(b"\xff\xd8")


def test_latest_frame_returns_404_before_any_frame():
    main_module.frame_store.reset()

    metadata_response = client.get(
        "/api/v1/vision/frame/latest",
        params={"source": "tb3_2_picam"},
    )
    image_response = client.get(
        "/api/v1/vision/frame/latest/image",
        params={"source": "tb3_2_picam"},
    )

    assert metadata_response.status_code == 404
    assert metadata_response.json()["error"]["code"] == "NOT_FOUND"
    assert image_response.status_code == 404
    assert image_response.json()["error"]["code"] == "NOT_FOUND"


def test_overlay_publish_payload_preview_only_allows_synced_overlay():
    main_module.source_health.reset()
    main_module.frame_store.reset()
    main_module.overlay_cache.reset()
    with main_module._overlay_images_lock:
        main_module._overlay_images.clear()

    no_frame = main_module._overlay_publish_payload_preview_for_source("tb3_1_picam")
    assert no_frame["payload_available"] is False
    assert no_frame["topic"] == "/sf/vision/sources/tb3_1_picam/overlay/compressed"
    assert no_frame["message_type"] == "sensor_msgs/msg/CompressedImage"
    assert no_frame["size_bytes"] == 0

    ingest = client.post(
        "/api/v1/vision/frame",
        data={"source": "tb3_1_picam"},
        files={"image": ("aruco.png", aruco_png_bytes(), "image/png")},
    )
    assert ingest.status_code == 200
    no_overlay = main_module._overlay_publish_payload_preview_for_source("tb3_1_picam")
    assert no_overlay["payload_available"] is False
    assert no_overlay["frame_seq"] == 1
    assert no_overlay["size_bytes"] == 0

    tick = client.post("/api/v1/vision/worker/tick", json={"source": "tb3_1_picam"})
    assert tick.status_code == 200
    ready = main_module._overlay_publish_payload_preview_for_source("tb3_1_picam")
    assert ready["payload_available"] is True
    assert ready["frame_seq"] == 1
    assert ready["content_type"] == "image/jpeg"
    assert ready["size_bytes"] > 0

    newer = client.post(
        "/api/v1/vision/frame",
        data={"source": "tb3_1_picam"},
        files={"image": ("aruco.png", aruco_png_bytes(), "image/png")},
    )
    assert newer.status_code == 200
    lagging = main_module._overlay_publish_payload_preview_for_source("tb3_1_picam")
    assert lagging["payload_available"] is False
    assert lagging["frame_seq"] == 1
    assert lagging["size_bytes"] > 0
    assert "does not match" in lagging["reason"]


def test_debug_overlay_mjpeg_rejects_invalid_max_fps_before_streaming():
    too_low = client.get("/api/v1/vision/stream/tb3_1_picam.mjpeg", params={"max_fps": 0})
    too_high = client.get("/api/v1/vision/stream/tb3_1_picam.mjpeg", params={"max_fps": 31})

    assert too_low.status_code == 422
    assert too_low.json()["error"]["code"] == "VALIDATION_ERROR"
    assert too_high.status_code == 422
    assert too_high.json()["error"]["code"] == "VALIDATION_ERROR"

def test_synthetic_frame_ingest_uses_latest_frame_overlay_path():
    main_module.source_health.reset()
    main_module.frame_store.reset()
    main_module.overlay_cache.reset()
    with main_module._overlay_images_lock:
        main_module._overlay_images.clear()

    response = client.post(
        "/api/v1/vision/synthetic/frame",
        json={"source": "tb3_2_picam", "marker_id": 9, "stale": True},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "tb3_2_picam"
    assert body["emitted"] is False
    assert body["emit_disabled"] is False
    assert len(body["events"]) == 1
    assert body["events"][0]["marker_id"] == "ARUCO_4X4_50_9"
    assert body["overlay"]["source"] == "tb3_2_picam"
    assert body["overlay"]["frame_seq"] == 1
    assert body["overlay"]["event_count"] == 1
    assert body["overlay"]["stale"] is True

    latest = client.get("/api/v1/vision/overlay/latest", params={"source": "tb3_2_picam"})
    assert latest.status_code == 200
    assert latest.json()["overlay"]["frame_seq"] == 1




def test_lane_b_api_served_overlay_visual_qa_distinguishes_fresh_and_stale_warning_band():
    main_module.store.reset()
    main_module.source_health.reset()
    main_module.frame_store.reset()
    main_module.overlay_cache.reset()
    with main_module._overlay_images_lock:
        main_module._overlay_images.clear()

    fresh = client.post(
        "/api/v1/vision/synthetic/frame",
        json={"source": "tb3_1_picam", "marker_id": 7, "stale": False},
    )
    assert fresh.status_code == 200
    fresh_image = client.get(
        "/api/v1/vision/overlay/latest/image",
        params={"source": "tb3_1_picam"},
    )
    assert fresh_image.status_code == 200
    fresh_decoded = cv2.imdecode(np.frombuffer(fresh_image.content, dtype=np.uint8), cv2.IMREAD_COLOR)
    assert fresh_decoded is not None

    stale = client.post(
        "/api/v1/vision/synthetic/frame",
        json={"source": "tb3_1_picam", "marker_id": 8, "stale": True},
    )
    assert stale.status_code == 200
    stale_metadata = client.get(
        "/api/v1/vision/overlay/latest",
        params={"source": "tb3_1_picam"},
    )
    stale_image = client.get(
        "/api/v1/vision/overlay/latest/image",
        params={"source": "tb3_1_picam"},
    )
    assert stale_metadata.status_code == 200
    assert stale_metadata.json()["overlay"]["visual_state"] == "stale"
    assert stale_metadata.json()["sync"]["overlay_visual_state"] == "stale"
    assert stale_image.status_code == 200
    stale_decoded = cv2.imdecode(np.frombuffer(stale_image.content, dtype=np.uint8), cv2.IMREAD_COLOR)
    assert stale_decoded is not None

    # API-served stale overlay must contain the same unmistakable amber header
    # as the renderer unit contract. Sample away from text to avoid anti-aliasing.
    stale_header_pixel = stale_decoded[3, stale_decoded.shape[1] - 10]
    fresh_header_pixel = fresh_decoded[3, fresh_decoded.shape[1] - 10]
    assert int(stale_header_pixel[2]) > 180
    assert int(stale_header_pixel[1]) > 100
    assert int(stale_header_pixel[0]) < 90
    assert np.linalg.norm(stale_header_pixel.astype(float) - fresh_header_pixel.astype(float)) > 100
    assert stale_image.content.startswith(b"\xff\xd8")


def test_synthetic_frame_rejects_unknown_source():
    response = client.post(
        "/api/v1/vision/synthetic/frame",
        json={"source": "bad_cam", "marker_id": 7},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "BAD_REQUEST"


def test_metrics_can_filter_lane_b_source_counters_and_rejects_unknown_source():
    main_module.metrics.reset()
    main_module.frame_store.reset()

    frame = main_module.frame_store.put_decoded(
        source="tb3_1_picam",
        image_bgr=main_module.generate_synthetic_aruco_frame(marker_id=7),
    )
    assert frame.frame_seq == 1
    main_module.frame_store.put_decoded(
        source="tb3_1_picam",
        image_bgr=main_module.generate_synthetic_aruco_frame(marker_id=8),
    )
    main_module.metrics.record_stream_client_opened(source="tb3_1_picam")
    main_module.metrics.record_stream_frame_sent(source="tb3_1_picam")
    main_module.metrics.record_stream_stale_poll(source="tb3_2_picam")
    main_module.metrics.record_worker_tick(source="tb3_1_picam", status="processed")
    main_module.metrics.record_worker_tick(source="tb3_2_picam", status="no_frame")

    response = client.get("/api/v1/metrics", params={"source": "tb3_1_picam"})

    assert response.status_code == 200
    body = response.json()
    assert body["requested_source"] == "tb3_1_picam"
    assert set(body["metrics"]["stream"]["by_source"]) == {"tb3_1_picam"}
    assert body["metrics"]["stream"]["frames_sent_total"] == 1
    assert body["metrics"]["stream"]["stale_polls_total"] == 0
    assert body["metrics"]["worker"]["by_source"] == {"tb3_1_picam": {"processed": 1}}
    assert body["metrics"]["worker"]["tick_total"] == {"processed": 1}
    assert body["frame_store"]["sources_with_frames"] == 1
    assert body["frame_store"]["frame_seq_by_source"] == {"tb3_1_picam": 2}
    assert body["frame_store"]["dropped_frames_by_source"] == {"tb3_1_picam": 1}
    assert body["frame_store"]["dropped_frames_total"] == 1

    empty = client.get("/api/v1/metrics", params={"source": "tb3_2_picam"})
    assert empty.status_code == 200
    assert empty.json()["requested_source"] == "tb3_2_picam"
    assert empty.json()["metrics"]["stream"]["by_source"]["tb3_2_picam"]["frames_sent_total"] == 0
    assert empty.json()["metrics"]["stream"]["stale_polls_total"] == 1
    assert empty.json()["frame_store"]["sources_with_frames"] == 0

    bad = client.get("/api/v1/metrics", params={"source": "bad_cam"})
    assert bad.status_code == 400
    assert bad.json()["error"]["code"] == "BAD_REQUEST"


def test_vision_worker_tick_skips_current_overlay_by_default_and_force_reprocesses():
    main_module.source_health.reset()
    main_module.frame_store.reset()
    main_module.overlay_cache.reset()
    with main_module._overlay_images_lock:
        main_module._overlay_images.clear()

    ingest = client.post(
        "/api/v1/vision/synthetic/frame",
        json={"source": "tb3_1_picam", "marker_id": 7},
    )
    assert ingest.status_code == 200

    skipped = client.post(
        "/api/v1/vision/worker/tick",
        json={"source": "tb3_1_picam"},
    )
    assert skipped.status_code == 200
    assert skipped.json()["summary"]["status_counts"]["skipped"] == 1
    assert skipped.json()["summary"]["event_count_total"] == 1
    skipped_result = skipped.json()["results"][0]
    assert skipped_result["status"] == "skipped"
    assert skipped_result["frame_seq"] == 1
    assert skipped_result["overlay"]["frame_seq"] == 1

    forced = client.post(
        "/api/v1/vision/worker/tick",
        json={"source": "tb3_1_picam", "force": True, "stale": True},
    )
    assert forced.status_code == 200
    assert forced.json()["summary"]["processed_count"] == 1
    assert forced.json()["summary"]["event_count_total"] == 1
    forced_result = forced.json()["results"][0]
    assert forced_result["status"] == "processed"
    assert forced_result["frame_seq"] == 1
    assert forced_result["event_count"] == 1
    assert forced_result["overlay"]["stale"] is True


def test_vision_worker_tick_skips_stale_frame_unless_forced():
    main_module.source_health.reset()
    main_module.metrics.reset()
    main_module.frame_store.reset()
    main_module.overlay_cache.reset()
    with main_module._overlay_images_lock:
        main_module._overlay_images.clear()

    decoded = main_module.generate_synthetic_aruco_frame(marker_id=7)
    frame = main_module.frame_store.put_decoded(
        source="tb3_1_picam",
        image_bgr=decoded,
        timestamp="2000-01-01T00:00:00+00:00",
    )
    main_module.source_health.record_frame("tb3_1_picam", at=frame.timestamp)

    stale = client.post(
        "/api/v1/vision/worker/tick",
        json={"source": "tb3_1_picam", "max_frame_age_s": 0.001},
    )

    assert stale.status_code == 200
    assert stale.json()["summary"]["stale_frame_count"] == 1
    assert stale.json()["summary"]["event_count_total"] == 0
    stale_result = stale.json()["results"][0]
    assert stale_result["status"] == "stale_frame"
    assert stale_result["frame_seq"] == 1
    assert stale_result["event_count"] == 0
    assert stale_result["overlay"] is None
    assert stale_result["max_frame_age_s"] == 0.001

    forced = client.post(
        "/api/v1/vision/worker/tick",
        json={"source": "tb3_1_picam", "max_frame_age_s": 0.001, "force": True},
    )
    assert forced.status_code == 200
    forced_result = forced.json()["results"][0]
    assert forced_result["status"] == "processed"
    assert forced_result["frame_seq"] == 1
    assert forced_result["event_count"] == 1
    assert forced_result["overlay"]["frame_seq"] == 1


def test_vision_worker_status_reports_pending_skipped_and_stale_without_processing():
    main_module.source_health.reset()
    main_module.metrics.reset()
    main_module.frame_store.reset()
    main_module.overlay_cache.reset()
    with main_module._overlay_images_lock:
        main_module._overlay_images.clear()

    empty = client.get(
        "/api/v1/vision/worker/status",
        params={"source": "tb3_1_picam"},
    )
    assert empty.status_code == 200
    assert empty.json()["sources"][0]["next_tick_status"] == "no_frame"
    assert empty.json()["sources"][0]["would_create_new_evidence"] is False
    assert empty.json()["sources"][0]["evidence_action_if_ticked"] == "none"
    assert empty.json()["sources"][0]["expected_new_event_count"] == 0
    assert empty.json()["sources"][0]["reused_event_count_if_ticked"] == 0
    assert empty.json()["summary"]["sources_total"] == 1
    assert empty.json()["summary"]["status_counts"]["no_frame"] == 1
    assert empty.json()["summary"]["would_create_new_evidence_count"] == 0
    assert empty.json()["summary"]["expected_new_event_count_total"] == 0
    assert empty.json()["summary"]["reused_event_count_if_ticked_total"] == 0

    ingest = client.post(
        "/api/v1/vision/frame",
        data={"source": "tb3_1_picam"},
        files={"image": ("aruco.png", aruco_png_bytes(), "image/png")},
    )
    assert ingest.status_code == 200

    pending = client.get(
        "/api/v1/vision/worker/status",
        params={"source": "tb3_1_picam"},
    )
    assert pending.status_code == 200
    pending_source = pending.json()["sources"][0]
    assert pending_source["next_tick_status"] == "processed"
    assert pending_source["pending"] is True
    assert pending_source["latest_frame_seq"] == 1
    assert pending_source["latest_overlay_frame_seq"] is None
    assert pending_source["overlay_lag_frames"] is None
    assert pending_source["would_create_new_evidence"] is True
    assert pending_source["evidence_action_if_ticked"] == "created"
    assert pending_source["expected_new_event_count"] is None
    assert pending_source["reused_event_count_if_ticked"] == 0
    assert pending.json()["summary"]["pending_count"] == 1
    assert pending.json()["summary"]["status_counts"]["processed"] == 1
    assert pending.json()["summary"]["would_create_new_evidence_count"] == 1
    assert pending.json()["summary"]["expected_new_event_count_total"] == 0
    assert pending.json()["summary"]["reused_event_count_if_ticked_total"] == 0

    tick = client.post(
        "/api/v1/vision/worker/tick",
        json={"source": "tb3_1_picam"},
    )
    assert tick.status_code == 200

    skipped = client.get(
        "/api/v1/vision/worker/status",
        params={"source": "tb3_1_picam"},
    )
    assert skipped.status_code == 200
    skipped_source = skipped.json()["sources"][0]
    assert skipped_source["next_tick_status"] == "skipped"
    assert skipped_source["pending"] is False
    assert skipped_source["latest_overlay_frame_seq"] == 1
    assert skipped_source["overlay_lag_frames"] == 0
    assert skipped_source["would_create_new_evidence"] is False
    assert skipped_source["evidence_action_if_ticked"] == "reused"
    assert skipped_source["expected_new_event_count"] == 0
    assert skipped_source["reused_event_count_if_ticked"] == 1
    assert skipped.json()["summary"]["pending_count"] == 0
    assert skipped.json()["summary"]["status_counts"]["skipped"] == 1
    assert skipped.json()["summary"]["would_create_new_evidence_count"] == 0
    assert skipped.json()["summary"]["expected_new_event_count_total"] == 0
    assert skipped.json()["summary"]["reused_event_count_if_ticked_total"] == 1

    stale = client.get(
        "/api/v1/vision/worker/status",
        params={"source": "tb3_1_picam", "max_frame_age_s": 0},
    )
    assert stale.status_code == 200
    stale_source = stale.json()["sources"][0]
    assert stale_source["next_tick_status"] == "stale_frame"
    assert stale_source["pending"] is False
    assert stale_source["would_create_new_evidence"] is False
    assert stale_source["evidence_action_if_ticked"] == "none"
    assert stale_source["expected_new_event_count"] == 0
    assert stale_source["reused_event_count_if_ticked"] == 0
    assert stale.json()["summary"]["stale_frame_count"] == 1
    assert stale.json()["summary"]["status_counts"]["stale_frame"] == 1
    assert stale.json()["summary"]["would_create_new_evidence_count"] == 0
    assert stale.json()["summary"]["expected_new_event_count_total"] == 0
    assert stale.json()["summary"]["reused_event_count_if_ticked_total"] == 0


def test_vision_worker_tick_reports_no_frame_for_empty_source():
    main_module.frame_store.reset()
    main_module.overlay_cache.reset()
    with main_module._overlay_images_lock:
        main_module._overlay_images.clear()

    response = client.post(
        "/api/v1/vision/worker/tick",
        json={"source": "tb3_2_picam"},
    )

    assert response.status_code == 200
    assert response.json()["summary"]["status_counts"]["no_frame"] == 1
    assert response.json()["summary"]["event_count_total"] == 0
    result = response.json()["results"][0]
    assert result["status"] == "no_frame"
    assert result["frame_seq"] is None
    assert result["overlay"] is None


def test_vision_worker_tick_rejects_unknown_source():
    response = client.post(
        "/api/v1/vision/worker/tick",
        json={"source": "bad_cam"},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "BAD_REQUEST"


def test_vision_debug_sources_returns_readiness_snapshot_for_one_source():
    main_module.source_health.reset()
    main_module.metrics.reset()
    main_module.frame_store.reset()
    main_module.overlay_cache.reset()
    with main_module._overlay_images_lock:
        main_module._overlay_images.clear()

    first = client.post(
        "/api/v1/vision/synthetic/frame",
        json={"source": "tb3_1_picam", "marker_id": 7},
    )
    assert first.status_code == 200
    second = client.post(
        "/api/v1/vision/synthetic/frame",
        json={"source": "tb3_1_picam", "marker_id": 8},
    )
    assert second.status_code == 200
    main_module.metrics.record_stream_frame_sent(source="tb3_1_picam")

    response = client.get("/api/v1/vision/debug/sources", params={"source": "tb3_1_picam"})

    assert response.status_code == 200
    body = response.json()
    assert body["primary_stream_plane"] == "rosbridge"
    assert body["requested_source"] == "tb3_1_picam"
    assert body["debug_only"] is True
    assert body["topic_exposure_policy"] == expected_ros_topic_exposure_policy()
    assert body["topic_exposure_summary"] == expected_topic_exposure_summary(["tb3_1_picam"])
    assert body["topic_exposure_summary"]["policy_status"] == "safe"
    assert body["topic_exposure_summary"]["policy_violation_count"] == 0
    assert body["summary"] == {
        "sources_total": 1,
        "with_frame_count": 1,
        "with_overlay_count": 1,
        "overlay_lag_count": 0,
        "ros_ingest_contract_ready_count": 1,
        "ros_publish_ready_count": 1,
        "ros_publish_payload_available_count": 1,
        "evidence_event_publish_ready_count": 1,
        "stale_overlay_count": 0,
        "health_status_counts": {"online": 1},
        "ros_ingest_status_counts": {"contract_ready": 1},
        "ros_publish_status_counts": {"ready_fresh": 1},
    }
    assert len(body["sources"]) == 1
    source = body["sources"][0]
    assert source["source"] == "tb3_1_picam"
    assert source["health"]["status"] == "online"
    assert source["latest_frame"]["frame_seq"] == 2
    assert source["latest_frame"]["size_bytes"] > 0
    assert source["latest_overlay"]["frame_seq"] == 2
    assert source["overlay_lag_frames"] == 0
    assert source["topic_exposure"] == expected_source_topic_exposure("tb3_1_picam")
    assert source["topic_exposure"]["control_topics_allowed"] == []
    assert source["topic_exposure"]["client_publish_allowed"] is False
    assert source["rosbridge_subscription_hints"] == expected_rosbridge_subscription_hints(
        "tb3_1_picam"
    )
    assert source["evidence_event_publish_readiness"]["event_available"] is True
    assert source["evidence_event_publish_readiness"]["publish_ready"] is True
    assert source["evidence_event_publish_readiness"]["topic"] == "/sf/vision/events"
    assert source["evidence_event_publish_readiness"]["message_type"] == (
        "smartfactory_msgs/msg/VisionEvent or JSON bridge payload"
    )
    assert source["evidence_event_publish_readiness"]["schema_version"] == "vision-event.v1"
    assert source["evidence_event_publish_readiness"]["latest_event_id"] is not None
    assert source["evidence_event_publish_readiness"]["latest_event_kind"] == "CONFIRMED"
    assert source["evidence_event_publish_readiness"]["latest_event_timestamp"] is not None
    assert source["evidence_event_publish_readiness"]["dedup_key"] == "event_id"
    assert source["evidence_event_publish_readiness"]["payload_contains_image_bytes"] is False
    assert source["evidence_event_publish_readiness"]["policy"] == (
        expected_ros_evidence_event_publish_policy()
    )
    assert source["evidence_event_publish_readiness"]["reason"] == (
        "latest schema-valid VisionEvent is available for future ROS evidence publisher"
    )
    assert source["rosbridge_subscription_hints"]["recommended_overlay_topic"] == (
        "/sf/vision/sources/tb3_1_picam/overlay/compressed"
    )
    assert source["ros_ingest_readiness"] == expected_ros_ingest_readiness("tb3_1_picam")
    assert source["ros_publish_readiness"]["readiness_state"] == "ready_fresh"
    assert source["ros_publish_readiness"]["overlay_ready"] is True
    assert source["ros_publish_readiness"]["latest_frame_seq"] == 2
    assert source["ros_publish_readiness"]["latest_overlay_frame_seq"] == 2
    assert source["ros_publish_readiness"]["overlay_visual_state"] == "fresh"
    assert source["ros_publish_readiness"]["runtime_plan"] == (
        expected_ros_publish_runtime_plan("tb3_1_picam")
    )
    assert source["evidence_event_publish_readiness"]["publish_ready"] is True
    assert source["evidence_event_publish_readiness"]["topic"] == "/sf/vision/events"
    assert source["evidence_event_publish_readiness"]["schema_version"] == "vision-event.v1"
    assert source["evidence_event_publish_readiness"]["latest_event_kind"] == "CONFIRMED"
    assert source["evidence_event_publish_readiness"]["dedup_key"] == "event_id"
    assert source["evidence_event_publish_readiness"]["payload_contains_image_bytes"] is False
    assert source["evidence_event_publish_readiness"]["policy"] == (
        expected_ros_evidence_event_publish_policy()
    )
    assert source["stream_metrics"]["frames_sent_total"] == 1
    assert source["drop_metrics"]["dropped_frames"] == 1
    assert source["debug_paths"]["frame_metadata"] == (
        "/api/v1/vision/frame/latest?source=tb3_1_picam"
    )
    assert source["debug_paths"]["frame_image"] == (
        "/api/v1/vision/frame/latest/image?source=tb3_1_picam"
    )
    assert source["debug_paths"]["metrics"] == "/api/v1/metrics?source=tb3_1_picam"
    assert source["debug_paths"]["metrics_all"] == "/api/v1/metrics"
    assert source["debug_paths"]["ros_handoff"] == "/api/v1/vision/ros/topics?source=tb3_1_picam"
    assert source["debug_paths"]["ros_handoff_all"] == "/api/v1/vision/ros/topics"


def test_vision_debug_sources_reports_overlay_lag_before_worker_tick():
    main_module.source_health.reset()
    main_module.frame_store.reset()
    main_module.overlay_cache.reset()
    with main_module._overlay_images_lock:
        main_module._overlay_images.clear()

    first = client.post(
        "/api/v1/vision/synthetic/frame",
        json={"source": "tb3_2_picam", "marker_id": 7},
    )
    assert first.status_code == 200
    # Store a newer raw latest frame without rendering a new overlay.
    decoded = main_module.generate_synthetic_aruco_frame(marker_id=8)
    frame = main_module.frame_store.put_decoded(source="tb3_2_picam", image_bgr=decoded)
    main_module.source_health.record_frame("tb3_2_picam", at=main_module._now_dt())
    assert frame.frame_seq == 2

    response = client.get("/api/v1/vision/debug/sources", params={"source": "tb3_2_picam"})

    assert response.status_code == 200
    body = response.json()
    assert body["requested_source"] == "tb3_2_picam"
    assert body["topic_exposure_summary"] == expected_topic_exposure_summary(["tb3_2_picam"])
    assert body["sources"][0]["topic_exposure"] == expected_source_topic_exposure("tb3_2_picam")
    assert body["sources"][0]["rosbridge_subscription_hints"] == expected_rosbridge_subscription_hints(
        "tb3_2_picam"
    )
    assert body["summary"]["sources_total"] == 1
    assert body["summary"]["with_frame_count"] == 1
    assert body["summary"]["with_overlay_count"] == 1
    assert body["summary"]["overlay_lag_count"] == 1
    assert body["summary"]["ros_publish_ready_count"] == 0
    assert body["summary"]["ros_publish_payload_available_count"] == 0
    assert body["summary"]["evidence_event_publish_ready_count"] == 1
    assert body["summary"]["health_status_counts"] == {"online": 1}
    assert body["summary"]["ros_ingest_status_counts"] == {"contract_ready": 1}
    assert body["summary"]["ros_publish_status_counts"] == {"overlay_lag": 1}
    source = body["sources"][0]
    assert source["latest_frame"]["frame_seq"] == 2
    assert source["latest_overlay"]["frame_seq"] == 1
    assert source["overlay_lag_frames"] == 1
    assert source["ros_publish_readiness"]["readiness_state"] == "overlay_lag"
    assert source["ros_publish_readiness"]["overlay_ready"] is False
    assert source["ros_publish_readiness"]["latest_frame_seq"] == 2
    assert source["ros_publish_readiness"]["latest_overlay_frame_seq"] == 1
    assert source["evidence_event_publish_readiness"]["publish_ready"] is True


def test_vision_debug_sources_rejects_unknown_source():
    response = client.get("/api/v1/vision/debug/sources", params={"source": "bad_cam"})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "BAD_REQUEST"
