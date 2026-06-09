from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import jsonschema

from .config import get_settings


class ContractValidationError(ValueError):
    """Raised when an event does not satisfy canonical contract policy."""


@lru_cache(maxsize=1)
def _validator() -> jsonschema.Draft202012Validator:
    settings = get_settings()
    schema_path = Path(settings.contract_schema_path)
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    return jsonschema.Draft202012Validator(
        schema,
        format_checker=jsonschema.FormatChecker(),
    )


def validate_vision_event(event: dict[str, Any]) -> None:
    """Validate a VisionEvent against schema and MVP1 policy checks."""

    _validator().validate(event)

    bbox = event.get("bbox_xyxy")
    if bbox is not None:
        x1, y1, x2, y2 = bbox
        if not (x1 < x2 and y1 < y2):
            raise ContractValidationError("bbox_xyxy must satisfy x1 < x2 and y1 < y2")

    source = event.get("source")
    robot_id = event.get("robot_id")
    expected_robot = {
        "global_cam_01": None,
        "tb3_1_picam": "tb3_1",
        "tb3_2_picam": "tb3_2",
    }.get(source)
    if robot_id != expected_robot:
        raise ContractValidationError(f"source {source!r} requires robot_id {expected_robot!r}")

    if event.get("depth_median_m") is not None:
        raise ContractValidationError("depth_median_m must remain null in MVP1")
