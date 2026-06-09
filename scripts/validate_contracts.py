#!/usr/bin/env python3
"""Validate SmartFactory API contract fixtures.

This script intentionally validates both valid and invalid fixtures:
- files named vision-event.valid.*.json must pass JSON Schema and policy checks
- files named vision-event.invalid.*.json must fail either JSON Schema or policy checks
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

try:
    import jsonschema
except ImportError as exc:  # pragma: no cover
    raise SystemExit("Missing dependency: jsonschema. Install it in the contract/dev environment.") from exc

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "docs/contracts/vision-event.schema.json"
FIXTURE_DIR = ROOT / "docs/contracts/fixtures"
MARKER_CLASSES = {"aruco_marker", "qr_marker", "apriltag_marker"}
DETECTION_CLASSES = {"person", "obstacle", "box", "dropped_item", "pallet", "unknown"}


class PolicyError(ValueError):
    """Raised when a fixture passes JSON Schema but violates MVP1 event policy."""


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def validate_policy(event: dict[str, Any]) -> None:
    source = event.get("source")
    robot_id = event.get("robot_id")
    if source == "global_cam_01" and robot_id is not None:
        raise PolicyError("global camera events must use robot_id null")
    if source == "tb3_1_picam" and robot_id != "tb3_1":
        raise PolicyError("tb3_1_picam events must use robot_id tb3_1")
    if source == "tb3_2_picam" and robot_id != "tb3_2":
        raise PolicyError("tb3_2_picam events must use robot_id tb3_2")

    if event.get("depth_median_m") is not None:
        raise PolicyError("depth_median_m must be null in MVP1")

    kind = event.get("event_kind")
    cls = event.get("class_name")
    marker_id = event.get("marker_id")
    bbox = event.get("bbox_xyxy")

    if kind == "STALE":
        if cls != "unknown" or event.get("wms_hint") != "VISION_STALE":
            raise PolicyError("STALE events must use class_name unknown and wms_hint VISION_STALE")
        if event.get("confidence") is not None or bbox is not None:
            raise PolicyError("STALE events must not include confidence or bbox evidence")

    if kind == "CONFIRMED" and cls in MARKER_CLASSES and not marker_id:
        raise PolicyError("CONFIRMED marker events require marker_id")

    if kind in {"CANDIDATE", "CONFIRMED"} and cls in DETECTION_CLASSES:
        if not isinstance(bbox, list) or len(bbox) != 4:
            raise PolicyError("Detection CANDIDATE/CONFIRMED events require bbox_xyxy")
        x1, y1, x2, y2 = bbox
        if not (x1 < x2 and y1 < y2):
            raise PolicyError("bbox_xyxy must satisfy x1 < x2 and y1 < y2")


def validate_event(path: Path, schema: dict[str, Any]) -> None:
    event = load_json(path)
    validator = jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker())
    validator.validate(event)
    validate_policy(event)


def main() -> int:
    schema = load_json(SCHEMA_PATH)
    valid = sorted(FIXTURE_DIR.glob("vision-event.valid.*.json"))
    invalid = sorted(FIXTURE_DIR.glob("vision-event.invalid.*.json"))
    failures: list[str] = []

    for path in valid:
        try:
            validate_event(path, schema)
            print(f"VALID ok: {path.relative_to(ROOT)}")
        except Exception as exc:  # noqa: BLE001 - report all validation failures
            failures.append(f"VALID fixture failed {path.name}: {exc}")

    for path in invalid:
        try:
            validate_event(path, schema)
        except Exception as exc:  # expected path
            print(f"INVALID rejected: {path.relative_to(ROOT)} ({exc.__class__.__name__}: {exc})")
        else:
            failures.append(f"INVALID fixture unexpectedly passed {path.name}")

    if failures:
        print("\nContract validation failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print("\nAll contract fixtures behaved as expected.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
