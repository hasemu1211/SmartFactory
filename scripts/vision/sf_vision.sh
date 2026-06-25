#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib/vision_bundle_common.sh
source "${SCRIPT_DIR}/../lib/vision_bundle_common.sh"
ROOT_DIR="$(sf_repo_root_from_script "${BASH_SOURCE[0]}")"
PROFILE_DIR="${ROOT_DIR}/config/vision/profiles"
RUN_DIR="${SMARTFACTORY_VISION_RUN_DIR:-${ROOT_DIR}/.run/vision}"
LOG_DIR="${RUN_DIR}/logs"
PID_FILE="${RUN_DIR}/pids.tsv"
SUPERVISOR_PID_FILE="${RUN_DIR}/supervisor.pid"
SUMMARY_FILE="${RUN_DIR}/summary.env"
DEFAULT_PROFILE="lab-gopro-tb3"

PROFILE=""
PROFILE_FILE=""
PIDS=()
NAMES=()
LOGS=()

usage() {
  cat <<USAGE
Usage: $(basename "$0") <command> [profile]

Operator entrypoint for SmartFactory Vision runtime. Long-running processes are
supervised as one local process group and remain media/evidence-only.

Commands:
  profiles                 List available profiles
  print-config [profile]   Print resolved operator config without starting live processes
  check [profile]          Run non-live preflight checks
  up [profile]             Start live Vision runtime in the foreground
  status                   Show recorded process status and local endpoint health
  smoke                    Curl local AI/gateway/discovery/WebRTC-fallback endpoints
  logs [name]              Tail all logs or one named log
  down                     Stop the supervised Vision runtime

Default profile: ${DEFAULT_PROFILE}

Typical demo:
  ./scripts/vision/sf_vision.sh up lab-gopro-tb3
  ./scripts/vision/sf_vision.sh status
  ./scripts/vision/sf_vision.sh smoke
  ./scripts/vision/sf_vision.sh down

WebRTC sidecar demo:
  ./scripts/vision/sf_vision.sh up lab-gopro-tb3-webrtc

Safety boundary: this script does not start robot motion, Nav2, teleop,
/cmd_vel, ROS parameter mutation, or a whole-graph rosbridge.
USAGE
}

is_truthy() {
  case "${1:-}" in
    1|true|TRUE|yes|YES|y|Y|on|ON) return 0 ;;
    *) return 1 ;;
  esac
}

list_profiles() {
  local file name
  for file in "${PROFILE_DIR}"/*.env; do
    [ -e "${file}" ] || continue
    name="$(basename "${file}" .env)"
    printf '%s\n' "${name}"
  done | sort
}

load_profile() {
  PROFILE="${1:-${DEFAULT_PROFILE}}"
  PROFILE_FILE="${PROFILE_DIR}/${PROFILE}.env"
  if [ ! -f "${PROFILE_FILE}" ]; then
    echo "ERROR: unknown profile '${PROFILE}'" >&2
    echo "Available profiles:" >&2
    list_profiles >&2
    return 2
  fi

  cd "${ROOT_DIR}"
  set -a
  # shellcheck disable=SC1090
  source "${PROFILE_FILE}"
  set +a

  RUN_DIR="${SMARTFACTORY_VISION_RUN_DIR:-${ROOT_DIR}/.run/vision}"
  LOG_DIR="${RUN_DIR}/logs"
  PID_FILE="${RUN_DIR}/pids.tsv"
  SUPERVISOR_PID_FILE="${RUN_DIR}/supervisor.pid"
  SUMMARY_FILE="${RUN_DIR}/summary.env"
  export SMARTFACTORY_VISION_RUN_DIR="${RUN_DIR}"

  export AI_SERVER_HOST="${AI_SERVER_HOST:-0.0.0.0}"
  export AI_SERVER_PORT="${AI_SERVER_PORT:-8100}"
  export AI_SERVER_URL="${AI_SERVER_URL:-http://127.0.0.1:${AI_SERVER_PORT}}"
  export AI_SERVER_VENV_DIR="${AI_SERVER_VENV_DIR:-${ROOT_DIR}/services/ai-server/.venv}"
  export VISION_STREAM_GATEWAY_PORT="${VISION_STREAM_GATEWAY_PORT:-8090}"
  export VISION_PUBLIC_HOST="${VISION_PUBLIC_HOST:-smartfactory-vision.local}"
  export MAIN_SERVER_URL="${MAIN_SERVER_URL:-http://smartfactory-main.local:8088}"
  export WMS_EMIT_ENABLED="${WMS_EMIT_ENABLED:-false}"
  export VISION_WEBRTC_ENABLED="${VISION_WEBRTC_ENABLED:-true}"
  export SF_VISION_MDNS_ENABLED="${SF_VISION_MDNS_ENABLED:-true}"
  export SF_VISION_BUNDLE_ENABLED="${SF_VISION_BUNDLE_ENABLED:-true}"
  export SF_VISION_GOPRO_ENABLED="${SF_VISION_GOPRO_ENABLED:-false}"
  export GOPRO_PORT="${GOPRO_PORT:-8554}"
  export GOPRO_PROTOCOL="${GOPRO_PROTOCOL:-TS}"
  export GOPRO_RESOLUTION="${GOPRO_RESOLUTION:-1080}"
  export GOPRO_FOV="${GOPRO_FOV:-WIDE}"
  export GOPRO_TEST_READ="${GOPRO_TEST_READ:-true}"
  export GOPRO_STREAM_WARMUP_SEC="${GOPRO_STREAM_WARMUP_SEC:-8}"
  export GOPRO_INPUT="${GOPRO_INPUT:-udp://0.0.0.0:${GOPRO_PORT}?overrun_nonfatal=1&fifo_size=50000000}"
  export GOPRO_SOURCE="${GOPRO_SOURCE:-global_cam_01}"
  export GOPRO_ROI_VIEW="${GOPRO_ROI_VIEW:-lift_roi}"
  export GOPRO_TARGET_FPS="${GOPRO_TARGET_FPS:-5}"
  export GOPRO_BUFFERLESS="${GOPRO_BUFFERLESS:-true}"
  export GOPRO_EVALUATE_LIFT_ROI="${GOPRO_EVALUATE_LIFT_ROI:-false}"
  export GOPRO_OPERATION="${GOPRO_OPERATION:-MONITOR}"
  export GOPRO_ROI_KIND="${GOPRO_ROI_KIND:-DROPPED_ITEM}"
  export SF_VISION_WEBRTC_SIDECAR_ENABLED="${SF_VISION_WEBRTC_SIDECAR_ENABLED:-false}"
  export MEDIAMTX_RTSP_PORT="${MEDIAMTX_RTSP_PORT:-18554}"
  export MEDIAMTX_WEBRTC_PORT="${MEDIAMTX_WEBRTC_PORT:-8889}"
  export MEDIAMTX_WEBRTC_ICE_UDP_PORT="${MEDIAMTX_WEBRTC_ICE_UDP_PORT:-8189}"
  export MEDIAMTX_API_PORT="${MEDIAMTX_API_PORT:-19997}"
  export WEBRTC_SIDECAR_PUBLIC_HOST="${WEBRTC_SIDECAR_PUBLIC_HOST:-${VISION_PUBLIC_HOST}}"
  export WEBRTC_SIDECAR_STREAMS="${WEBRTC_SIDECAR_STREAMS:-${GOPRO_SOURCE}/full,${GOPRO_SOURCE}/${GOPRO_ROI_VIEW}}"
  export WEBRTC_SIDECAR_INPUT_MAX_FPS="${WEBRTC_SIDECAR_INPUT_MAX_FPS:-15}"
  export WEBRTC_SIDECAR_TARGET_FPS="${WEBRTC_SIDECAR_TARGET_FPS:-15}"
  export SF_VISION_TMUX_GUARD_ENABLED="${SF_VISION_TMUX_GUARD_ENABLED:-true}"
  export SF_VISION_TMUX_REQUIRED_CONTEXT="${SF_VISION_TMUX_REQUIRED_CONTEXT:-Smartfactory:3:Development}"
  if is_truthy "${SF_VISION_WEBRTC_SIDECAR_ENABLED}"; then
    if [ -z "${VISION_WEBRTC_SIDECAR_WHEP_URL_TEMPLATE:-}" ]; then
      VISION_WEBRTC_SIDECAR_WHEP_URL_TEMPLATE="http://${WEBRTC_SIDECAR_PUBLIC_HOST}:${MEDIAMTX_WEBRTC_PORT}/{source}_{view}/whep"
    fi
    if [ -z "${VISION_WEBRTC_SIDECAR_BROWSER_URL_TEMPLATE:-}" ]; then
      VISION_WEBRTC_SIDECAR_BROWSER_URL_TEMPLATE="http://${WEBRTC_SIDECAR_PUBLIC_HOST}:${MEDIAMTX_WEBRTC_PORT}/{source}_{view}"
    fi
    if [ -z "${VISION_WEBRTC_SIDECAR_HEALTH_URL:-}" ]; then
      VISION_WEBRTC_SIDECAR_HEALTH_URL="http://127.0.0.1:${MEDIAMTX_WEBRTC_PORT}/"
    fi
    export VISION_WEBRTC_SIDECAR_WHEP_URL_TEMPLATE
    export VISION_WEBRTC_SIDECAR_BROWSER_URL_TEMPLATE
    export VISION_WEBRTC_SIDECAR_HEALTH_URL
    export VISION_WEBRTC_SIDECAR_HEALTH_TIMEOUT_S="${VISION_WEBRTC_SIDECAR_HEALTH_TIMEOUT_S:-0.25}"
  else
    export VISION_WEBRTC_SIDECAR_WHEP_URL_TEMPLATE="${VISION_WEBRTC_SIDECAR_WHEP_URL_TEMPLATE:-}"
    export VISION_WEBRTC_SIDECAR_BROWSER_URL_TEMPLATE="${VISION_WEBRTC_SIDECAR_BROWSER_URL_TEMPLATE:-}"
    export VISION_WEBRTC_SIDECAR_HEALTH_URL="${VISION_WEBRTC_SIDECAR_HEALTH_URL:-}"
    export VISION_WEBRTC_SIDECAR_HEALTH_TIMEOUT_S="${VISION_WEBRTC_SIDECAR_HEALTH_TIMEOUT_S:-0.25}"
  fi
}

public_base_url() {
  printf 'http://%s:%s\n' "${VISION_PUBLIC_HOST}" "${VISION_STREAM_GATEWAY_PORT:-8090}"
}

api_base_url() {
  printf 'http://%s:%s\n' "${VISION_PUBLIC_HOST}" "${AI_SERVER_PORT:-8100}"
}

print_config() {
  local ip
  ip="$(sf_lan_ip "${VISION_MAIN_HOST:-}" || true)"
  ip="${ip:-127.0.0.1}"
  cat <<CONFIG
SmartFactory Vision operator config
  profile: ${PROFILE}
  profile_file: ${PROFILE_FILE}
  description: ${SF_VISION_DESCRIPTION:-<none>}
  run_dir: ${RUN_DIR}
  logs: ${LOG_DIR}

Processes selected by profile:
  mdns_alias: ${SF_VISION_MDNS_ENABLED}
  local_bundle: ${SF_VISION_BUNDLE_ENABLED}
  gopro_stream_adapter: ${SF_VISION_GOPRO_ENABLED}
  source1_enabled: ${VISION_SOURCE_1_ENABLED:-true} (${VISION_SOURCE_1_ID:-tb3_1_picam}, domain=${VISION_SOURCE_1_DOMAIN:-2})
  source2_enabled: ${VISION_SOURCE_2_ENABLED:-true} (${VISION_SOURCE_2_ID:-tb3_2_picam}, domain=${VISION_SOURCE_2_DOMAIN:-5})

Main-facing URLs:
  VISION_API_BASE_URL=$(api_base_url)
  VISION_STREAM_BASE_URL=$(public_base_url)
  LMS_VISION_STREAM_BASE_URL=$(public_base_url)
  detected_lan_fallback=http://${ip}:${VISION_STREAM_GATEWAY_PORT}

WebRTC status:
  VISION_WEBRTC_ENABLED=${VISION_WEBRTC_ENABLED}
  SF_VISION_WEBRTC_SIDECAR_ENABLED=${SF_VISION_WEBRTC_SIDECAR_ENABLED}
  VISION_WEBRTC_SIDECAR_OFFER_URL_TEMPLATE=${VISION_WEBRTC_SIDECAR_OFFER_URL_TEMPLATE:-<empty>}
  VISION_WEBRTC_SIDECAR_WHEP_URL_TEMPLATE=${VISION_WEBRTC_SIDECAR_WHEP_URL_TEMPLATE:-<empty>}
  VISION_WEBRTC_SIDECAR_BROWSER_URL_TEMPLATE=${VISION_WEBRTC_SIDECAR_BROWSER_URL_TEMPLATE:-<empty>}
  VISION_WEBRTC_SIDECAR_HEALTH_URL=${VISION_WEBRTC_SIDECAR_HEALTH_URL:-<empty>}
  sidecar_streams=${WEBRTC_SIDECAR_STREAMS:-<empty>}
  sidecar_ports=rtsp:${MEDIAMTX_RTSP_PORT:-18554}/tcp,webrtc:${MEDIAMTX_WEBRTC_PORT:-8889}/tcp,ice:${MEDIAMTX_WEBRTC_ICE_UDP_PORT:-8189}/udp
  tmux_guard=${SF_VISION_TMUX_GUARD_ENABLED} required=${SF_VISION_TMUX_REQUIRED_CONTEXT}
  note: without sidecar templates, WebRTC offer intentionally selects MJPEG fallback.

GoPro:
  enabled=${SF_VISION_GOPRO_ENABLED}
  protocol/resolution/fov/port=${GOPRO_PROTOCOL}/${GOPRO_RESOLUTION}/${GOPRO_FOV}/${GOPRO_PORT}
  input=${GOPRO_INPUT}
  source/view=${GOPRO_SOURCE}/${GOPRO_ROI_VIEW}
  target_fps=${GOPRO_TARGET_FPS}
CONFIG
}

ensure_dirs() {
  mkdir -p "${LOG_DIR}"
}

alive_pid() {
  local pid="${1:-}"
  [ -n "${pid}" ] && kill -0 "${pid}" 2>/dev/null
}

ensure_not_running() {
  if [ -f "${SUPERVISOR_PID_FILE}" ]; then
    local old_pid
    old_pid="$(cat "${SUPERVISOR_PID_FILE}" 2>/dev/null || true)"
    if alive_pid "${old_pid}"; then
      echo "ERROR: Vision runtime already appears to be running (supervisor pid=${old_pid})." >&2
      echo "Run: ./scripts/vision/sf_vision.sh status or down" >&2
      return 1
    fi
  fi
  rm -f "${PID_FILE}" "${SUPERVISOR_PID_FILE}" "${SUMMARY_FILE}"
}

record_summary() {
  cat > "${SUMMARY_FILE}" <<SUMMARY
PROFILE=${PROFILE}
PROFILE_FILE=${PROFILE_FILE}
VISION_API_BASE_URL=$(api_base_url)
VISION_STREAM_BASE_URL=$(public_base_url)
LMS_VISION_STREAM_BASE_URL=$(public_base_url)
AI_SERVER_URL=${AI_SERVER_URL}
MAIN_SERVER_URL=${MAIN_SERVER_URL}
SF_VISION_WEBRTC_SIDECAR_ENABLED=${SF_VISION_WEBRTC_SIDECAR_ENABLED}
VISION_WEBRTC_SIDECAR_WHEP_URL_TEMPLATE=${VISION_WEBRTC_SIDECAR_WHEP_URL_TEMPLATE:-}
VISION_WEBRTC_SIDECAR_BROWSER_URL_TEMPLATE=${VISION_WEBRTC_SIDECAR_BROWSER_URL_TEMPLATE:-}
VISION_WEBRTC_SIDECAR_HEALTH_URL=${VISION_WEBRTC_SIDECAR_HEALTH_URL:-}
SF_VISION_TMUX_REQUIRED_CONTEXT=${SF_VISION_TMUX_REQUIRED_CONTEXT}
SUMMARY
}

record_process() {
  local name="$1" pid="$2" log="$3"
  printf '%s\t%s\t%s\n' "${name}" "${pid}" "${log}" >> "${PID_FILE}"
}

start_logged() {
  local name="$1"
  shift
  local log="${LOG_DIR}/${name}.log"
  {
    printf '[sf-vision] start %s at %s\n' "${name}" "$(date -Is)"
    printf '[sf-vision] command:'
    printf ' %q' "$@"
    printf '\n--- output ---\n'
  } > "${log}"
  (cd "${ROOT_DIR}" && exec "$@" >> "${log}" 2>&1) &
  local pid=$!
  PIDS+=("${pid}")
  NAMES+=("${name}")
  LOGS+=("${log}")
  record_process "${name}" "${pid}" "${log}"
  echo "[sf-vision] ${name} pid=${pid} log=${log}"
}

wait_for_url() {
  local label="$1" url="$2" timeout_s="${3:-45}"
  local start now
  start="$(date +%s)"
  echo "[sf-vision] waiting for ${label}: ${url}"
  while true; do
    if command -v curl >/dev/null 2>&1 && curl -fsS --max-time 1 "${url}" >/dev/null 2>&1; then
      echo "[sf-vision] ${label}: ok"
      return 0
    fi
    now="$(date +%s)"
    if [ $((now - start)) -ge "${timeout_s}" ]; then
      echo "ERROR: timeout waiting for ${label}: ${url}" >&2
      return 1
    fi
    sleep 1
  done
}

current_tmux_context() {
  if [ -z "${TMUX:-}" ] || ! command -v tmux >/dev/null 2>&1; then
    return 1
  fi
  tmux display-message -p '#S:#I:#W' 2>/dev/null
}

require_live_tmux_context() {
  if ! is_truthy "${SF_VISION_TMUX_GUARD_ENABLED:-true}"; then
    return 0
  fi
  local current
  current="$(current_tmux_context || true)"
  if [ "${current}" = "${SF_VISION_TMUX_REQUIRED_CONTEXT}" ]; then
    return 0
  fi
  cat >&2 <<ERROR
ERROR: live Vision processes must run in tmux ${SF_VISION_TMUX_REQUIRED_CONTEXT}.
Current context: ${current:-<not inside tmux>}
Open/switch to that tmux window before running: ./scripts/vision/sf_vision.sh up ${PROFILE:-${DEFAULT_PROFILE}}
ERROR
  return 1
}

run_enabled_preflights() {
  bash -n "${BASH_SOURCE[0]}"
  bash -n "${ROOT_DIR}/scripts/vision/run_d1_vision_multi_source_gateway_bundle.sh"
  bash -n "${ROOT_DIR}/scripts/vision/run_webrtc_sidecar_mediamtx.sh"
  if is_truthy "${SF_VISION_BUNDLE_ENABLED}"; then
    "${ROOT_DIR}/scripts/vision/run_d1_vision_multi_source_gateway_bundle.sh" --check
  fi
  if is_truthy "${SF_VISION_GOPRO_ENABLED}"; then
    local py="${AI_SERVER_VENV_DIR}/bin/python"
    "${py}" "${ROOT_DIR}/scripts/vision/run_gopro_smart_roi_adapter.py" --check
    "${py}" "${ROOT_DIR}/scripts/vision/start_gopro_webcam_stream.py" --help >/dev/null
  fi
  if is_truthy "${SF_VISION_WEBRTC_SIDECAR_ENABLED}"; then
    "${ROOT_DIR}/scripts/vision/run_webrtc_sidecar_mediamtx.sh" --check
  fi
}

start_mdns() {
  if is_truthy "${SF_VISION_MDNS_ENABLED}"; then
    start_logged mdns-alias python3 scripts/vision/publish_vision_mdns_alias.py
  fi
}

start_bundle() {
  if is_truthy "${SF_VISION_BUNDLE_ENABLED}"; then
    start_logged vision-bundle ./scripts/vision/run_d1_vision_multi_source_gateway_bundle.sh
    wait_for_url "AI Server" "${AI_SERVER_URL%/}/api/v1/health" "${AI_SERVER_START_TIMEOUT_SEC:-60}"
    wait_for_url "Vision Stream Gateway" "http://127.0.0.1:${VISION_STREAM_GATEWAY_PORT}/api/v1/vision/bridge/status" "${VISION_GATEWAY_START_TIMEOUT_SEC:-45}"
  fi
}

start_gopro() {
  if ! is_truthy "${SF_VISION_GOPRO_ENABLED}"; then
    return 0
  fi
  local py="${AI_SERVER_VENV_DIR}/bin/python"
  if [ ! -x "${py}" ]; then
    echo "ERROR: AI Server python not found: ${py}" >&2
    return 1
  fi

  local stream_cmd=("${py}" scripts/vision/start_gopro_webcam_stream.py --protocol "${GOPRO_PROTOCOL}" --resolution "${GOPRO_RESOLUTION}" --fov "${GOPRO_FOV}" --port "${GOPRO_PORT}")
  if is_truthy "${GOPRO_TEST_READ}"; then
    stream_cmd+=(--test-read)
  fi
  start_logged gopro-stream "${stream_cmd[@]}"

  echo "[sf-vision] warming up GoPro stream for ${GOPRO_STREAM_WARMUP_SEC}s"
  sleep "${GOPRO_STREAM_WARMUP_SEC}"

  local adapter_cmd=("${py}" scripts/vision/run_gopro_smart_roi_adapter.py --input "${GOPRO_INPUT}" --source "${GOPRO_SOURCE}" --roi-view "${GOPRO_ROI_VIEW}" --ai-server-url "${AI_SERVER_URL}" --target-fps "${GOPRO_TARGET_FPS}" --operation "${GOPRO_OPERATION}" --roi-kind "${GOPRO_ROI_KIND}")
  if is_truthy "${GOPRO_BUFFERLESS}"; then
    adapter_cmd+=(--bufferless)
  else
    adapter_cmd+=(--no-bufferless)
  fi
  if is_truthy "${GOPRO_EVALUATE_LIFT_ROI}"; then
    adapter_cmd+=(--evaluate-lift-roi)
  fi
  start_logged gopro-adapter "${adapter_cmd[@]}"
}

start_webrtc_sidecar() {
  if ! is_truthy "${SF_VISION_WEBRTC_SIDECAR_ENABLED}"; then
    return 0
  fi
  "${ROOT_DIR}/scripts/vision/run_webrtc_sidecar_mediamtx.sh" --check
  start_logged webrtc-sidecar ./scripts/vision/run_webrtc_sidecar_mediamtx.sh
}

cleanup() {
  local status=$?
  trap - INT TERM EXIT
  if [ "${#PIDS[@]}" -gt 0 ]; then
    echo "[sf-vision] stopping ${#PIDS[@]} child process(es)"
    local i
    for ((i=${#PIDS[@]}-1; i>=0; i--)); do
      kill -INT "${PIDS[$i]}" 2>/dev/null || true
    done
    sleep 2
    for ((i=${#PIDS[@]}-1; i>=0; i--)); do
      kill -TERM "${PIDS[$i]}" 2>/dev/null || true
    done
    wait 2>/dev/null || true
  fi
  rm -f "${SUPERVISOR_PID_FILE}"
  exit "${status}"
}

run_up() {
  load_profile "${1:-${DEFAULT_PROFILE}}"
  require_live_tmux_context
  print_config
  run_enabled_preflights
  ensure_dirs
  ensure_not_running
  echo "$$" > "${SUPERVISOR_PID_FILE}"
  : > "${PID_FILE}"
  record_summary
  trap cleanup INT TERM EXIT
  start_mdns
  start_bundle
  start_gopro
  start_webrtc_sidecar
  echo "[sf-vision] running. Ctrl-C or ./scripts/vision/sf_vision.sh down stops all child processes."
  set +e
  wait -n "${PIDS[@]}"
  local child_status=$?
  set -e
  echo "[sf-vision] a child process exited (status=${child_status}); shutting down runtime"
  exit "${child_status}"
}

run_check() {
  load_profile "${1:-${DEFAULT_PROFILE}}"
  print_config
  run_enabled_preflights
  echo "[sf-vision] check ok: ${PROFILE}"
}

status() {
  echo "SmartFactory Vision runtime status"
  if [ -f "${SUMMARY_FILE}" ]; then
    sed 's/^/  /' "${SUMMARY_FILE}"
  else
    echo "  no summary file: ${SUMMARY_FILE}"
  fi
  if [ -f "${SUPERVISOR_PID_FILE}" ]; then
    local spid
    spid="$(cat "${SUPERVISOR_PID_FILE}" 2>/dev/null || true)"
    if alive_pid "${spid}"; then
      echo "  supervisor: alive pid=${spid}"
    else
      echo "  supervisor: stale pid=${spid}"
    fi
  else
    echo "  supervisor: not recorded"
  fi
  if [ -f "${PID_FILE}" ]; then
    while IFS=$'\t' read -r name pid log; do
      [ -n "${name:-}" ] || continue
      if alive_pid "${pid}"; then
        printf '  %-18s alive pid=%s log=%s\n' "${name}" "${pid}" "${log}"
      else
        printf '  %-18s stopped pid=%s log=%s\n' "${name}" "${pid}" "${log}"
      fi
    done < "${PID_FILE}"
  else
    echo "  process table: not recorded"
  fi
}

smoke() {
  local api="http://127.0.0.1:${AI_SERVER_PORT:-8100}"
  local stream="http://127.0.0.1:${VISION_STREAM_GATEWAY_PORT:-8090}"
  echo "[sf-vision] smoke AI health"
  curl -fsS --max-time 2 "${api}/api/v1/health" >/dev/null
  echo "[sf-vision] smoke gateway status"
  curl -fsS --max-time 2 "${stream}/api/v1/vision/bridge/status" >/dev/null
  echo "[sf-vision] smoke stream discovery: global_cam_01"
  curl -fsS --max-time 2 "${api}/api/v1/vision/streams?source=global_cam_01" >/dev/null
  echo "[sf-vision] smoke WebRTC candidate/fallback offer"
  curl -fsS --max-time 2 -X POST "${api}/api/v1/vision/streams/global_cam_01/webrtc/offer?view=full" -H 'Content-Type: application/json' -d '{}' >/dev/null
  if [ -f "${SUMMARY_FILE}" ] && grep -q '^SF_VISION_WEBRTC_SIDECAR_ENABLED=true$' "${SUMMARY_FILE}"; then
    echo "[sf-vision] smoke WebRTC sidecar status"
    "${ROOT_DIR}/scripts/vision/run_webrtc_sidecar_mediamtx.sh" --status >/dev/null
  fi
  echo "[sf-vision] smoke ok"
}

logs() {
  local name="${1:-}"
  if [ -n "${name}" ]; then
    if [ ! -f "${LOG_DIR}/${name}.log" ]; then
      echo "ERROR: log not found: ${LOG_DIR}/${name}.log" >&2
      return 1
    fi
    tail -n 80 -f "${LOG_DIR}/${name}.log"
  else
    local logs=()
    while IFS= read -r log; do
      logs+=("${log}")
    done < <(find "${LOG_DIR}" -maxdepth 1 -type f -name '*.log' 2>/dev/null | sort)
    if [ "${#logs[@]}" -eq 0 ]; then
      echo "No logs found under ${LOG_DIR}"
      return 0
    fi
    printf '%s\n' "${logs[@]}"
    tail -n 40 -f "${logs[@]}"
  fi
}

down() {
  local stopped=0
  if [ -f "${SUPERVISOR_PID_FILE}" ]; then
    local spid
    spid="$(cat "${SUPERVISOR_PID_FILE}" 2>/dev/null || true)"
    if alive_pid "${spid}"; then
      echo "[sf-vision] stopping supervisor pid=${spid}"
      kill -INT "${spid}" 2>/dev/null || true
      stopped=1
      sleep 3
    fi
  fi
  if [ -f "${PID_FILE}" ]; then
    while IFS=$'\t' read -r name pid log; do
      [ -n "${pid:-}" ] || continue
      if alive_pid "${pid}"; then
        echo "[sf-vision] stopping child ${name} pid=${pid}"
        kill -TERM "${pid}" 2>/dev/null || true
        stopped=1
      fi
    done < "${PID_FILE}"
  fi
  if [ "${stopped}" -eq 0 ]; then
    echo "[sf-vision] no live recorded runtime found"
  fi
}

cmd="${1:-}"
case "${cmd}" in
  profiles) list_profiles ;;
  print-config) load_profile "${2:-${DEFAULT_PROFILE}}"; print_config ;;
  check) run_check "${2:-${DEFAULT_PROFILE}}" ;;
  up) run_up "${2:-${DEFAULT_PROFILE}}" ;;
  status) status ;;
  smoke) smoke ;;
  logs) logs "${2:-}" ;;
  down) down ;;
  --help|-h|help|"") usage ;;
  *) echo "ERROR: unknown command: ${cmd}" >&2; usage >&2; exit 2 ;;
esac
