from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "vision" / "sf_vision.sh"
SIDECAR_SCRIPT = ROOT / "scripts" / "vision" / "run_webrtc_sidecar_mediamtx.sh"
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
    subprocess.run(["bash", "-n", str(SIDECAR_SCRIPT)], cwd=ROOT, check=True)


def test_operator_profiles_are_discoverable() -> None:
    result = run("profiles")

    assert "local-smoke" in result.stdout
    assert "tb3-live" in result.stdout
    assert "gopro-segment" in result.stdout
    assert "lab-gopro-tb3" in result.stdout
    assert "lab-gopro-tb3-webrtc" in result.stdout


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


def test_lab_gopro_tb3_webrtc_profile_prints_sidecar_urls_without_starting_processes() -> None:
    result = run("print-config", "lab-gopro-tb3-webrtc")

    assert "profile: lab-gopro-tb3-webrtc" in result.stdout
    assert "SF_VISION_WEBRTC_SIDECAR_ENABLED=true" in result.stdout
    assert "VISION_WEBRTC_SIDECAR_WHEP_URL_TEMPLATE=http://smartfactory-vision.local:8889/{source}_{view}/whep" in result.stdout
    assert "VISION_WEBRTC_SIDECAR_BROWSER_URL_TEMPLATE=http://smartfactory-vision.local:8889/{source}_{view}" in result.stdout
    assert "sidecar_streams=global_cam_01/full,global_cam_01/lift_roi" in result.stdout


def test_webrtc_sidecar_print_config_exposes_media_only_urls() -> None:
    result = subprocess.run(
        [str(SIDECAR_SCRIPT), "--print-config"],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
        env={
            "PATH": "/usr/bin:/bin",
            "WEBRTC_SIDECAR_STREAMS": "global_cam_01/full,global_cam_01/lift_roi",
            "VISION_PUBLIC_HOST": "smartfactory-vision.local",
        },
    )

    assert "path=global_cam_01_full" in result.stdout
    assert "browser=http://smartfactory-vision.local:8889/global_cam_01_full" in result.stdout
    assert "whep=http://smartfactory-vision.local:8889/global_cam_01_full/whep" in result.stdout
    assert "rtsp://127.0.0.1:18554/global_cam_01_lift_roi" in result.stdout


def test_webrtc_sidecar_check_reports_missing_mediamtx_actionably() -> None:
    result = subprocess.run(
        [str(SIDECAR_SCRIPT), "--check"],
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
        env={
            "PATH": "/usr/bin:/bin",
            "MEDIAMTX_BIN": "definitely_missing_mediamtx_for_test",
            "FFMPEG_BIN": "/usr/bin/ffmpeg",
            "FFPROBE_BIN": "/usr/bin/ffprobe",
            "CURL_BIN": "/usr/bin/curl",
        },
    )

    assert result.returncode != 0
    combined = result.stdout + result.stderr
    assert "mediamtx executable not found" in combined
    assert "MEDIAMTX_BIN=/absolute/path/to/mediamtx" in combined


def test_operator_up_refuses_wrong_tmux_context_before_starting_processes() -> None:
    result = subprocess.run(
        [str(SCRIPT), "up", "local-smoke"],
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
        env={
            "PATH": "/usr/bin:/bin",
            "TMUX": "",
            "SF_VISION_TMUX_REQUIRED_CONTEXT": "NoSuchSession:9:Nowhere",
        },
    )

    assert result.returncode != 0
    assert "live Vision processes must run in tmux NoSuchSession:9:Nowhere" in result.stderr
    assert "[sf-vision] start" not in result.stdout + result.stderr


def test_webrtc_sidecar_run_refuses_wrong_tmux_context_before_dependency_checks() -> None:
    result = subprocess.run(
        [str(SIDECAR_SCRIPT), "run"],
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
        env={
            "PATH": "/usr/bin:/bin",
            "TMUX": "",
            "MEDIAMTX_BIN": "definitely_missing_mediamtx_for_test",
            "SF_VISION_TMUX_REQUIRED_CONTEXT": "NoSuchSession:9:Nowhere",
        },
    )

    assert result.returncode != 0
    assert "live WebRTC sidecar processes must run in tmux NoSuchSession:9:Nowhere" in result.stderr
    assert "mediamtx executable not found" not in result.stderr
