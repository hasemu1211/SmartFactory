from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "vision" / "run_gopro_evidence_capture_sidecar.py"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )


def test_evidence_capture_sidecar_check_is_no_hardware_and_reuse_first() -> None:
    result = _run("--check")
    payload = json.loads(result.stdout)

    assert payload["schema_version"] == "gopro-evidence-capture-sidecar.plan.v1"
    assert payload["public_endpoint_added"] is False
    assert payload["main_db_mutation"] is False
    assert payload["long_running_live_process"] is False
    assert payload["capture_profile"]["runtime_scope"] == "plan_mock_no_hardware"
    assert payload["reuse_first_endpoints"]["lift_roi_evaluate_image"].endswith(
        "/api/v1/lift-roi/evaluate-image"
    )
    assert payload["reuse_first_endpoints"]["evidence_evaluate"].endswith(
        "/api/v1/evidence/evaluate"
    )
    assert payload["forbidden_public_endpoint"] == "/api/v1/capture-lift-roi"


def test_evidence_capture_sidecar_mock_reports_quality_review_without_capture() -> None:
    result = _run("--mock-once", "--operation", "DROPOFF")
    payload = json.loads(result.stdout)

    assert payload["mode"] == "mock"
    assert payload["operation"] == "DROPOFF"
    assert payload["mock_result"]["verification_status"] == "UNCERTAIN"
    assert payload["mock_result"]["reason_code"] == "LOW_QUALITY_EVIDENCE"
