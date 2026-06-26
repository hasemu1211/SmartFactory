from __future__ import annotations

import os
import subprocess
import tempfile
import time
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
    assert "tb3-live-webrtc" in result.stdout
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
    assert "stream_target_fps=30" in result.stdout
    assert "ai_monitor_fps=5" in result.stdout
    assert "evidence_imgsz=960" in result.stdout
    assert "evidence_runtime_scope=plan_mock_no_hardware" in result.stdout
    assert "without sidecar templates" in result.stdout


def test_profile_files_are_sourceable_by_bash() -> None:
    for profile in PROFILE_DIR.glob("*.env"):
        subprocess.run(
            ["bash", "-c", f"set -euo pipefail; cd {ROOT}; source {profile}; true"],
            cwd=ROOT,
            check=True,
        )



def test_tb3_live_webrtc_profile_scopes_sidecar_to_single_robot_camera() -> None:
    result = run("print-config", "tb3-live-webrtc")

    assert "profile: tb3-live-webrtc" in result.stdout
    assert "SF_VISION_WEBRTC_SIDECAR_ENABLED=true" in result.stdout
    assert "gopro_stream_adapter: false" in result.stdout
    assert "source1_enabled: true" in result.stdout
    assert "source2_enabled: false" in result.stdout
    assert "sidecar_streams=tb3_1_picam/full" in result.stdout
    assert "VISION_WEBRTC_SIDECAR_WHEP_URL_TEMPLATE=http://smartfactory-vision.local:8889/{source}_{view}/whep" in result.stdout


def test_tb3_live_webrtc_profile_uses_hermetic_mjpeg_candidate_policy() -> None:
    result = subprocess.run(
        [
            "bash",
            "-lc",
            (
                "set -euo pipefail; "
                f"cd {ROOT}; "
                "export DIRECT_CLEAN_MEDIA_URL='rtsp://admin:secret@camera.local:8554/leak?token=abc'; "
                "export WEBRTC_CAMERA_INPUT_URL='/dev/video9'; "
                "set -a; source config/vision/profiles/tb3-live-webrtc.env; set +a; "
                "./scripts/vision/run_webrtc_sidecar_mediamtx.sh --print-config"
            ),
        ],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )

    assert "input_priority: mjpeg" in result.stdout
    assert "input_transport=mjpeg_overlay_h264_transcode_webrtc" in result.stdout
    assert "direct_clean_media_webrtc" not in result.stdout
    assert "camera_input_h264_transcode_webrtc" not in result.stdout
    assert "admin:secret" not in result.stdout
    assert "token=abc" not in result.stdout


def test_lab_gopro_tb3_webrtc_profile_prints_sidecar_urls_without_starting_processes() -> None:
    result = run("print-config", "lab-gopro-tb3-webrtc")

    assert "profile: lab-gopro-tb3-webrtc" in result.stdout
    assert "SF_VISION_WEBRTC_SIDECAR_ENABLED=true" in result.stdout
    assert "VISION_WEBRTC_SIDECAR_WHEP_URL_TEMPLATE=http://smartfactory-vision.local:8889/{source}_{view}/whep" in result.stdout
    assert "VISION_WEBRTC_SIDECAR_BROWSER_URL_TEMPLATE=http://smartfactory-vision.local:8889/{source}_{view}" in result.stdout
    assert "sidecar_streams=global_cam_01/full,global_cam_01/lift_roi,tb3_1_picam/full,tb3_2_picam/full" in result.stdout
    assert "ai_server_sidecar_streams=global_cam_01/full,global_cam_01/lift_roi,tb3_1_picam/full,tb3_2_picam/full" in result.stdout
    assert "stream_target_fps=30" in result.stdout
    assert "ai_monitor_fps=5" in result.stdout
    assert "ai_monitor_imgsz=640" in result.stdout


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
            "MEDIAMTX_WEBRTC_ADDITIONAL_HOSTS": "192.168.10.59",
        },
    )

    assert "path=global_cam_01_full" in result.stdout
    assert "webrtc_additional_hosts: 192.168.10.59" in result.stdout
    assert "gop: 15" in result.stdout
    assert "input_probesize: 2048" in result.stdout
    assert "input_analyzeduration: 0" in result.stdout
    assert "avioflags_direct: false" in result.stdout
    assert "output_muxdelay: 0" in result.stdout
    assert "browser=http://smartfactory-vision.local:8889/global_cam_01_full/" in result.stdout
    assert "whep=http://smartfactory-vision.local:8889/global_cam_01_full/whep" in result.stdout
    assert "rtsp://127.0.0.1:18554/global_cam_01_lift_roi" in result.stdout


def test_lab_gopro_tb3_webrtc_profile_exports_latency_knobs_to_sidecar_child() -> None:
    result = subprocess.run(
        [
            "bash",
            "-lc",
            (
                "set -euo pipefail; "
                f"cd {ROOT}; "
                "set -a; "
                "source config/vision/profiles/lab-gopro-tb3-webrtc.env; "
                "set +a; "
                "./scripts/vision/run_webrtc_sidecar_mediamtx.sh --print-config"
            ),
        ],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )

    assert "target_fps: 30" in result.stdout
    assert "x264_preset: ultrafast" in result.stdout
    assert "gop: 15" in result.stdout
    assert "bufsize: 500k" in result.stdout
    assert "input_probesize: 2048" in result.stdout
    assert "avioflags_direct: false" in result.stdout



def test_webrtc_sidecar_print_config_prefers_direct_camera_then_mjpeg_fallback() -> None:
    result = subprocess.run(
        [str(SIDECAR_SCRIPT), "--print-config"],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
        env={
            "PATH": "/usr/bin:/bin",
            "WEBRTC_SIDECAR_STREAMS": "global_cam_01/full",
            "WEBRTC_SIDECAR_INPUT_PRIORITY": "direct,camera",
            "WEBRTC_SIDECAR_DIRECT_INPUT_URL_TEMPLATE": "rtsp://127.0.0.1:8555/{source}_{view}",
            "WEBRTC_SIDECAR_CAMERA_INPUT_URL_TEMPLATE": "/dev/video0",
            "WEBRTC_SIDECAR_INPUT_URL_TEMPLATE": "http://127.0.0.1:8090/fallback?source={source}&view={view}&path={path}&max_fps={max_fps}",
            "VISION_PUBLIC_HOST": "smartfactory-vision.local",
            "MEDIAMTX_WEBRTC_ADDITIONAL_HOSTS": "192.168.10.59",
        },
    )

    assert "input_priority: direct,camera" in result.stdout
    assert "input=rtsp://127.0.0.1:8555/global_cam_01_full" in result.stdout
    assert "input_transport=direct_clean_media_webrtc" in result.stdout
    assert "- transport=direct_clean_media_webrtc format=auto url=rtsp://127.0.0.1:8555/global_cam_01_full" in result.stdout
    assert "- transport=camera_input_h264_transcode_webrtc format=v4l2 url=/dev/video0" in result.stdout
    assert "- transport=mjpeg_overlay_h264_transcode_webrtc format=mpjpeg url=http://127.0.0.1:8090/fallback?source=global_cam_01&view=full&path=global_cam_01_full&max_fps=15" in result.stdout


def test_webrtc_sidecar_print_config_redacts_camera_credentials() -> None:
    result = subprocess.run(
        [str(SIDECAR_SCRIPT), "--print-config"],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
        env={
            "PATH": "/usr/bin:/bin",
            "WEBRTC_SIDECAR_STREAMS": "global_cam_01/full",
            "WEBRTC_SIDECAR_DIRECT_INPUT_URL_TEMPLATE": "rtsp://admin:secret@camera.local:8554/{path}?token=abc&quality=ok",
            "WEBRTC_SIDECAR_INPUT_PRIORITY": "direct",
            "VISION_PUBLIC_HOST": "smartfactory-vision.local",
        },
    )

    assert "admin:secret" not in result.stdout
    assert "token=abc" not in result.stdout
    assert "direct_input_url_template: rtsp://<redacted>@camera.local:8554/{path}?token=REDACTED&quality=ok" in result.stdout
    assert "url=rtsp://<redacted>@camera.local:8554/global_cam_01_full?token=REDACTED&quality=ok" in result.stdout

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



def test_webrtc_sidecar_candidate_start_timeout_reaches_mjpeg_fallback() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        ffmpeg_log = tmp / "ffmpeg.log"
        mediamtx = tmp / "mediamtx"
        mediamtx.write_text("#!/usr/bin/env bash\nsleep 20\n", encoding="utf-8")
        mediamtx.chmod(0o755)
        ffmpeg = tmp / "ffmpeg"
        ffmpeg.write_text(
            "#!/usr/bin/env bash\n"
            f"printf '%s\\n' \"$*\" >> {ffmpeg_log}\n"
            "sleep 20\n",
            encoding="utf-8",
        )
        ffmpeg.chmod(0o755)
        curl = tmp / "curl"
        curl.write_text(
            "#!/usr/bin/env bash\n"
            "case \"$*\" in\n"
            "  */v3/paths/list*) printf '%s\\n' '{\"items\":[]}' ;;\n"
            "  *) echo ok ;;\n"
            "esac\n",
            encoding="utf-8",
        )
        curl.chmod(0o755)

        result = subprocess.run(
            [
                "timeout",
                "7s",
                str(SIDECAR_SCRIPT),
                "run",
            ],
            cwd=ROOT,
            check=False,
            text=True,
            capture_output=True,
            env={
                "PATH": f"{tmpdir}:/usr/bin:/bin",
                "SF_VISION_TMUX_GUARD_ENABLED": "false",
                "MEDIAMTX_BIN": str(mediamtx),
                "FFMPEG_BIN": str(ffmpeg),
                "FFPROBE_BIN": "/usr/bin/ffprobe",
                "CURL_BIN": str(curl),
                "SMARTFACTORY_VISION_RUN_DIR": str(tmp / "run"),
                "MEDIAMTX_RTSP_PORT": "28554",
                "MEDIAMTX_WEBRTC_PORT": "28889",
                "MEDIAMTX_WEBRTC_ICE_UDP_PORT": "28189",
                "MEDIAMTX_API_PORT": "29997",
                "WEBRTC_SIDECAR_STREAMS": "global_cam_01/full",
                "WEBRTC_SIDECAR_INPUT_PRIORITY": "direct",
                "WEBRTC_SIDECAR_DIRECT_INPUT_URL_TEMPLATE": "rtsp://127.0.0.1:29999/{path}",
                "WEBRTC_SIDECAR_INPUT_URL_TEMPLATE": "http://127.0.0.1:8090/fallback?source={source}&view={view}",
                "WEBRTC_SIDECAR_CANDIDATE_START_TIMEOUT_S": "1",
                "WEBRTC_SIDECAR_RESTART_SEC": "1",
            },
        )

        logged = ffmpeg_log.read_text(encoding="utf-8")
        publisher_log = tmp / "run" / "webrtc-sidecar" / "logs" / "publisher-global_cam_01_full.log"
        publisher_text = publisher_log.read_text(encoding="utf-8") if publisher_log.exists() else ""
        candidate_file = tmp / "run" / "webrtc-sidecar" / "input-candidates-global_cam_01_full.tsv"
        candidate_file_mode = candidate_file.stat().st_mode & 0o777 if candidate_file.exists() else None
        publisher_log_mode = publisher_log.stat().st_mode & 0o777 if publisher_log.exists() else None

    assert result.returncode in {124, 130, 143}
    assert "rtsp://127.0.0.1:29999/global_cam_01_full" in logged
    assert "http://127.0.0.1:8090/fallback?source=global_cam_01&view=full" in logged
    assert "did not become ready within 1s; trying next candidate" in publisher_text
    assert candidate_file_mode == 0o600
    assert publisher_log_mode == 0o600


def test_webrtc_sidecar_redacts_ffmpeg_emitted_credentials_in_publisher_log() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        mediamtx = tmp / "mediamtx"
        mediamtx.write_text("#!/usr/bin/env bash\nsleep 20\n", encoding="utf-8")
        mediamtx.chmod(0o755)
        ffmpeg = tmp / "ffmpeg"
        ffmpeg.write_text(
            "#!/usr/bin/env bash\n"
            "printf 'ffmpeg saw %s\\n' \"$*\" >&2\n"
            "sleep 20\n",
            encoding="utf-8",
        )
        ffmpeg.chmod(0o755)
        curl = tmp / "curl"
        curl.write_text(
            "#!/usr/bin/env bash\n"
            "case \"$*\" in\n"
            "  */v3/paths/list*) printf '%s\\n' '{\"items\":[]}' ;;\n"
            "  *) echo ok ;;\n"
            "esac\n",
            encoding="utf-8",
        )
        curl.chmod(0o755)
        raw_url = "rtsp://admin:secret@camera.local:8554/{path}?token=abc&quality=ok"

        result = subprocess.run(
            ["timeout", "5s", str(SIDECAR_SCRIPT), "run"],
            cwd=ROOT,
            check=False,
            text=True,
            capture_output=True,
            env={
                "PATH": f"{tmpdir}:/usr/bin:/bin",
                "SF_VISION_TMUX_GUARD_ENABLED": "false",
                "MEDIAMTX_BIN": str(mediamtx),
                "FFMPEG_BIN": str(ffmpeg),
                "FFPROBE_BIN": "/usr/bin/ffprobe",
                "CURL_BIN": str(curl),
                "SMARTFACTORY_VISION_RUN_DIR": str(tmp / "run"),
                "MEDIAMTX_RTSP_PORT": "28554",
                "MEDIAMTX_WEBRTC_PORT": "28889",
                "MEDIAMTX_WEBRTC_ICE_UDP_PORT": "28189",
                "MEDIAMTX_API_PORT": "29997",
                "WEBRTC_SIDECAR_STREAMS": "global_cam_01/full",
                "WEBRTC_SIDECAR_INPUT_PRIORITY": "direct",
                "WEBRTC_SIDECAR_DIRECT_INPUT_URL_TEMPLATE": raw_url,
                "WEBRTC_SIDECAR_CANDIDATE_START_TIMEOUT_S": "1",
                "WEBRTC_SIDECAR_RESTART_SEC": "1",
            },
        )

        publisher_log = tmp / "run" / "webrtc-sidecar" / "logs" / "publisher-global_cam_01_full.log"
        publisher_text = publisher_log.read_text(encoding="utf-8") if publisher_log.exists() else ""

    assert result.returncode in {124, 130, 143}
    assert "admin:secret" not in publisher_text
    assert "token=abc" not in publisher_text
    assert "rtsp://<redacted>@camera.local:8554/global_cam_01_full?token=REDACTED&quality=ok" in publisher_text


def _spawn_marker_process(*argv_markers: str) -> subprocess.Popen[str]:
    return subprocess.Popen(
        [
            "python3",
            "-c",
            "import time; time.sleep(30)",
            *argv_markers,
        ],
        text=True,
    )


def _spawn_fake_ffmpeg_process(*argv_markers: str) -> subprocess.Popen[str]:
    marker_script = "import time; time.sleep(30)"
    return subprocess.Popen(
        [
            "bash",
            "-c",
            'exec -a ffmpeg python3 -c "$1" "${@:2}"',
            "fake-ffmpeg-launcher",
            marker_script,
            *argv_markers,
        ],
        text=True,
    )


def _wait_for_process_exit(proc: subprocess.Popen[str], timeout_s: float = 5.0) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if proc.poll() is not None:
            return True
        time.sleep(0.1)
    return False


def test_operator_down_stale_sweep_does_not_kill_python_marker_with_matching_substrings() -> None:
    proc = _spawn_marker_process(
        "ffmpeg",
        "http://127.0.0.1:8090/api/v1/vision/overlay/stream?source=tb3_1_picam&view=full",
        "rtsp://127.0.0.1:18554/tb3_1_picam_full",
    )
    try:
        tmp_run_dir = tempfile.mkdtemp(prefix="sf-vision-down-test-")
        result = subprocess.run(
            [str(SCRIPT), "down"],
            cwd=ROOT,
            check=True,
            text=True,
            capture_output=True,
            env={
                "PATH": "/usr/bin:/bin",
                "SMARTFACTORY_VISION_RUN_DIR": tmp_run_dir,
            },
        )

        assert "stale SmartFactory MJPEG WebRTC publisher" not in result.stdout
        assert proc.poll() is None
    finally:
        proc.terminate()
        proc.wait(timeout=5)


def test_operator_down_stale_sweep_targets_smartfactory_mjpeg_publisher() -> None:
    proc = _spawn_fake_ffmpeg_process(
        "http://127.0.0.1:8090/api/v1/vision/overlay/stream?source=tb3_1_picam&view=full",
        "rtsp://127.0.0.1:38554/tb3_1_picam_full",
    )
    try:
        tmp_run_dir = Path(tempfile.mkdtemp(prefix="sf-vision-down-test-"))
        sidecar_run_dir = tmp_run_dir / "webrtc-sidecar"
        sidecar_run_dir.mkdir(parents=True)
        (sidecar_run_dir / "status.env").write_text("STATUS=stale\n", encoding="utf-8")
        result = subprocess.run(
            [str(SCRIPT), "down"],
            cwd=ROOT,
            check=True,
            text=True,
            capture_output=True,
            env={
                "PATH": "/usr/bin:/bin",
                "SMARTFACTORY_VISION_RUN_DIR": str(tmp_run_dir),
                "MEDIAMTX_RTSP_PORT": "38554",
            },
        )

        assert "stale SmartFactory MJPEG WebRTC publisher" in result.stdout
        assert _wait_for_process_exit(proc)
    finally:
        if subprocess.run(["kill", "-0", str(proc.pid)], check=False).returncode == 0:
            proc.terminate()
            proc.wait(timeout=5)

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



def test_webrtc_sidecar_tmux_guard_uses_current_pane_target() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmux = Path(tmpdir) / "tmux"
        tmux.write_text(
            "#!/usr/bin/env bash\n"
            "if [ \"$1\" = display-message ] && [ \"$3\" = -t ] && [ \"$4\" = %12 ]; then\n"
            "  echo Smartfactory:3:Development\n"
            "else\n"
            "  echo Smartfactory:1:Jira/Confluence\n"
            "fi\n",
            encoding="utf-8",
        )
        tmux.chmod(0o755)
        env = {
            "PATH": f"{tmpdir}:{os.environ.get('PATH', '')}",
            "TMUX": "/tmp/fake-tmux",
            "TMUX_PANE": "%12",
            "MEDIAMTX_BIN": "definitely_missing_mediamtx_for_test",
            "FFMPEG_BIN": "/usr/bin/ffmpeg",
            "FFPROBE_BIN": "/usr/bin/ffprobe",
            "CURL_BIN": "/usr/bin/curl",
            "SF_VISION_TMUX_REQUIRED_CONTEXT": "Smartfactory:3:Development",
        }

        result = subprocess.run(
            [str(SIDECAR_SCRIPT), "run"],
            cwd=ROOT,
            check=False,
            text=True,
            capture_output=True,
            env=env,
        )

    assert result.returncode != 0
    assert "live WebRTC sidecar processes must run" not in result.stderr
    assert "mediamtx executable not found" in result.stderr

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
