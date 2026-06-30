from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import cv2
import numpy as np

from .evidence_cache import DEFAULT_VIEW_ID, normalize_view_id
from .frame_store import StoredFrame


@dataclass(frozen=True)
class OverlayRenderResult:
    source: str
    frame_seq: int
    frame_timestamp: str
    evidence_timestamp: str | None
    overlay_timestamp: str
    latency_ms: float | None
    event_count: int
    stale: bool
    image_width: int
    image_height: int
    jpeg: bytes
    view: str = DEFAULT_VIEW_ID
    content_type: str = "image/jpeg"

    def __post_init__(self) -> None:
        object.__setattr__(self, "view", normalize_view_id(self.view))

    def metadata(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "view": self.view,
            "frame_seq": self.frame_seq,
            "frame_timestamp": self.frame_timestamp,
            "evidence_timestamp": self.evidence_timestamp,
            "overlay_timestamp": self.overlay_timestamp,
            "latency_ms": self.latency_ms,
            "event_count": self.event_count,
            "stale": self.stale,
            "visual_state": "stale" if self.stale else "fresh",
            "image": {"width": self.image_width, "height": self.image_height},
            "content_type": self.content_type,
        }


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def _local_clock_label() -> str:
    """Return the operator-facing local wall-clock time for live overlays."""

    return datetime.now(timezone.utc).astimezone().strftime("%H:%M:%S")


def _draw_label(image: np.ndarray, text: str, x: int, y: int, color: tuple[int, int, int]) -> None:
    font = cv2.FONT_HERSHEY_SIMPLEX
    scale = 0.45
    thickness = 1
    (text_width, text_height), baseline = cv2.getTextSize(text, font, scale, thickness)
    y_top = max(0, y - text_height - baseline - 4)
    x_right = min(image.shape[1] - 1, x + text_width + 6)
    cv2.rectangle(image, (x, y_top), (x_right, y_top + text_height + baseline + 4), color, -1)
    cv2.putText(image, text, (x + 3, y_top + text_height + 1), font, scale, (255, 255, 255), thickness, cv2.LINE_AA)


def _bbox(event: dict[str, Any]) -> tuple[int, int, int, int] | None:
    raw = event.get("bbox_xyxy")
    if not isinstance(raw, list) or len(raw) != 4:
        return None
    try:
        x1, y1, x2, y2 = [int(round(float(value))) for value in raw]
    except (TypeError, ValueError):
        return None
    if x2 <= x1 or y2 <= y1:
        return None
    return x1, y1, x2, y2


def render_overlay(
    frame: StoredFrame,
    *,
    events: list[dict[str, Any]] | tuple[dict[str, Any], ...] = (),
    stale: bool = False,
    view: str | None = None,
) -> OverlayRenderResult:
    """Render visual evidence overlay for the latest frame.

    Overlay is non-authoritative: it shows detection evidence only and never
    implies Main/WMS task success.
    """

    image = render_overlay_bgr(frame, events=events, stale=stale, view=view)

    ok, buffer = cv2.imencode(".jpg", image)
    if not ok:
        raise ValueError("failed to encode overlay JPEG")

    evidence_timestamps = [event.get("timestamp") for event in events if isinstance(event.get("timestamp"), str)]
    latencies = [event.get("metadata", {}).get("latency_ms") for event in events if isinstance(event.get("metadata"), dict)]
    numeric_latencies = [float(value) for value in latencies if isinstance(value, int | float)]
    return OverlayRenderResult(
        source=frame.source,
        view=normalize_view_id(view),
        frame_seq=frame.frame_seq,
        frame_timestamp=frame.timestamp,
        evidence_timestamp=max(evidence_timestamps) if evidence_timestamps else None,
        overlay_timestamp=_now_iso(),
        latency_ms=max(numeric_latencies) if numeric_latencies else None,
        event_count=len(events),
        stale=stale,
        image_width=frame.image_width,
        image_height=frame.image_height,
        jpeg=buffer.tobytes(),
    )


def render_overlay_bgr(
    frame: StoredFrame,
    *,
    events: list[dict[str, Any]] | tuple[dict[str, Any], ...] = (),
    stale: bool = False,
    view: str | None = None,
) -> np.ndarray:
    """Render visual evidence overlay and return BGR pixels without JPEG encoding."""

    _ = normalize_view_id(view)

    if frame.decoded_bgr is None:
        image_array = np.frombuffer(frame.encoded, dtype=np.uint8)
        image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError("stored frame is not decodable")
    else:
        image = frame.decoded_bgr.copy()

    color = (0, 180, 0) if not stale else (0, 165, 255)
    for event in events:
        bbox = _bbox(event)
        if bbox is None:
            continue
        x1, y1, x2, y2 = bbox
        cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)
        label_parts = [str(event.get("class_name") or "evidence")]
        if event.get("marker_id"):
            label_parts.append(str(event["marker_id"]))
        confidence = event.get("confidence")
        if isinstance(confidence, int | float):
            label_parts.append(f"{confidence:.2f}")
        _draw_label(image, " ".join(label_parts), max(0, x1), max(14, y1), color)

    if stale:
        # Make stale evidence visually unmistakable for GUI/debug QA.  The full-width
        # amber header is intentionally stronger than bbox color alone so operators
        # do not confuse old visual evidence with current WMS/task success.
        cv2.rectangle(image, (0, 0), (image.shape[1] - 1, min(25, image.shape[0] - 1)), (0, 165, 255), -1)
        warning_text = "STALE FRAME - DEBUG ONLY"
        if image.shape[1] < 220:
            warning_text = "STALE FRAME"
        cv2.putText(
            image,
            warning_text,
            (6, min(18, image.shape[0] - 5)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 0, 0),
            1,
            cv2.LINE_AA,
        )

    clock_label = _local_clock_label()
    if image.shape[1] < 240:
        short_source = frame.source.replace("_picam", "").replace("global_cam_", "gcam")
        banner = f"{short_source} {clock_label} e={len(events)}"
        if stale:
            banner = f"STALE {clock_label} e={len(events)}"
    else:
        banner = f"{frame.source} time={clock_label} events={len(events)}"
        if stale:
            banner = f"STALE {banner}"
    _draw_label(image, banner, 4, image.shape[0] - 6, (40, 40, 40))

    return image
