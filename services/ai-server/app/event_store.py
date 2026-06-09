from __future__ import annotations

from collections import deque
from threading import Lock
from typing import Any


class InMemoryEventStore:
    """Small thread-safe ring buffer for latest detections during MVP1 scaffolding."""

    def __init__(self, maxlen: int = 200) -> None:
        self._events: deque[dict[str, Any]] = deque(maxlen=maxlen)
        self._lock = Lock()

    def add(self, event: dict[str, Any]) -> None:
        with self._lock:
            self._events.appendleft(event)

    def latest(self, *, source: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
        with self._lock:
            events = list(self._events)
        if source:
            events = [event for event in events if event.get("source") == source]
        return events[:limit]
