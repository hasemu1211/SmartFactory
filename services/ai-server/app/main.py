from __future__ import annotations

from datetime import datetime, timezone
from time import perf_counter
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse

from .config import get_settings
from .contracts import ContractValidationError, validate_vision_event
from .detectors import MarkerDetection, decode_image, detect_markers
from .docking import CameraIntrinsics, MarkerPose, estimate_marker_pose
from .event_store import InMemoryEventStore
from .wms_client import emit_vision_events

app = FastAPI(
    title="SmartFactory AI Server",
    version="0.1.0",
    description="API-first MVP1 AI Server. Emits evidence only; WMS owns decisions.",
)
store = InMemoryEventStore()


def _robot_id_for_source(source: str) -> str | None:
    mapping = {
        "global_cam_01": None,
        "tb3_1_picam": "tb3_1",
        "tb3_2_picam": "tb3_2",
    }
    return mapping[source]


def _frame_id_for_source(source: str) -> str:
    mapping = {
        "global_cam_01": "global_camera_frame",
        "tb3_1_picam": "tb3_1_pi_camera_optical_frame",
        "tb3_2_picam": "tb3_2_pi_camera_optical_frame",
    }
    return mapping[source]


def _source_kind(source: str) -> str:
    return "global_rgb" if source == "global_cam_01" else "robot_pi_camera"


def _source_notes(source: str) -> str:
    if source == "global_cam_01":
        return "overview/slot/zone evidence"
    return "front marker/dock/local item evidence"


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def _pose_confidence(pose: MarkerPose) -> float:
    # Reprojection error near 0 px should be high confidence. At >=5 px,
    # keep the pose as weak evidence rather than pretending it is certain.
    return round(max(0.0, min(1.0, 1.0 - (pose.reprojection_error_px / 5.0))), 3)


def _pose_estimate_payload(pose: MarkerPose) -> dict[str, Any]:
    return {
        "method": "ARUCO_POSE",
        # Camera-frame planar convention for docking evidence:
        # x = lateral offset in meters, y = forward distance in meters.
        "x": pose.lateral_m,
        "y": pose.distance_m,
        "yaw": pose.yaw_rad,
        "confidence": _pose_confidence(pose),
    }


def build_marker_event(
    *,
    source: str,
    detection: MarkerDetection,
    image_width: int,
    image_height: int,
    latency_ms: float | None = None,
    pose: MarkerPose | None = None,
) -> dict[str, Any]:
    """Build a schema-valid VisionEvent from a deterministic marker detection."""

    settings = get_settings()
    event: dict[str, Any] = {
        "schema_version": settings.vision_event_schema_version,
        "event_id": str(uuid4()),
        "timestamp": _now_iso(),
        "source": source,
        "robot_id": _robot_id_for_source(source),
        "frame_id": _frame_id_for_source(source),
        "event_kind": "CONFIRMED",
        "class_name": detection.class_name,
        "confidence": detection.confidence,
        "bbox_xyxy": detection.bbox_xyxy,
        "marker_id": detection.marker_id,
        "zone": None,
        "roi_id": None,
        "track_id": None,
        "pose_estimate": _pose_estimate_payload(pose) if pose is not None else None,
        "depth_median_m": None,
        "wms_hint": "TAG_DETECTED",
        "metadata": {
            "n_frame_count": 1,
            "policy_version": settings.policy_version,
            "model": detection.detector,
            "image_width": image_width,
            "image_height": image_height,
            "latency_ms": latency_ms,
        },
    }
    validate_vision_event(event)
    return event


def _parse_dist_coeffs(value: str | None) -> tuple[float, ...]:
    if value is None or value.strip() == "":
        return ()
    try:
        return tuple(float(part.strip()) for part in value.split(",") if part.strip())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="camera_dist_coeffs must be comma-separated numbers") from exc


def _optional_pose_request(
    *,
    marker_size_m: float | None,
    camera_fx: float | None,
    camera_fy: float | None,
    camera_cx: float | None,
    camera_cy: float | None,
    camera_dist_coeffs: str | None,
) -> tuple[float, CameraIntrinsics] | None:
    fields = [marker_size_m, camera_fx, camera_fy, camera_cx, camera_cy]
    if all(value is None for value in fields) and not camera_dist_coeffs:
        return None
    if any(value is None for value in fields):
        raise HTTPException(
            status_code=400,
            detail=(
                "ArUco pose requires marker_size_m, camera_fx, camera_fy, "
                "camera_cx, and camera_cy together"
            ),
        )
    assert marker_size_m is not None
    assert camera_fx is not None
    assert camera_fy is not None
    assert camera_cx is not None
    assert camera_cy is not None
    if marker_size_m <= 0:
        raise HTTPException(status_code=400, detail="marker_size_m must be positive")
    if camera_fx <= 0 or camera_fy <= 0:
        raise HTTPException(status_code=400, detail="camera_fx and camera_fy must be positive")
    return (
        marker_size_m,
        CameraIntrinsics(
            fx=camera_fx,
            fy=camera_fy,
            cx=camera_cx,
            cy=camera_cy,
            dist_coeffs=_parse_dist_coeffs(camera_dist_coeffs),
        ),
    )


def _estimate_detection_pose(
    detection: MarkerDetection,
    pose_request: tuple[float, CameraIntrinsics] | None,
) -> MarkerPose | None:
    if pose_request is None or not detection.corners_xy:
        return None
    marker_size_m, intrinsics = pose_request
    try:
        return estimate_marker_pose(
            detection.corners_xy,
            marker_size_m=marker_size_m,
            intrinsics=intrinsics,
        )
    except ValueError:
        return None


@app.exception_handler(ContractValidationError)
async def contract_validation_exception_handler(_, exc: ContractValidationError):
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "CONTRACT_VALIDATION_FAILED",
                "message": str(exc),
            }
        },
    )


@app.get("/api/v1/health")
def health() -> dict[str, Any]:
    settings = get_settings()
    source_count = len(settings.source_ids)
    return {
        "service": "ai-server",
        "status": "ok",
        "service_version": app.version,
        "contract_version": settings.vision_event_schema_version,
        "model_status": "loaded",
        "source_summary": {
            "configured": source_count,
            "online": 0,
            "stale": 0,
            "disabled": 0,
            "offline": source_count,
        },
        # Backward-compatible aliases retained for existing local checks.
        "version": app.version,
        "schema_version": settings.vision_event_schema_version,
        "main_server_url": settings.main_server_url,
        "sources": settings.source_ids,
    }


@app.get("/api/v1/sources")
def sources() -> dict[str, Any]:
    settings = get_settings()
    topics = settings.image_topics
    source_items = []
    for idx, source in enumerate(settings.source_ids):
        source_items.append(
            {
                "source": source,
                "source_id": source,
                "kind": _source_kind(source),
                "robot_id": _robot_id_for_source(source),
                "enabled": True,
                "status": "offline",
                "frame_id": _frame_id_for_source(source),
                "last_frame_at": None,
                "target_fps": 10,
                "notes": _source_notes(source),
                "ros_topic": topics[idx] if idx < len(topics) else None,
            }
        )
    return {"sources": source_items}


@app.get("/api/v1/detections/latest")
def latest_detections(
    source: str | None = Query(default=None),
    limit: int = Query(default=10, ge=1, le=50),
) -> dict[str, Any]:
    settings = get_settings()
    if source is not None and source not in settings.source_ids:
        raise HTTPException(status_code=400, detail=f"unknown source: {source}")
    return {"generated_at": _now_iso(), "events": store.latest(source=source, limit=limit)}


@app.post("/api/v1/detect/image")
async def detect_image(
    source: str = Form(...),
    image: UploadFile = File(...),
    emit: bool = Form(default=False),
    marker_size_m: float | None = Form(default=None),
    camera_fx: float | None = Form(default=None),
    camera_fy: float | None = Form(default=None),
    camera_cx: float | None = Form(default=None),
    camera_cy: float | None = Form(default=None),
    camera_dist_coeffs: str | None = Form(default=None),
) -> dict[str, Any]:
    """Debug/offline detector endpoint.

    The endpoint decodes uploaded images, runs deterministic marker detectors,
    and returns contract-valid VisionEvents for detections.
    """

    settings = get_settings()
    if source not in settings.source_ids:
        raise HTTPException(status_code=400, detail=f"unknown source: {source}")
    payload = await image.read()
    try:
        decoded_image = decode_image(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    pose_request = _optional_pose_request(
        marker_size_m=marker_size_m,
        camera_fx=camera_fx,
        camera_fy=camera_fy,
        camera_cx=camera_cx,
        camera_cy=camera_cy,
        camera_dist_coeffs=camera_dist_coeffs,
    )

    image_height, image_width = decoded_image.shape[:2]
    started = perf_counter()
    detections = detect_markers(decoded_image)
    latency_ms = round((perf_counter() - started) * 1000.0, 3)
    events = [
        build_marker_event(
            source=source,
            detection=detection,
            image_width=image_width,
            image_height=image_height,
            latency_ms=latency_ms,
            pose=_estimate_detection_pose(detection, pose_request),
        )
        for detection in detections
    ]
    for event in events:
        store.add(event)

    emit_disabled = bool(emit and not settings.wms_emit_enabled)
    emit_results: list[dict[str, Any]] = []
    if emit and settings.wms_emit_enabled and events:
        emit_results = await emit_vision_events(events, settings=settings)
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
