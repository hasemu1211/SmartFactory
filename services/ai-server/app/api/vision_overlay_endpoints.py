from __future__ import annotations

import asyncio
from collections.abc import Callable
from time import perf_counter
from typing import Any

from fastapi import HTTPException
from fastapi.responses import Response, StreamingResponse

from ..runtime_state import RuntimeContext


LatestOverlayImageGetter = Callable[..., Any]
FrameOverlaySyncStatus = Callable[..., dict[str, Any]]


def build_latest_overlay_response(
    *,
    source: str,
    runtime_context: RuntimeContext,
    frame_overlay_sync_status: FrameOverlaySyncStatus,
    now_iso: Callable[[], str],
) -> dict[str, Any]:
    overlay = runtime_context.overlay_cache.latest(source)
    if overlay is None:
        raise HTTPException(
            status_code=404,
            detail=f"no overlay available for source: {source}",
        )
    return {
        "generated_at": now_iso(),
        "requested_source": source,
        "sync": frame_overlay_sync_status(source, runtime_context=runtime_context),
        "overlay": overlay,
    }


def build_latest_overlay_image_response(
    *,
    source: str,
    latest_overlay_image: LatestOverlayImageGetter,
) -> Response:
    overlay = latest_overlay_image(source)
    if overlay is None:
        raise HTTPException(
            status_code=404,
            detail=f"no overlay image available for source: {source}",
        )
    return Response(content=overlay.jpeg, media_type=overlay.content_type)


async def mjpeg_latest_overlay_generator(
    source: str,
    *,
    max_fps: int,
    runtime_context: RuntimeContext,
    latest_overlay_image: LatestOverlayImageGetter,
):
    last_frame_seq = 0
    last_send_at = 0.0
    min_interval_s = 1.0 / float(max_fps)
    runtime_context.metrics.record_stream_client_opened(source=source)
    try:
        while True:
            overlay = latest_overlay_image(source, runtime_context=runtime_context)
            if overlay is None or overlay.frame_seq == last_frame_seq:
                runtime_context.metrics.record_stream_stale_poll(source=source)
                await asyncio.sleep(0.05)
                continue
            now = perf_counter()
            wait_s = min_interval_s - (now - last_send_at)
            if wait_s > 0:
                await asyncio.sleep(wait_s)
            last_frame_seq = overlay.frame_seq
            last_send_at = perf_counter()
            runtime_context.metrics.record_stream_frame_sent(source=source)
            yield (
                b"--frame\r\nContent-Type: image/jpeg\r\n"
                + f"X-Debug-Max-FPS: {max_fps}\r\n".encode("ascii")
                + b"\r\n"
                + overlay.jpeg
                + b"\r\n"
            )
    finally:
        runtime_context.metrics.record_stream_client_closed(source=source)


def build_debug_overlay_mjpeg_stream_response(
    *,
    source: str,
    max_fps: int,
    runtime_context: RuntimeContext,
    latest_overlay_image: LatestOverlayImageGetter,
) -> StreamingResponse:
    if latest_overlay_image(source, runtime_context=runtime_context) is None:
        raise HTTPException(
            status_code=404,
            detail=f"no overlay image available for source: {source}",
        )
    return StreamingResponse(
        mjpeg_latest_overlay_generator(
            source,
            max_fps=max_fps,
            runtime_context=runtime_context,
            latest_overlay_image=latest_overlay_image,
        ),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )
