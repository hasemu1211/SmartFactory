import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import REPO_ROOT, _legacy_source_registry, get_settings
from app.main import app

client = TestClient(app)


def test_source_registry_loads_mvp_sources_and_topics():
    registry = get_settings().source_registry

    assert registry.schema_version == "vision-sources.v1"
    assert registry.source_ids == ["global_cam_01", "tb3_1_picam", "tb3_2_picam"]
    assert registry.all_source_ids == [
        "global_cam_01",
        "global_depth_01",
        "tb3_1_picam",
        "tb3_2_picam",
    ]
    tb3_1 = registry.get("tb3_1_picam")
    assert tb3_1.robot_id == "tb3_1"
    assert tb3_1.frame_id == "tb3_1_pi_camera_optical_frame"
    assert tb3_1.physical_input.topic == "/tb3_1/camera/image_raw/compressed"
    assert tb3_1.physical_input.message_type == "sensor_msgs/msg/CompressedImage"
    assert tb3_1.normalized_topics.overlay == "/sf/vision/sources/tb3_1_picam/overlay/compressed"


def test_source_registry_view_contract_keeps_realsense_planned_and_view_scoped():
    registry = get_settings().source_registry
    source = registry.get("global_depth_01")

    assert not source.enabled
    assert source.view_ids == ("full", "pallet_zoom")
    assert source.resolve_view().view_id == "full"
    assert not registry.can_confirm_internal_color_indexing("global_depth_01")
    assert registry.can_confirm_internal_color_indexing("global_depth_01", "pallet_zoom")
    assert not registry.can_confirm_internal_color_indexing("global_cam_01")
    try:
        registry.resolve_view("global_depth_01", "bad_view")
    except KeyError as exc:
        assert exc.args == ("bad_view",)
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("unknown source view must be rejected")


def test_legacy_source_registry_keeps_implicit_full_view_contract():
    registry = _legacy_source_registry(
        source_ids=["legacy_cam"],
        image_topics=["/legacy/camera/image_raw"],
    )
    source = registry.get("legacy_cam")

    assert registry.source_ids == ["legacy_cam"]
    assert source.view_ids == ("full",)
    assert source.resolve_view().view_id == "full"
    assert not registry.can_confirm_internal_color_indexing("legacy_cam")


def test_contract_schema_source_enums_match_registry():
    source_ids = get_settings().source_registry.source_ids
    contract_dir = REPO_ROOT / "docs" / "contracts"

    for name in ("vision-event.schema.json", "lift-roi-evidence.schema.json"):
        schema = json.loads((contract_dir / name).read_text(encoding="utf-8"))
        assert schema["properties"]["source"]["enum"] == source_ids


def test_generated_source_registry_snapshot_matches_registry():
    registry = get_settings().source_registry.as_snapshot()
    generated = json.loads(
        (REPO_ROOT / "docs" / "contracts" / "generated" / "source-registry.snapshot.json").read_text(
            encoding="utf-8"
        )
    )
    fixture = json.loads(
        (REPO_ROOT / "docs" / "contracts" / "fixtures" / "source-registry.valid.json").read_text(
            encoding="utf-8"
        )
    )

    assert generated == registry
    assert fixture == registry


def _source_property(schema: dict, path: str, method: str, name: str = "source") -> dict:
    operation = schema["paths"][path][method]
    for parameter in operation.get("parameters", []):
        if parameter["name"] == name:
            return parameter["schema"]
    body_ref = operation["requestBody"]["content"]
    content = next(iter(body_ref.values()))
    ref = content["schema"]["$ref"].rsplit("/", 1)[-1]
    return schema["components"]["schemas"][ref]["properties"][name]


def test_openapi_source_fields_expose_registry_enum_without_changing_runtime_400s():
    schema = app.openapi()
    source_ids = get_settings().source_registry.source_ids

    assert _source_property(schema, "/api/v1/vision/streams", "get")["enum"] == source_ids
    assert _source_property(schema, "/api/v1/vision/frame", "post")["enum"] == source_ids
    assert _source_property(schema, "/api/v1/vision/synthetic/frame", "post")["enum"] == source_ids
    assert _source_property(schema, "/api/v1/detect/image", "post")["enum"] == source_ids

    bad = client.get("/api/v1/vision/streams", params={"source": "bad_cam"})
    assert bad.status_code == 400
    assert bad.json()["error"]["code"] == "BAD_REQUEST"
