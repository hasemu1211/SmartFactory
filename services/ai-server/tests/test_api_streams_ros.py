"""Vision stream and ROS handoff read-model API tests."""

from api_test_helpers import (
    aruco_png_bytes,
    client,
    expected_ros_evidence_event_publish_policy,
    expected_ros_ingest_readiness,
    expected_ros_overlay_publish_policy,
    expected_ros_overlay_publish_qos_policy,
    expected_ros_publish_runtime_plan,
    expected_ros_topic_exposure_policy,
    expected_rosbridge_subscription_hints,
    expected_source_topic_exposure,
    expected_topic_exposure_summary,
    main_module,
    source_definition,
)

def test_vision_streams_declares_http_gateway_primary_and_internal_rosbridge_policy():
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
    assert body["primary_stream_plane"] == "http_mjpeg_gateway"
    assert body["stream_base_url"] == "http://<vision-host>:8090"
    assert body["debug_only"] is False
    assert body["internal_rosbridge"] == {
        "scope": "operator_prototype_only",
        "url": "ws://<vision-host>:9090",
        "exposes_all_topics": False,
    }
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
    assert body["primary_stream_plane"] == "http_mjpeg_gateway"
    assert body["stream_base_url"] == "http://<vision-host>:8090"
    assert body["debug_only"] is False
    assert body["motion_command_allowed"] is False
    assert body["control_topics_published"] == []
    assert [item["source"] for item in body["sources"]] == ["tb3_1_picam"]
    source = body["sources"][0]
    assert source["mjpeg_path"] == "/api/v1/vision/stream/tb3_1_picam.mjpeg"
    assert source["default_view"] == "full"
    assert source["available_views"] == ["full"]
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
    assert body["primary_stream_plane"] == "http_mjpeg_gateway"
    assert body["stream_base_url"] == "http://<vision-host>:8090"
    assert body["debug_only"] is True
    assert body["internal_rosbridge"] == {
        "scope": "operator_prototype_only",
        "url": "ws://<vision-host>:9090",
        "exposes_all_topics": False,
    }
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
