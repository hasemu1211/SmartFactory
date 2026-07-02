from fastapi.testclient import TestClient

from app.factory import create_app
from app.runtime_state import create_runtime_context
from app.vision_monitor_profiles import (
    DROP_WATCH_PROFILE_ID,
    PERSON_DRIVE_PROFILE_ID,
    PERSON_DRIVE_THRESHOLD_SET_ID,
)


def _client():
    context = create_runtime_context()
    return TestClient(create_app(runtime_context=context))


def test_monitor_state_defaults_are_disabled_for_known_profiles():
    client = _client()

    response = client.get("/api/v1/vision/monitors")

    assert response.status_code == 200
    body = response.json()
    monitors = {item["monitor_id"]: item for item in body["monitors"]}
    assert set(monitors) == {"person_drive", "drop_watch", "lift_evidence"}
    assert all(item["enabled"] is False for item in monitors.values())
    assert all(item["operation_state"] == "IDLE" for item in monitors.values())
    assert all(item["revision"] == 0 for item in monitors.values())


def test_put_monitor_state_enables_person_drive_and_infers_robot_from_picam_source():
    client = _client()

    response = client.put(
        "/api/v1/vision/monitors/person_drive/state",
        json={
            "enabled": True,
            "source": "tb3_1_picam",
            "operation_state": "DRIVE",
            "task_id": 101,
            "target_fps": 3,
            "profile_id": PERSON_DRIVE_PROFILE_ID,
            "threshold_set_id": PERSON_DRIVE_THRESHOLD_SET_ID,
        },
    )

    assert response.status_code == 200
    monitor = response.json()["monitor"]
    assert monitor["enabled"] is True
    assert monitor["source"] == "tb3_1_picam"
    assert monitor["robot_id"] == "tb3_1"
    assert monitor["operation_state"] == "DRIVE"
    assert monitor["target_fps"] == 3.0
    assert monitor["updated_at"] is not None
    assert monitor["revision"] == 1

    get_response = client.get("/api/v1/vision/monitors/person_drive/state")
    assert get_response.status_code == 200
    assert get_response.json()["monitor"] == monitor

    second_response = client.put(
        "/api/v1/vision/monitors/person_drive/state",
        json={
            "enabled": True,
            "source": "tb3_1_picam",
            "operation_state": "DRIVE",
            "task_id": 102,
            "target_fps": 2,
        },
    )
    assert second_response.status_code == 200
    assert second_response.json()["monitor"]["revision"] == 2


def test_monitor_state_accepts_global_drop_watch_context_without_fixed_robot_identity():
    client = _client()

    response = client.put(
        "/api/v1/vision/monitors/drop_watch/state",
        json={
            "enabled": True,
            "source": "global_cam_01",
            "operation_state": "DRIVE",
            "target_fps": 2,
            "profile_id": DROP_WATCH_PROFILE_ID,
        },
    )

    assert response.status_code == 200
    monitor = response.json()["monitor"]
    assert monitor["source"] == "global_cam_01"
    assert monitor["robot_id"] is None
    assert monitor["operation_state"] == "DRIVE"


def test_monitor_state_requires_lift_evidence_robot_context():
    client = _client()

    response = client.put(
        "/api/v1/vision/monitors/lift_evidence/state",
        json={"enabled": True, "source": "global_cam_01", "operation_state": "PICKUP"},
    )

    assert response.status_code == 400
    assert "requires robot_id" in response.json()["error"]["message"]


def test_monitor_state_rejects_invalid_source_robot_mapping():
    client = _client()

    response = client.put(
        "/api/v1/vision/monitors/person_drive/state",
        json={
            "enabled": True,
            "source": "tb3_1_picam",
            "robot_id": "tb3_2",
            "operation_state": "DRIVE",
        },
    )

    assert response.status_code == 400
    assert "requires robot_id" in response.json()["error"]["message"]


def test_monitor_state_rejects_wrong_operation_for_drive_only_monitors():
    client = _client()

    response = client.put(
        "/api/v1/vision/monitors/drop_watch/state",
        json={"enabled": True, "source": "global_cam_01", "operation_state": "PICKUP"},
    )

    assert response.status_code == 400
    assert "DROP_WATCH" not in response.text
    assert "drop_watch can be enabled only in DRIVE" in response.json()["error"]["message"]


def test_monitor_state_rejects_unknown_monitor_id():
    client = _client()

    response = client.get("/api/v1/vision/monitors/not_a_monitor/state")

    assert response.status_code == 400
    assert "unknown monitor_id" in response.json()["error"]["message"]


def test_main_dashboard_cors_allows_put_monitor_state():
    client = _client()

    response = client.options(
        "/api/v1/vision/monitors/person_drive/state",
        headers={
            "Origin": "http://smartfactory-main.local:8088",
            "Access-Control-Request-Method": "PUT",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://smartfactory-main.local:8088"
    assert "PUT" in response.headers["access-control-allow-methods"]


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


def test_person_hazard_latest_returns_no_active_monitor_until_drive_monitor_enabled():
    client = _client()

    response = client.get("/api/v1/vision/hazards/person/latest", params={"robot_id": "tb3_1"})

    assert response.status_code == 200
    body = response.json()
    assert body["result"] == "NO_ACTIVE_MONITOR"
    assert body["event"] is None


def test_person_hazard_latest_maps_existing_person_event_to_advisory_payload():
    context = create_runtime_context()
    client = TestClient(create_app(runtime_context=context))
    context.store.add(
        {
            "event_id": "source-person-event-1",
            "source": "tb3_1_picam",
            "class_name": "person",
            "confidence": 0.87,
            "timestamp": "2026-06-30T05:00:00+00:00",
            "bbox_xyxy": [1, 2, 3, 4],
        }
    )
    context.store.add(
        {
            "event_id": "source-marker-event-1",
            "source": "tb3_1_picam",
            "class_name": "aruco_marker",
            "confidence": 0.99,
            "timestamp": "2026-06-30T05:00:01+00:00",
        }
    )
    client.put(
        "/api/v1/vision/monitors/person_drive/state",
        json={
            "enabled": True,
            "source": "tb3_1_picam",
            "operation_state": "DRIVE",
            "task_id": 777,
        },
    )

    response = client.get("/api/v1/vision/hazards/person/latest", params={"robot_id": "tb3_1"})

    assert response.status_code == 200
    body = response.json()
    event = body["event"]
    assert body["result"] == "ADVISORY"
    assert body["reason_code"] == "HUMAN_DETECTED"
    assert event["schema_version"] == "vision-monitor-event.v1"
    assert event["event_type"] == "HUMAN_DETECTED"
    assert event["source"] == "tb3_1_picam"
    assert event["robot_id"] == "tb3_1"
    assert event["task_id"] == 777
    assert event["trusted"] is False
    assert event["confidence"] == 0.87
    assert event["data_json"]["source_event_id"] == "source-person-event-1"
    assert "bbox_xyxy" not in set(_flatten(event))
    assert "HOLD" not in set(_flatten(event))


def test_person_hazard_latest_returns_empty_when_monitor_active_but_no_person_event():
    context = create_runtime_context()
    client = TestClient(create_app(runtime_context=context))
    context.store.add(
        {
            "event_id": "source-marker-event-2",
            "source": "tb3_2_picam",
            "class_name": "aruco_marker",
            "confidence": 0.99,
            "timestamp": "2026-06-30T05:00:01+00:00",
        }
    )
    client.put(
        "/api/v1/vision/monitors/person_drive/state",
        json={"enabled": True, "source": "tb3_2_picam", "operation_state": "DRIVE"},
    )

    response = client.get("/api/v1/vision/hazards/person/latest", params={"robot_id": "tb3_2"})

    assert response.status_code == 200
    body = response.json()
    assert body["result"] == "NO_RELEVANT_DETECTION"
    assert body["event"] is None


def test_person_drive_monitor_supports_two_robots_driving_at_the_same_time():
    context = create_runtime_context()
    client = TestClient(create_app(runtime_context=context))
    context.store.add(
        {
            "event_id": "tb3-1-person",
            "source": "tb3_1_picam",
            "class_name": "person",
            "confidence": 0.81,
            "timestamp": "2026-06-30T05:00:00+00:00",
        }
    )
    context.store.add(
        {
            "event_id": "tb3-2-person",
            "source": "tb3_2_picam",
            "class_name": "person",
            "confidence": 0.91,
            "timestamp": "2026-06-30T05:00:01+00:00",
        }
    )

    tb3_1_on = client.put(
        "/api/v1/vision/monitors/person_drive/state",
        json={
            "enabled": True,
            "source": "tb3_1_picam",
            "operation_state": "DRIVE",
            "task_id": 101,
        },
    )
    tb3_2_on = client.put(
        "/api/v1/vision/monitors/person_drive/state",
        json={
            "enabled": True,
            "source": "tb3_2_picam",
            "operation_state": "DRIVE",
            "task_id": 202,
        },
    )
    assert tb3_1_on.status_code == 200
    assert tb3_2_on.status_code == 200

    tb3_1_state = client.get(
        "/api/v1/vision/monitors/person_drive/state",
        params={"robot_id": "tb3_1"},
    ).json()["monitor"]
    tb3_2_state = client.get(
        "/api/v1/vision/monitors/person_drive/state",
        params={"robot_id": "tb3_2"},
    ).json()["monitor"]
    assert tb3_1_state["enabled"] is True
    assert tb3_1_state["source"] == "tb3_1_picam"
    assert tb3_1_state["task_id"] == 101
    assert tb3_2_state["enabled"] is True
    assert tb3_2_state["source"] == "tb3_2_picam"
    assert tb3_2_state["task_id"] == 202

    tb3_1_latest = client.get(
        "/api/v1/vision/hazards/person/latest",
        params={"robot_id": "tb3_1"},
    ).json()
    tb3_2_latest = client.get(
        "/api/v1/vision/hazards/person/latest",
        params={"robot_id": "tb3_2"},
    ).json()
    assert tb3_1_latest["result"] == "ADVISORY"
    assert tb3_1_latest["event"]["task_id"] == 101
    assert tb3_1_latest["event"]["data_json"]["source_event_id"] == "tb3-1-person"
    assert tb3_2_latest["result"] == "ADVISORY"
    assert tb3_2_latest["event"]["task_id"] == 202
    assert tb3_2_latest["event"]["data_json"]["source_event_id"] == "tb3-2-person"


def test_disabling_one_person_drive_robot_keeps_the_other_robot_active():
    context = create_runtime_context()
    client = TestClient(create_app(runtime_context=context))
    for source, event_id in (
        ("tb3_1_picam", "tb3-1-person"),
        ("tb3_2_picam", "tb3-2-person"),
    ):
        context.store.add(
            {
                "event_id": event_id,
                "source": source,
                "class_name": "person",
                "confidence": 0.88,
                "timestamp": "2026-06-30T05:00:00+00:00",
            }
        )
        client.put(
            "/api/v1/vision/monitors/person_drive/state",
            json={
                "enabled": True,
                "source": source,
                "operation_state": "DRIVE",
            },
        )

    response = client.put(
        "/api/v1/vision/monitors/person_drive/state",
        json={
            "enabled": False,
            "source": "tb3_1_picam",
            "operation_state": "IDLE",
        },
    )
    assert response.status_code == 200

    tb3_1_latest = client.get(
        "/api/v1/vision/hazards/person/latest",
        params={"robot_id": "tb3_1"},
    ).json()
    tb3_2_latest = client.get(
        "/api/v1/vision/hazards/person/latest",
        params={"robot_id": "tb3_2"},
    ).json()
    assert tb3_1_latest["result"] == "NO_ACTIVE_MONITOR"
    assert tb3_1_latest["event"] is None
    assert tb3_2_latest["result"] == "ADVISORY"
    assert tb3_2_latest["event"]["source"] == "tb3_2_picam"


def test_person_hazard_latest_rejects_robot_source_mismatch():
    client = _client()

    response = client.get(
        "/api/v1/vision/hazards/person/latest",
        params={"robot_id": "tb3_1", "source": "tb3_2_picam"},
    )

    assert response.status_code == 400
    assert "requires source tb3_1_picam" in response.json()["error"]["message"]


def test_monitor_and_person_hazard_routes_have_explicit_openapi_response_schemas():
    schema = create_app(runtime_context=create_runtime_context()).openapi()

    monitor_list_schema = schema["paths"]["/api/v1/vision/monitors"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    monitor_state_schema = schema["paths"]["/api/v1/vision/monitors/{monitor_id}/state"]["put"]["responses"]["200"]["content"]["application/json"]["schema"]
    hazard_schema = schema["paths"]["/api/v1/vision/hazards/person/latest"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]

    assert monitor_list_schema["additionalProperties"] is False
    assert monitor_list_schema["properties"]["monitors"]["minItems"] == 4
    assert monitor_list_schema["properties"]["monitors"]["items"]["properties"]["revision"]["minimum"] == 0
    assert monitor_state_schema["properties"]["monitor"]["description"].startswith("Process-local")
    assert hazard_schema["properties"]["event"]["anyOf"][0]["type"] == "null"
    assert hazard_schema["properties"]["event"]["anyOf"][1]["properties"]["trusted"]["const"] is False
