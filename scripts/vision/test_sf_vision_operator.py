from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "vision" / "sf_vision.sh"
PROFILE_DIR = ROOT / "config" / "vision" / "profiles"


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(SCRIPT), *args],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )


def test_operator_script_is_valid_bash() -> None:
    subprocess.run(["bash", "-n", str(SCRIPT)], cwd=ROOT, check=True)


def test_operator_profiles_are_discoverable() -> None:
    result = run("profiles")

    assert "local-smoke" in result.stdout
    assert "tb3-live" in result.stdout
    assert "gopro-segment" in result.stdout
    assert "lab-gopro-tb3" in result.stdout


def test_lab_gopro_tb3_profile_prints_main_facing_urls_without_starting_processes() -> None:
    result = run("print-config", "lab-gopro-tb3")

    assert "profile: lab-gopro-tb3" in result.stdout
    assert "VISION_API_BASE_URL=http://smartfactory-vision.local:8100" in result.stdout
    assert "VISION_STREAM_BASE_URL=http://smartfactory-vision.local:8090" in result.stdout
    assert "gopro_stream_adapter: true" in result.stdout
    assert "source1_enabled: true" in result.stdout
    assert "source2_enabled: false" in result.stdout
    assert "without sidecar templates" in result.stdout


def test_profile_files_are_sourceable_by_bash() -> None:
    for profile in PROFILE_DIR.glob("*.env"):
        subprocess.run(
            ["bash", "-c", f"set -euo pipefail; cd {ROOT}; source {profile}; true"],
            cwd=ROOT,
            check=True,
        )
