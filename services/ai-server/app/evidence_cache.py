from __future__ import annotations

from collections import deque
from threading import Lock
from typing import Any


class LatestEvidenceCache:
    """Thread-safe latest evidence/overlay metadata cache per source."""

    def __init__(self, maxlen_per_source: int = 20) -> None:
        if maxlen_per_source <= 0:
            raise ValueError("maxlen_per_source must be positive")
        self._maxlen = maxlen_per_source
        self._items: dict[str, deque[dict[str, Any]]] = {}
        self._lock = Lock()

    def add(self, item: dict[str, Any]) -> None:
        source = item.get("source")
        if not isinstance(source, str) or not source:
            raise ValueError("evidence item must include source")
        with self._lock:
            bucket = self._items.setdefault(source, deque(maxlen=self._maxlen))
            bucket.appendleft(dict(item))

    def latest(self, source: str) -> dict[str, Any] | None:
        with self._lock:
            bucket = self._items.get(source)
            if not bucket:
                return None
            return dict(bucket[0])

    def latest_all(self) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(bucket[0]) for bucket in self._items.values() if bucket]

    def reset(self) -> None:
        with self._lock:
            self._items.clear()
