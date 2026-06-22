from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ..runtime_state import RuntimeContext
from .vision_read_model_ros import _zero_stream_metrics


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
