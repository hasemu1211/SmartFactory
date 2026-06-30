from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from typing import Any

from .source_registry import SourceRegistry
from .vision_monitor_profiles import POLICY_VERSION


class VisionMonitorStateError(ValueError):
    """Raised when a monitor state request violates the no-hardware contract."""


KNOWN_MONITOR_IDS = {"person_drive", "drop_watch", "lift_evidence"}
KNOWN_OPERATION_STATES = {"IDLE", "DRIVE", "PICKUP", "DROPOFF", "MONITOR", "UNKNOWN"}
KNOWN_ROBOT_IDS = {"tb3_1", "tb3_2"}


@dataclass(frozen=True, slots=True)
class VisionMonitorState:
    monitor_id: str
    enabled: bool
    source: str | None
    robot_id: str | None
    task_id: int | str | None
    operation_state: str
    target_fps: float | None
    profile_id: str | None
    policy_version: str
    threshold_set_id: str | None
    updated_at: str | None
    revision: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "monitor_id": self.monitor_id,
            "enabled": self.enabled,
            "source": self.source,
            "robot_id": self.robot_id,
            "task_id": self.task_id,
            "operation_state": self.operation_state,
            "target_fps": self.target_fps,
            "profile_id": self.profile_id,
            "policy_version": self.policy_version,
            "threshold_set_id": self.threshold_set_id,
            "updated_at": self.updated_at,
            "revision": self.revision,
        }


def default_monitor_state(monitor_id: str) -> VisionMonitorState:
    _ensure_monitor_id(monitor_id)
    return VisionMonitorState(
        monitor_id=monitor_id,
        enabled=False,
        source=None,
        robot_id=None,
        task_id=None,
        operation_state="IDLE",
        target_fps=None,
        profile_id=None,
        policy_version=POLICY_VERSION,
        threshold_set_id=None,
        updated_at=None,
        revision=0,
    )


class VisionMonitorStateStore:
    """Process-local monitor state store for no-hardware API scaffolding.

    The store is intentionally ephemeral: Main must reassert monitor state after
    an AI Server restart. ``revision`` is a per-process monotonic counter for
    smoke tests and simple stale-response detection; it is not a durable DB
    version.
    """

    def __init__(self) -> None:
        self._states: dict[str, VisionMonitorState] = {}
        self._lock = Lock()

    def get(self, monitor_id: str) -> VisionMonitorState:
        _ensure_monitor_id(monitor_id)
        with self._lock:
            return self._states.get(monitor_id, default_monitor_state(monitor_id))

    def list(self) -> list[VisionMonitorState]:
        with self._lock:
            return [self._states.get(monitor_id, default_monitor_state(monitor_id)) for monitor_id in sorted(KNOWN_MONITOR_IDS)]

    def update(
        self,
        monitor_id: str,
        payload: dict[str, Any],
        *,
        source_registry: SourceRegistry,
        updated_at: str,
    ) -> VisionMonitorState:
        with self._lock:
            previous = self._states.get(monitor_id, default_monitor_state(monitor_id))
        revision = previous.revision + 1
        state = validate_monitor_state_payload(
            monitor_id,
            payload,
            source_registry=source_registry,
            updated_at=updated_at,
            revision=revision,
        )
        with self._lock:
            self._states[monitor_id] = state
        return state


def _ensure_monitor_id(monitor_id: str) -> None:
    if monitor_id not in KNOWN_MONITOR_IDS:
        raise VisionMonitorStateError(f"unknown monitor_id: {monitor_id}")


def _normalized_operation_state(value: Any) -> str:
    state = "UNKNOWN" if value is None else str(value).strip().upper()
    if state not in KNOWN_OPERATION_STATES:
        raise VisionMonitorStateError(f"unknown operation_state: {state}")
    return state


def _validate_robot_id(value: Any) -> str | None:
    if value is None or value == "":
        return None
    robot_id = str(value)
    if robot_id not in KNOWN_ROBOT_IDS:
        raise VisionMonitorStateError(f"unknown robot_id: {robot_id}")
    return robot_id


def _validate_target_fps(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise VisionMonitorStateError("target_fps must be a positive number")
    return float(value)


def _source_robot_id(source: str, source_registry: SourceRegistry) -> str | None:
    try:
        return source_registry.get(source).robot_id
    except KeyError as exc:
        raise VisionMonitorStateError(f"unknown source: {source}") from exc


def validate_monitor_state_payload(
    monitor_id: str,
    payload: dict[str, Any],
    *,
    source_registry: SourceRegistry,
    updated_at: str,
    revision: int = 0,
) -> VisionMonitorState:
    _ensure_monitor_id(monitor_id)
    enabled = bool(payload.get("enabled", True))
    source = payload.get("source")
    source = None if source is None or source == "" else str(source)
    source_robot = _source_robot_id(source, source_registry) if source is not None else None
    robot_id = _validate_robot_id(payload.get("robot_id"))
    operation_state = _normalized_operation_state(payload.get("operation_state"))

    if robot_id is None and source_robot is not None:
        robot_id = source_robot
    if source_robot is not None and robot_id != source_robot:
        raise VisionMonitorStateError(
            f"source {source!r} requires robot_id {source_robot!r}"
        )

    if enabled:
        if monitor_id == "person_drive":
            if source not in {"tb3_1_picam", "tb3_2_picam"}:
                raise VisionMonitorStateError("person_drive requires tb3_1_picam or tb3_2_picam")
            if operation_state != "DRIVE":
                raise VisionMonitorStateError("person_drive can be enabled only in DRIVE")
        elif monitor_id == "drop_watch":
            if source != "global_cam_01":
                raise VisionMonitorStateError("drop_watch requires global_cam_01")
            if operation_state != "DRIVE":
                raise VisionMonitorStateError("drop_watch can be enabled only in DRIVE")
        elif monitor_id == "lift_evidence":
            if source != "global_cam_01":
                raise VisionMonitorStateError("lift_evidence requires global_cam_01")
            if robot_id is None:
                raise VisionMonitorStateError("lift_evidence requires robot_id")
            if operation_state not in {"PICKUP", "DROPOFF"}:
                raise VisionMonitorStateError("lift_evidence can be enabled only in PICKUP or DROPOFF")

    policy_version = str(payload.get("policy_version") or POLICY_VERSION)
    profile_id = payload.get("profile_id")
    threshold_set_id = payload.get("threshold_set_id")

    return VisionMonitorState(
        monitor_id=monitor_id,
        enabled=enabled,
        source=source,
        robot_id=robot_id,
        task_id=payload.get("task_id"),
        operation_state=operation_state,
        target_fps=_validate_target_fps(payload.get("target_fps")),
        profile_id=None if profile_id is None or profile_id == "" else str(profile_id),
        policy_version=policy_version,
        threshold_set_id=None if threshold_set_id is None or threshold_set_id == "" else str(threshold_set_id),
        updated_at=updated_at,
        revision=revision,
    )


__all__ = [
    "KNOWN_MONITOR_IDS",
    "VisionMonitorState",
    "VisionMonitorStateError",
    "VisionMonitorStateStore",
    "default_monitor_state",
    "validate_monitor_state_payload",
]
