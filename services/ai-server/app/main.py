from __future__ import annotations

from datetime import datetime, timezone
from time import perf_counter
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse

from .config import get_settings
from .contracts import ContractValidationError, validate_vision_event
from .event_store import InMemoryEventStore
from .detectors import MarkerDetection, decode_image, detect_markers

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
        "tb3_1_picam": "tb3_1_pi_camera_frame",
        "tb3_2_picam": "tb3_2_pi_camera_frame",
    }
    return mapping[source]


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def build_marker_event(
    *,
    source: str,
    detection: MarkerDetection,
    image_width: int,
    image_height: int,
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
        "pose_estimate": None,
        "depth_median_m": None,
        "wms_hint": "TAG_DETECTED",
        "metadata": {
            "n_frame_count": 1,
            "policy_version": settings.policy_version,
            "model": detection.detector,
            "image_width": image_width,
            "image_height": image_height,
            "latency_ms": None,
        },
    }
    validate_vision_event(event)
    return event


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
    return {
        "status": "ok",
        "service": "smartfactory-ai-server",
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
                "source_id": source,
                "robot_id": _robot_id_for_source(source),
                "ros_topic": topics[idx] if idx < len(topics) else None,
                "frame_id": _frame_id_for_source(source),
                "status": "configured",
            }
        )
    return {"sources": source_items}


@app.get("/api/v1/detections/latest")
def latest_detections(
    source: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
) -> dict[str, Any]:
    settings = get_settings()
    if source is not None and source not in settings.source_ids:
        raise HTTPException(status_code=400, detail=f"unknown source: {source}")
    return {"events": store.latest(source=source, limit=limit)}


@app.post("/api/v1/detect/image")
async def detect_image(
    source: str = Form(...),
    image: UploadFile = File(...),
    emit: bool = Form(default=False),
) -> dict[str, Any]:
    """Debug/offline detector endpoint.

    The endpoint decodes uploaded images, runs deterministic marker detectors,
    and returns contract-valid VisionEvents for detections.
    """

    settings = get_settings()
    if source not in settings.source_ids:
        raise HTTPException(status_code=400, detail=f"unknown source: {source}")
    payload = await image.read()
    event = build_mock_event(source=source, image_size=len(payload))
    store.add(event)
    return {"source": source, "emitted": emit, "events": [event]}
