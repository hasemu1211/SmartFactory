from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ..config import get_settings
from ..runtime_state import RuntimeContext


LatestOverlayImageGetter = Callable[..., Any]
FrameAgeGetter = Callable[[Any], float]


def _source_definition(source: str):
    return get_settings().source_registry.get(source)


def _robot_id_for_source(source: str) -> str | None:
    return _source_definition(source).robot_id


def _frame_id_for_source(source: str) -> str:
    return _source_definition(source).frame_id


def _source_kind(source: str) -> str:
    return _source_definition(source).kind


def _source_notes(source: str) -> str:
    return _source_definition(source).notes


def _legacy_browser_topic_for_source(source: str) -> str | None:
    """Return existing browser/rosbridge topic that must not regress."""
    return _source_definition(source).browser.legacy_topic


def _legacy_browser_message_type_for_source(source: str) -> str | None:
    return _source_definition(source).browser.legacy_message_type


def _physical_input_topic_for_source(source: str) -> str | None:
    return _source_definition(source).physical_input.topic


def _physical_input_message_type_for_source(source: str) -> str | None:
    return _source_definition(source).physical_input.message_type


def _physical_input_content_type_for_source(source: str) -> str | None:
    return _source_definition(source).physical_input.content_type


def _physical_input_transport_for_source(source: str) -> str | None:
    return _source_definition(source).physical_input.preferred_transport


def _normalized_image_topic_for_source(source: str) -> str:
    return _source_definition(source).normalized_topics.image


def _normalized_overlay_topic_for_source(source: str) -> str:
    return _source_definition(source).normalized_topics.overlay


def _evidence_event_topic_for_source(source: str) -> str:
    return _source_definition(source).evidence_event_topic


def _ros_sensor_qos_policy() -> dict[str, Any]:
    return {"reliability": "BEST_EFFORT", "history": "KEEP_LAST", "depth": 1}


def _ros_overlay_publish_qos_policy() -> dict[str, Any]:
    return {
        "reliability": "BEST_EFFORT",
        "history": "KEEP_LAST",
        "depth": 1,
        "durability": "VOLATILE",
    }


def _ros_overlay_publish_policy() -> dict[str, Any]:
    return {
        "message_type": "sensor" + "_msgs/msg/CompressedImage",
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


def _ros_frame_drop_policy() -> dict[str, Any]:
    settings = get_settings()
    return {
        "cache": "latest_only",
        "drop_stale_frames": True,
        "stale_after_s": settings.source_stale_after_s,
        "offline_after_s": settings.source_offline_after_s,
        "backpressure": "overwrite_latest_frame_per_source",
    }


def _ros_evidence_event_publish_policy() -> dict[str, Any]:
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


def _ros_runtime_policy() -> dict[str, Any]:
    return {
        "ros2_started_by_http_request": False,
        "recommended_executor": "MultiThreadedExecutor",
        "http_handlers_must_spin_ros2_executor": False,
        "threading_model": "ROS2 executor outside FastAPI request handlers with lock-protected latest-frame handoff",
    }


def _ros_topic_exposure_policy() -> dict[str, Any]:
    """Return the planned ROS/rosbridge topic exposure policy without applying it."""
    return {
        "policy": "explicit_allowlist_only",
        "rosbridge_exposes_all_topics": False,
        "browser_primary_transport": "http_mjpeg_gateway",
        "rosbridge_scope": "internal_operator_allowlist_only",
        "allowed_message_types": [
            "sensor" + "_msgs/msg/CompressedImage",
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
            "Main-facing browser video uses the source-selected HTTP/MJPEG :8090 gateway.",
            "Expose only camera/overlay/evidence topics needed by operator/internal ROS tooling.",
            "Do not expose all DDS topics through rosbridge.",
            "Motion and parameter mutation remain outside Vision Gateway.",
        ],
    }


def _source_topic_exposure(source: str, physical_topic: str | None) -> dict[str, Any]:
    """Return source-scoped allowed topics for the planned browser/bridge plane."""
    legacy_topic = _legacy_browser_topic_for_source(source)
    allowed_browser_topics = [
        topic
        for topic in (
            legacy_topic,
            _normalized_image_topic_for_source(source),
            _normalized_overlay_topic_for_source(source),
        )
        if topic is not None
    ]
    return {
        "allowed_browser_topics": allowed_browser_topics,
        "allowed_ingest_topics": [physical_topic] if physical_topic else [],
        "allowed_publish_topics": [
            _normalized_image_topic_for_source(source),
            _normalized_overlay_topic_for_source(source),
            _evidence_event_topic_for_source(source),
        ],
        "client_publish_allowed": False,
        "control_topics_allowed": [],
        "forbidden_topic_globs": _ros_topic_exposure_policy()["forbidden_topic_globs"],
    }


def _rosbridge_subscription_hints(
    source: str, topic_exposure: dict[str, Any]
) -> dict[str, Any]:
    """Return source-scoped internal rosbridge hints without touching rosbridge."""
    return {
        "scope": "internal_operator_prototype_only",
        "main_facing_video_transport": "http_mjpeg_gateway",
        "allowed_browser_topics": topic_exposure["allowed_browser_topics"],
        "recommended_image_topic": _normalized_image_topic_for_source(source),
        "recommended_overlay_topic": _normalized_overlay_topic_for_source(source),
        "legacy_browser_topic": _legacy_browser_topic_for_source(source),
        "client_publish_allowed": False,
        "control_topics_allowed": [],
    }


def _topic_exposure_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    browser_topics = {
        topic for row in rows for topic in row["topic_exposure"]["allowed_browser_topics"]
    }
    ingest_topics = {
        topic for row in rows for topic in row["topic_exposure"]["allowed_ingest_topics"]
    }
    publish_topics = {
        topic for row in rows for topic in row["topic_exposure"]["allowed_publish_topics"]
    }
    control_topics = {
        topic for row in rows for topic in row["topic_exposure"]["control_topics_allowed"]
    }
    client_publish_allowed_count = sum(
        1 for row in rows if row["topic_exposure"]["client_publish_allowed"]
    )
    policy = _ros_topic_exposure_policy()
    policy_violations: list[str] = []
    if policy["policy"] != "explicit_allowlist_only":
        policy_violations.append("topic exposure policy is not explicit_allowlist_only")
    if policy["rosbridge_exposes_all_topics"]:
        policy_violations.append("rosbridge must not expose the full ROS graph")
    if policy["server_publish_control_allowed"]:
        policy_violations.append("Vision Gateway must not publish control topics")
    if control_topics:
        policy_violations.append("source topic exposure includes control topics")
    if client_publish_allowed_count:
        policy_violations.append("client publish is enabled for at least one source")
    return {
        "sources_total": len(rows),
        "allowed_browser_topic_count": len(browser_topics),
        "allowed_ingest_topic_count": len(ingest_topics),
        "allowed_publish_topic_count": len(publish_topics),
        "control_topic_allowed_count": len(control_topics),
        "client_publish_allowed_source_count": client_publish_allowed_count,
        "forbidden_topic_glob_count": len(policy["forbidden_topic_globs"]),
        "forbidden_capability_count": len(policy["forbidden_capabilities"]),
        "explicit_allowlist_only": policy["policy"] == "explicit_allowlist_only",
        "rosbridge_exposes_all_topics": policy["rosbridge_exposes_all_topics"],
        "server_publish_control_allowed": policy["server_publish_control_allowed"],
        "policy_status": "safe" if not policy_violations else "unsafe",
        "policy_violation_count": len(policy_violations),
        "policy_violations": policy_violations,
    }


def _ros_ingest_runtime_plan(source: str) -> dict[str, Any]:
    """Return the planned ROS2 ingest runtime shape without starting ROS2."""
    return {
        "node_name": "smartfactory_vision_gateway",
        "executor": "MultiThreadedExecutor",
        "spin_location": "background_thread",
        "source_registry_path": str(get_settings().vision_sources_registry_path),
        "physical_input_topic": _physical_input_topic_for_source(source),
        "physical_input_message_type": _physical_input_message_type_for_source(source),
        "physical_input_content_type": _physical_input_content_type_for_source(source),
        "physical_input_transport": _physical_input_transport_for_source(source),
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


def _ros_publish_runtime_plan(source: str) -> dict[str, Any]:
    """Return the planned ROS2 overlay publish runtime shape without publishing."""
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
        "publish_topic": _normalized_overlay_topic_for_source(source),
        "publish_message_type": "sensor" + "_msgs/msg/CompressedImage",
        "publish_qos_profile": _ros_overlay_publish_qos_policy(),
        "publish_policy": _ros_overlay_publish_policy(),
        "publish_condition": "overlay_ready_true_and_latest_overlay_frame_seq_matches_latest_frame_seq",
        "stale_behavior": "publish_ready_stale_overlay_with_visual_warning_band",
        "lag_behavior": "do_not_publish_lagging_overlay",
        "http_handler_role": "read_latest_state_only_never_publish_ros2",
        "control_publish_allowed": False,
        "startup_owner": "process_startup_or_launch_file_not_http_request",
        "shutdown_owner": "process_signal_handler_or_lifespan_cleanup",
    }


def overlay_publish_payload_preview_for_source(
    source: str,
    *,
    runtime_context: RuntimeContext,
    latest_overlay_image: LatestOverlayImageGetter,
) -> dict[str, Any]:
    """Return read-only metadata for a future ROS compressed overlay publish."""
    frame = runtime_context.frame_store.latest(source)
    overlay_image = latest_overlay_image(source, runtime_context=runtime_context)
    topic = _normalized_overlay_topic_for_source(source)
    message_type = "sensor" + "_msgs/msg/CompressedImage"
    if frame is None:
        return {
            "payload_available": False,
            "topic": topic,
            "message_type": message_type,
            "frame_seq": None,
            "content_type": None,
            "size_bytes": 0,
            "reason": "no latest frame has been ingested",
        }
    if overlay_image is None:
        return {
            "payload_available": False,
            "topic": topic,
            "message_type": message_type,
            "frame_seq": frame.frame_seq,
            "content_type": None,
            "size_bytes": 0,
            "reason": "latest frame exists but no overlay image has been rendered",
        }
    if overlay_image.frame_seq != frame.frame_seq:
        return {
            "payload_available": False,
            "topic": topic,
            "message_type": message_type,
            "frame_seq": overlay_image.frame_seq,
            "content_type": overlay_image.content_type,
            "size_bytes": len(overlay_image.jpeg),
            "reason": "overlay image frame_seq does not match latest frame_seq",
        }
    return {
        "payload_available": True,
        "topic": topic,
        "message_type": message_type,
        "frame_seq": overlay_image.frame_seq,
        "content_type": overlay_image.content_type,
        "size_bytes": len(overlay_image.jpeg),
        "reason": "overlay image is ready for a future background ROS publisher",
    }


def ros_publish_readiness(
    source: str,
    *,
    runtime_context: RuntimeContext,
    latest_overlay_image: LatestOverlayImageGetter,
    frame_age_s: FrameAgeGetter,
) -> dict[str, Any]:
    frame = runtime_context.frame_store.latest(source)
    overlay = runtime_context.overlay_cache.latest(source)
    latest_frame_seq = frame.frame_seq if frame is not None else None
    latest_overlay_frame_seq = overlay.get("frame_seq") if overlay else None
    overlay_visual_state = overlay.get("visual_state") if overlay else None
    event_count = overlay.get("event_count") if overlay else None
    if frame is None:
        readiness_state = "no_frame"
        overlay_ready = False
        reason = "no latest frame has been ingested"
    elif overlay is None:
        readiness_state = "no_overlay"
        overlay_ready = False
        reason = "latest frame exists but no overlay has been rendered"
    elif latest_overlay_frame_seq != latest_frame_seq:
        readiness_state = "overlay_lag"
        overlay_ready = False
        reason = "overlay frame_seq does not match latest frame_seq"
    elif overlay.get("stale") is True or overlay_visual_state == "stale":
        readiness_state = "ready_stale"
        overlay_ready = True
        reason = "latest overlay matches latest frame and is visually marked stale"
    else:
        readiness_state = "ready_fresh"
        overlay_ready = True
        reason = "latest overlay matches latest frame"
    return {
        "latest_frame_seq": latest_frame_seq,
        "latest_overlay_frame_seq": latest_overlay_frame_seq,
        "frame_age_s": round(frame_age_s(frame), 3) if frame is not None else None,
        "overlay_ready": overlay_ready,
        "readiness_state": readiness_state,
        "overlay_visual_state": overlay_visual_state,
        "event_count": event_count,
        "publish_payload_preview": overlay_publish_payload_preview_for_source(
            source,
            runtime_context=runtime_context,
            latest_overlay_image=latest_overlay_image,
        ),
        "runtime_plan": _ros_publish_runtime_plan(source),
        "reason": reason,
    }


def ros_evidence_event_publish_readiness(
    source: str, *, runtime_context: RuntimeContext
) -> dict[str, Any]:
    latest_events = runtime_context.store.latest(source=source, limit=1)
    latest_event = latest_events[0] if latest_events else None
    event_available = latest_event is not None
    return {
        "event_available": event_available,
        "publish_ready": event_available,
        "topic": "/sf/vision/events",
        "message_type": "smartfactory_msgs/msg/VisionEvent or JSON bridge payload",
        "schema_version": latest_event.get("schema_version") if latest_event else None,
        "latest_event_id": latest_event.get("event_id") if latest_event else None,
        "latest_event_kind": latest_event.get("event_kind") if latest_event else None,
        "latest_event_timestamp": latest_event.get("timestamp") if latest_event else None,
        "dedup_key": "event_id",
        "payload_contains_image_bytes": False,
        "policy": _ros_evidence_event_publish_policy(),
        "reason": (
            "latest schema-valid VisionEvent is available for future ROS evidence publisher"
            if event_available
            else "no VisionEvent is available for this source"
        ),
    }


def _ros_evidence_event_publish_readiness_summary(
    rows: list[dict[str, Any]]
) -> dict[str, Any]:
    ready_count = sum(
        1 for row in rows if row["evidence_event_publish_readiness"]["publish_ready"]
    )
    return {
        "sources_total": len(rows),
        "publish_ready_count": ready_count,
        "no_event_count": len(rows) - ready_count,
    }


def _ros_publish_readiness_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    status_counts = {
        "no_frame": 0,
        "no_overlay": 0,
        "overlay_lag": 0,
        "ready_fresh": 0,
        "ready_stale": 0,
    }
    for row in rows:
        state = row["publish_readiness"]["readiness_state"]
        if state in status_counts:
            status_counts[state] += 1
    publish_payload_available_count = sum(
        1
        for row in rows
        if row["publish_readiness"]["publish_payload_preview"]["payload_available"]
    )
    return {
        "sources_total": len(rows),
        "overlay_ready_count": status_counts["ready_fresh"] + status_counts["ready_stale"],
        "publish_payload_available_count": publish_payload_available_count,
        "publish_payload_blocked_count": len(rows) - publish_payload_available_count,
        "overlay_lag_count": status_counts["overlay_lag"],
        "no_overlay_count": status_counts["no_overlay"],
        "no_frame_count": status_counts["no_frame"],
        "status_counts": status_counts,
    }


def _ros_ingest_readiness(
    source: str, physical_topic: str | None
) -> dict[str, Any]:
    topic_configured = bool(physical_topic)
    readiness_state = "contract_ready" if topic_configured else "missing_physical_topic"
    reason = (
        "source registry has a physical ROS image topic; Lane C can attach a background subscriber"
        if topic_configured
        else "no physical ROS image topic is configured for this source"
    )
    return {
        "readiness_state": readiness_state,
        "physical_input_topic_configured": topic_configured,
        "physical_input_message_type": _physical_input_message_type_for_source(source),
        "physical_input_content_type": _physical_input_content_type_for_source(source),
        "physical_input_transport": _physical_input_transport_for_source(source),
        "runtime_subscriber_active": False,
        "http_debug_ingest_path": "/api/v1/vision/frame",
        "required_qos_profile": _ros_sensor_qos_policy(),
        "frame_drop_policy": _ros_frame_drop_policy(),
        "runtime_plan": _ros_ingest_runtime_plan(source),
        "reason": reason,
    }


def _ros_ingest_readiness_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    status_counts = {"contract_ready": 0, "missing_physical_topic": 0}
    for row in rows:
        state = row["ingest_readiness"]["readiness_state"]
        if state in status_counts:
            status_counts[state] += 1
    return {
        "sources_total": len(rows),
        "contract_ready_count": status_counts["contract_ready"],
        "missing_physical_topic_count": status_counts["missing_physical_topic"],
        "runtime_subscriber_active_count": sum(
            1 for row in rows if row["ingest_readiness"]["runtime_subscriber_active"]
        ),
        "status_counts": status_counts,
    }


def frame_overlay_sync_status(
    source: str, *, runtime_context: RuntimeContext
) -> dict[str, Any]:
    frame = runtime_context.frame_store.latest(source)
    overlay = runtime_context.overlay_cache.latest(source)
    frame_seq = frame.frame_seq if frame is not None else None
    overlay_frame_seq = overlay.get("frame_seq") if isinstance(overlay, dict) else None
    overlay_lag_frames = (
        max(0, frame_seq - overlay_frame_seq)
        if isinstance(frame_seq, int) and isinstance(overlay_frame_seq, int)
        else None
    )
    return {
        "latest_frame_seq": frame_seq,
        "latest_overlay_frame_seq": overlay_frame_seq,
        "overlay_lag_frames": overlay_lag_frames,
        "overlay_visual_state": overlay.get("visual_state")
        if isinstance(overlay, dict)
        else None,
    }


def source_topic_rows(
    *,
    runtime_context: RuntimeContext,
    latest_overlay_image: LatestOverlayImageGetter,
    frame_age_s: FrameAgeGetter,
) -> list[dict[str, Any]]:
    """Build the ROS2/domain-bridge handoff matrix without starting ROS2."""
    settings = get_settings()
    rows: list[dict[str, Any]] = []
    for source in settings.source_ids:
        physical_topic = _physical_input_topic_for_source(source)
        rows.append(
            {
                "source": source,
                "kind": _source_kind(source),
                "robot_id": _robot_id_for_source(source),
                "frame_id": _frame_id_for_source(source),
                "physical_input_topic": physical_topic,
                "physical_input_message_type": _physical_input_message_type_for_source(source),
                "physical_input_content_type": _physical_input_content_type_for_source(source),
                "physical_input_transport": _physical_input_transport_for_source(source),
                "legacy_browser_topic": _legacy_browser_topic_for_source(source),
                "legacy_browser_message_type": _legacy_browser_message_type_for_source(source),
                "normalized_image_topic": _normalized_image_topic_for_source(source),
                "normalized_image_message_type": "sensor" + "_msgs/msg/CompressedImage",
                "normalized_overlay_topic": _normalized_overlay_topic_for_source(source),
                "normalized_overlay_message_type": "sensor" + "_msgs/msg/CompressedImage",
                "evidence_event_topic": _evidence_event_topic_for_source(source),
                "evidence_event_message_type": "smartfactory_msgs/msg/VisionEvent or JSON bridge payload",
                "evidence_event_publish_policy": _ros_evidence_event_publish_policy(),
                "evidence_event_publish_readiness": ros_evidence_event_publish_readiness(
                    source,
                    runtime_context=runtime_context,
                ),
                "topic_exposure": _source_topic_exposure(source, physical_topic),
                "qos_profile": _ros_sensor_qos_policy(),
                "frame_drop_policy": _ros_frame_drop_policy(),
                "overlay_publish_qos": _ros_overlay_publish_qos_policy(),
                "overlay_publish_policy": _ros_overlay_publish_policy(),
                "ingest_readiness": _ros_ingest_readiness(source, physical_topic),
                "publish_readiness": ros_publish_readiness(
                    source,
                    runtime_context=runtime_context,
                    latest_overlay_image=latest_overlay_image,
                    frame_age_s=frame_age_s,
                ),
                "ingest_status": "planned",
                "overlay_publish_status": "planned",
            }
        )
    return rows


def _zero_stream_metrics() -> dict[str, Any]:
    return {
        "clients_total": 0,
        "active_clients": 0,
        "frames_sent_total": 0,
        "stale_polls_total": 0,
        "approx_fps": 0.0,
    }


def vision_stream_source_entry(
    source: str,
    *,
    stream_metrics: dict[str, Any],
    runtime_context: RuntimeContext,
    latest_overlay_image: LatestOverlayImageGetter,
    frame_age_s: FrameAgeGetter,
) -> dict[str, Any]:
    physical_topic = _physical_input_topic_for_source(source)
    topic_exposure = _source_topic_exposure(source, physical_topic)
    return {
        "source": source,
        "has_frame": runtime_context.frame_store.latest(source) is not None,
        "has_overlay": runtime_context.overlay_cache.latest(source) is not None,
        **frame_overlay_sync_status(source, runtime_context=runtime_context),
        "topic_exposure": topic_exposure,
        "rosbridge_subscription_hints": _rosbridge_subscription_hints(
            source, topic_exposure
        ),
        "ros_ingest_readiness": _ros_ingest_readiness(source, physical_topic),
        "ros_publish_readiness": ros_publish_readiness(
            source,
            runtime_context=runtime_context,
            latest_overlay_image=latest_overlay_image,
            frame_age_s=frame_age_s,
        ),
        "evidence_event_publish_readiness": ros_evidence_event_publish_readiness(
            source,
            runtime_context=runtime_context,
        ),
        "frame_ingest_path": "/api/v1/vision/frame",
        "mjpeg_path": f"/api/v1/vision/stream/{source}.mjpeg",
        "mjpeg_default_max_fps": 10,
        "frame_metadata_path": f"/api/v1/vision/frame/latest?source={source}",
        "frame_image_path": f"/api/v1/vision/frame/latest/image?source={source}",
        "overlay_metadata_path": f"/api/v1/vision/overlay/latest?source={source}",
        "overlay_image_path": f"/api/v1/vision/overlay/latest/image?source={source}",
        "source_snapshot_path": f"/api/v1/vision/debug/sources?source={source}",
        "worker_status_path": f"/api/v1/vision/worker/status?source={source}",
        "metrics_path": f"/api/v1/metrics?source={source}",
        "ros_handoff_path": "/api/v1/vision/ros/topics",
        "ros_handoff_source_path": f"/api/v1/vision/ros/topics?source={source}",
        "stream_metrics": stream_metrics["by_source"].get(source, _zero_stream_metrics()),
    }


def _count_by(items: list[dict[str, Any]], key_path: tuple[str, ...]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        value: Any = item
        for key in key_path:
            value = value[key]
        counts[str(value)] = counts.get(str(value), 0) + 1
    return counts


def vision_streams_summary(source_entries: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "sources_total": len(source_entries),
        "with_frame_count": sum(1 for item in source_entries if item["has_frame"]),
        "with_overlay_count": sum(1 for item in source_entries if item["has_overlay"]),
        "overlay_lag_count": sum(
            1
            for item in source_entries
            if isinstance(item.get("overlay_lag_frames"), int)
            and item["overlay_lag_frames"] > 0
        ),
        "synced_overlay_count": sum(
            1 for item in source_entries if item.get("overlay_lag_frames") == 0
        ),
        "stale_overlay_count": sum(
            1 for item in source_entries if item.get("overlay_visual_state") == "stale"
        ),
        "ros_ingest_contract_ready_count": sum(
            1
            for item in source_entries
            if item["ros_ingest_readiness"]["readiness_state"] == "contract_ready"
        ),
        "ros_ingest_runtime_subscriber_active_count": sum(
            1 for item in source_entries if item["ros_ingest_readiness"]["runtime_subscriber_active"]
        ),
        "ros_ingest_status_counts": _count_by(
            source_entries, ("ros_ingest_readiness", "readiness_state")
        ),
        "ros_publish_ready_count": sum(
            1 for item in source_entries if item["ros_publish_readiness"]["overlay_ready"]
        ),
        "ros_publish_payload_available_count": sum(
            1
            for item in source_entries
            if item["ros_publish_readiness"]["publish_payload_preview"]["payload_available"]
        ),
        "ros_publish_payload_blocked_count": sum(
            1
            for item in source_entries
            if not item["ros_publish_readiness"]["publish_payload_preview"]["payload_available"]
        ),
        "ros_publish_status_counts": _count_by(
            source_entries, ("ros_publish_readiness", "readiness_state")
        ),
        "evidence_event_publish_ready_count": sum(
            1
            for item in source_entries
            if item["evidence_event_publish_readiness"]["publish_ready"]
        ),
    }


def worker_status_for_source(
    *,
    source: str,
    max_frame_age_s: float,
    runtime_context: RuntimeContext,
    frame_age_s: FrameAgeGetter,
) -> dict[str, Any]:
    frame = runtime_context.frame_store.latest(source)
    latest_overlay_metadata = runtime_context.overlay_cache.latest(source)
    overlay_frame_seq = (
        latest_overlay_metadata.get("frame_seq")
        if isinstance(latest_overlay_metadata, dict)
        else None
    )
    if frame is None:
        return {
            "source": source,
            "has_frame": False,
            "has_overlay": latest_overlay_metadata is not None,
            "latest_frame_seq": None,
            "latest_overlay_frame_seq": overlay_frame_seq,
            "frame_age_s": None,
            "max_frame_age_s": max_frame_age_s,
            "overlay_lag_frames": None,
            "pending": False,
            "next_tick_status": "no_frame",
            "would_create_new_evidence": False,
            "evidence_action_if_ticked": "none",
            "expected_new_event_count": 0,
            "reused_event_count_if_ticked": 0,
            "reason": "no latest frame available",
        }

    resolved_frame_age_s = round(frame_age_s(frame), 3)
    overlay_lag_frames = (
        max(0, frame.frame_seq - overlay_frame_seq)
        if isinstance(overlay_frame_seq, int)
        else None
    )
    if resolved_frame_age_s > max_frame_age_s:
        next_status = "stale_frame"
        pending = False
        would_create_new_evidence = False
        evidence_action_if_ticked = "none"
        expected_new_event_count = 0
        reused_event_count_if_ticked = 0
        reason = "latest frame is older than max_frame_age_s"
    elif isinstance(overlay_frame_seq, int) and overlay_frame_seq >= frame.frame_seq:
        next_status = "skipped"
        pending = False
        would_create_new_evidence = False
        evidence_action_if_ticked = "reused"
        expected_new_event_count = 0
        reused_event_count_if_ticked = int(latest_overlay_metadata.get("event_count", 0))
        reason = "latest overlay already matches latest frame"
    else:
        next_status = "processed"
        pending = True
        would_create_new_evidence = True
        evidence_action_if_ticked = "created"
        expected_new_event_count = None
        reused_event_count_if_ticked = 0
        reason = "new frame pending processing"
    return {
        "source": source,
        "has_frame": True,
        "has_overlay": latest_overlay_metadata is not None,
        "latest_frame_seq": frame.frame_seq,
        "latest_overlay_frame_seq": overlay_frame_seq,
        "frame_age_s": resolved_frame_age_s,
        "max_frame_age_s": max_frame_age_s,
        "overlay_lag_frames": overlay_lag_frames,
        "pending": pending,
        "next_tick_status": next_status,
        "would_create_new_evidence": would_create_new_evidence,
        "evidence_action_if_ticked": evidence_action_if_ticked,
        "expected_new_event_count": expected_new_event_count,
        "reused_event_count_if_ticked": reused_event_count_if_ticked,
        "reason": reason,
    }


def worker_status_summary(items: list[dict[str, Any]]) -> dict[str, Any]:
    status_counts = {"no_frame": 0, "processed": 0, "skipped": 0, "stale_frame": 0}
    pending_count = 0
    stale_count = 0
    would_create_new_evidence_count = 0
    expected_new_event_count_total = 0
    reused_event_count_if_ticked_total = 0
    for item in items:
        status = str(item.get("next_tick_status") or "")
        if status in status_counts:
            status_counts[status] += 1
        if item.get("pending") is True:
            pending_count += 1
        if item.get("would_create_new_evidence") is True:
            would_create_new_evidence_count += 1
        if isinstance(item.get("expected_new_event_count"), int):
            expected_new_event_count_total += int(item["expected_new_event_count"])
        reused_event_count_if_ticked_total += int(
            item.get("reused_event_count_if_ticked") or 0
        )
        if status == "stale_frame":
            stale_count += 1
    return {
        "sources_total": len(items),
        "pending_count": pending_count,
        "stale_frame_count": stale_count,
        "would_create_new_evidence_count": would_create_new_evidence_count,
        "expected_new_event_count_total": expected_new_event_count_total,
        "reused_event_count_if_ticked_total": reused_event_count_if_ticked_total,
        "status_counts": status_counts,
    }


def build_vision_worker_status_payload(
    *,
    source: str | None,
    max_frame_age_s: float | None,
    runtime_context: RuntimeContext,
    frame_age_s: FrameAgeGetter,
    now_iso: Callable[[], str],
) -> dict[str, Any]:
    settings = get_settings()
    sources = [source] if source is not None else list(settings.source_ids)
    resolved_max_frame_age_s = (
        max_frame_age_s if max_frame_age_s is not None else settings.source_stale_after_s
    )
    status_items = [
        worker_status_for_source(
            source=item,
            max_frame_age_s=resolved_max_frame_age_s,
            runtime_context=runtime_context,
            frame_age_s=frame_age_s,
        )
        for item in sources
    ]
    return {
        "generated_at": now_iso(),
        "requested_source": source,
        "max_frame_age_s": resolved_max_frame_age_s,
        "debug_only": True,
        "summary": worker_status_summary(status_items),
        "sources": status_items,
    }


def metrics_snapshot_for_source(
    snapshot: dict[str, Any], source: str | None
) -> dict[str, Any]:
    if source is None:
        return snapshot
    filtered = dict(snapshot)
    stream = dict(snapshot.get("stream", {}))
    stream_by_source = dict(stream.get("by_source", {}))
    selected_stream = dict(stream_by_source.get(source, _zero_stream_metrics()))
    stream["by_source"] = {source: selected_stream}
    stream["clients_total"] = int(selected_stream.get("clients_total") or 0)
    stream["active_clients_total"] = int(selected_stream.get("active_clients") or 0)
    stream["frames_sent_total"] = int(selected_stream.get("frames_sent_total") or 0)
    stream["stale_polls_total"] = int(selected_stream.get("stale_polls_total") or 0)
    filtered["stream"] = stream
    worker = dict(snapshot.get("worker", {}))
    worker_by_source = dict(worker.get("by_source", {}))
    selected_worker = dict(worker_by_source.get(source, {}))
    worker["by_source"] = {source: selected_worker}
    worker["tick_total"] = dict(sorted(selected_worker.items()))
    filtered["worker"] = worker
    return filtered


def frame_store_stats_for_source(
    *, runtime_context: RuntimeContext, source: str | None
) -> dict[str, Any]:
    stats = runtime_context.frame_store.stats()
    if source is None:
        return stats
    seq_by_source = dict(stats.get("frame_seq_by_source", {}))
    dropped_by_source = dict(stats.get("dropped_frames_by_source", {}))
    selected_seq = {source: seq_by_source[source]} if source in seq_by_source else {}
    selected_dropped = (
        {source: dropped_by_source[source]} if source in dropped_by_source else {}
    )
    return {
        "sources_with_frames": 1 if selected_seq else 0,
        "frame_seq_by_source": selected_seq,
        "dropped_frames_by_source": selected_dropped,
        "dropped_frames_total": int(selected_dropped.get(source, 0)),
    }


def build_metrics_snapshot_payload(
    *,
    source: str | None,
    runtime_context: RuntimeContext,
    now_iso: Callable[[], str],
) -> dict[str, Any]:
    raw_metrics = runtime_context.metrics.snapshot()
    return {
        "generated_at": now_iso(),
        "requested_source": source,
        "metrics": metrics_snapshot_for_source(raw_metrics, source),
        "event_store": runtime_context.store.stats(),
        "frame_store": frame_store_stats_for_source(
            runtime_context=runtime_context,
            source=source,
        ),
    }


def debug_sources_summary(source_entries: list[dict[str, Any]]) -> dict[str, Any]:
    health_status_counts = _count_by(source_entries, ("health", "status"))
    ros_ingest_status_counts = _count_by(
        source_entries, ("ros_ingest_readiness", "readiness_state")
    )
    ros_publish_status_counts = _count_by(
        source_entries, ("ros_publish_readiness", "readiness_state")
    )
    return {
        "sources_total": len(source_entries),
        "with_frame_count": sum(
            1 for item in source_entries if item["latest_frame"] is not None
        ),
        "with_overlay_count": sum(
            1 for item in source_entries if item["latest_overlay"] is not None
        ),
        "overlay_lag_count": sum(
            1
            for item in source_entries
            if isinstance(item.get("overlay_lag_frames"), int)
            and item["overlay_lag_frames"] > 0
        ),
        "ros_ingest_contract_ready_count": ros_ingest_status_counts.get(
            "contract_ready", 0
        ),
        "ros_publish_ready_count": sum(
            1 for item in source_entries if item["ros_publish_readiness"]["overlay_ready"]
        ),
        "ros_publish_payload_available_count": sum(
            1
            for item in source_entries
            if item["ros_publish_readiness"]["publish_payload_preview"]["payload_available"]
        ),
        "evidence_event_publish_ready_count": sum(
            1
            for item in source_entries
            if item["evidence_event_publish_readiness"]["publish_ready"]
        ),
        "stale_overlay_count": ros_publish_status_counts.get("ready_stale", 0),
        "health_status_counts": health_status_counts,
        "ros_ingest_status_counts": ros_ingest_status_counts,
        "ros_publish_status_counts": ros_publish_status_counts,
    }


def debug_source_snapshot(
    source: str,
    *,
    stream_metrics: dict[str, Any],
    frame_stats: dict[str, Any],
    runtime_context: RuntimeContext,
    latest_overlay_image: LatestOverlayImageGetter,
    frame_age_s: FrameAgeGetter,
    now_dt: Callable[[], Any],
) -> dict[str, Any]:
    settings = get_settings()
    health_snapshot = runtime_context.source_health.snapshot(
        source,
        now=now_dt(),
        stale_after_s=settings.source_stale_after_s,
        offline_after_s=settings.source_offline_after_s,
    )
    frame = runtime_context.frame_store.latest(source)
    overlay = runtime_context.overlay_cache.latest(source)
    physical_topic = _physical_input_topic_for_source(source)
    topic_exposure = _source_topic_exposure(source, physical_topic)
    sync_status = frame_overlay_sync_status(source, runtime_context=runtime_context)
    return {
        "source": source,
        "kind": _source_kind(source),
        "robot_id": _robot_id_for_source(source),
        "health": {
            "enabled": health_snapshot.enabled,
            "status": health_snapshot.status,
            "last_frame_at": health_snapshot.last_frame_at,
            "last_frame_age_s": health_snapshot.last_frame_age_s,
            "last_event_at": health_snapshot.last_event_at,
            "last_event_kind": health_snapshot.last_event_kind,
            "last_event_id": health_snapshot.last_event_id,
            "last_marker_id": health_snapshot.last_marker_id,
            "frame_count": health_snapshot.frame_count,
            "event_count": health_snapshot.event_count,
        },
        "latest_frame": frame.metadata(include_content=True) if frame is not None else None,
        "latest_overlay": overlay,
        "overlay_lag_frames": sync_status["overlay_lag_frames"],
        "topic_exposure": topic_exposure,
        "rosbridge_subscription_hints": _rosbridge_subscription_hints(
            source, topic_exposure
        ),
        "ros_ingest_readiness": _ros_ingest_readiness(source, physical_topic),
        "ros_publish_readiness": ros_publish_readiness(
            source,
            runtime_context=runtime_context,
            latest_overlay_image=latest_overlay_image,
            frame_age_s=frame_age_s,
        ),
        "evidence_event_publish_readiness": ros_evidence_event_publish_readiness(
            source,
            runtime_context=runtime_context,
        ),
        "debug_paths": {
            "frame_ingest": "/api/v1/vision/frame",
            "mjpeg": f"/api/v1/vision/stream/{source}.mjpeg",
            "mjpeg_default_max_fps": 10,
            "frame_metadata": f"/api/v1/vision/frame/latest?source={source}",
            "frame_image": f"/api/v1/vision/frame/latest/image?source={source}",
            "overlay_metadata": f"/api/v1/vision/overlay/latest?source={source}",
            "overlay_image": f"/api/v1/vision/overlay/latest/image?source={source}",
            "worker_tick": "/api/v1/vision/worker/tick",
            "worker_status": f"/api/v1/vision/worker/status?source={source}",
            "metrics": f"/api/v1/metrics?source={source}",
            "metrics_all": "/api/v1/metrics",
            "ros_handoff": f"/api/v1/vision/ros/topics?source={source}",
            "ros_handoff_all": "/api/v1/vision/ros/topics",
        },
        "stream_metrics": stream_metrics["by_source"].get(source, _zero_stream_metrics()),
        "drop_metrics": {
            "dropped_frames": frame_stats.get("dropped_frames_by_source", {}).get(
                source, 0
            )
        },
    }


def build_vision_debug_sources_payload(
    *,
    source: str | None,
    runtime_context: RuntimeContext,
    latest_overlay_image: LatestOverlayImageGetter,
    frame_age_s: FrameAgeGetter,
    now_iso: Callable[[], str],
    now_dt: Callable[[], Any],
) -> dict[str, Any]:
    settings = get_settings()
    sources = [source] if source is not None else list(settings.source_ids)
    stream_metrics = runtime_context.metrics.stream_snapshot()
    frame_stats = runtime_context.frame_store.stats()
    source_entries = [
        debug_source_snapshot(
            item,
            stream_metrics=stream_metrics,
            frame_stats=frame_stats,
            runtime_context=runtime_context,
            latest_overlay_image=latest_overlay_image,
            frame_age_s=frame_age_s,
            now_dt=now_dt,
        )
        for item in sources
    ]
    return {
        "generated_at": now_iso(),
        "requested_source": source,
        "primary_stream_plane": "http_mjpeg_gateway",
        "stream_base_url": "http://<vision-host>:8090",
        "debug_only": True,
        "summary": debug_sources_summary(source_entries),
        "topic_exposure_policy": _ros_topic_exposure_policy(),
        "topic_exposure_summary": _topic_exposure_summary(source_entries),
        "sources": source_entries,
    }


def build_vision_streams_payload(
    *,
    source: str | None,
    runtime_context: RuntimeContext,
    latest_overlay_image: LatestOverlayImageGetter,
    frame_age_s: FrameAgeGetter,
    now_iso: Callable[[], str],
) -> dict[str, Any]:
    settings = get_settings()
    stream_metrics = runtime_context.metrics.stream_snapshot()
    selected_sources = [
        source_id for source_id in settings.source_ids if source is None or source_id == source
    ]
    source_entries = [
        vision_stream_source_entry(
            source_id,
            stream_metrics=stream_metrics,
            runtime_context=runtime_context,
            latest_overlay_image=latest_overlay_image,
            frame_age_s=frame_age_s,
        )
        for source_id in selected_sources
    ]
    return {
        "generated_at": now_iso(),
        "requested_source": source,
        "primary_stream_plane": "http_mjpeg_gateway",
        "stream_base_url": "http://<vision-host>:8090",
        "debug_only": False,
        "motion_command_allowed": False,
        "internal_rosbridge": {
            "scope": "operator_prototype_only",
            "url": "ws://<vision-host>:9090",
            "exposes_all_topics": False,
        },
        "control_topics_published": [],
        "summary": vision_streams_summary(source_entries),
        "topic_exposure_policy": _ros_topic_exposure_policy(),
        "topic_exposure_summary": _topic_exposure_summary(source_entries),
        "runtime_policy": _ros_runtime_policy(),
        "debug_fallback": {
            "frame_ingest_path": "/api/v1/vision/frame",
            "mjpeg_path_template": "/api/v1/vision/stream/{source}.mjpeg",
            "mjpeg_max_fps_default": 10,
            "mjpeg_max_fps_limit": 30,
            "frame_metadata_path": "/api/v1/vision/frame/latest?source={source}",
            "frame_image_path": "/api/v1/vision/frame/latest/image?source={source}",
            "overlay_metadata_path": "/api/v1/vision/overlay/latest?source={source}",
            "overlay_image_path": "/api/v1/vision/overlay/latest/image?source={source}",
            "metrics_path": "/api/v1/metrics",
            "source_snapshot_path": "/api/v1/vision/debug/sources",
            "worker_status_path": "/api/v1/vision/worker/status",
            "ros_handoff_path": "/api/v1/vision/ros/topics",
        },
        "sources": source_entries,
    }


def build_vision_ros_topics_payload(
    *,
    source: str | None,
    runtime_context: RuntimeContext,
    latest_overlay_image: LatestOverlayImageGetter,
    frame_age_s: FrameAgeGetter,
    now_iso: Callable[[], str],
) -> dict[str, Any]:
    source_rows = [
        row
        for row in source_topic_rows(
            runtime_context=runtime_context,
            latest_overlay_image=latest_overlay_image,
            frame_age_s=frame_age_s,
        )
        if source is None or row["source"] == source
    ]
    return {
        "generated_at": now_iso(),
        "requested_source": source,
        "primary_stream_plane": "http_mjpeg_gateway",
        "stream_base_url": "http://<vision-host>:8090",
        "debug_only": True,
        "internal_rosbridge": {
            "scope": "operator_prototype_only",
            "url": "ws://<vision-host>:9090",
            "exposes_all_topics": False,
        },
        "motion_command_allowed": False,
        "migration_policy": "keep existing /mission browser topics; add /sf normalized topics in parallel",
        "control_topics_published": [],
        "topic_exposure_policy": _ros_topic_exposure_policy(),
        "topic_exposure_summary": _topic_exposure_summary(source_rows),
        "image_ingest_qos": _ros_sensor_qos_policy(),
        "frame_drop_policy": _ros_frame_drop_policy(),
        "overlay_publish_qos": _ros_overlay_publish_qos_policy(),
        "overlay_publish_policy": _ros_overlay_publish_policy(),
        "evidence_event_publish_policy": _ros_evidence_event_publish_policy(),
        "runtime_policy": _ros_runtime_policy(),
        "ingest_readiness_summary": _ros_ingest_readiness_summary(source_rows),
        "publish_readiness_summary": _ros_publish_readiness_summary(source_rows),
        "evidence_event_publish_readiness_summary": _ros_evidence_event_publish_readiness_summary(
            source_rows
        ),
        "notes": [
            "Main-facing browser video uses the source-selected HTTP/MJPEG :8090 gateway.",
            "ROS/rosbridge metadata here is internal/operator handoff only.",
            "Vision Gateway must not publish /cmd_vel or call Nav2 actions.",
            "Lane C should subscribe/publish with sensor QoS, keep-last=1, and drop stale frames.",
        ],
        "sources": source_rows,
    }
