from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_ai_server_env_example_is_hostname_and_fixture_first():
    text = (ROOT / "services" / "ai-server" / ".env.example").read_text(encoding="utf-8")

    assert "VISION_MONITOR_EVENT_SCHEMA_VERSION=vision-monitor-event.v1" in text
    assert "VISION_MODEL_WORKER_ENABLED=false" in text
    assert "VISION_PUBLIC_HOST=smartfactory-vision.local" in text
    assert "http://192.168." not in text


def test_laptop_setup_doc_has_no_hardware_monitor_smoke_and_no_alert_wording():
    text = (ROOT / "docs" / "setup" / "ubuntu24-ai-vision-laptop.md").read_text(encoding="utf-8")

    assert "## No-hardware monitor/API smoke" in text
    assert "test_vision_monitor_event_contract.py" in text
    assert "test_main_db_adapter_shape.py" in text
    assert "ADVISORY/CANDIDATE" in text
    assert "CANDIDATE/ALERT" not in text
    assert "MX450/2GB-VRAM" in text
    assert "<handoff-git-ref>" in text
    assert "process-local/ephemeral" in text
    assert "revision" in text
    assert "reassert" in text
