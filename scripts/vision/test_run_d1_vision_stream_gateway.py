from __future__ import annotations

import importlib.util
import json
import subprocess
from http import HTTPStatus
from pathlib import Path
from types import SimpleNamespace

import pytest

MODULE_PATH = Path(__file__).resolve().parent / "run_d1_vision_stream_gateway.py"
spec = importlib.util.spec_from_file_location("run_d1_vision_stream_gateway", MODULE_PATH)
gateway = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(gateway)


def test_env_source_upstreams_defaults_to_internal_loopback_allowlist(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("VISION_STREAM_SOURCE_UPSTREAMS_JSON", raising=False)

    assert gateway._env_source_upstreams() == {
        "tb3_1_picam": "http://127.0.0.1:18090",
        "tb3_2_picam": "http://127.0.0.1:18091",
    }


def test_env_source_upstreams_requires_json_object_and_loopback_http_urls(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VISION_STREAM_SOURCE_UPSTREAMS_JSON", '["http://127.0.0.1:18090"]')
    with pytest.raises(ValueError, match="JSON object"):
        gateway._env_source_upstreams()

    monkeypatch.setenv(
        "VISION_STREAM_SOURCE_UPSTREAMS_JSON",
        json.dumps({"tb3_1_picam": "file:///tmp/not-an-internal-stream"}),
    )
    with pytest.raises(ValueError, match="invalid source upstream mapping"):
        gateway._env_source_upstreams()

    monkeypatch.setenv(
        "VISION_STREAM_SOURCE_UPSTREAMS_JSON",
        json.dumps({"tb3_1_picam": "http://203.0.113.10:18090"}),
    )
    monkeypatch.delenv("VISION_STREAM_ALLOW_NON_LOOPBACK_UPSTREAMS", raising=False)
    with pytest.raises(ValueError, match="invalid source upstream mapping"):
        gateway._env_source_upstreams()

    monkeypatch.setenv("VISION_STREAM_ALLOW_NON_LOOPBACK_UPSTREAMS", "true")
    assert gateway._env_source_upstreams() == {"tb3_1_picam": "http://203.0.113.10:18090"}


def test_clamp_fps_keeps_stream_gateway_bounded() -> None:
    assert gateway._clamp_fps(None) == 30.0
    assert gateway._clamp_fps("bad") == 30.0
    assert gateway._clamp_fps("0") == 1.0
    assert gateway._clamp_fps("120") == 30.0
    assert gateway._clamp_fps("12.5") == 12.5


class _MethodCaptureHandler(gateway.VisionStreamGatewayHandler):
    def __init__(self) -> None:
        self.responses: list[int] = []
        self.headers: list[tuple[str, str]] = []
        self.wfile = SimpleNamespace(payload=b"")
        self.wfile.write = lambda data: setattr(self.wfile, "payload", self.wfile.payload + data)

    def send_response(self, code: int, message: str | None = None) -> None:  # type: ignore[override]
        self.responses.append(code)

    def send_header(self, keyword: str, value: str) -> None:  # type: ignore[override]
        self.headers.append((keyword, value))

    def end_headers(self) -> None:  # type: ignore[override]
        return None


def test_mutating_http_methods_are_read_only() -> None:
    handler = _MethodCaptureHandler()

    handler.do_POST()

    assert handler.responses == [HTTPStatus.METHOD_NOT_ALLOWED.value]
    assert ("Allow", "GET, OPTIONS") in handler.headers
    assert json.loads(handler.wfile.payload.decode("utf-8")) == {
        "ok": False,
        "error": "read-only gateway",
    }


def test_multi_source_bundle_print_config_keeps_source_bridges_loopback_only() -> None:
    result = subprocess.run(
        ["bash", "scripts/vision/run_d1_vision_multi_source_gateway_bundle.sh", "--print-config"],
        check=True,
        cwd=Path(__file__).resolve().parents[2],
        text=True,
        capture_output=True,
    )

    assert "public_gateway: 0.0.0.0:8090" in result.stdout
    assert '"tb3_1_picam":"http://127.0.0.1:18090"' in result.stdout
    assert '"tb3_2_picam":"http://127.0.0.1:18091"' in result.stdout
    assert "http://0.0.0.0:18090" not in result.stdout
    assert "http://0.0.0.0:18091" not in result.stdout
