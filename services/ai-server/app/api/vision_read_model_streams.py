from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ..config import get_settings
from ..runtime_state import RuntimeContext
from .vision_read_model_ros import (
    FrameAgeGetter,
    LatestOverlayImageGetter,
    _count_by,
    _physical_input_topic_for_source,
    _ros_ingest_readiness,
    _ros_runtime_policy,
    _ros_topic_exposure_policy,
    _rosbridge_subscription_hints,
    _source_topic_exposure,
    _topic_exposure_summary,
    _zero_stream_metrics,
    frame_overlay_sync_status,
    ros_evidence_event_publish_readiness,
    ros_publish_readiness,
)


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
