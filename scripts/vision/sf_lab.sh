#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"

DEFAULT_PROFILE="lab-gopro-tb3-webrtc"
DEFAULT_AI_SERVER_URL="http://127.0.0.1:8100"
DEFAULT_PUBLIC_HOST="smartfactory-vision.local"
DEFAULT_AI_SERVER_PORT="8100"
DEFAULT_WEBRTC_PORT="8889"
DEFAULT_STREAM_PORT="8090"
DEFAULT_MAIN_SERVER_URL="http://smartfactory-main.local:8088"

PROFILE="${SF_LAB_PROFILE:-${PROFILE:-${DEFAULT_PROFILE}}}"
AI_SERVER_URL="${AI_SERVER_URL:-${DEFAULT_AI_SERVER_URL}}"
VISION_PUBLIC_HOST="${VISION_PUBLIC_HOST:-${DEFAULT_PUBLIC_HOST}}"
AI_SERVER_PORT="${AI_SERVER_PORT:-${DEFAULT_AI_SERVER_PORT}}"
VISION_API_BASE_URL="${VISION_API_BASE_URL:-http://${VISION_PUBLIC_HOST}:${AI_SERVER_PORT}}"
MEDIAMTX_WEBRTC_PORT="${MEDIAMTX_WEBRTC_PORT:-${DEFAULT_WEBRTC_PORT}}"
VISION_STREAM_GATEWAY_PORT="${VISION_STREAM_GATEWAY_PORT:-${DEFAULT_STREAM_PORT}}"
MAIN_SERVER_URL="${MAIN_SERVER_URL:-${DEFAULT_MAIN_SERVER_URL}}"
CURL_TIMEOUT="${SF_LAB_CURL_TIMEOUT:-5}"

usage() {
  cat <<USAGE
Usage: $(basename "$0") <command> [args]

SmartFactory lab-friendly Vision entrypoint. It hides profile/env details for the
current GoPro global camera + TurtleBot Pi camera lab setup.

All-in-one live runtime (must run in tmux Smartfactory:3:Development):
  $(basename "$0") all                 # WebRTC global/Pi streams + AI Server API + MJPEG fallback
  $(basename "$0") stream              # same live runtime; operator-friendly alias
  $(basename "$0") down                # stop the bundled runtime

Separated checks / URLs:
  $(basename "$0") status              # bundle status + safe direct-media probe
  $(basename "$0") urls                # Main-facing WebRTC/MJPEG/API URLs
  $(basename "$0") check               # non-live dependency/profile preflight
  $(basename "$0") probe               # read-only direct-media/WebRTC path probe

API JSON helpers (call a running AI Server and print JSON for Main/connector checks):
  $(basename "$0") api health
  $(basename "$0") api streams [source]
  $(basename "$0") api worker-status [source]
  $(basename "$0") api worker-tick [source] [force]
  $(basename "$0") api webrtc-offer [source] [view]
  $(basename "$0") api evidence-plan [operation]
  $(basename "$0") api evidence-mock [operation]
  $(basename "$0") api evaluate-no-frame [source] [view] [operation]
  $(basename "$0") api evaluate-quality [source] [view]

Defaults:
  profile=${PROFILE}
  ai_server=${AI_SERVER_URL}
  public_host=${VISION_PUBLIC_HOST}
  main_facing_api=${VISION_API_BASE_URL}

Safety boundary: this wrapper does not launch robot motion, Nav2, teleop,
/cmd_vel, ROS parameter mutation, or whole-graph rosbridge. Robot Pi camera
bringup remains manual on the TurtleBot.
USAGE
}

need_cmd() {
  local name="$1"
  if ! command -v "${name}" >/dev/null 2>&1; then
    echo "ERROR: required command not found: ${name}" >&2
    return 127
  fi
}

curl_json_get() {
  need_cmd curl
  curl -fsS --max-time "${CURL_TIMEOUT}" "$1"
}

curl_json_post() {
  need_cmd curl
  local url="$1"
  local payload="$2"
  curl -fsS --max-time "${CURL_TIMEOUT}" \
    -H 'Content-Type: application/json' \
    -d "${payload}" \
    "${url}"
}

python_json() {
  python3 - "$@"
}

url_quote() {
  need_cmd python3
  python3 - "$1" <<'PY'
from urllib.parse import quote
import sys
print(quote(sys.argv[1], safe=""))
PY
}

upper_value() {
  printf '%s' "$1" | tr '[:lower:]' '[:upper:]'
}

normalize_plan_operation() {
  local operation
  operation="$(upper_value "${1:-PICKUP}")"
  case "${operation}" in
    PICKUP|DROPOFF|MONITOR) printf '%s\n' "${operation}" ;;
    *)
      echo "ERROR: operation must be PICKUP, DROPOFF, or MONITOR: ${1:-}" >&2
      return 2
      ;;
  esac
}

normalize_transition_operation() {
  local operation
  operation="$(upper_value "${1:-PICKUP}")"
  case "${operation}" in
    PICKUP|DROPOFF) printf '%s\n' "${operation}" ;;
    *)
      echo "ERROR: evaluate-no-frame operation must be PICKUP or DROPOFF: ${1:-}" >&2
      return 2
      ;;
  esac
}

cmd_all() {
  exec "${SCRIPT_DIR}/sf_vision.sh" up "${PROFILE}"
}

cmd_down() {
  exec "${SCRIPT_DIR}/sf_vision.sh" down
}

cmd_check() {
  "${SCRIPT_DIR}/sf_vision.sh" check "${PROFILE}"
}

cmd_status() {
  local status_code=0
  "${SCRIPT_DIR}/sf_vision.sh" status || status_code=$?
  echo
  echo "[sf-lab] safe direct-media/WebRTC probe"
  if command -v python3 >/dev/null 2>&1; then
    python3 "${SCRIPT_DIR}/probe_direct_media_candidates.py" || true
  else
    echo "python3 not found; skipping probe" >&2
  fi
  return "${status_code}"
}

cmd_probe() {
  need_cmd python3
  python3 "${SCRIPT_DIR}/probe_direct_media_candidates.py" "$@"
}

cmd_urls() {
  cat <<URLS
SmartFactory lab Vision URLs

Main dashboard:
  ${MAIN_SERVER_URL%/}/operate/control

AI Server API/discovery (Main-facing):
  ${VISION_API_BASE_URL%/}/api/v1/health
  ${VISION_API_BASE_URL%/}/api/v1/vision/streams
  ${VISION_API_BASE_URL%/}/api/v1/evidence/evaluate

Local API helper target:
  ${AI_SERVER_URL%/}

WebRTC browser URLs:
  http://${VISION_PUBLIC_HOST}:${MEDIAMTX_WEBRTC_PORT}/global_cam_01_full/
  http://${VISION_PUBLIC_HOST}:${MEDIAMTX_WEBRTC_PORT}/global_cam_01_lift_roi/
  http://${VISION_PUBLIC_HOST}:${MEDIAMTX_WEBRTC_PORT}/tb3_1_picam_full/
  http://${VISION_PUBLIC_HOST}:${MEDIAMTX_WEBRTC_PORT}/tb3_2_picam_full/

WebRTC WHEP URLs:
  http://${VISION_PUBLIC_HOST}:${MEDIAMTX_WEBRTC_PORT}/global_cam_01_full/whep
  http://${VISION_PUBLIC_HOST}:${MEDIAMTX_WEBRTC_PORT}/global_cam_01_lift_roi/whep
  http://${VISION_PUBLIC_HOST}:${MEDIAMTX_WEBRTC_PORT}/tb3_1_picam_full/whep
  http://${VISION_PUBLIC_HOST}:${MEDIAMTX_WEBRTC_PORT}/tb3_2_picam_full/whep

MJPEG fallback URLs:
  http://${VISION_PUBLIC_HOST}:${VISION_STREAM_GATEWAY_PORT}/streams/global_cam_01.mjpeg
  http://${VISION_PUBLIC_HOST}:${VISION_STREAM_GATEWAY_PORT}/streams/global_cam_01/lift_roi.mjpeg
  http://${VISION_PUBLIC_HOST}:${VISION_STREAM_GATEWAY_PORT}/streams/tb3_1_picam.mjpeg
  http://${VISION_PUBLIC_HOST}:${VISION_STREAM_GATEWAY_PORT}/streams/tb3_2_picam.mjpeg

Operator commands:
  ./scripts/vision/sf_lab.sh all
  ./scripts/vision/sf_lab.sh status
  ./scripts/vision/sf_lab.sh api streams
  ./scripts/vision/sf_lab.sh api evaluate-no-frame
URLS
}

api_health() {
  curl_json_get "${AI_SERVER_URL%/}/api/v1/health"
}

api_streams() {
  local source="${1:-}"
  local url="${AI_SERVER_URL%/}/api/v1/vision/streams"
  if [ -n "${source}" ]; then
    url="${url}?source=$(url_quote "${source}")"
  fi
  curl_json_get "${url}"
}

api_worker_status() {
  local source="${1:-global_cam_01}"
  curl_json_get "${AI_SERVER_URL%/}/api/v1/vision/worker/status?source=$(url_quote "${source}")"
}

api_worker_tick() {
  local source="${1:-global_cam_01}"
  local force="${2:-false}"
  local payload
  payload="$(python_json "${source}" "${force}" <<'PY'
import json
import sys
source = sys.argv[1]
force = sys.argv[2].lower() in {"1", "true", "yes", "y", "on", "force"}
print(json.dumps({"source": source, "force": force}, separators=(",", ":")))
PY
)"
  curl_json_post "${AI_SERVER_URL%/}/api/v1/vision/worker/tick" "${payload}"
}

api_webrtc_offer() {
  local source="${1:-global_cam_01}"
  local view="${2:-full}"
  curl_json_post "${AI_SERVER_URL%/}/api/v1/vision/streams/$(url_quote "${source}")/webrtc/offer?view=$(url_quote "${view}")" '{}'
}

api_evidence_plan() {
  local operation
  operation="$(normalize_plan_operation "${1:-PICKUP}")"
  need_cmd python3
  python3 "${SCRIPT_DIR}/run_gopro_evidence_capture_sidecar.py" \
    --check \
    --ai-server-url "${AI_SERVER_URL}" \
    --operation "${operation}"
}

api_evidence_mock() {
  local operation
  operation="$(normalize_plan_operation "${1:-PICKUP}")"
  need_cmd python3
  python3 "${SCRIPT_DIR}/run_gopro_evidence_capture_sidecar.py" \
    --mock-once \
    --ai-server-url "${AI_SERVER_URL}" \
    --operation "${operation}"
}

api_evaluate_no_frame() {
  local source="${1:-global_cam_01}"
  local view="${2:-lift_roi}"
  local operation
  local expected
  operation="$(normalize_transition_operation "${3:-PICKUP}")"
  case "${operation}" in
    PICKUP) expected="ITEM_PICKED" ;;
    DROPOFF) expected="ITEM_PLACED" ;;
  esac
  local payload
  payload="$(python_json "${source}" "${view}" "${operation}" "${expected}" <<'PY'
import json
import sys
source, view, operation, expected = sys.argv[1:5]
print(json.dumps({
    "source": source,
    "view": view,
    "operation": operation,
    "expected_evidence_type": expected,
    "expected_count": 1,
    "task_ref": {"task_id": "OPERATOR-NO-FRAME-CHECK"},
}, separators=(",", ":")))
PY
)"
  curl_json_post "${AI_SERVER_URL%/}/api/v1/evidence/evaluate" "${payload}"
}

api_evaluate_quality() {
  local source="${1:-global_cam_01}"
  local view="${2:-full}"
  local payload
  payload="$(python_json "${source}" "${view}" <<'PY'
import json
import sys
source, view = sys.argv[1:3]
print(json.dumps({
    "source": source,
    "view": view,
    "operation": "MONITOR",
    "expected_evidence_type": "ITEM_DROPPED_CANDIDATE",
    "task_ref": {"task_id": "OPERATOR-QUALITY-REVIEW"},
    "quality_flags": {
        "low_pixel_budget": True,
        "details": {
            "object_size_m": 0.04,
            "note": "operator helper for GoPro dropped-item pixel-budget review",
        },
    },
}, separators=(",", ":")))
PY
)"
  curl_json_post "${AI_SERVER_URL%/}/api/v1/evidence/evaluate" "${payload}"
}

cmd_api() {
  local subcommand="${1:-help}"
  shift || true
  case "${subcommand}" in
    health) api_health "$@" ;;
    streams) api_streams "$@" ;;
    worker-status|status) api_worker_status "$@" ;;
    worker-tick|tick) api_worker_tick "$@" ;;
    webrtc-offer|offer) api_webrtc_offer "$@" ;;
    evidence-plan|plan) api_evidence_plan "$@" ;;
    evidence-mock|mock) api_evidence_mock "$@" ;;
    evaluate-no-frame|no-frame) api_evaluate_no_frame "$@" ;;
    evaluate-quality|quality) api_evaluate_quality "$@" ;;
    help|-h|--help) usage ;;
    *)
      echo "ERROR: unknown api command: ${subcommand}" >&2
      usage >&2
      return 2
      ;;
  esac
}

main() {
  local command="${1:-help}"
  shift || true
  cd "${ROOT_DIR}"
  case "${command}" in
    all|up|stream) cmd_all "$@" ;;
    down|stop) cmd_down "$@" ;;
    check) cmd_check "$@" ;;
    status) cmd_status "$@" ;;
    probe) cmd_probe "$@" ;;
    urls|url) cmd_urls "$@" ;;
    api) cmd_api "$@" ;;
    help|-h|--help) usage ;;
    *)
      echo "ERROR: unknown command: ${command}" >&2
      usage >&2
      return 2
      ;;
  esac
}

main "$@"
