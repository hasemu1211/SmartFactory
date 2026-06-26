from __future__ import annotations

from collections.abc import Callable
import json
import re
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request as UrlRequest, urlopen

from ..config import get_settings
from ..evidence_cache import DEFAULT_VIEW_ID
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


def overlay_stream_path(source: str, view: str, *, max_fps: int = 30) -> str:
    """Main-facing public overlay gateway path for one source/view."""

    return "/api/v1/vision/overlay/stream?" + urlencode(
        {"source": source, "view": view, "max_fps": max_fps}
    )


def vision_stream_base_url() -> str:
    settings = get_settings()
    return f"http://{settings.vision_public_host}:{settings.vision_stream_gateway_port}"


def vision_gateway_url(path: str) -> str:
    return f"{vision_stream_base_url()}{path}"


def webrtc_offer_path(source: str, view: str) -> str:
    return (
        f"/api/v1/vision/streams/{quote(source, safe='')}/webrtc/offer?"
        + urlencode({"view": view})
    )


def _slug_path_part(value: str) -> str:
    slugged = re.sub(r"[^A-Za-z0-9_-]", "_", value.strip())
    return slugged.strip("_")


def webrtc_sidecar_path_id(source: str, view: str) -> str:
    return f"{_slug_path_part(source)}_{_slug_path_part(view)}"


def _render_sidecar_url(template: str, *, source: str, view: str) -> str | None:
    template = template.strip()
    if not template:
        return None
    return template.format(
        source=quote(source, safe=""),
        source_id=quote(source, safe=""),
        view=quote(view, safe=""),
        view_id=quote(view, safe=""),
    )


def _configured_sidecar_streams() -> set[tuple[str, str]]:
    raw = get_settings().vision_webrtc_sidecar_streams.strip()
    if not raw:
        return set()
    streams: set[tuple[str, str]] = set()
    for item in raw.split(","):
        spec = item.strip()
        if not spec:
            continue
        if "/" in spec:
            source, view = spec.split("/", 1)
        else:
            source, view = spec, DEFAULT_VIEW_ID
        source = source.strip()
        view = view.strip() or DEFAULT_VIEW_ID
        if source:
            streams.add((source, view))
    return streams


def _sidecar_stream_is_allowed(source: str, view: str) -> bool:
    configured_streams = _configured_sidecar_streams()
    return not configured_streams or (source, view) in configured_streams


def webrtc_sidecar_descriptor(source: str, view: str) -> dict[str, Any]:
    settings = get_settings()
    configured_streams = _configured_sidecar_streams()
    stream_allowed = _sidecar_stream_is_allowed(source, view)
    offer_url = _render_sidecar_url(
        settings.vision_webrtc_sidecar_offer_url_template,
        source=source,
        view=view,
    )
    whep_url = _render_sidecar_url(
        settings.vision_webrtc_sidecar_whep_url_template,
        source=source,
        view=view,
    )
    browser_url = _render_sidecar_url(
        settings.vision_webrtc_sidecar_browser_url_template,
        source=source,
        view=view,
    )
    configured = stream_allowed and bool(offer_url or whep_url or browser_url)
    health_url = settings.vision_webrtc_sidecar_health_url.strip() or None
    if health_url:
        runtime_health = "check_required"
    elif configured and settings.vision_webrtc_sidecar_assume_healthy_without_health_url:
        runtime_health = "assume_healthy"
    elif configured:
        runtime_health = "unknown"
    else:
        runtime_health = "not_configured"
    return {
        "status": "configured" if configured else "not_configured",
        "path_id": webrtc_sidecar_path_id(source, view),
        "url_configured": bool(offer_url or whep_url or browser_url),
        "stream_configured": stream_allowed,
        "configured_streams": [f"{item[0]}/{item[1]}" for item in sorted(configured_streams)],
        "runtime_health": runtime_health,
        "runtime_health_url": health_url,
        "offer_url": offer_url if configured else None,
        "whep_url": whep_url if configured else None,
        "browser_url": browser_url if configured else None,
        "owner": "media_sidecar",
        "proxy_mode": "descriptor_only",
    }


def _webrtc_sidecar_runtime_health(sidecar: dict[str, Any]) -> str:
    """Return live WebRTC sidecar HTTP health for discovery readiness."""

    settings = get_settings()
    if sidecar.get("status") != "configured":
        return "not_configured"
    health_url = sidecar.get("runtime_health_url")
    if not health_url:
        if settings.vision_webrtc_sidecar_assume_healthy_without_health_url:
            return "assume_healthy"
        return "unknown"
    request = UrlRequest(str(health_url), method="GET")
    try:
        with urlopen(request, timeout=settings.vision_webrtc_sidecar_health_timeout_s) as response:
            status = getattr(response, "status", 200)
            return "healthy" if status < 500 else "unhealthy"
    except HTTPError as exc:
        return "healthy" if exc.code < 500 else "unhealthy"
    except (OSError, TimeoutError, URLError):
        return "unhealthy"


def _webrtc_sidecar_path_runtime_health(sidecar: dict[str, Any]) -> str:
    """Return whether the requested MediaMTX path is online."""

    if sidecar.get("status") != "configured":
        return "not_configured"
    settings = get_settings()
    paths_api_url = settings.vision_webrtc_sidecar_paths_api_url.strip()
    if not paths_api_url:
        return "not_checked"
    path_id = str(sidecar.get("path_id") or "")
    if not path_id:
        return "missing_path_id"
    request = UrlRequest(paths_api_url, method="GET")
    try:
        with urlopen(request, timeout=settings.vision_webrtc_sidecar_health_timeout_s) as response:
            status = getattr(response, "status", 200)
            if status >= 500:
                return "api_unhealthy"
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        return "api_unhealthy" if exc.code >= 500 else "api_unavailable"
    except (OSError, TimeoutError, URLError, ValueError, json.JSONDecodeError):
        return "api_unavailable"

    items = payload.get("items", []) if isinstance(payload, dict) else []
    for item in items:
        if not isinstance(item, dict) or item.get("name") != path_id:
            continue
        if bool(item.get("ready")) and bool(item.get("available")) and bool(item.get("online")):
            return "online"
        return "offline"
    return "missing"


def _webrtc_transport_status(sidecar: dict[str, Any]) -> dict[str, Any]:
    """Compute Main-facing WebRTC discovery gates from live sidecar state."""

    settings = get_settings()
    answer_capable = bool(sidecar.get("whep_url"))
    configured = bool(
        settings.vision_webrtc_enabled
        and sidecar.get("status") == "configured"
        and answer_capable
    )
    runtime_health = _webrtc_sidecar_runtime_health(sidecar)
    path_runtime_health = _webrtc_sidecar_path_runtime_health(sidecar)
    runtime_ok = runtime_health in {"healthy", "assume_healthy"}
    path_ok = path_runtime_health == "online"
    ready = configured and runtime_ok and path_ok
    sidecar["answer_capable"] = answer_capable
    sidecar["runtime_health"] = runtime_health
    sidecar["path_runtime_health"] = path_runtime_health
    if ready:
        sidecar["status"] = "healthy"
    return {
        "configured": configured,
        "healthy": ready,
        "status": "ready" if ready else ("candidate" if settings.vision_webrtc_enabled else "disabled"),
    }


def stream_transports_for_source(source: str) -> list[dict[str, Any]]:
    settings = get_settings()
    source_definition = settings.source_registry.get(source)
    transports: list[dict[str, Any]] = []
    for view in source_definition.view_ids:
        fallback_path = overlay_stream_path(source, view)
        transports.append(
            {
                "kind": "mjpeg",
                "status": "current_stable",
                "source": source,
                "view": view,
                "url": vision_gateway_url(fallback_path),
                "path": fallback_path,
                "fallback_path": fallback_path,
                "transport_origin": "http_mjpeg_gateway",
                "transport_class": "http_mjpeg_gateway",
                "transport_rank": 4,
                "transport_rank_order": "lower_is_preferred",
                "production_compatible_fallback": True,
                "media_only": True,
                "db_writes": False,
                "evidence_truth_mutation": False,
                "motion_command_allowed": False,
                "control_topics_published": [],
            }
        )
        sidecar = webrtc_sidecar_descriptor(source, view)
        transport_status = _webrtc_transport_status(sidecar)
        transports.append(
            {
                "kind": "webrtc",
                "configured": transport_status["configured"],
                "healthy": transport_status["healthy"],
                "status": transport_status["status"],
                "source": source,
                "view": view,
                "signaling": "http-post-offer-or-sidecar-whep",
                "offer_path": webrtc_offer_path(source, view),
                "fallback_path": fallback_path,
                "fallback_kind": "mjpeg",
                "transport_origin": "mjpeg_overlay_gateway",
                "transport_class": "mjpeg_overlay_h264_transcode_webrtc",
                "transport_rank": 3,
                "transport_rank_order": "lower_is_preferred",
                "preferred_until_direct_media_ready": False,
                "media_only": True,
                "sidecar_required": True,
                "sidecar": sidecar,
                "db_writes": False,
                "evidence_truth_mutation": False,
                "motion_command_allowed": False,
                "control_topics_published": [],
            }
        )
    return transports


def webrtc_transport_policy() -> dict[str, Any]:
    return {
        "status": "candidate_additive",
        "primary_until_parity": "mjpeg",
        "production_compatible_fallback": "http_mjpeg_gateway",
        "preferred_order": [
            "direct_clean_media_webrtc",
            "camera_input_h264_transcode_webrtc",
            "mjpeg_overlay_h264_transcode_webrtc",
            "http_mjpeg_gateway",
        ],
        "transport_rank_order": "lower_is_preferred",
        "promotion_gate": {
            "requires_backward_compatible_fields": True,
            "requires_health_check": True,
            "requires_latency_or_quality_evidence": True,
            "must_keep_mjpeg_fallback": True,
        },
        "current_webrtc_transport_origin": "mjpeg_overlay_gateway",
        "browser_preference_order": ["webrtc", "mjpeg"],
        "fallback_kind": "mjpeg",
        "signaling_scope": "ephemeral_media_session_only",
        "media_only": True,
        "db_writes": False,
        "evidence_truth_mutation": False,
        "motion_command_allowed": False,
        "control_topics_published": [],
        "forbidden_capabilities": [
            "motion_command_publish",
            "nav2_action_call",
            "parameter_mutation",
            "full_rosbridge_graph_exposure",
            "db_write",
            "evidence_truth_mutation",
        ],
    }


def vision_stream_source_entry(
    source: str,
    *,
    stream_metrics: dict[str, Any],
    runtime_context: RuntimeContext,
    latest_overlay_image: LatestOverlayImageGetter,
    frame_age_s: FrameAgeGetter,
) -> dict[str, Any]:
    source_definition = get_settings().source_registry.get(source)
    physical_topic = _physical_input_topic_for_source(source)
    topic_exposure = _source_topic_exposure(source, physical_topic)
    return {
        "source": source,
        "default_view": DEFAULT_VIEW_ID,
        "available_views": list(source_definition.view_ids),
        "budgets": source_definition.budgets.as_snapshot(),
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
        "stream_transports": stream_transports_for_source(source),
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
        "candidate_stream_plane": "webrtc",
        "stream_base_url": vision_stream_base_url(),
        "debug_only": False,
        "motion_command_allowed": False,
        "internal_rosbridge": {
            "scope": "operator_prototype_only",
            "url": "ws://<vision-host>:9090",
            "exposes_all_topics": False,
        },
        "control_topics_published": [],
        "webrtc_policy": webrtc_transport_policy(),
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
