from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml


class SourceRegistryError(ValueError):
    """Raised when the configured vision source registry is invalid."""


@dataclass(frozen=True)
class PhysicalInput:
    topic: str | None
    message_type: str | None
    content_type: str | None
    preferred_transport: str | None


@dataclass(frozen=True)
class BrowserSurface:
    legacy_topic: str | None
    legacy_message_type: str | None
    primary_transport: str


@dataclass(frozen=True)
class NormalizedTopics:
    image: str
    overlay: str


@dataclass(frozen=True)
class SourceDefinition:
    source_id: str
    kind: str
    robot_id: str | None
    frame_id: str
    enabled: bool
    target_fps: float | None
    notes: str
    physical_input: PhysicalInput
    browser: BrowserSurface
    normalized_topics: NormalizedTopics
    evidence_event_topic: str

    def as_snapshot(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "kind": self.kind,
            "robot_id": self.robot_id,
            "frame_id": self.frame_id,
            "enabled": self.enabled,
            "target_fps": self.target_fps,
            "notes": self.notes,
            "physical_input": {
                "topic": self.physical_input.topic,
                "message_type": self.physical_input.message_type,
                "content_type": self.physical_input.content_type,
                "preferred_transport": self.physical_input.preferred_transport,
            },
            "browser": {
                "legacy_topic": self.browser.legacy_topic,
                "legacy_message_type": self.browser.legacy_message_type,
                "primary_transport": self.browser.primary_transport,
            },
            "normalized_topics": {
                "image": self.normalized_topics.image,
                "overlay": self.normalized_topics.overlay,
            },
            "evidence_event_topic": self.evidence_event_topic,
        }


@dataclass(frozen=True)
class SourceRegistry:
    schema_version: str
    sources: tuple[SourceDefinition, ...]

    @property
    def source_ids(self) -> list[str]:
        return [source.source_id for source in self.sources]

    def get(self, source_id: str) -> SourceDefinition:
        for source in self.sources:
            if source.source_id == source_id:
                return source
        raise KeyError(source_id)

    def as_snapshot(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "source_ids": self.source_ids,
            "sources": [source.as_snapshot() for source in self.sources],
        }


_REQUIRED_SOURCE_FIELDS = {
    "source_id",
    "kind",
    "robot_id",
    "frame_id",
    "enabled",
    "notes",
    "physical_input",
    "browser",
    "normalized_topics",
    "evidence_event_topic",
}


def _require_mapping(value: Any, *, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise SourceRegistryError(f"{path} must be an object")
    return value


def _require_string(value: Any, *, path: str, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise SourceRegistryError(f"{path} must be a string")
    if not allow_empty and not value.strip():
        raise SourceRegistryError(f"{path} must not be empty")
    return value


def _optional_string(value: Any, *, path: str) -> str | None:
    if value is None:
        return None
    return _require_string(value, path=path)


def _parse_source(raw: Any, *, index: int) -> SourceDefinition:
    item = _require_mapping(raw, path=f"sources[{index}]")
    missing = sorted(_REQUIRED_SOURCE_FIELDS - set(item))
    if missing:
        raise SourceRegistryError(f"sources[{index}] missing required fields: {', '.join(missing)}")

    source_id = _require_string(item["source_id"], path=f"sources[{index}].source_id")
    physical = _require_mapping(item["physical_input"], path=f"sources[{index}].physical_input")
    browser = _require_mapping(item["browser"], path=f"sources[{index}].browser")
    normalized = _require_mapping(item["normalized_topics"], path=f"sources[{index}].normalized_topics")

    enabled = item["enabled"]
    if not isinstance(enabled, bool):
        raise SourceRegistryError(f"sources[{index}].enabled must be a boolean")

    target_fps = item.get("target_fps")
    if target_fps is not None:
        if not isinstance(target_fps, (int, float)) or target_fps <= 0:
            raise SourceRegistryError(f"sources[{index}].target_fps must be a positive number")
        target_fps = float(target_fps)

    return SourceDefinition(
        source_id=source_id,
        kind=_require_string(item["kind"], path=f"sources[{index}].kind"),
        robot_id=_optional_string(item["robot_id"], path=f"sources[{index}].robot_id"),
        frame_id=_require_string(item["frame_id"], path=f"sources[{index}].frame_id"),
        enabled=enabled,
        target_fps=target_fps,
        notes=_require_string(item["notes"], path=f"sources[{index}].notes", allow_empty=True),
        physical_input=PhysicalInput(
            topic=_optional_string(physical.get("topic"), path=f"sources[{index}].physical_input.topic"),
            message_type=_optional_string(
                physical.get("message_type"), path=f"sources[{index}].physical_input.message_type"
            ),
            content_type=_optional_string(
                physical.get("content_type"), path=f"sources[{index}].physical_input.content_type"
            ),
            preferred_transport=_optional_string(
                physical.get("preferred_transport"),
                path=f"sources[{index}].physical_input.preferred_transport",
            ),
        ),
        browser=BrowserSurface(
            legacy_topic=_optional_string(
                browser.get("legacy_topic"), path=f"sources[{index}].browser.legacy_topic"
            ),
            legacy_message_type=_optional_string(
                browser.get("legacy_message_type"),
                path=f"sources[{index}].browser.legacy_message_type",
            ),
            primary_transport=_require_string(
                browser.get("primary_transport", "rosbridge"),
                path=f"sources[{index}].browser.primary_transport",
            ),
        ),
        normalized_topics=NormalizedTopics(
            image=_require_string(normalized.get("image"), path=f"sources[{index}].normalized_topics.image"),
            overlay=_require_string(
                normalized.get("overlay"), path=f"sources[{index}].normalized_topics.overlay"
            ),
        ),
        evidence_event_topic=_require_string(
            item["evidence_event_topic"], path=f"sources[{index}].evidence_event_topic"
        ),
    )


def load_source_registry(path: Path) -> SourceRegistry:
    if not path.exists():
        raise SourceRegistryError(f"source registry not found: {path}")
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    data = _require_mapping(loaded, path=str(path))
    schema_version = _require_string(data.get("schema_version"), path="schema_version")
    raw_sources = data.get("sources")
    if not isinstance(raw_sources, list) or not raw_sources:
        raise SourceRegistryError("sources must be a non-empty list")

    sources = tuple(_parse_source(raw, index=index) for index, raw in enumerate(raw_sources))
    seen: set[str] = set()
    duplicates: list[str] = []
    for source in sources:
        if source.source_id in seen:
            duplicates.append(source.source_id)
        seen.add(source.source_id)
    if duplicates:
        raise SourceRegistryError(f"duplicate source_id values: {', '.join(sorted(duplicates))}")

    return SourceRegistry(schema_version=schema_version, sources=sources)


@lru_cache(maxsize=8)
def load_source_registry_cached(path: str) -> SourceRegistry:
    return load_source_registry(Path(path))
