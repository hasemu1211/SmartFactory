#!/usr/bin/env python3
"""No-hardware-safe plan/mock for GoPro transition-proof evidence capture.

The production direction is reuse-first:

1. keep the normal stream path alive where possible,
2. evaluate transition proof through /api/v1/lift-roi/evaluate-image, and
3. expose the connector-facing judgement through /api/v1/evidence/evaluate.

This helper intentionally does not add a public capture-lift-roi endpoint and
does not start a live hardware loop. It gives operators and tests a stable
contract for the high-resolution evidence path that will later sit beside the
live GoPro adapter.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any


FORBIDDEN_PUBLIC_ENDPOINT = "/api/v1/capture-lift-roi"


def _truthy(value: str | None) -> bool:
    return str(value or "").lower() in {"1", "true", "yes", "y", "on"}


def _plan(args: argparse.Namespace) -> dict[str, Any]:
    ai_server_url = args.ai_server_url.rstrip("/")
    return {
        "schema_version": "gopro-evidence-capture-sidecar.plan.v1",
        "mode": args.mode,
        "source": args.source,
        "view": args.view,
        "operation": args.operation,
        "capture_profile": {
            "stream_target_fps": args.stream_target_fps,
            "ai_monitor_fps": args.ai_monitor_fps,
            "ai_monitor_imgsz": args.ai_monitor_imgsz,
            "evidence_imgsz": args.evidence_imgsz,
            "capture_mode": args.capture_mode,
            "runtime_scope": args.runtime_scope,
            "dropped_item_conf": args.dropped_item_conf,
        },
        "reuse_first_endpoints": {
            "lift_roi_evaluate_image": f"{ai_server_url}/api/v1/lift-roi/evaluate-image",
            "evidence_evaluate": f"{ai_server_url}/api/v1/evidence/evaluate",
        },
        "forbidden_public_endpoint": FORBIDDEN_PUBLIC_ENDPOINT,
        "public_endpoint_added": False,
        "advisory_only": True,
        "main_db_mutation": False,
        "long_running_live_process": False,
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="print the reusable capture/evidence plan and exit successfully",
    )
    parser.add_argument(
        "--mock-once",
        action="store_true",
        help="print one mock transition-proof decision without touching hardware",
    )
    parser.add_argument(
        "--mode",
        choices=["plan", "mock", "live"],
        default="plan",
        help="live is reserved for a later hardware-gated implementation",
    )
    parser.add_argument(
        "--ai-server-url",
        default=os.environ.get("AI_SERVER_URL", "http://127.0.0.1:8100"),
    )
    parser.add_argument("--source", default=os.environ.get("GOPRO_SOURCE", "global_cam_01"))
    parser.add_argument("--view", default=os.environ.get("GOPRO_ROI_VIEW", "lift_roi"))
    parser.add_argument(
        "--operation",
        choices=["PICKUP", "DROPOFF", "MONITOR"],
        default=os.environ.get("GOPRO_OPERATION", "PICKUP"),
    )
    parser.add_argument(
        "--stream-target-fps",
        type=float,
        default=float(os.environ.get("GOPRO_STREAM_TARGET_FPS", "30")),
    )
    parser.add_argument(
        "--ai-monitor-fps",
        type=float,
        default=float(
            os.environ.get("GOPRO_AI_MONITOR_FPS", os.environ.get("GOPRO_TARGET_FPS", "5"))
        ),
    )
    parser.add_argument(
        "--ai-monitor-imgsz",
        type=int,
        default=int(
            os.environ.get("GOPRO_AI_MONITOR_IMGSZ", os.environ.get("VISION_MODEL_IMGSZ", "640"))
        ),
    )
    parser.add_argument(
        "--evidence-imgsz",
        type=int,
        default=int(os.environ.get("GOPRO_EVIDENCE_IMGSZ", "960")),
    )
    parser.add_argument(
        "--dropped-item-conf",
        type=float,
        default=float(os.environ.get("GOPRO_DROPPED_ITEM_CONF", "0.25")),
    )
    parser.add_argument(
        "--capture-mode",
        default=os.environ.get(
            "GOPRO_EVIDENCE_CAPTURE_MODE",
            "parallel_then_pause_then_stream_frame",
        ),
    )
    parser.add_argument(
        "--runtime-scope",
        default=os.environ.get("GOPRO_EVIDENCE_RUNTIME_SCOPE", "plan_mock_no_hardware"),
    )
    return parser.parse_args(argv)


def run(args: argparse.Namespace) -> int:
    if args.check:
        args.mode = "plan"
    if args.mock_once:
        args.mode = "mock"

    plan = _plan(args)
    if args.mode == "mock":
        plan["mock_result"] = {
            "verification_status": "UNCERTAIN",
            "reason_code": "LOW_QUALITY_EVIDENCE",
            "next_endpoint": plan["reuse_first_endpoints"]["evidence_evaluate"],
            "notes": "Mock only; no image capture or Main DB mutation was performed.",
        }
    elif args.mode == "live":
        if not _truthy(os.environ.get("GOPRO_EVIDENCE_LIVE_ALLOWED")):
            plan["blocked"] = {
                "reason": "live hardware capture is outside the no-hardware implementation goal",
                "required_override": "GOPRO_EVIDENCE_LIVE_ALLOWED=true",
            }
            print(json.dumps(plan, ensure_ascii=False, sort_keys=True))
            return 2

    print(json.dumps(plan, ensure_ascii=False, sort_keys=True))
    return 0


def main(argv: list[str] | None = None) -> int:
    return run(parse_args(argv or sys.argv[1:]))


if __name__ == "__main__":
    raise SystemExit(main())
