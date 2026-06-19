from __future__ import annotations

import asyncio
import json
from contextvars import ContextVar
from collections.abc import Callable
from datetime import datetime, timezone
from functools import lru_cache, wraps
from inspect import isawaitable
from time import perf_counter
from uuid import uuid4
from typing import Any

from fastapi import File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field

from ..config import get_settings
from ..contracts import ContractValidationError, validate_vision_event
from ..detectors import MarkerDetection, decode_image, detect_markers, generate_synthetic_aruco_frame
from ..docking import CameraIntrinsics, MarkerPose, estimate_marker_pose
from ..frame_store import StoredFrame
from ..lift_roi_evidence import LiftRoiEvidenceRequestError, build_lift_roi_evidence
from ..model_adapters import ModelAdapterError, UltralyticsSegmenterAdapter, VisionModelConfig
from ..openapi_schemas import (
    ERROR_RESPONSE_OPENAPI,
    METRICS_RESPONSE_OPENAPI,
    SOURCE_ID_OPENAPI_EXTRA,
    _debug_sources_response_schema,
    _detect_image_response_schema,
    _frame_ingest_response_schema,
    _frame_process_response_schema,
    _json_response_openapi,
    _latest_frame_response_schema,
    _lift_roi_openapi_schema,
    _ros_handoff_response_schema,
    _synthetic_frame_response_schema,
    _vision_streams_response_schema,
    _worker_status_response_schema,
)
from ..overlay import OverlayRenderResult, render_overlay
from ..pose_profiles import ArucoPoseProfile, PoseProfileError, get_pose_profile
from ..runtime_state import RuntimeContext, default_runtime_context
from ..vision_interfaces import DetectorResult
from ..wms_client import emit_vision_events as default_emit_vision_events
from .dependencies import ContextGetter

PoseRequest = tuple[float, CameraIntrinsics] | ArucoPoseProfile

_context_getter_var: ContextVar[ContextGetter] = ContextVar(
    "smartfactory_ai_server_vision_context_getter",
    default=lambda: default_runtime_context,
)
_emit_vision_events_getter_var: ContextVar[Callable[[], Any]] = ContextVar(
    "smartfactory_ai_server_vision_emit_vision_events_getter",
    default=lambda: default_emit_vision_events,
)
_lift_roi_segmenter_getter_var: ContextVar[Callable[[], Any]] = ContextVar(
    "smartfactory_ai_server_vision_lift_roi_segmenter_getter",
    default=lambda: _get_lift_roi_segmenter,
)


def _runtime_context() -> RuntimeContext:
    return _context_getter_var.get()()


def _emit_vision_events():
    return _emit_vision_events_getter_var.get()()


def _lift_roi_segmenter():
    return _lift_roi_segmenter_getter_var.get()()


class SyntheticFrameRequest(BaseModel):
    """Robot-free synthetic frame ingest request for Lane B debug validation."""
    source: str = Field(..., json_schema_extra=SOURCE_ID_OPENAPI_EXTRA)
    marker_id: int = Field(default=7, ge=0, le=49)
    marker_size: int = Field(default=96, ge=16, le=512)
    padding: int = Field(default=32, ge=0, le=512)
    stale: bool = False
    emit: bool = False

class VisionWorkerTickRequest(BaseModel):
    """Controlled one-shot latest-frame processing tick for Lane B validation."""
    source: str | None = Field(default=None, json_schema_extra=SOURCE_ID_OPENAPI_EXTRA)
    force: bool = False
    stale: bool = False
    max_frame_age_s: float | None = Field(default=None, ge=0)

@lru_cache(maxsize=1)
def _parse_vision_model_class_map(class_map_json: str) -> dict[str, str]:
    if not class_map_json.strip():
        return {}
    try:
        parsed = json.loads(class_map_json)
    except json.JSONDecodeError as exc:
        raise ModelAdapterError('vision model class map must be valid JSON') from exc
    if not isinstance(parsed, dict):
        raise ModelAdapterError('vision model class map must be a JSON object')
    return {str(key): str(value) for key, value in parsed.items()}

@lru_cache(maxsize=1)
def _get_lift_roi_segmenter(*, model_path: str, task: str, confidence: float, iou: float, image_size: int, device: str, class_map_json: str, unmapped_class: str) -> UltralyticsSegmenterAdapter:
    return UltralyticsSegmenterAdapter(VisionModelConfig(model_path=model_path, task=task, confidence=confidence, iou=iou, image_size=image_size, device=device, class_map=_parse_vision_model_class_map(class_map_json), unmapped_class=unmapped_class))

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
    return {'reliability': 'BEST_EFFORT', 'history': 'KEEP_LAST', 'depth': 1}

def _ros_overlay_publish_qos_policy() -> dict[str, Any]:
    return {'reliability': 'BEST_EFFORT', 'history': 'KEEP_LAST', 'depth': 1, 'durability': 'VOLATILE'}

def _ros_overlay_publish_policy() -> dict[str, Any]:
    return {'message_type': 'sensor' + '_msgs/msg/CompressedImage', 'encoding': 'jpeg', 'publish_when': 'publish_payload_preview.payload_available_true', 'drop_when': ['no_frame', 'no_overlay', 'overlay_lag'], 'max_publish_fps': 10, 'queue_policy': 'keep_last_1_drop_old_overlay', 'include_stale_warning_band': True, 'publish_lagging_overlay': False, 'publish_control_topics': False, 'http_handlers_may_publish': False}

def _ros_frame_drop_policy() -> dict[str, Any]:
    settings = get_settings()
    return {'cache': 'latest_only', 'drop_stale_frames': True, 'stale_after_s': settings.source_stale_after_s, 'offline_after_s': settings.source_offline_after_s, 'backpressure': 'overwrite_latest_frame_per_source'}

def _ros_evidence_event_publish_policy() -> dict[str, Any]:
    return {'topic': '/sf/vision/events', 'message_type': 'smartfactory_msgs/msg/VisionEvent or JSON bridge payload', 'schema_version': 'vision-event.v1', 'qos_profile': {'reliability': 'RELIABLE', 'history': 'KEEP_LAST', 'depth': 10, 'durability': 'VOLATILE'}, 'publish_when': 'worker_tick_or_detector_emits_schema_valid_vision_event', 'dedup_key': 'event_id', 'source_of_truth': 'Main/WMS remains authoritative; Vision publishes evidence only', 'publish_control_topics': False, 'http_handlers_may_publish': False, 'payload_contains_image_bytes': False}

def _ros_runtime_policy() -> dict[str, Any]:
    return {'ros2_started_by_http_request': False, 'recommended_executor': 'MultiThreadedExecutor', 'http_handlers_must_spin_ros2_executor': False, 'threading_model': 'ROS2 executor outside FastAPI request handlers with lock-protected latest-frame handoff'}

def _ros_topic_exposure_policy() -> dict[str, Any]:
    """Return the planned ROS/rosbridge topic exposure policy without applying it."""
    return {'policy': 'explicit_allowlist_only', 'rosbridge_exposes_all_topics': False, 'browser_primary_transport': 'http_mjpeg_gateway', 'rosbridge_scope': 'internal_operator_allowlist_only', 'allowed_message_types': ['sensor' + '_msgs/msg/CompressedImage', 'smartfactory_msgs/msg/VisionEvent or JSON bridge payload'], 'forbidden_topic_globs': ['/cmd_vel', '*/cmd_vel', '/navigate_to_pose', '/follow_path', '/parameter_events', '/rosout', '/tf', '/tf_static'], 'forbidden_capabilities': ['motion_command_publish', 'nav2_action_call', 'parameter_mutation', 'raw_dds_forwarding'], 'client_publish_allowed': False, 'server_publish_control_allowed': False, 'auth_required_when_exposed_beyond_private_network': True, 'notes': ['Main-facing browser video uses the source-selected HTTP/MJPEG :8090 gateway.', 'Expose only camera/overlay/evidence topics needed by operator/internal ROS tooling.', 'Do not expose all DDS topics through rosbridge.', 'Motion and parameter mutation remain outside Vision Gateway.']}

def _source_topic_exposure(source: str, physical_topic: str | None) -> dict[str, Any]:
    """Return source-scoped allowed topics for the planned browser/bridge plane."""
    legacy_topic = _legacy_browser_topic_for_source(source)
    allowed_browser_topics = [topic for topic in (legacy_topic, _normalized_image_topic_for_source(source), _normalized_overlay_topic_for_source(source)) if topic is not None]
    return {'allowed_browser_topics': allowed_browser_topics, 'allowed_ingest_topics': [physical_topic] if physical_topic else [], 'allowed_publish_topics': [_normalized_image_topic_for_source(source), _normalized_overlay_topic_for_source(source), _evidence_event_topic_for_source(source)], 'client_publish_allowed': False, 'control_topics_allowed': [], 'forbidden_topic_globs': _ros_topic_exposure_policy()['forbidden_topic_globs']}

def _rosbridge_subscription_hints(source: str, topic_exposure: dict[str, Any]) -> dict[str, Any]:
    """Return source-scoped internal rosbridge hints without touching rosbridge."""
    return {'scope': 'internal_operator_prototype_only', 'main_facing_video_transport': 'http_mjpeg_gateway', 'allowed_browser_topics': topic_exposure['allowed_browser_topics'], 'recommended_image_topic': _normalized_image_topic_for_source(source), 'recommended_overlay_topic': _normalized_overlay_topic_for_source(source), 'legacy_browser_topic': _legacy_browser_topic_for_source(source), 'client_publish_allowed': False, 'control_topics_allowed': []}

def _topic_exposure_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    browser_topics = {topic for row in rows for topic in row['topic_exposure']['allowed_browser_topics']}
    ingest_topics = {topic for row in rows for topic in row['topic_exposure']['allowed_ingest_topics']}
    publish_topics = {topic for row in rows for topic in row['topic_exposure']['allowed_publish_topics']}
    control_topics = {topic for row in rows for topic in row['topic_exposure']['control_topics_allowed']}
    client_publish_allowed_count = sum((1 for row in rows if row['topic_exposure']['client_publish_allowed']))
    policy = _ros_topic_exposure_policy()
    policy_violations: list[str] = []
    if policy['policy'] != 'explicit_allowlist_only':
        policy_violations.append('topic exposure policy is not explicit_allowlist_only')
    if policy['rosbridge_exposes_all_topics']:
        policy_violations.append('rosbridge must not expose the full ROS graph')
    if policy['server_publish_control_allowed']:
        policy_violations.append('Vision Gateway must not publish control topics')
    if control_topics:
        policy_violations.append('source topic exposure includes control topics')
    if client_publish_allowed_count:
        policy_violations.append('client publish is enabled for at least one source')
    return {'sources_total': len(rows), 'allowed_browser_topic_count': len(browser_topics), 'allowed_ingest_topic_count': len(ingest_topics), 'allowed_publish_topic_count': len(publish_topics), 'control_topic_allowed_count': len(control_topics), 'client_publish_allowed_source_count': client_publish_allowed_count, 'forbidden_topic_glob_count': len(policy['forbidden_topic_globs']), 'forbidden_capability_count': len(policy['forbidden_capabilities']), 'explicit_allowlist_only': policy['policy'] == 'explicit_allowlist_only', 'rosbridge_exposes_all_topics': policy['rosbridge_exposes_all_topics'], 'server_publish_control_allowed': policy['server_publish_control_allowed'], 'policy_status': 'safe' if not policy_violations else 'unsafe', 'policy_violation_count': len(policy_violations), 'policy_violations': policy_violations}

def _ros_ingest_runtime_plan(source: str) -> dict[str, Any]:
    """Return the planned ROS2 ingest runtime shape without starting ROS2."""
    return {'node_name': 'smartfactory_vision_gateway', 'executor': 'MultiThreadedExecutor', 'spin_location': 'background_thread', 'source_registry_path': str(get_settings().vision_sources_registry_path), 'physical_input_topic': _physical_input_topic_for_source(source), 'physical_input_message_type': _physical_input_message_type_for_source(source), 'physical_input_content_type': _physical_input_content_type_for_source(source), 'physical_input_transport': _physical_input_transport_for_source(source), 'subscription_callback': 'registry_source_image_message_to_latest_frame_store_put', 'ingest_adapter': '_store_latest_frame_from_bytes', 'ingest_adapter_contract': {'input': 'registry source plus encoded image bytes plus content_type from HTTP or future ROS callback', 'output': 'StoredFrame in LatestFrameStore', 'updates_source_health': True, 'runs_detection_inline': False, 'renders_overlay_inline': False, 'safe_for_http_handlers': True, 'raw_image_requires_callback_encoding': True}, 'shared_state': 'LatestFrameStore', 'shared_state_guard': 'threading.Lock inside frame store', 'http_handler_role': 'read_latest_state_only_never_spin_ros2', 'backpressure': 'overwrite_latest_frame_per_source', 'target_frame_store_source': source, 'startup_owner': 'process_startup_or_launch_file_not_http_request', 'shutdown_owner': 'process_signal_handler_or_lifespan_cleanup'}

def _ros_publish_runtime_plan(source: str) -> dict[str, Any]:
    """Return the planned ROS2 overlay publish runtime shape without publishing."""
    return {'node_name': 'smartfactory_vision_gateway', 'executor': 'MultiThreadedExecutor', 'spin_location': 'background_thread', 'publisher_callback': 'read_latest_overlay_then_publish_compressed_image_when_ready', 'publish_adapter': '_overlay_publish_payload_preview_for_source', 'publish_adapter_contract': {'input': 'source plus latest frame and overlay cache state', 'output': 'publishable compressed overlay metadata when overlay is ready', 'reads_latest_overlay_cache': True, 'requires_frame_overlay_seq_match': True, 'publishes_lagging_overlay': False, 'publishes_control_topics': False, 'safe_for_http_handlers': True}, 'shared_state': 'LatestEvidenceCache plus overlay image cache', 'shared_state_guard': 'threading.Lock around overlay image cache', 'publish_topic': _normalized_overlay_topic_for_source(source), 'publish_message_type': 'sensor' + '_msgs/msg/CompressedImage', 'publish_qos_profile': _ros_overlay_publish_qos_policy(), 'publish_policy': _ros_overlay_publish_policy(), 'publish_condition': 'overlay_ready_true_and_latest_overlay_frame_seq_matches_latest_frame_seq', 'stale_behavior': 'publish_ready_stale_overlay_with_visual_warning_band', 'lag_behavior': 'do_not_publish_lagging_overlay', 'http_handler_role': 'read_latest_state_only_never_publish_ros2', 'control_publish_allowed': False, 'startup_owner': 'process_startup_or_launch_file_not_http_request', 'shutdown_owner': 'process_signal_handler_or_lifespan_cleanup'}

def _overlay_publish_payload_preview_for_source(source: str) -> dict[str, Any]:
    """Return read-only metadata for a future ROS compressed overlay publish.

    This helper deliberately does not publish to ROS. It answers whether the
    currently cached overlay image is eligible for a future background publisher
    callback: a latest frame must exist, an overlay image must exist, and their
    frame sequences must match. Stale overlays are allowed only because they are
    visually marked stale by the renderer.
    """
    frame = _runtime_context().frame_store.latest(source)
    overlay_image = _latest_overlay_image(source)
    topic = _normalized_overlay_topic_for_source(source)
    message_type = 'sensor' + '_msgs/msg/CompressedImage'
    if frame is None:
        return {'payload_available': False, 'topic': topic, 'message_type': message_type, 'frame_seq': None, 'content_type': None, 'size_bytes': 0, 'reason': 'no latest frame has been ingested'}
    if overlay_image is None:
        return {'payload_available': False, 'topic': topic, 'message_type': message_type, 'frame_seq': frame.frame_seq, 'content_type': None, 'size_bytes': 0, 'reason': 'latest frame exists but no overlay image has been rendered'}
    if overlay_image.frame_seq != frame.frame_seq:
        return {'payload_available': False, 'topic': topic, 'message_type': message_type, 'frame_seq': overlay_image.frame_seq, 'content_type': overlay_image.content_type, 'size_bytes': len(overlay_image.jpeg), 'reason': 'overlay image frame_seq does not match latest frame_seq'}
    return {'payload_available': True, 'topic': topic, 'message_type': message_type, 'frame_seq': overlay_image.frame_seq, 'content_type': overlay_image.content_type, 'size_bytes': len(overlay_image.jpeg), 'reason': 'overlay image is ready for a future background ROS publisher'}

def _ros_publish_readiness(source: str) -> dict[str, Any]:
    frame = _runtime_context().frame_store.latest(source)
    overlay = _runtime_context().overlay_cache.latest(source)
    latest_frame_seq = frame.frame_seq if frame is not None else None
    latest_overlay_frame_seq = overlay.get('frame_seq') if overlay else None
    overlay_visual_state = overlay.get('visual_state') if overlay else None
    event_count = overlay.get('event_count') if overlay else None
    if frame is None:
        readiness_state = 'no_frame'
        overlay_ready = False
        reason = 'no latest frame has been ingested'
    elif overlay is None:
        readiness_state = 'no_overlay'
        overlay_ready = False
        reason = 'latest frame exists but no overlay has been rendered'
    elif latest_overlay_frame_seq != latest_frame_seq:
        readiness_state = 'overlay_lag'
        overlay_ready = False
        reason = 'overlay frame_seq does not match latest frame_seq'
    elif overlay.get('stale') is True or overlay_visual_state == 'stale':
        readiness_state = 'ready_stale'
        overlay_ready = True
        reason = 'latest overlay matches latest frame and is visually marked stale'
    else:
        readiness_state = 'ready_fresh'
        overlay_ready = True
        reason = 'latest overlay matches latest frame'
    return {'latest_frame_seq': latest_frame_seq, 'latest_overlay_frame_seq': latest_overlay_frame_seq, 'frame_age_s': round(_frame_age_s(frame), 3) if frame is not None else None, 'overlay_ready': overlay_ready, 'readiness_state': readiness_state, 'overlay_visual_state': overlay_visual_state, 'event_count': event_count, 'publish_payload_preview': _overlay_publish_payload_preview_for_source(source), 'runtime_plan': _ros_publish_runtime_plan(source), 'reason': reason}

def _ros_evidence_event_publish_readiness(source: str) -> dict[str, Any]:
    latest_events = _runtime_context().store.latest(source=source, limit=1)
    latest_event = latest_events[0] if latest_events else None
    event_available = latest_event is not None
    return {'event_available': event_available, 'publish_ready': event_available, 'topic': '/sf/vision/events', 'message_type': 'smartfactory_msgs/msg/VisionEvent or JSON bridge payload', 'schema_version': latest_event.get('schema_version') if latest_event else None, 'latest_event_id': latest_event.get('event_id') if latest_event else None, 'latest_event_kind': latest_event.get('event_kind') if latest_event else None, 'latest_event_timestamp': latest_event.get('timestamp') if latest_event else None, 'dedup_key': 'event_id', 'payload_contains_image_bytes': False, 'policy': _ros_evidence_event_publish_policy(), 'reason': 'latest schema-valid VisionEvent is available for future ROS evidence publisher' if event_available else 'no VisionEvent is available for this source'}

def _ros_evidence_event_publish_readiness_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ready_count = sum((1 for row in rows if row['evidence_event_publish_readiness']['publish_ready']))
    return {'sources_total': len(rows), 'publish_ready_count': ready_count, 'no_event_count': len(rows) - ready_count}

def _ros_publish_readiness_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    status_counts = {'no_frame': 0, 'no_overlay': 0, 'overlay_lag': 0, 'ready_fresh': 0, 'ready_stale': 0}
    for row in rows:
        state = row['publish_readiness']['readiness_state']
        if state in status_counts:
            status_counts[state] += 1
    publish_payload_available_count = sum((1 for row in rows if row['publish_readiness']['publish_payload_preview']['payload_available']))
    return {'sources_total': len(rows), 'overlay_ready_count': status_counts['ready_fresh'] + status_counts['ready_stale'], 'publish_payload_available_count': publish_payload_available_count, 'publish_payload_blocked_count': len(rows) - publish_payload_available_count, 'overlay_lag_count': status_counts['overlay_lag'], 'no_overlay_count': status_counts['no_overlay'], 'no_frame_count': status_counts['no_frame'], 'status_counts': status_counts}

def _ros_ingest_readiness(source: str, physical_topic: str | None) -> dict[str, Any]:
    topic_configured = bool(physical_topic)
    readiness_state = 'contract_ready' if topic_configured else 'missing_physical_topic'
    reason = 'source registry has a physical ROS image topic; Lane C can attach a background subscriber' if topic_configured else 'no physical ROS image topic is configured for this source'
    return {'readiness_state': readiness_state, 'physical_input_topic_configured': topic_configured, 'physical_input_message_type': _physical_input_message_type_for_source(source), 'physical_input_content_type': _physical_input_content_type_for_source(source), 'physical_input_transport': _physical_input_transport_for_source(source), 'runtime_subscriber_active': False, 'http_debug_ingest_path': '/api/v1/vision/frame', 'required_qos_profile': _ros_sensor_qos_policy(), 'frame_drop_policy': _ros_frame_drop_policy(), 'runtime_plan': _ros_ingest_runtime_plan(source), 'reason': reason}

def _ros_ingest_readiness_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    status_counts = {'contract_ready': 0, 'missing_physical_topic': 0}
    for row in rows:
        state = row['ingest_readiness']['readiness_state']
        if state in status_counts:
            status_counts[state] += 1
    return {'sources_total': len(rows), 'contract_ready_count': status_counts['contract_ready'], 'missing_physical_topic_count': status_counts['missing_physical_topic'], 'runtime_subscriber_active_count': sum((1 for row in rows if row['ingest_readiness']['runtime_subscriber_active'])), 'status_counts': status_counts}

def _frame_overlay_sync_status(source: str) -> dict[str, Any]:
    frame = _runtime_context().frame_store.latest(source)
    overlay = _runtime_context().overlay_cache.latest(source)
    frame_seq = frame.frame_seq if frame is not None else None
    overlay_frame_seq = overlay.get('frame_seq') if isinstance(overlay, dict) else None
    overlay_lag_frames = max(0, frame_seq - overlay_frame_seq) if isinstance(frame_seq, int) and isinstance(overlay_frame_seq, int) else None
    return {'latest_frame_seq': frame_seq, 'latest_overlay_frame_seq': overlay_frame_seq, 'overlay_lag_frames': overlay_lag_frames, 'overlay_visual_state': overlay.get('visual_state') if isinstance(overlay, dict) else None}

def _source_topic_rows() -> list[dict[str, Any]]:
    """Build the ROS2/domain-bridge handoff matrix without starting ROS2.

    This is a contract/readiness helper for Lane B. It intentionally exposes no
    motion topics and does not subscribe/publish to ROS2 at HTTP request time.
    """
    settings = get_settings()
    rows: list[dict[str, Any]] = []
    for source in settings.source_ids:
        physical_topic = _physical_input_topic_for_source(source)
        rows.append({'source': source, 'kind': _source_kind(source), 'robot_id': _robot_id_for_source(source), 'frame_id': _frame_id_for_source(source), 'physical_input_topic': physical_topic, 'physical_input_message_type': _physical_input_message_type_for_source(source), 'physical_input_content_type': _physical_input_content_type_for_source(source), 'physical_input_transport': _physical_input_transport_for_source(source), 'legacy_browser_topic': _legacy_browser_topic_for_source(source), 'legacy_browser_message_type': _legacy_browser_message_type_for_source(source), 'normalized_image_topic': _normalized_image_topic_for_source(source), 'normalized_image_message_type': 'sensor' + '_msgs/msg/CompressedImage', 'normalized_overlay_topic': _normalized_overlay_topic_for_source(source), 'normalized_overlay_message_type': 'sensor' + '_msgs/msg/CompressedImage', 'evidence_event_topic': _evidence_event_topic_for_source(source), 'evidence_event_message_type': 'smartfactory_msgs/msg/VisionEvent or JSON bridge payload', 'evidence_event_publish_policy': _ros_evidence_event_publish_policy(), 'evidence_event_publish_readiness': _ros_evidence_event_publish_readiness(source), 'topic_exposure': _source_topic_exposure(source, physical_topic), 'qos_profile': _ros_sensor_qos_policy(), 'frame_drop_policy': _ros_frame_drop_policy(), 'overlay_publish_qos': _ros_overlay_publish_qos_policy(), 'overlay_publish_policy': _ros_overlay_publish_policy(), 'ingest_readiness': _ros_ingest_readiness(source, physical_topic), 'publish_readiness': _ros_publish_readiness(source), 'ingest_status': 'planned', 'overlay_publish_status': 'planned'})
    return rows

def _ensure_known_source(source: str) -> None:
    if source not in get_settings().source_ids:
        raise HTTPException(status_code=400, detail=f'unknown source: {source}')

def _store_overlay_result(result: OverlayRenderResult) -> None:
    _runtime_context().overlay_cache.add(result.metadata())
    with _runtime_context().overlay_images_lock:
        _runtime_context().overlay_images[result.source] = result

def _latest_overlay_image(
    source: str,
    *,
    runtime_context: RuntimeContext | None = None,
) -> OverlayRenderResult | None:
    context = runtime_context or _runtime_context()
    with context.overlay_images_lock:
        return context.overlay_images.get(source)

def _now_dt() -> datetime:
    return datetime.now(timezone.utc).astimezone()

def _now_iso() -> str:
    return _now_dt().isoformat()

def _frame_age_s(frame: StoredFrame, *, now: datetime | None=None) -> float:
    current = now or _now_dt()
    timestamp = datetime.fromisoformat(frame.timestamp)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return max(0.0, (current - timestamp).total_seconds())

def _zero_stream_metrics() -> dict[str, Any]:
    return {'clients_total': 0, 'active_clients': 0, 'frames_sent_total': 0, 'stale_polls_total': 0, 'approx_fps': 0.0}

def _metrics_snapshot_for_source(snapshot: dict[str, Any], source: str | None) -> dict[str, Any]:
    if source is None:
        return snapshot
    filtered = dict(snapshot)
    stream = dict(snapshot.get('stream', {}))
    stream_by_source = dict(stream.get('by_source', {}))
    selected_stream = dict(stream_by_source.get(source, _zero_stream_metrics()))
    stream['by_source'] = {source: selected_stream}
    stream['clients_total'] = int(selected_stream.get('clients_total') or 0)
    stream['active_clients_total'] = int(selected_stream.get('active_clients') or 0)
    stream['frames_sent_total'] = int(selected_stream.get('frames_sent_total') or 0)
    stream['stale_polls_total'] = int(selected_stream.get('stale_polls_total') or 0)
    filtered['stream'] = stream
    worker = dict(snapshot.get('worker', {}))
    worker_by_source = dict(worker.get('by_source', {}))
    selected_worker = dict(worker_by_source.get(source, {}))
    worker['by_source'] = {source: selected_worker}
    worker['tick_total'] = dict(sorted(selected_worker.items()))
    filtered['worker'] = worker
    return filtered

def _frame_store_stats_for_source(source: str | None) -> dict[str, Any]:
    stats = _runtime_context().frame_store.stats()
    if source is None:
        return stats
    seq_by_source = dict(stats.get('frame_seq_by_source', {}))
    dropped_by_source = dict(stats.get('dropped_frames_by_source', {}))
    selected_seq = {source: seq_by_source[source]} if source in seq_by_source else {}
    selected_dropped = {source: dropped_by_source[source]} if source in dropped_by_source else {}
    return {'sources_with_frames': 1 if selected_seq else 0, 'frame_seq_by_source': selected_seq, 'dropped_frames_by_source': selected_dropped, 'dropped_frames_total': int(selected_dropped.get(source, 0))}

def _pose_confidence(pose: MarkerPose) -> float:
    return round(max(0.0, min(1.0, 1.0 - pose.reprojection_error_px / 5.0)), 3)

def _pose_estimate_payload(pose: MarkerPose) -> dict[str, Any]:
    return {'method': 'ARUCO_POSE', 'x': pose.lateral_m, 'y': pose.distance_m, 'yaw': pose.yaw_rad, 'confidence': _pose_confidence(pose)}

def build_marker_event(*, source: str, detection: MarkerDetection, image_width: int, image_height: int, latency_ms: float | None=None, pose: MarkerPose | None=None) -> dict[str, Any]:
    """Build a schema-valid VisionEvent from a deterministic marker detection."""
    settings = get_settings()
    event: dict[str, Any] = {'schema_version': settings.vision_event_schema_version, 'event_id': str(uuid4()), 'timestamp': _now_iso(), 'source': source, 'robot_id': _robot_id_for_source(source), 'frame_id': _frame_id_for_source(source), 'event_kind': 'CONFIRMED', 'class_name': detection.class_name, 'confidence': detection.confidence, 'bbox_xyxy': detection.bbox_xyxy, 'marker_id': detection.marker_id, 'zone': None, 'roi_id': None, 'track_id': None, 'pose_estimate': _pose_estimate_payload(pose) if pose is not None else None, 'depth_median_m': None, 'wms_hint': 'TAG_DETECTED', 'metadata': {'n_frame_count': 1, 'policy_version': settings.policy_version, 'model': detection.detector, 'image_width': image_width, 'image_height': image_height, 'latency_ms': latency_ms}}
    validate_vision_event(event)
    return event

def _normalize_public_model_class(raw_class_name: str) -> str:
    settings = get_settings()
    try:
        class_map = _parse_vision_model_class_map(settings.vision_model_class_map_json)
    except ModelAdapterError:
        class_map = {}
    mapped = class_map.get(raw_class_name, raw_class_name)
    allowed = {'person', 'obstacle', 'box', 'dropped_item', 'pallet', 'unknown'}
    if mapped in allowed:
        return mapped
    fallback = settings.vision_model_unmapped_class
    return fallback if fallback in allowed else 'unknown'

def _model_wms_hint(class_name: str) -> str | None:
    return {'person': 'PERSON_CANDIDATE', 'obstacle': 'OBSTACLE_CANDIDATE', 'box': 'ITEM_CANDIDATE', 'pallet': 'ITEM_CANDIDATE', 'dropped_item': 'DROPPED_ITEM_CANDIDATE'}.get(class_name)

def _bbox_payload(result: DetectorResult) -> list[float]:
    bbox = getattr(result, 'bbox_xyxy')
    return [float(value) for value in bbox]

def build_model_event(*, source: str, result: DetectorResult, image_width: int, image_height: int, latency_ms: float | None=None) -> dict[str, Any]:
    """Build a candidate VisionEvent from optional model output for ROS overlay streaming."""
    settings = get_settings()
    class_name = _normalize_public_model_class(str(getattr(result, 'class_name', 'unknown')))
    event: dict[str, Any] = {'schema_version': settings.vision_event_schema_version, 'event_id': str(uuid4()), 'timestamp': _now_iso(), 'source': source, 'robot_id': _robot_id_for_source(source), 'frame_id': _frame_id_for_source(source), 'event_kind': 'CANDIDATE', 'class_name': class_name, 'confidence': float(getattr(result, 'confidence', 0.0)), 'bbox_xyxy': _bbox_payload(result), 'marker_id': None, 'zone': None, 'roi_id': None, 'track_id': getattr(result, 'track_id', None), 'pose_estimate': None, 'depth_median_m': None, 'wms_hint': _model_wms_hint(class_name), 'metadata': {'n_frame_count': 1, 'policy_version': settings.policy_version, 'model': getattr(result, 'detector', None), 'image_width': image_width, 'image_height': image_height, 'latency_ms': latency_ms}}
    validate_vision_event(event)
    return event

def _parse_dist_coeffs(value: str | None) -> tuple[float, ...]:
    if value is None or value.strip() == '':
        return ()
    try:
        return tuple((float(part.strip()) for part in value.split(',') if part.strip()))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail='camera_dist_coeffs must be comma-separated numbers') from exc

def _manual_pose_fields_present(*, marker_size_m: float | None, camera_fx: float | None, camera_fy: float | None, camera_cx: float | None, camera_cy: float | None, camera_dist_coeffs: str | None) -> bool:
    return any((value is not None for value in [marker_size_m, camera_fx, camera_fy, camera_cx, camera_cy, camera_dist_coeffs]))

def _optional_pose_request(*, pose_profile: str | None, marker_size_m: float | None, camera_fx: float | None, camera_fy: float | None, camera_cx: float | None, camera_cy: float | None, camera_dist_coeffs: str | None) -> PoseRequest | None:
    settings = get_settings()
    manual_present = _manual_pose_fields_present(marker_size_m=marker_size_m, camera_fx=camera_fx, camera_fy=camera_fy, camera_cx=camera_cx, camera_cy=camera_cy, camera_dist_coeffs=camera_dist_coeffs)
    if pose_profile is not None and pose_profile.strip():
        if manual_present:
            raise HTTPException(status_code=400, detail='pose_profile cannot be combined with manual camera calibration fields')
        try:
            return get_pose_profile(pose_profile, path=settings.aruco_pose_profiles_path)
        except PoseProfileError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    fields = [marker_size_m, camera_fx, camera_fy, camera_cx, camera_cy]
    if all((value is None for value in fields)) and (not camera_dist_coeffs):
        return None
    if any((value is None for value in fields)):
        raise HTTPException(status_code=400, detail='ArUco pose requires marker_size_m, camera_fx, camera_fy, camera_cx, and camera_cy together')
    assert marker_size_m is not None
    assert camera_fx is not None
    assert camera_fy is not None
    assert camera_cx is not None
    assert camera_cy is not None
    if marker_size_m <= 0:
        raise HTTPException(status_code=400, detail='marker_size_m must be positive')
    if camera_fx <= 0 or camera_fy <= 0:
        raise HTTPException(status_code=400, detail='camera_fx and camera_fy must be positive')
    return (marker_size_m, CameraIntrinsics(fx=camera_fx, fy=camera_fy, cx=camera_cx, cy=camera_cy, dist_coeffs=_parse_dist_coeffs(camera_dist_coeffs)))

def _estimate_detection_pose(*, source: str, detection: MarkerDetection, pose_request: PoseRequest | None) -> MarkerPose | None:
    if pose_request is None or not detection.corners_xy:
        return None
    if isinstance(pose_request, ArucoPoseProfile):
        if not pose_request.applies_to(source=source, marker_id=detection.marker_id):
            return None
        marker_size_m = pose_request.marker_size_m
        intrinsics = pose_request.intrinsics
    else:
        marker_size_m, intrinsics = pose_request
    try:
        return estimate_marker_pose(detection.corners_xy, marker_size_m=marker_size_m, intrinsics=intrinsics)
    except ValueError:
        return None

def _detect_and_overlay_frame_snapshot(*, frame: StoredFrame, pose_request: PoseRequest | None=None, stale: bool=False) -> dict[str, Any]:
    """Run marker detection on an already-stored latest-frame snapshot."""
    if frame.decoded_bgr is None:
        decoded_image = decode_image(frame.encoded)
    else:
        decoded_image = frame.decoded_bgr
    image_height, image_width = decoded_image.shape[:2]
    started = perf_counter()
    detections = detect_markers(decoded_image)
    latency_ms = round((perf_counter() - started) * 1000.0, 3)
    events = [build_marker_event(source=frame.source, detection=detection, image_width=image_width, image_height=image_height, latency_ms=latency_ms, pose=_estimate_detection_pose(source=frame.source, detection=detection, pose_request=pose_request)) for detection in detections]
    events.extend(_detect_model_events(source=frame.source, decoded_image=decoded_image, image_width=image_width, image_height=image_height))
    for event in events:
        _runtime_context().store.add(event)
        _runtime_context().source_health.record_event(event)
    overlay = render_overlay(frame, events=events, stale=stale)
    _store_overlay_result(overlay)
    _runtime_context().metrics.record_detect_image(event_count=len(events))
    return {'frame': frame, 'events': events, 'overlay': overlay}

def _store_latest_frame_from_bytes(*, source: str, payload: bytes, content_type: str) -> StoredFrame:
    """Decode and store one latest frame for HTTP debug ingest or future ROS callbacks.

    This adapter intentionally performs no detection, overlay rendering, ROS2
    spinning, or publishing. It is the common Lane B/C seam that a future
    background ROS subscriber callback can call after receiving an image
    message, while FastAPI handlers continue to read cached state only.
    """
    _ensure_known_source(source)
    decoded_image = decode_image(payload)
    frame = _runtime_context().frame_store.put_decoded(source=source, image_bgr=decoded_image, encoded=payload, content_type=content_type)
    _runtime_context().source_health.record_frame(source, at=_now_dt())
    return frame

def _frame_ingest_context(*, transport: str, topic: str | None, processed_inline: bool=False) -> dict[str, Any]:
    return {'transport': transport, 'topic': topic, 'stored_in_latest_frame_cache': True, 'processed_inline': processed_inline, 'source_health_updated': True, 'ros_callback_compatible': True}

def _detect_and_overlay_decoded_frame(*, source: str, decoded_image, encoded: bytes | None=None, content_type: str='image/jpeg', pose_request: PoseRequest | None=None, stale: bool=False) -> dict[str, Any]:
    """Store latest frame, run marker detection, update evidence overlay state."""
    _ensure_known_source(source)
    frame = _runtime_context().frame_store.put_decoded(source=source, image_bgr=decoded_image, encoded=encoded, content_type=content_type)
    _runtime_context().source_health.record_frame(source, at=_now_dt())
    return _detect_and_overlay_frame_snapshot(frame=frame, pose_request=pose_request, stale=stale)


def _model_worker_enabled(settings) -> bool:
    return bool(settings.vision_model_worker_enabled and settings.vision_model_path.strip())

def _detect_model_events(*, source: str, decoded_image, image_width: int, image_height: int) -> list[dict[str, Any]]:
    settings = get_settings()
    if not _model_worker_enabled(settings):
        return []
    try:
        provider = _lift_roi_segmenter()(model_path=settings.vision_model_path, task=settings.vision_model_task, confidence=settings.vision_model_conf, iou=settings.vision_model_iou, image_size=settings.vision_model_imgsz, device=settings.vision_model_device, class_map_json=settings.vision_model_class_map_json, unmapped_class=settings.vision_model_unmapped_class)
        started = perf_counter()
        detector_results = tuple(provider.detect(decoded_image))
        latency_ms = round((perf_counter() - started) * 1000.0, 3)
    except ModelAdapterError:
        return []
    max_events = max(0, int(settings.vision_model_max_events))
    model_events: list[dict[str, Any]] = []
    for result in detector_results[:max_events]:
        try:
            model_events.append(build_model_event(source=source, result=result, image_width=image_width, image_height=image_height, latency_ms=latency_ms))
        except (ContractValidationError, ValueError, TypeError):
            continue
    return model_events

def _vision_stream_source_entry(source: str, *, stream_metrics: dict[str, Any]) -> dict[str, Any]:
    physical_topic = _physical_input_topic_for_source(source)
    topic_exposure = _source_topic_exposure(source, physical_topic)
    return {'source': source, 'has_frame': _runtime_context().frame_store.latest(source) is not None, 'has_overlay': _runtime_context().overlay_cache.latest(source) is not None, **_frame_overlay_sync_status(source), 'topic_exposure': topic_exposure, 'rosbridge_subscription_hints': _rosbridge_subscription_hints(source, topic_exposure), 'ros_ingest_readiness': _ros_ingest_readiness(source, physical_topic), 'ros_publish_readiness': _ros_publish_readiness(source), 'evidence_event_publish_readiness': _ros_evidence_event_publish_readiness(source), 'frame_ingest_path': '/api/v1/vision/frame', 'mjpeg_path': f'/api/v1/vision/stream/{source}.mjpeg', 'mjpeg_default_max_fps': 10, 'frame_metadata_path': f'/api/v1/vision/frame/latest?source={source}', 'frame_image_path': f'/api/v1/vision/frame/latest/image?source={source}', 'overlay_metadata_path': f'/api/v1/vision/overlay/latest?source={source}', 'overlay_image_path': f'/api/v1/vision/overlay/latest/image?source={source}', 'source_snapshot_path': f'/api/v1/vision/debug/sources?source={source}', 'worker_status_path': f'/api/v1/vision/worker/status?source={source}', 'metrics_path': f'/api/v1/metrics?source={source}', 'ros_handoff_path': '/api/v1/vision/ros/topics', 'ros_handoff_source_path': f'/api/v1/vision/ros/topics?source={source}', 'stream_metrics': stream_metrics['by_source'].get(source, {'clients_total': 0, 'active_clients': 0, 'frames_sent_total': 0, 'stale_polls_total': 0, 'approx_fps': 0.0})}

def _vision_streams_summary(source_entries: list[dict[str, Any]]) -> dict[str, Any]:
    return {'sources_total': len(source_entries), 'with_frame_count': sum((1 for item in source_entries if item['has_frame'])), 'with_overlay_count': sum((1 for item in source_entries if item['has_overlay'])), 'overlay_lag_count': sum((1 for item in source_entries if isinstance(item.get('overlay_lag_frames'), int) and item['overlay_lag_frames'] > 0)), 'synced_overlay_count': sum((1 for item in source_entries if item.get('overlay_lag_frames') == 0)), 'stale_overlay_count': sum((1 for item in source_entries if item.get('overlay_visual_state') == 'stale')), 'ros_ingest_contract_ready_count': sum((1 for item in source_entries if item['ros_ingest_readiness']['readiness_state'] == 'contract_ready')), 'ros_ingest_runtime_subscriber_active_count': sum((1 for item in source_entries if item['ros_ingest_readiness']['runtime_subscriber_active'])), 'ros_ingest_status_counts': _count_by(source_entries, ('ros_ingest_readiness', 'readiness_state')), 'ros_publish_ready_count': sum((1 for item in source_entries if item['ros_publish_readiness']['overlay_ready'])), 'ros_publish_payload_available_count': sum((1 for item in source_entries if item['ros_publish_readiness']['publish_payload_preview']['payload_available'])), 'ros_publish_payload_blocked_count': sum((1 for item in source_entries if not item['ros_publish_readiness']['publish_payload_preview']['payload_available'])), 'ros_publish_status_counts': _count_by(source_entries, ('ros_publish_readiness', 'readiness_state')), 'evidence_event_publish_ready_count': sum((1 for item in source_entries if item['evidence_event_publish_readiness']['publish_ready']))}

def vision_streams(source: str | None=Query(default=None, json_schema_extra=SOURCE_ID_OPENAPI_EXTRA)) -> dict[str, Any]:
    """Describe Vision Gateway stream surfaces.

    Main-facing production browser video uses the source-selected HTTP/MJPEG
    Vision Stream Gateway on :8090. ROS/rosbridge is internal allowlisted
    operator/prototype infrastructure unless a future ADR promotes it.
    """
    settings = get_settings()
    if source is not None:
        _ensure_known_source(source)
    stream_metrics = _runtime_context().metrics.stream_snapshot()
    selected_sources = [source_id for source_id in settings.source_ids if source is None or source_id == source]
    source_entries = [_vision_stream_source_entry(source_id, stream_metrics=stream_metrics) for source_id in selected_sources]
    return {'generated_at': _now_iso(), 'requested_source': source, 'primary_stream_plane': 'http_mjpeg_gateway', 'stream_base_url': 'http://<vision-host>:8090', 'debug_only': False, 'motion_command_allowed': False, 'internal_rosbridge': {'scope': 'operator_prototype_only', 'url': 'ws://<vision-host>:9090', 'exposes_all_topics': False}, 'control_topics_published': [], 'summary': _vision_streams_summary(source_entries), 'topic_exposure_policy': _ros_topic_exposure_policy(), 'topic_exposure_summary': _topic_exposure_summary(source_entries), 'runtime_policy': _ros_runtime_policy(), 'debug_fallback': {'frame_ingest_path': '/api/v1/vision/frame', 'mjpeg_path_template': '/api/v1/vision/stream/{source}.mjpeg', 'mjpeg_max_fps_default': 10, 'mjpeg_max_fps_limit': 30, 'frame_metadata_path': '/api/v1/vision/frame/latest?source={source}', 'frame_image_path': '/api/v1/vision/frame/latest/image?source={source}', 'overlay_metadata_path': '/api/v1/vision/overlay/latest?source={source}', 'overlay_image_path': '/api/v1/vision/overlay/latest/image?source={source}', 'metrics_path': '/api/v1/metrics', 'source_snapshot_path': '/api/v1/vision/debug/sources', 'worker_status_path': '/api/v1/vision/worker/status', 'ros_handoff_path': '/api/v1/vision/ros/topics'}, 'sources': source_entries}

def vision_ros_topics(source: str | None=Query(default=None, json_schema_extra=SOURCE_ID_OPENAPI_EXTRA)) -> dict[str, Any]:
    """Return the read-only ROS2 topic handoff matrix for Lane B/C planning.

    This endpoint does not start ROS2, does not publish overlays, and does not
    expose motion control. It exists so GUI/Main/ROS developers can align on the
    source-to-topic contract before Lane C ROS ingest/domain bridge work.
    """
    if source is not None:
        _ensure_known_source(source)
    source_rows = [row for row in _source_topic_rows() if source is None or row['source'] == source]
    return {'generated_at': _now_iso(), 'requested_source': source, 'primary_stream_plane': 'http_mjpeg_gateway', 'stream_base_url': 'http://<vision-host>:8090', 'debug_only': True, 'internal_rosbridge': {'scope': 'operator_prototype_only', 'url': 'ws://<vision-host>:9090', 'exposes_all_topics': False}, 'motion_command_allowed': False, 'migration_policy': 'keep existing /mission browser topics; add /sf normalized topics in parallel', 'control_topics_published': [], 'topic_exposure_policy': _ros_topic_exposure_policy(), 'topic_exposure_summary': _topic_exposure_summary(source_rows), 'image_ingest_qos': _ros_sensor_qos_policy(), 'frame_drop_policy': _ros_frame_drop_policy(), 'overlay_publish_qos': _ros_overlay_publish_qos_policy(), 'overlay_publish_policy': _ros_overlay_publish_policy(), 'evidence_event_publish_policy': _ros_evidence_event_publish_policy(), 'runtime_policy': _ros_runtime_policy(), 'ingest_readiness_summary': _ros_ingest_readiness_summary(source_rows), 'publish_readiness_summary': _ros_publish_readiness_summary(source_rows), 'evidence_event_publish_readiness_summary': _ros_evidence_event_publish_readiness_summary(source_rows), 'notes': ['Main-facing browser video uses the source-selected HTTP/MJPEG :8090 gateway.', 'ROS/rosbridge metadata here is internal/operator handoff only.', 'Vision Gateway must not publish /cmd_vel or call Nav2 actions.', 'Lane C should subscribe/publish with sensor QoS, keep-last=1, and drop stale frames.'], 'sources': source_rows}

def _worker_tick_sources(requested_source: str | None) -> list[str]:
    settings = get_settings()
    if requested_source is not None:
        _ensure_known_source(requested_source)
        return [requested_source]
    return list(settings.source_ids)

def _worker_tick_result_for_source(*, source: str, force: bool, stale: bool, max_frame_age_s: float) -> dict[str, Any]:
    frame = _runtime_context().frame_store.latest(source)
    if frame is None:
        _runtime_context().metrics.record_worker_tick(source=source, status='no_frame')
        return {'source': source, 'status': 'no_frame', 'frame_seq': None, 'event_count': 0, 'new_event_count': 0, 'evidence_action': 'none', 'overlay': None, 'reason': 'no latest frame available'}
    frame_age_s = round(_frame_age_s(frame), 3)
    if not force and frame_age_s > max_frame_age_s:
        _runtime_context().metrics.record_worker_tick(source=source, status='stale_frame')
        return {'source': source, 'status': 'stale_frame', 'frame_seq': frame.frame_seq, 'frame_age_s': frame_age_s, 'max_frame_age_s': max_frame_age_s, 'event_count': 0, 'new_event_count': 0, 'evidence_action': 'none', 'overlay': None, 'reason': 'latest frame is older than max_frame_age_s'}
    latest_overlay_metadata = _runtime_context().overlay_cache.latest(source)
    overlay_frame_seq = latest_overlay_metadata.get('frame_seq') if isinstance(latest_overlay_metadata, dict) else None
    if not force and isinstance(overlay_frame_seq, int) and (overlay_frame_seq >= frame.frame_seq):
        _runtime_context().metrics.record_worker_tick(source=source, status='skipped')
        return {'source': source, 'status': 'skipped', 'frame_seq': frame.frame_seq, 'frame_age_s': frame_age_s, 'max_frame_age_s': max_frame_age_s, 'event_count': int(latest_overlay_metadata.get('event_count', 0)), 'new_event_count': 0, 'evidence_action': 'reused', 'overlay': latest_overlay_metadata, 'reason': 'latest overlay already matches latest frame'}
    processed = _detect_and_overlay_frame_snapshot(frame=frame, stale=stale)
    overlay: OverlayRenderResult = processed['overlay']
    new_event_count = len(processed['events'])
    _runtime_context().metrics.record_worker_tick(source=source, status='processed')
    return {'source': source, 'status': 'processed', 'frame_seq': frame.frame_seq, 'frame_age_s': frame_age_s, 'max_frame_age_s': max_frame_age_s, 'event_count': new_event_count, 'new_event_count': new_event_count, 'evidence_action': 'created', 'overlay': overlay.metadata(), 'reason': 'forced' if force else 'new frame processed'}

def _worker_status_for_source(*, source: str, max_frame_age_s: float) -> dict[str, Any]:
    frame = _runtime_context().frame_store.latest(source)
    latest_overlay_metadata = _runtime_context().overlay_cache.latest(source)
    overlay_frame_seq = latest_overlay_metadata.get('frame_seq') if isinstance(latest_overlay_metadata, dict) else None
    if frame is None:
        return {'source': source, 'has_frame': False, 'has_overlay': latest_overlay_metadata is not None, 'latest_frame_seq': None, 'latest_overlay_frame_seq': overlay_frame_seq, 'frame_age_s': None, 'max_frame_age_s': max_frame_age_s, 'overlay_lag_frames': None, 'pending': False, 'next_tick_status': 'no_frame', 'would_create_new_evidence': False, 'evidence_action_if_ticked': 'none', 'expected_new_event_count': 0, 'reused_event_count_if_ticked': 0, 'reason': 'no latest frame available'}
    frame_age_s = round(_frame_age_s(frame), 3)
    overlay_lag_frames = max(0, frame.frame_seq - overlay_frame_seq) if isinstance(overlay_frame_seq, int) else None
    if frame_age_s > max_frame_age_s:
        next_status = 'stale_frame'
        pending = False
        would_create_new_evidence = False
        evidence_action_if_ticked = 'none'
        expected_new_event_count = 0
        reused_event_count_if_ticked = 0
        reason = 'latest frame is older than max_frame_age_s'
    elif isinstance(overlay_frame_seq, int) and overlay_frame_seq >= frame.frame_seq:
        next_status = 'skipped'
        pending = False
        would_create_new_evidence = False
        evidence_action_if_ticked = 'reused'
        expected_new_event_count = 0
        reused_event_count_if_ticked = int(latest_overlay_metadata.get('event_count', 0))
        reason = 'latest overlay already matches latest frame'
    else:
        next_status = 'processed'
        pending = True
        would_create_new_evidence = True
        evidence_action_if_ticked = 'created'
        expected_new_event_count = None
        reused_event_count_if_ticked = 0
        reason = 'new frame pending processing'
    return {'source': source, 'has_frame': True, 'has_overlay': latest_overlay_metadata is not None, 'latest_frame_seq': frame.frame_seq, 'latest_overlay_frame_seq': overlay_frame_seq, 'frame_age_s': frame_age_s, 'max_frame_age_s': max_frame_age_s, 'overlay_lag_frames': overlay_lag_frames, 'pending': pending, 'next_tick_status': next_status, 'would_create_new_evidence': would_create_new_evidence, 'evidence_action_if_ticked': evidence_action_if_ticked, 'expected_new_event_count': expected_new_event_count, 'reused_event_count_if_ticked': reused_event_count_if_ticked, 'reason': reason}

def _worker_status_summary(items: list[dict[str, Any]]) -> dict[str, Any]:
    status_counts = {'no_frame': 0, 'processed': 0, 'skipped': 0, 'stale_frame': 0}
    pending_count = 0
    stale_count = 0
    would_create_new_evidence_count = 0
    expected_new_event_count_total = 0
    reused_event_count_if_ticked_total = 0
    for item in items:
        status = str(item.get('next_tick_status') or '')
        if status in status_counts:
            status_counts[status] += 1
        if item.get('pending') is True:
            pending_count += 1
        if item.get('would_create_new_evidence') is True:
            would_create_new_evidence_count += 1
        if isinstance(item.get('expected_new_event_count'), int):
            expected_new_event_count_total += int(item['expected_new_event_count'])
        reused_event_count_if_ticked_total += int(item.get('reused_event_count_if_ticked') or 0)
        if status == 'stale_frame':
            stale_count += 1
    return {'sources_total': len(items), 'pending_count': pending_count, 'stale_frame_count': stale_count, 'would_create_new_evidence_count': would_create_new_evidence_count, 'expected_new_event_count_total': expected_new_event_count_total, 'reused_event_count_if_ticked_total': reused_event_count_if_ticked_total, 'status_counts': status_counts}

def _worker_result_summary(items: list[dict[str, Any]]) -> dict[str, Any]:
    status_counts = {'no_frame': 0, 'processed': 0, 'skipped': 0, 'stale_frame': 0}
    event_count_total = 0
    new_event_count_total = 0
    reused_event_count_total = 0
    for item in items:
        status = str(item.get('status') or '')
        if status in status_counts:
            status_counts[status] += 1
        event_count = int(item.get('event_count') or 0)
        new_event_count = int(item.get('new_event_count') or 0)
        event_count_total += event_count
        new_event_count_total += new_event_count
        if item.get('evidence_action') == 'reused':
            reused_event_count_total += event_count
    return {'sources_total': len(items), 'processed_count': status_counts['processed'], 'skipped_count': status_counts['skipped'], 'stale_frame_count': status_counts['stale_frame'], 'event_count_total': event_count_total, 'new_event_count_total': new_event_count_total, 'reused_event_count_total': reused_event_count_total, 'status_counts': status_counts}

def vision_worker_status(source: str | None=Query(default=None, json_schema_extra=SOURCE_ID_OPENAPI_EXTRA), max_frame_age_s: float | None=Query(default=None, ge=0)) -> dict[str, Any]:
    """Return what the next worker tick would do without processing frames."""
    sources = _worker_tick_sources(source)
    settings = get_settings()
    resolved_max_frame_age_s = max_frame_age_s if max_frame_age_s is not None else settings.source_stale_after_s
    status_items = [_worker_status_for_source(source=item, max_frame_age_s=resolved_max_frame_age_s) for item in sources]
    return {'generated_at': _now_iso(), 'requested_source': source, 'max_frame_age_s': resolved_max_frame_age_s, 'debug_only': True, 'summary': _worker_status_summary(status_items), 'sources': status_items}

def vision_worker_tick(payload: VisionWorkerTickRequest) -> dict[str, Any]:
    """Run one controlled latest-frame processing tick for Lane B validation.

    This is a robot-free debug/control surface for the future evidence worker.
    It processes only explicit configured sources and never publishes ROS motion
    commands. Main-facing production browser video uses the source-selected
    HTTP/MJPEG Vision Stream Gateway on :8090; rosbridge is internal allowlisted
    operator/prototype infrastructure only.
    """
    sources = _worker_tick_sources(payload.source)
    settings = get_settings()
    max_frame_age_s = payload.max_frame_age_s if payload.max_frame_age_s is not None else settings.source_stale_after_s
    results = [_worker_tick_result_for_source(source=source, force=payload.force, stale=payload.stale, max_frame_age_s=max_frame_age_s) for source in sources]
    return {'generated_at': _now_iso(), 'requested_source': payload.source, 'force': payload.force, 'stale': payload.stale, 'max_frame_age_s': max_frame_age_s, 'summary': _worker_result_summary(results), 'results': results}

def _default_stream_metrics() -> dict[str, Any]:
    return {'clients_total': 0, 'active_clients': 0, 'frames_sent_total': 0, 'stale_polls_total': 0, 'approx_fps': 0.0}

def _count_by(items: list[dict[str, Any]], key_path: tuple[str, ...]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        value: Any = item
        for key in key_path:
            value = value[key]
        counts[str(value)] = counts.get(str(value), 0) + 1
    return counts

def _debug_sources_summary(source_entries: list[dict[str, Any]]) -> dict[str, Any]:
    health_status_counts = _count_by(source_entries, ('health', 'status'))
    ros_ingest_status_counts = _count_by(source_entries, ('ros_ingest_readiness', 'readiness_state'))
    ros_publish_status_counts = _count_by(source_entries, ('ros_publish_readiness', 'readiness_state'))
    return {'sources_total': len(source_entries), 'with_frame_count': sum((1 for item in source_entries if item['latest_frame'] is not None)), 'with_overlay_count': sum((1 for item in source_entries if item['latest_overlay'] is not None)), 'overlay_lag_count': sum((1 for item in source_entries if isinstance(item.get('overlay_lag_frames'), int) and item['overlay_lag_frames'] > 0)), 'ros_ingest_contract_ready_count': ros_ingest_status_counts.get('contract_ready', 0), 'ros_publish_ready_count': sum((1 for item in source_entries if item['ros_publish_readiness']['overlay_ready'])), 'ros_publish_payload_available_count': sum((1 for item in source_entries if item['ros_publish_readiness']['publish_payload_preview']['payload_available'])), 'evidence_event_publish_ready_count': sum((1 for item in source_entries if item['evidence_event_publish_readiness']['publish_ready'])), 'stale_overlay_count': ros_publish_status_counts.get('ready_stale', 0), 'health_status_counts': health_status_counts, 'ros_ingest_status_counts': ros_ingest_status_counts, 'ros_publish_status_counts': ros_publish_status_counts}

def _debug_source_snapshot(source: str, *, stream_metrics: dict[str, Any], frame_stats: dict[str, Any]) -> dict[str, Any]:
    settings = get_settings()
    health_snapshot = _runtime_context().source_health.snapshot(source, now=_now_dt(), stale_after_s=settings.source_stale_after_s, offline_after_s=settings.source_offline_after_s)
    frame = _runtime_context().frame_store.latest(source)
    overlay = _runtime_context().overlay_cache.latest(source)
    physical_topic = _physical_input_topic_for_source(source)
    topic_exposure = _source_topic_exposure(source, physical_topic)
    sync_status = _frame_overlay_sync_status(source)
    return {'source': source, 'kind': _source_kind(source), 'robot_id': _robot_id_for_source(source), 'health': {'enabled': health_snapshot.enabled, 'status': health_snapshot.status, 'last_frame_at': health_snapshot.last_frame_at, 'last_frame_age_s': health_snapshot.last_frame_age_s, 'last_event_at': health_snapshot.last_event_at, 'last_event_kind': health_snapshot.last_event_kind, 'last_event_id': health_snapshot.last_event_id, 'last_marker_id': health_snapshot.last_marker_id, 'frame_count': health_snapshot.frame_count, 'event_count': health_snapshot.event_count}, 'latest_frame': frame.metadata(include_content=True) if frame is not None else None, 'latest_overlay': overlay, 'overlay_lag_frames': sync_status['overlay_lag_frames'], 'topic_exposure': topic_exposure, 'rosbridge_subscription_hints': _rosbridge_subscription_hints(source, topic_exposure), 'ros_ingest_readiness': _ros_ingest_readiness(source, physical_topic), 'ros_publish_readiness': _ros_publish_readiness(source), 'evidence_event_publish_readiness': _ros_evidence_event_publish_readiness(source), 'debug_paths': {'frame_ingest': '/api/v1/vision/frame', 'mjpeg': f'/api/v1/vision/stream/{source}.mjpeg', 'mjpeg_default_max_fps': 10, 'frame_metadata': f'/api/v1/vision/frame/latest?source={source}', 'frame_image': f'/api/v1/vision/frame/latest/image?source={source}', 'overlay_metadata': f'/api/v1/vision/overlay/latest?source={source}', 'overlay_image': f'/api/v1/vision/overlay/latest/image?source={source}', 'worker_tick': '/api/v1/vision/worker/tick', 'worker_status': f'/api/v1/vision/worker/status?source={source}', 'metrics': f'/api/v1/metrics?source={source}', 'metrics_all': '/api/v1/metrics', 'ros_handoff': f'/api/v1/vision/ros/topics?source={source}', 'ros_handoff_all': '/api/v1/vision/ros/topics'}, 'stream_metrics': stream_metrics['by_source'].get(source, _default_stream_metrics()), 'drop_metrics': {'dropped_frames': frame_stats.get('dropped_frames_by_source', {}).get(source, 0)}}

def vision_debug_sources(source: str | None=Query(default=None, json_schema_extra=SOURCE_ID_OPENAPI_EXTRA)) -> dict[str, Any]:
    """Return one-shot source/frame/overlay readiness snapshots for Lane B debug use."""
    settings = get_settings()
    if source is not None:
        _ensure_known_source(source)
        sources = [source]
    else:
        sources = list(settings.source_ids)
    stream_metrics = _runtime_context().metrics.stream_snapshot()
    frame_stats = _runtime_context().frame_store.stats()
    source_entries = [_debug_source_snapshot(source=item, stream_metrics=stream_metrics, frame_stats=frame_stats) for item in sources]
    return {'generated_at': _now_iso(), 'requested_source': source, 'primary_stream_plane': 'http_mjpeg_gateway', 'stream_base_url': 'http://<vision-host>:8090', 'debug_only': True, 'summary': _debug_sources_summary(source_entries), 'topic_exposure_policy': _ros_topic_exposure_policy(), 'topic_exposure_summary': _topic_exposure_summary(source_entries), 'sources': source_entries}

async def ingest_frame(source: str=Form(..., json_schema_extra=SOURCE_ID_OPENAPI_EXTRA), image: UploadFile=File(...)) -> dict[str, Any]:
    """Store one raw frame in the latest-frame cache without detection.

    This is a Lane B robot-free seam for future ROS2/camera ingest. It lets
    callers push a frame, inspect it with `/vision/frame/latest`, and then run
    `/vision/worker/tick` to process it. It is not the production browser stream
    plane and it does not publish ROS motion commands.
    """
    payload = await image.read()
    content_type = image.content_type or 'application/octet-stream'
    try:
        frame = _store_latest_frame_from_bytes(source=source, payload=payload, content_type=content_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {'source': source, 'processed': False, 'frame': frame.metadata(include_content=True), 'overlay': None, 'ingest_context': _frame_ingest_context(transport='http_debug', topic=None), 'worker_tick_path': '/api/v1/vision/worker/tick'}

async def ingest_and_process_frame(source: str=Form(..., json_schema_extra=SOURCE_ID_OPENAPI_EXTRA), image: UploadFile=File(...), force: bool=Form(default=True), stale: bool=Form(default=False)) -> dict[str, Any]:
    """Store one raw frame and immediately render AI/detection overlay.

    This ROS-free endpoint is optimized for the D1 gateway hot path: one HTTP
    request updates the latest-frame cache and overlay cache, avoiding the older
    frame POST -> worker tick race. It still publishes no ROS/control topics.
    """
    payload = await image.read()
    content_type = image.content_type or 'application/octet-stream'
    try:
        frame = _store_latest_frame_from_bytes(source=source, payload=payload, content_type=content_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    latest_overlay_metadata = _runtime_context().overlay_cache.latest(source)
    overlay_frame_seq = latest_overlay_metadata.get('frame_seq') if isinstance(latest_overlay_metadata, dict) else None
    if not force and isinstance(overlay_frame_seq, int) and (overlay_frame_seq >= frame.frame_seq):
        return {'source': source, 'processed': False, 'status': 'skipped', 'frame_seq': frame.frame_seq, 'event_count': int(latest_overlay_metadata.get('event_count', 0)), 'new_event_count': 0, 'evidence_action': 'reused', 'frame': frame.metadata(include_content=True), 'overlay': latest_overlay_metadata, 'reason': 'latest overlay already matches latest frame', 'ingest_context': _frame_ingest_context(transport='http_debug', topic=None, processed_inline=True)}
    processed = _detect_and_overlay_frame_snapshot(frame=frame, stale=stale)
    overlay: OverlayRenderResult = processed['overlay']
    events = processed['events']
    return {'source': source, 'processed': True, 'status': 'processed', 'frame_seq': frame.frame_seq, 'event_count': len(events), 'new_event_count': len(events), 'evidence_action': 'created', 'frame': frame.metadata(include_content=True), 'overlay': overlay.metadata(), 'events': events, 'reason': 'forced' if force else 'new frame processed', 'ingest_context': _frame_ingest_context(transport='http_debug', topic=None, processed_inline=True)}

def latest_frame(source: str=Query(..., json_schema_extra=SOURCE_ID_OPENAPI_EXTRA)) -> dict[str, Any]:
    """Return latest raw frame metadata for one source.

    This is a Lane B debug/fallback endpoint for visual QA. It exposes only the
    newest cached frame and does not queue historical frames.
    """
    _ensure_known_source(source)
    frame = _runtime_context().frame_store.latest(source)
    if frame is None:
        raise HTTPException(status_code=404, detail=f'no latest frame available for source: {source}')
    return {'generated_at': _now_iso(), 'frame': frame.metadata(include_content=True)}

def latest_frame_image(source: str=Query(..., json_schema_extra=SOURCE_ID_OPENAPI_EXTRA)) -> Response:
    """Return latest raw frame image for one source.

    This is a debug/fallback image endpoint for comparing raw frame evidence
    against rendered overlays. Main-facing production browser streaming uses the
    source-selected HTTP/MJPEG Vision Stream Gateway on :8090; rosbridge is
    internal allowlisted operator/prototype infrastructure only.
    """
    _ensure_known_source(source)
    frame = _runtime_context().frame_store.latest(source)
    if frame is None:
        raise HTTPException(status_code=404, detail=f'no latest frame image available for source: {source}')
    return Response(content=frame.encoded, media_type=frame.content_type)

def latest_overlay(source: str=Query(..., json_schema_extra=SOURCE_ID_OPENAPI_EXTRA)) -> dict[str, Any]:
    """Return latest visual evidence overlay metadata for one source."""
    _ensure_known_source(source)
    overlay = _runtime_context().overlay_cache.latest(source)
    if overlay is None:
        raise HTTPException(status_code=404, detail=f'no overlay available for source: {source}')
    return {'generated_at': _now_iso(), 'requested_source': source, 'sync': _frame_overlay_sync_status(source), 'overlay': overlay}

def latest_overlay_image(source: str=Query(..., json_schema_extra=SOURCE_ID_OPENAPI_EXTRA)) -> Response:
    """Return latest overlay image for one source as JPEG."""
    _ensure_known_source(source)
    overlay = _latest_overlay_image(source)
    if overlay is None:
        raise HTTPException(status_code=404, detail=f'no overlay image available for source: {source}')
    return Response(content=overlay.jpeg, media_type=overlay.content_type)

async def _mjpeg_latest_overlay_generator(
    source: str,
    *,
    max_fps: int,
    runtime_context: RuntimeContext | None = None,
):
    context = runtime_context or _runtime_context()
    last_frame_seq = 0
    last_send_at = 0.0
    min_interval_s = 1.0 / float(max_fps)
    context.metrics.record_stream_client_opened(source=source)
    try:
        while True:
            overlay = _latest_overlay_image(source, runtime_context=context)
            if overlay is None or overlay.frame_seq == last_frame_seq:
                context.metrics.record_stream_stale_poll(source=source)
                await asyncio.sleep(0.05)
                continue
            now = perf_counter()
            wait_s = min_interval_s - (now - last_send_at)
            if wait_s > 0:
                await asyncio.sleep(wait_s)
            last_frame_seq = overlay.frame_seq
            last_send_at = perf_counter()
            context.metrics.record_stream_frame_sent(source=source)
            yield (
                b"--frame\r\nContent-Type: image/jpeg\r\n"
                + f"X-Debug-Max-FPS: {max_fps}\r\n".encode("ascii")
                + b"\r\n"
                + overlay.jpeg
                + b"\r\n"
            )
    finally:
        context.metrics.record_stream_client_closed(source=source)

def debug_overlay_mjpeg_stream(source: str, max_fps: int=Query(default=10, ge=1, le=30)) -> StreamingResponse:
    """Debug/fallback MJPEG stream of latest overlays.

    This stream is served behind the Main-facing :8090 HTTP/MJPEG gateway when
    exposed through the source-selected public gateway. ROS/rosbridge remains
    internal allowlisted operator/prototype infrastructure unless a future ADR
    promotes it.
    """
    _ensure_known_source(source)
    context = _runtime_context()
    if _latest_overlay_image(source, runtime_context=context) is None:
        raise HTTPException(status_code=404, detail=f'no overlay image available for source: {source}')
    return StreamingResponse(
        _mjpeg_latest_overlay_generator(
            source,
            max_fps=max_fps,
            runtime_context=context,
        ),
        media_type='multipart/x-mixed-replace; boundary=frame',
    )

def metrics_snapshot(source: str | None=Query(default=None, json_schema_extra=SOURCE_ID_OPENAPI_EXTRA)) -> dict[str, Any]:
    if source is not None:
        _ensure_known_source(source)
    raw_metrics = _runtime_context().metrics.snapshot()
    return {'generated_at': _now_iso(), 'requested_source': source, 'metrics': _metrics_snapshot_for_source(raw_metrics, source), 'event_store': _runtime_context().store.stats(), 'frame_store': _frame_store_stats_for_source(source)}

async def ingest_synthetic_frame(payload: SyntheticFrameRequest) -> dict[str, Any]:
    """Generate and ingest a synthetic ArUco frame for robot-free Lane B validation.

    This debug endpoint exercises the same latest-frame, detection, and overlay
    path used by uploaded images, without requiring a physical camera or ROS2.
    """
    _ensure_known_source(payload.source)
    try:
        decoded_image = generate_synthetic_aruco_frame(marker_id=payload.marker_id, marker_size=payload.marker_size, padding=payload.padding)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    processed = _detect_and_overlay_decoded_frame(source=payload.source, decoded_image=decoded_image, content_type='image/jpeg', stale=payload.stale)
    events = processed['events']
    overlay: OverlayRenderResult = processed['overlay']
    settings = get_settings()
    emit_disabled = bool(payload.emit and (not settings.wms_emit_enabled))
    emit_results: list[dict[str, Any]] = []
    if payload.emit and settings.wms_emit_enabled and events:
        emit_results = await _emit_vision_events()(events, settings=settings)
    emitted = bool(payload.emit and settings.wms_emit_enabled and events and all((result['ok'] for result in emit_results)))
    return {'source': payload.source, 'emitted': emitted, 'emit_disabled': emit_disabled, 'emit_results': emit_results, 'events': events, 'overlay': overlay.metadata()}

def _json_form_object(value: str | None, field: str) -> dict[str, Any]:
    if value is None or value.strip() == '':
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f'{field} must be valid JSON') from exc
    if not isinstance(parsed, dict):
        raise HTTPException(status_code=400, detail=f'{field} must be a JSON object')
    return parsed

def evaluate_lift_roi(payload: dict[str, Any]) -> dict[str, Any]:
    """Evaluate caller-supplied detector/segmenter candidates against an ROI.

    This is the MVP seam between future model providers and the stable
    LiftRoiEvidence contract. It intentionally accepts synthetic/provided
    candidates instead of selecting a concrete runtime model.
    """
    settings = get_settings()
    try:
        evidence = build_lift_roi_evidence(payload, source_ids=settings.source_ids, policy_version=settings.policy_version, robot_id_for_source=_robot_id_for_source, frame_id_for_source=_frame_id_for_source, now_iso=_now_iso)
    except LiftRoiEvidenceRequestError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _runtime_context().metrics.record_lift_roi_evaluation(verification_status=evidence['verification']['status'])
    return evidence

async def evaluate_lift_roi_image(source: str=Form(..., json_schema_extra=SOURCE_ID_OPENAPI_EXTRA), operation: str=Form(...), roi_json: str=Form(...), image: UploadFile=File(...), task_id: str | None=Form(default=None), expected_count: int | None=Form(default=None), stable_frames: int=Form(default=1), count_stable: bool=Form(default=False), lift_up: bool | None=Form(default=None), lift_down_complete: bool | None=Form(default=None), backoff_complete: bool | None=Form(default=None), dropped_item_count: int | None=Form(default=None), policy_json: str | None=Form(default=None)) -> dict[str, Any]:
    """Evaluate lift ROI evidence from an uploaded image using the configured segmenter."""
    settings = get_settings()
    if source not in settings.source_ids:
        raise HTTPException(status_code=400, detail=f'unknown source: {source}')
    payload = await image.read()
    try:
        decoded_image = decode_image(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    image_height, image_width = decoded_image.shape[:2]
    _runtime_context().source_health.record_frame(source, at=_now_dt())
    try:
        provider = _lift_roi_segmenter()(model_path=settings.vision_model_path, task=settings.vision_model_task, confidence=settings.vision_model_conf, iou=settings.vision_model_iou, image_size=settings.vision_model_imgsz, device=settings.vision_model_device, class_map_json=settings.vision_model_class_map_json, unmapped_class=settings.vision_model_unmapped_class)
        detector_results = tuple(provider.detect(decoded_image))
    except ModelAdapterError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    evidence_payload: dict[str, Any] = {'source': source, 'operation': operation, 'task_id': task_id, 'image': {'width': image_width, 'height': image_height}, 'roi': _json_form_object(roi_json, 'roi_json'), 'expected_count': expected_count, 'stable_frames': stable_frames, 'count_stable': count_stable, 'lift_sensor': {'lift_up': lift_up, 'lift_down_complete': lift_down_complete, 'backoff_complete': backoff_complete}, 'candidates': []}
    if dropped_item_count is not None:
        evidence_payload['dropped_item_count'] = dropped_item_count
    policy = _json_form_object(policy_json, 'policy_json')
    if policy:
        evidence_payload['policy'] = policy
    try:
        evidence = build_lift_roi_evidence(evidence_payload, source_ids=settings.source_ids, policy_version=settings.policy_version, robot_id_for_source=_robot_id_for_source, frame_id_for_source=_frame_id_for_source, now_iso=_now_iso, detector_results=detector_results, image_size_override=(image_width, image_height), detector_name_override=getattr(provider, 'detector_name', None))
    except LiftRoiEvidenceRequestError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _runtime_context().metrics.record_lift_roi_evaluation(verification_status=evidence['verification']['status'])
    return evidence

async def detect_image(source: str=Form(..., json_schema_extra=SOURCE_ID_OPENAPI_EXTRA), image: UploadFile=File(...), emit: bool=Form(default=False), pose_profile: str | None=Form(default=None), marker_size_m: float | None=Form(default=None), camera_fx: float | None=Form(default=None), camera_fy: float | None=Form(default=None), camera_cx: float | None=Form(default=None), camera_cy: float | None=Form(default=None), camera_dist_coeffs: str | None=Form(default=None)) -> dict[str, Any]:
    """Debug/offline detector endpoint.

    The endpoint decodes uploaded images, runs deterministic marker detectors,
    and returns contract-valid VisionEvents for detections.
    """
    settings = get_settings()
    if source not in settings.source_ids:
        raise HTTPException(status_code=400, detail=f'unknown source: {source}')
    payload = await image.read()
    try:
        decoded_image = decode_image(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    pose_request = _optional_pose_request(pose_profile=pose_profile, marker_size_m=marker_size_m, camera_fx=camera_fx, camera_fy=camera_fy, camera_cx=camera_cx, camera_cy=camera_cy, camera_dist_coeffs=camera_dist_coeffs)
    processed = _detect_and_overlay_decoded_frame(source=source, decoded_image=decoded_image, encoded=payload, content_type=image.content_type or 'application/octet-stream', pose_request=pose_request)
    events = processed['events']
    emit_disabled = bool(emit and (not settings.wms_emit_enabled))
    emit_results: list[dict[str, Any]] = []
    if emit and settings.wms_emit_enabled and events:
        emit_results = await _emit_vision_events()(events, settings=settings)
    emitted = bool(emit and settings.wms_emit_enabled and events and all((result['ok'] for result in emit_results)))
    return {'source': source, 'emitted': emitted, 'emit_disabled': emit_disabled, 'emit_results': emit_results, 'events': events}

def _with_route_dependencies(
    handler,
    *,
    context_getter: ContextGetter,
    emit_vision_events_getter: Callable[[], Any],
    lift_roi_segmenter_getter: Callable[[], Any],
):
    @wraps(handler)
    async def wrapper(*args, **kwargs):
        context_token = _context_getter_var.set(context_getter)
        emit_token = _emit_vision_events_getter_var.set(emit_vision_events_getter)
        segmenter_token = _lift_roi_segmenter_getter_var.set(lift_roi_segmenter_getter)
        try:
            result = handler(*args, **kwargs)
            if isawaitable(result):
                return await result
            return result
        finally:
            _lift_roi_segmenter_getter_var.reset(segmenter_token)
            _emit_vision_events_getter_var.reset(emit_token)
            _context_getter_var.reset(context_token)

    return wrapper


def register_vision_routes(
    app,
    *,
    context_getter: ContextGetter,
    emit_vision_events_getter: Callable[[], Any] | None = None,
    lift_roi_segmenter_getter: Callable[[], Any] | None = None,
) -> None:
    """Register remaining non-health AI Server route clusters."""
    emit_getter = emit_vision_events_getter or (lambda: default_emit_vision_events)
    segmenter_getter = lift_roi_segmenter_getter or (lambda: _get_lift_roi_segmenter)

    def route(handler):
        return _with_route_dependencies(
            handler,
            context_getter=context_getter,
            emit_vision_events_getter=emit_getter,
            lift_roi_segmenter_getter=segmenter_getter,
        )

    app.get('/api/v1/vision/streams', responses={200: _json_response_openapi('Main-facing HTTP/MJPEG Vision Stream Gateway discovery', _vision_streams_response_schema()), 400: ERROR_RESPONSE_OPENAPI})(route(vision_streams))
    app.get('/api/v1/vision/ros/topics', responses={200: _json_response_openapi('Lane B ROS2/domain-bridge handoff topic matrix', _ros_handoff_response_schema())})(route(vision_ros_topics))
    app.get('/api/v1/vision/worker/status', responses={200: _json_response_openapi('Lane B read-only worker readiness snapshot', _worker_status_response_schema()), 400: ERROR_RESPONSE_OPENAPI, 422: ERROR_RESPONSE_OPENAPI})(route(vision_worker_status))
    app.post('/api/v1/vision/worker/tick', responses={400: ERROR_RESPONSE_OPENAPI, 422: ERROR_RESPONSE_OPENAPI, 500: ERROR_RESPONSE_OPENAPI})(route(vision_worker_tick))
    app.get('/api/v1/vision/debug/sources', responses={200: _json_response_openapi('Lane B source/frame/overlay debug snapshot', _debug_sources_response_schema()), 400: ERROR_RESPONSE_OPENAPI})(route(vision_debug_sources))
    app.post('/api/v1/vision/frame', responses={200: _json_response_openapi('Latest-frame ingest debug response', _frame_ingest_response_schema()), 400: ERROR_RESPONSE_OPENAPI, 422: ERROR_RESPONSE_OPENAPI})(route(ingest_frame))
    app.post('/api/v1/vision/frame/process', responses={200: _json_response_openapi('Latest-frame ingest plus immediate overlay processing response', _frame_process_response_schema()), 400: ERROR_RESPONSE_OPENAPI, 422: ERROR_RESPONSE_OPENAPI})(route(ingest_and_process_frame))
    app.get('/api/v1/vision/frame/latest', responses={200: _json_response_openapi('Latest raw frame debug metadata', _latest_frame_response_schema()), 400: ERROR_RESPONSE_OPENAPI, 404: ERROR_RESPONSE_OPENAPI})(route(latest_frame))
    app.get('/api/v1/vision/frame/latest/image', responses={400: ERROR_RESPONSE_OPENAPI, 404: ERROR_RESPONSE_OPENAPI})(route(latest_frame_image))
    app.get('/api/v1/vision/overlay/latest', responses={400: ERROR_RESPONSE_OPENAPI, 404: ERROR_RESPONSE_OPENAPI})(route(latest_overlay))
    app.get('/api/v1/vision/overlay/latest/image', responses={400: ERROR_RESPONSE_OPENAPI, 404: ERROR_RESPONSE_OPENAPI})(route(latest_overlay_image))
    app.get('/api/v1/vision/stream/{source}.mjpeg', responses={400: ERROR_RESPONSE_OPENAPI, 404: ERROR_RESPONSE_OPENAPI})(route(debug_overlay_mjpeg_stream))
    app.get('/api/v1/metrics', responses={200: METRICS_RESPONSE_OPENAPI, 400: ERROR_RESPONSE_OPENAPI})(route(metrics_snapshot))
    app.post('/api/v1/vision/synthetic/frame', responses={200: _json_response_openapi('Synthetic frame detection response with overlay metadata', _synthetic_frame_response_schema()), 400: ERROR_RESPONSE_OPENAPI, 422: ERROR_RESPONSE_OPENAPI, 500: ERROR_RESPONSE_OPENAPI})(route(ingest_synthetic_frame))
    app.post('/api/v1/lift-roi/evaluate', responses={200: _json_response_openapi('Contract-valid LiftRoiEvidence v1', _lift_roi_openapi_schema()), 400: ERROR_RESPONSE_OPENAPI, 500: ERROR_RESPONSE_OPENAPI})(route(evaluate_lift_roi))
    app.post('/api/v1/lift-roi/evaluate-image', responses={200: _json_response_openapi('Contract-valid LiftRoiEvidence v1', _lift_roi_openapi_schema()), 400: ERROR_RESPONSE_OPENAPI, 503: ERROR_RESPONSE_OPENAPI, 500: ERROR_RESPONSE_OPENAPI})(route(evaluate_lift_roi_image))
    app.post('/api/v1/detect/image', responses={200: _json_response_openapi('Image detection response with VisionEvent v1 events', _detect_image_response_schema()), 400: ERROR_RESPONSE_OPENAPI, 422: ERROR_RESPONSE_OPENAPI, 500: ERROR_RESPONSE_OPENAPI})(route(detect_image))


__all__ = ["_mjpeg_latest_overlay_generator", "register_vision_routes"]

