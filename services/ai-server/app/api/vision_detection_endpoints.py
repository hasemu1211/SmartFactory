from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from fastapi import HTTPException, UploadFile

from ..config import get_settings
from ..lift_roi_evidence import LiftRoiEvidenceRequestError, build_lift_roi_evidence
from ..model_adapters import ModelAdapterError
from ..runtime_state import RuntimeContext


def json_form_object(value: str | None, field: str) -> dict[str, Any]:
    if value is None or value.strip() == "":
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"{field} must be valid JSON") from exc
    if not isinstance(parsed, dict):
        raise HTTPException(status_code=400, detail=f"{field} must be a JSON object")
    return parsed


def build_lift_roi_response(
    *,
    payload: dict[str, Any],
    runtime_context: RuntimeContext,
    robot_id_for_source: Callable[[str], str | None],
    frame_id_for_source: Callable[[str], str],
    now_iso: Callable[[], str],
) -> dict[str, Any]:
    settings = get_settings()
    try:
        evidence = build_lift_roi_evidence(
            payload,
            source_ids=settings.source_ids,
            policy_version=settings.policy_version,
            robot_id_for_source=robot_id_for_source,
            frame_id_for_source=frame_id_for_source,
            now_iso=now_iso,
        )
    except LiftRoiEvidenceRequestError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    runtime_context.metrics.record_lift_roi_evaluation(
        verification_status=evidence["verification"]["status"]
    )
    return evidence


async def build_lift_roi_image_response(
    *,
    source: str,
    operation: str,
    roi_json: str,
    image: UploadFile,
    task_id: str | None,
    expected_count: int | None,
    stable_frames: int,
    count_stable: bool,
    lift_up: bool | None,
    lift_down_complete: bool | None,
    backoff_complete: bool | None,
    dropped_item_count: int | None,
    policy_json: str | None,
    runtime_context: RuntimeContext,
    decode_image: Callable[[bytes], Any],
    lift_roi_segmenter: Callable[[], Any],
    model_config_for_source: Callable[[str], Any],
    robot_id_for_source: Callable[[str], str | None],
    frame_id_for_source: Callable[[str], str],
    now_iso: Callable[[], str],
    now_dt: Callable[[], Any],
) -> dict[str, Any]:
    settings = get_settings()
    if source not in settings.source_ids:
        raise HTTPException(status_code=400, detail=f"unknown source: {source}")

    payload = await image.read()
    try:
        decoded_image = decode_image(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    image_height, image_width = decoded_image.shape[:2]
    runtime_context.source_health.record_frame(source, at=now_dt())
    try:
        model_config = model_config_for_source(source)
        if model_config is None:
            raise ModelAdapterError("vision model path is not configured")
        provider = lift_roi_segmenter()(
            model_path=model_config.model_path,
            task=model_config.task,
            confidence=model_config.confidence,
            iou=model_config.iou,
            image_size=model_config.image_size,
            device=model_config.device,
            class_map_json=model_config.class_map_json,
            unmapped_class=model_config.unmapped_class,
        )
        detector_results = tuple(provider.detect(decoded_image))
    except ModelAdapterError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    evidence_payload: dict[str, Any] = {
        "source": source,
        "operation": operation,
        "task_id": task_id,
        "image": {"width": image_width, "height": image_height},
        "roi": json_form_object(roi_json, "roi_json"),
        "expected_count": expected_count,
        "stable_frames": stable_frames,
        "count_stable": count_stable,
        "lift_sensor": {
            "lift_up": lift_up,
            "lift_down_complete": lift_down_complete,
            "backoff_complete": backoff_complete,
        },
        "candidates": [],
    }
    if dropped_item_count is not None:
        evidence_payload["dropped_item_count"] = dropped_item_count
    policy = json_form_object(policy_json, "policy_json")
    if policy:
        evidence_payload["policy"] = policy

    try:
        evidence = build_lift_roi_evidence(
            evidence_payload,
            source_ids=settings.source_ids,
            policy_version=settings.policy_version,
            robot_id_for_source=robot_id_for_source,
            frame_id_for_source=frame_id_for_source,
            now_iso=now_iso,
            detector_results=detector_results,
            image_size_override=(image_width, image_height),
            detector_name_override=getattr(provider, "detector_name", None),
        )
    except LiftRoiEvidenceRequestError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    runtime_context.metrics.record_lift_roi_evaluation(
        verification_status=evidence["verification"]["status"]
    )
    return evidence


async def build_detect_image_response(
    *,
    source: str,
    image: UploadFile,
    emit: bool,
    pose_profile: str | None,
    marker_size_m: float | None,
    camera_fx: float | None,
    camera_fy: float | None,
    camera_cx: float | None,
    camera_cy: float | None,
    camera_dist_coeffs: str | None,
    decode_image: Callable[[bytes], Any],
    optional_pose_request: Callable[..., Any],
    detect_and_overlay_decoded_frame: Callable[..., dict[str, Any]],
    emit_vision_events: Callable[[], Any],
) -> dict[str, Any]:
    settings = get_settings()
    if source not in settings.source_ids:
        raise HTTPException(status_code=400, detail=f"unknown source: {source}")

    payload = await image.read()
    try:
        decoded_image = decode_image(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    pose_request = optional_pose_request(
        pose_profile=pose_profile,
        marker_size_m=marker_size_m,
        camera_fx=camera_fx,
        camera_fy=camera_fy,
        camera_cx=camera_cx,
        camera_cy=camera_cy,
        camera_dist_coeffs=camera_dist_coeffs,
    )
    processed = detect_and_overlay_decoded_frame(
        source=source,
        decoded_image=decoded_image,
        encoded=payload,
        content_type=image.content_type or "application/octet-stream",
        pose_request=pose_request,
    )
    events = processed["events"]
    emit_disabled = bool(emit and not settings.wms_emit_enabled)
    emit_results: list[dict[str, Any]] = []
    if emit and settings.wms_emit_enabled and events:
        emit_results = await emit_vision_events()(events, settings=settings)
    emitted = bool(
        emit
        and settings.wms_emit_enabled
        and events
        and all(result["ok"] for result in emit_results)
    )
    return {
        "source": source,
        "emitted": emitted,
        "emit_disabled": emit_disabled,
        "emit_results": emit_results,
        "events": events,
    }
