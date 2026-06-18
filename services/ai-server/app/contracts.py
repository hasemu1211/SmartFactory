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


@lru_cache(maxsize=1)
def _lift_roi_validator() -> jsonschema.Draft202012Validator:
    settings = get_settings()
    schema_path = Path(settings.lift_roi_evidence_schema_path)
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


def _validate_bbox_order(bbox: list[Any]) -> None:
    x1, y1, x2, y2 = bbox
    if not (x1 < x2 and y1 < y2):
        raise ContractValidationError("bbox_xyxy must satisfy x1 < x2 and y1 < y2")


def validate_lift_roi_evidence(payload: dict[str, Any]) -> None:
    """Validate LiftRoiEvidence against schema and MVP1 policy checks."""

    _lift_roi_validator().validate(payload)

    load = payload["load"]
    accepted = load["accepted_items"]
    rejected = load["rejected_items"]
    if load["count"] != len(accepted):
        raise ContractValidationError("lift ROI load.count must equal accepted_items length")
    if load["empty"] != (load["count"] == 0):
        raise ContractValidationError("lift ROI load.empty must match count == 0")

    for item in accepted:
        _validate_bbox_order(item["bbox_xyxy"])
        if item["reason"] != "accepted":
            raise ContractValidationError("accepted lift ROI items must use reason accepted")
        if not item["center_inside_roi"]:
            raise ContractValidationError(
                "accepted lift ROI items must have center_inside_roi true"
            )
    for item in rejected:
        _validate_bbox_order(item["bbox_xyxy"])
        if item["reason"] == "accepted":
            raise ContractValidationError("rejected lift ROI items must not use reason accepted")

    verification = payload["verification"]
    if verification["status"] == "CONFIRMED" and payload["operation"] == "PICKUP":
        if payload["expected_count"] is None:
            raise ContractValidationError("confirmed pickup lift ROI evidence requires expected_count")
        if load["count"] != payload["expected_count"]:
            raise ContractValidationError(
                "confirmed pickup lift ROI evidence count must match expected_count"
            )
        if not payload["count_stable"]:
            raise ContractValidationError(
                "confirmed pickup lift ROI evidence requires count_stable true"
            )
        if payload["lift_sensor"].get("lift_up") is not True:
            raise ContractValidationError("confirmed pickup lift ROI evidence requires lift_up true")
        if payload["dropped_item_count"] != 0:
            raise ContractValidationError(
                "confirmed pickup lift ROI evidence requires dropped_item_count 0"
            )

    if verification["status"] == "CONFIRMED" and payload["operation"] == "DROPOFF":
        if payload["lift_sensor"].get("lift_down_complete") is not True:
            raise ContractValidationError(
                "confirmed dropoff lift ROI evidence requires lift_down_complete true"
            )
        if payload["lift_sensor"].get("backoff_complete") is not True:
            raise ContractValidationError(
                "confirmed dropoff lift ROI evidence requires backoff_complete true"
            )
