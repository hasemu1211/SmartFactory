from app.vision_monitor_policies import (
    RectRoi,
    evaluate_lift_load_burst,
    evaluate_lift_load_marker_burst,
)


def _carrier():
    return RectRoi("tb3_1_carrier", 100, 100, 400, 400, robot_id="tb3_1")


def _item(x=200, y=200, confidence=0.9):
    return {
        "class_name": "target_item",
        "confidence": confidence,
        "bbox_xyxy": [x - 5, y - 5, x + 5, y + 5],
    }


def _flatten(value):
    if isinstance(value, dict):
        for key, child in value.items():
            yield key
            yield from _flatten(child)
    elif isinstance(value, list):
        for child in value:
            yield from _flatten(child)
    else:
        yield value


def test_lift_load_burst_passes_when_expected_count_is_stable_in_enough_frames():
    result = evaluate_lift_load_burst(
        frames=[[_item()], [_item(confidence=0.88)], [_item(confidence=0.92)], [_item()], []],
        expected_count=1,
        carrier_roi=_carrier(),
        operation="PICKUP",
        min_pass_frames=4,
    )

    assert result["result"] == "PASS"
    assert result["event_type"] == "ITEM_PICKED"
    assert result["reason_code"] == "EXPECTED_ITEM_COUNT_MATCH_AND_STABLE"
    assert result["expected_count"] == 1
    assert result["observed_count"] == 1
    assert result["accepted_frames"] == 4
    assert result["total_frames"] == 5
    assert result["command_satisfying"] is True


def test_lift_load_burst_fails_when_expected_item_missing_in_all_frames():
    result = evaluate_lift_load_burst(
        frames=[[], [], [], [], []],
        expected_count=1,
        carrier_roi=_carrier(),
        operation="PICKUP",
        min_pass_frames=3,
    )

    assert result["result"] == "FAIL"
    assert result["event_type"] == "LIFT_LOAD_EVIDENCE"
    assert result["reason_code"] == "EXPECTED_ITEM_COUNT_MISMATCH"
    assert result["observed_count"] == 0
    assert result["command_satisfying"] is False


def test_lift_load_burst_uncertain_when_low_confidence_prevents_stable_pass():
    result = evaluate_lift_load_burst(
        frames=[[_item(confidence=0.9)], [_item(confidence=0.41)], [_item(confidence=0.92)], [], []],
        expected_count=1,
        carrier_roi=_carrier(),
        operation="PICKUP",
        min_confidence=0.5,
        min_pass_frames=3,
    )

    assert result["result"] == "UNCERTAIN"
    assert result["event_type"] == "LIFT_LOAD_UNCERTAIN"
    assert result["reason_code"] == "LOW_CONFIDENCE"
    assert result["accepted_frames"] == 2
    assert result["command_satisfying"] is False


def test_lift_load_burst_uncertain_when_detections_are_outside_carrier_roi():
    result = evaluate_lift_load_burst(
        frames=[[_item(x=800, y=800)], [_item(x=800, y=800)], [_item(x=800, y=800)]],
        expected_count=1,
        carrier_roi=_carrier(),
        operation="DROPOFF",
        min_pass_frames=2,
    )

    assert result["result"] == "UNCERTAIN"
    assert result["event_type"] == "LIFT_LOAD_UNCERTAIN"
    assert result["reason_code"] == "UNCERTAIN_ROI_CONFLICT"
    assert result["command_satisfying"] is False


def test_lift_load_burst_dropoff_pass_maps_to_item_placed():
    result = evaluate_lift_load_burst(
        frames=[[_item()], [_item()], [_item()]],
        expected_count=1,
        carrier_roi=_carrier(),
        operation="DROPOFF",
        min_pass_frames=3,
    )

    assert result["result"] == "PASS"
    assert result["event_type"] == "ITEM_PLACED"
    assert result["command_satisfying"] is True


def test_lift_load_burst_empty_frame_set_is_uncertain_not_command_satisfying():
    result = evaluate_lift_load_burst(
        frames=[],
        expected_count=1,
        carrier_roi=_carrier(),
        operation="PICKUP",
    )

    assert result["result"] == "UNCERTAIN"
    assert result["command_satisfying"] is False
    assert result["total_frames"] == 0


def test_lift_load_burst_output_is_compact_no_bbox_or_control_action():
    result = evaluate_lift_load_burst(
        frames=[[_item()], [_item()], [_item()]],
        expected_count=1,
        carrier_roi=_carrier(),
        operation="PICKUP",
    )
    flattened = set(_flatten(result))

    assert not (flattened & {"bbox", "bbox_xyxy", "mask", "polygon", "raw_detections"})
    assert not (flattened & {"E_STOP", "HOLD", "STOP_COMMAND", "MOTION_CANCELLED"})


def test_lift_load_marker_burst_passes_with_stable_expected_item_counts():
    result = evaluate_lift_load_marker_burst(
        per_frame_expected_counts=[1, 1, 1, 0, 0],
        per_frame_item_counts=[1, 1, 1, 0, 0],
        expected_count=1,
        operation="PICKUP",
        min_pass_frames=3,
        requested_frames=5,
    )

    assert result["result"] == "PASS"
    assert result["event_type"] == "ITEM_PICKED"
    assert result["reason_code"] == "EXPECTED_ITEM_COUNT_MATCH_AND_STABLE"
    assert result["confidence"] == 0.6
    assert result["accepted_frames"] == 3
    assert result["total_frames"] == 5


def test_lift_load_marker_burst_is_uncertain_when_default_burst_has_too_few_frames():
    result = evaluate_lift_load_marker_burst(
        per_frame_expected_counts=[1],
        per_frame_item_counts=[1],
        expected_count=1,
        operation="PICKUP",
        min_pass_frames=3,
        requested_frames=5,
    )

    assert result["result"] == "UNCERTAIN"
    assert result["event_type"] == "LIFT_LOAD_UNCERTAIN"
    assert result["reason_code"] == "LOW_CONFIDENCE"
    assert result["confidence"] == 0.2
    assert result["accepted_frames"] == 1
    assert result["total_frames"] == 1


def test_lift_load_marker_burst_fails_when_wrong_item_marker_is_present():
    result = evaluate_lift_load_marker_burst(
        per_frame_expected_counts=[0, 0, 0],
        per_frame_item_counts=[1, 1, 1],
        expected_count=1,
        operation="DROPOFF",
        min_pass_frames=2,
        requested_frames=3,
    )

    assert result["result"] == "FAIL"
    assert result["event_type"] == "LIFT_LOAD_EVIDENCE"
    assert result["reason_code"] == "EXPECTED_ITEM_COUNT_MISMATCH"
    assert result["observed_count"] == 1
    assert result["command_satisfying"] is False
