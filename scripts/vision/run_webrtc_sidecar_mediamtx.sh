#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib/vision_bundle_common.sh
source "${SCRIPT_DIR}/../lib/vision_bundle_common.sh"
ROOT_DIR="$(sf_repo_root_from_script "${BASH_SOURCE[0]}")"

RUN_DIR="${SMARTFACTORY_VISION_RUN_DIR:-${ROOT_DIR}/.run/vision}/webrtc-sidecar"
LOG_DIR="${RUN_DIR}/logs"
PID_FILE="${RUN_DIR}/pids.tsv"
STATUS_FILE="${RUN_DIR}/status.env"
CONFIG_FILE="${WEBRTC_SIDECAR_CONFIG_FILE:-${RUN_DIR}/mediamtx.yml}"

MEDIAMTX_BIN="${MEDIAMTX_BIN:-mediamtx}"
FFMPEG_BIN="${FFMPEG_BIN:-ffmpeg}"
FFPROBE_BIN="${FFPROBE_BIN:-ffprobe}"
CURL_BIN="${CURL_BIN:-curl}"

MEDIAMTX_RTSP_PORT="${MEDIAMTX_RTSP_PORT:-18554}"
MEDIAMTX_WEBRTC_PORT="${MEDIAMTX_WEBRTC_PORT:-8889}"
MEDIAMTX_WEBRTC_ICE_UDP_PORT="${MEDIAMTX_WEBRTC_ICE_UDP_PORT:-8189}"
MEDIAMTX_API_PORT="${MEDIAMTX_API_PORT:-19997}"
MEDIAMTX_WEBRTC_ALLOW_ORIGINS="${MEDIAMTX_WEBRTC_ALLOW_ORIGINS:-http://smartfactory-main.local:8088,http://localhost:8088,http://127.0.0.1:8088}"
WEBRTC_SIDECAR_PUBLIC_HOST="${WEBRTC_SIDECAR_PUBLIC_HOST:-${VISION_PUBLIC_HOST:-smartfactory-vision.local}}"
WEBRTC_SIDECAR_STREAMS="${WEBRTC_SIDECAR_STREAMS:-global_cam_01/full,global_cam_01/lift_roi}"
WEBRTC_SIDECAR_INPUT_MAX_FPS="${WEBRTC_SIDECAR_INPUT_MAX_FPS:-15}"
WEBRTC_SIDECAR_TARGET_FPS="${WEBRTC_SIDECAR_TARGET_FPS:-15}"
WEBRTC_SIDECAR_BITRATE="${WEBRTC_SIDECAR_BITRATE:-2500k}"
WEBRTC_SIDECAR_BUFSIZE="${WEBRTC_SIDECAR_BUFSIZE:-5000k}"
WEBRTC_SIDECAR_RESTART_SEC="${WEBRTC_SIDECAR_RESTART_SEC:-2}"
WEBRTC_SIDECAR_VIDEO_FILTER="${WEBRTC_SIDECAR_VIDEO_FILTER:-scale=trunc(iw/2)*2:trunc(ih/2)*2}"
WEBRTC_SIDECAR_INPUT_URL_TEMPLATE="${WEBRTC_SIDECAR_INPUT_URL_TEMPLATE:-}"
if [ -z "${WEBRTC_SIDECAR_INPUT_URL_TEMPLATE}" ]; then
  WEBRTC_SIDECAR_INPUT_URL_TEMPLATE="http://127.0.0.1:${VISION_STREAM_GATEWAY_PORT:-8090}/api/v1/vision/overlay/stream?source={source}&view={view}&max_fps={max_fps}"
fi
WEBRTC_SIDECAR_ENCODER="${WEBRTC_SIDECAR_ENCODER:-libx264}"
WEBRTC_SIDECAR_X264_PRESET="${WEBRTC_SIDECAR_X264_PRESET:-veryfast}"
SF_VISION_TMUX_GUARD_ENABLED="${SF_VISION_TMUX_GUARD_ENABLED:-true}"
SF_VISION_TMUX_REQUIRED_CONTEXT="${SF_VISION_TMUX_REQUIRED_CONTEXT:-Smartfactory:3:Development}"

PIDS=()
NAMES=()

usage() {
  cat <<USAGE
Usage: $(basename "$0") [--check|--print-config|--status|--smoke|run]

Run a MediaMTX WebRTC sidecar for SmartFactory Vision overlay streams.
The sidecar is media-only: it does not expose ROS control, Nav2, /cmd_vel,
DB writes, or evidence truth mutation.

Typical operator path:
  ./scripts/vision/sf_vision.sh up lab-gopro-tb3-webrtc
  ./scripts/vision/sf_vision.sh status
  ./scripts/vision/run_webrtc_sidecar_mediamtx.sh --status

Prerequisites:
  - mediamtx on PATH, or MEDIAMTX_BIN=/path/to/mediamtx
  - ffmpeg/ffprobe on PATH
  - for live run: tmux ${SF_VISION_TMUX_REQUIRED_CONTEXT}
USAGE
}

log() {
  printf '[webrtc-sidecar] %s\n' "$*"
}

is_truthy() {
  case "${1:-}" in
    1|true|TRUE|yes|YES|y|Y|on|ON) return 0 ;;
    *) return 1 ;;
  esac
}

current_tmux_context() {
  if [ -z "${TMUX:-}" ] || ! command -v tmux >/dev/null 2>&1; then
    return 1
  fi
  tmux display-message -p '#S:#I:#W' 2>/dev/null
}

require_live_tmux_context() {
  if ! is_truthy "${SF_VISION_TMUX_GUARD_ENABLED}"; then
    return 0
  fi
  local current
  current="$(current_tmux_context || true)"
  if [ "${current}" = "${SF_VISION_TMUX_REQUIRED_CONTEXT}" ]; then
    return 0
  fi
  cat >&2 <<ERROR
ERROR: live WebRTC sidecar processes must run in tmux ${SF_VISION_TMUX_REQUIRED_CONTEXT}.
Current context: ${current:-<not inside tmux>}
Use ./scripts/vision/sf_vision.sh up lab-gopro-tb3-webrtc from that tmux window.
ERROR
  return 1
}

is_executable_cmd() {
  local cmd="$1"
  if [[ "${cmd}" == */* ]]; then
    [ -x "${cmd}" ]
  else
    command -v "${cmd}" >/dev/null 2>&1
  fi
}

slug() {
  printf '%s' "$1" | tr -c 'A-Za-z0-9_-' '_' | sed -e 's/^_*//' -e 's/_*$//'
}

csv_to_json_array() {
  local raw="$1"
  if command -v python3 >/dev/null 2>&1; then
    python3 - "$raw" <<'PY'
import json
import sys
print(json.dumps([item.strip() for item in sys.argv[1].split(",") if item.strip()]))
PY
    return
  fi
  local IFS=',' item first=1
  printf '['
  for item in ${raw}; do
    item="${item#${item%%[![:space:]]*}}"
    item="${item%${item##*[![:space:]]}}"
    [ -n "${item}" ] || continue
    if [ "${first}" -eq 0 ]; then printf ','; fi
    first=0
    item="${item//\"/}"
    printf '"%s"' "${item}"
  done
  printf ']'
}

stream_source() {
  local spec="$1"
  spec="${spec//[[:space:]]/}"
  printf '%s' "${spec%%/*}"
}

stream_view() {
  local spec="$1"
  spec="${spec//[[:space:]]/}"
  if [[ "${spec}" == */* ]]; then
    printf '%s' "${spec#*/}"
  else
    printf 'full'
  fi
}

stream_path_id() {
  local source view
  source="$(slug "$(stream_source "$1")")"
  view="$(slug "$(stream_view "$1")")"
  printf '%s_%s' "${source}" "${view}"
}

render_input_url() {
  local source="$1" view="$2"
  local url="${WEBRTC_SIDECAR_INPUT_URL_TEMPLATE}"
  url="${url//\{source\}/${source}}"
  url="${url//\{source_id\}/${source}}"
  url="${url//\{view\}/${view}}"
  url="${url//\{view_id\}/${view}}"
  url="${url//\{max_fps\}/${WEBRTC_SIDECAR_INPUT_MAX_FPS}}"
  printf '%s' "${url}"
}

read_stream_specs() {
  local -n _out="$1"
  local raw spec
  IFS=',' read -r -a _out <<< "${WEBRTC_SIDECAR_STREAMS}"
  local cleaned=()
  for raw in "${_out[@]}"; do
    spec="${raw//[[:space:]]/}"
    [ -n "${spec}" ] || continue
    cleaned+=("${spec}")
  done
  _out=("${cleaned[@]}")
}

stream_paths_csv() {
  local specs=() spec path paths=()
  read_stream_specs specs
  for spec in "${specs[@]}"; do
    path="$(stream_path_id "${spec}")"
    paths+=("${path}")
  done
  local IFS=','
  printf '%s' "${paths[*]}"
}

print_config() {
  local specs=() spec source view path input_url
  read_stream_specs specs
  cat <<CONFIG
SmartFactory Vision WebRTC sidecar config
  run_dir: ${RUN_DIR}
  config_file: ${CONFIG_FILE}
  mediamtx_bin: ${MEDIAMTX_BIN}
  ffmpeg_bin: ${FFMPEG_BIN}
  ffprobe_bin: ${FFPROBE_BIN}
  public_host: ${WEBRTC_SIDECAR_PUBLIC_HOST}
  rtsp: rtsp://127.0.0.1:${MEDIAMTX_RTSP_PORT}/<path>
  browser_url_template: http://${WEBRTC_SIDECAR_PUBLIC_HOST}:${MEDIAMTX_WEBRTC_PORT}/{source}_{view}
  whep_url_template: http://${WEBRTC_SIDECAR_PUBLIC_HOST}:${MEDIAMTX_WEBRTC_PORT}/{source}_{view}/whep
  mediamtx_ports: rtsp=${MEDIAMTX_RTSP_PORT}/tcp, webrtc=${MEDIAMTX_WEBRTC_PORT}/tcp, ice=${MEDIAMTX_WEBRTC_ICE_UDP_PORT}/udp, api=127.0.0.1:${MEDIAMTX_API_PORT}/tcp
  webrtc_allow_origins: ${MEDIAMTX_WEBRTC_ALLOW_ORIGINS}
  input_url_template: ${WEBRTC_SIDECAR_INPUT_URL_TEMPLATE}
  video_filter: ${WEBRTC_SIDECAR_VIDEO_FILTER}
  streams:
CONFIG
  for spec in "${specs[@]}"; do
    source="$(stream_source "${spec}")"
    view="$(stream_view "${spec}")"
    path="$(stream_path_id "${spec}")"
    input_url="$(render_input_url "${source}" "${view}")"
    cat <<CONFIG
    - spec=${spec} path=${path}
      input=${input_url}
      rtsp=rtsp://127.0.0.1:${MEDIAMTX_RTSP_PORT}/${path}
      browser=http://${WEBRTC_SIDECAR_PUBLIC_HOST}:${MEDIAMTX_WEBRTC_PORT}/${path}
      whep=http://${WEBRTC_SIDECAR_PUBLIC_HOST}:${MEDIAMTX_WEBRTC_PORT}/${path}/whep
CONFIG
  done
}

install_guidance() {
  cat <<'GUIDANCE' >&2

Install MediaMTX before using the WebRTC sidecar:
  1) Download the Linux amd64 release from https://github.com/bluenviron/mediamtx/releases
  2) Extract it and place the `mediamtx` binary on PATH, or set:
       export MEDIAMTX_BIN=/absolute/path/to/mediamtx
  3) Verify:
       ./scripts/vision/run_webrtc_sidecar_mediamtx.sh --check

ffmpeg is also required. On Ubuntu it is usually available with:
  sudo apt install ffmpeg
GUIDANCE
}

port_tcp_in_use() {
  local port="$1"
  if command -v ss >/dev/null 2>&1; then
    ss -H -ltn 2>/dev/null | awk '{print $4}' | grep -Eq "(^|:)${port}$"
  else
    return 1
  fi
}

port_udp_in_use() {
  local port="$1"
  if command -v ss >/dev/null 2>&1; then
    ss -H -lun 2>/dev/null | awk '{print $4}' | grep -Eq "(^|:)${port}$"
  else
    return 1
  fi
}

check_port_free() {
  local kind="$1" port="$2" label="$3"
  if [ "${kind}" = "tcp" ]; then
    if port_tcp_in_use "${port}"; then
      echo "ERROR: ${label} tcp/${port} is already in use" >&2
      return 1
    fi
  else
    if port_udp_in_use "${port}"; then
      echo "ERROR: ${label} udp/${port} is already in use" >&2
      return 1
    fi
  fi
}

validate_specs() {
  local specs=() spec source view path count=0
  read_stream_specs specs
  if [ "${#specs[@]}" -eq 0 ]; then
    echo "ERROR: WEBRTC_SIDECAR_STREAMS is empty" >&2
    return 1
  fi
  for spec in "${specs[@]}"; do
    source="$(stream_source "${spec}")"
    view="$(stream_view "${spec}")"
    path="$(stream_path_id "${spec}")"
    if [ -z "${source}" ] || [ -z "${view}" ] || [ -z "${path}" ]; then
      echo "ERROR: invalid stream spec: ${spec}" >&2
      return 1
    fi
    count=$((count + 1))
  done
}

run_check() {
  local ok=0
  validate_specs || ok=1
  if ! is_executable_cmd "${MEDIAMTX_BIN}"; then
    echo "ERROR: mediamtx executable not found: ${MEDIAMTX_BIN}" >&2
    install_guidance
    ok=1
  fi
  if ! is_executable_cmd "${FFMPEG_BIN}"; then
    echo "ERROR: ffmpeg executable not found: ${FFMPEG_BIN}" >&2
    ok=1
  fi
  if ! is_executable_cmd "${FFPROBE_BIN}"; then
    echo "WARN: ffprobe executable not found: ${FFPROBE_BIN}; --smoke RTSP readability check will be unavailable" >&2
  fi
  if ! is_executable_cmd "${CURL_BIN}"; then
    echo "ERROR: curl executable not found: ${CURL_BIN}" >&2
    ok=1
  fi
  check_port_free tcp "${MEDIAMTX_RTSP_PORT}" "MediaMTX RTSP" || ok=1
  check_port_free tcp "${MEDIAMTX_WEBRTC_PORT}" "MediaMTX WebRTC HTTP" || ok=1
  check_port_free tcp "${MEDIAMTX_API_PORT}" "MediaMTX API" || ok=1
  check_port_free udp "${MEDIAMTX_WEBRTC_ICE_UDP_PORT}" "MediaMTX WebRTC ICE" || ok=1
  if [ "${ok}" -ne 0 ]; then
    return 1
  fi
  log "check ok"
}

write_config() {
  mkdir -p "${RUN_DIR}" "${LOG_DIR}"
  local specs=() spec path
  read_stream_specs specs
  local additional_hosts="[]"
  local allow_origins
  allow_origins="$(csv_to_json_array "${MEDIAMTX_WEBRTC_ALLOW_ORIGINS}")"
  if [ -n "${WEBRTC_SIDECAR_PUBLIC_HOST}" ]; then
    additional_hosts="[\"${WEBRTC_SIDECAR_PUBLIC_HOST}\"]"
  fi
  cat > "${CONFIG_FILE}" <<YAML
logLevel: info
logDestinations: [stdout]

api: true
apiAddress: 127.0.0.1:${MEDIAMTX_API_PORT}
metrics: false
pprof: false
playback: false

rtsp: true
rtspTransports: [tcp]
rtspAddress: 127.0.0.1:${MEDIAMTX_RTSP_PORT}
rtmp: false
hls: false
srt: false
moq: false

webrtc: true
webrtcAddress: :${MEDIAMTX_WEBRTC_PORT}
webrtcEncryption: false
webrtcAllowOrigins: ${allow_origins}
webrtcLocalUDPAddress: :${MEDIAMTX_WEBRTC_ICE_UDP_PORT}
webrtcLocalTCPAddress: ""
webrtcIPsFromInterfaces: true
webrtcAdditionalHosts: ${additional_hosts}

pathDefaults:
  source: publisher
  overridePublisher: false

paths:
YAML
  for spec in "${specs[@]}"; do
    path="$(stream_path_id "${spec}")"
    cat >> "${CONFIG_FILE}" <<YAML
  ${path}:
    source: publisher
YAML
  done
}

record_process() {
  local name="$1" pid="$2" log_file="$3"
  printf '%s\t%s\t%s\n' "${name}" "${pid}" "${log_file}" >> "${PID_FILE}"
}

write_status() {
  local status="$1" mediamtx_pid="${2:-}" expected="${3:-0}"
  cat > "${STATUS_FILE}" <<STATUS
STATUS=${status}
MEDIAMTX_PID=${mediamtx_pid}
EXPECTED_PUBLISHERS=${expected}
STREAM_PATHS=$(stream_paths_csv)
MEDIAMTX_RTSP_PORT=${MEDIAMTX_RTSP_PORT}
MEDIAMTX_WEBRTC_PORT=${MEDIAMTX_WEBRTC_PORT}
MEDIAMTX_WEBRTC_ICE_UDP_PORT=${MEDIAMTX_WEBRTC_ICE_UDP_PORT}
MEDIAMTX_API_PORT=${MEDIAMTX_API_PORT}
WEBRTC_SIDECAR_PUBLIC_HOST=${WEBRTC_SIDECAR_PUBLIC_HOST}
CONFIG_FILE=${CONFIG_FILE}
STATUS
}

alive_pid() {
  local pid="${1:-}"
  [ -n "${pid}" ] && kill -0 "${pid}" 2>/dev/null
}

publisher_loop() {
  local source="$1" view="$2" path="$3" input_url="$4" rtsp_url="$5"
  local restart_count=0
  while true; do
    restart_count=$((restart_count + 1))
    printf '[webrtc-sidecar] publisher path=%s source=%s view=%s start attempt=%s input=%s output=%s at %s\n' \
      "${path}" "${source}" "${view}" "${restart_count}" "${input_url}" "${rtsp_url}" "$(date -Is)"
    set +e
    "${FFMPEG_BIN}" \
      -hide_banner -loglevel warning \
      -reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 2 \
      -fflags nobuffer -flags low_delay \
      -f mpjpeg -i "${input_url}" \
      -vf "${WEBRTC_SIDECAR_VIDEO_FILTER}" \
      -an -c:v "${WEBRTC_SIDECAR_ENCODER}" -preset "${WEBRTC_SIDECAR_X264_PRESET}" \
      -tune zerolatency -pix_fmt yuv420p -r "${WEBRTC_SIDECAR_TARGET_FPS}" \
      -g "$((WEBRTC_SIDECAR_TARGET_FPS * 2))" -bf 0 \
      -b:v "${WEBRTC_SIDECAR_BITRATE}" -maxrate "${WEBRTC_SIDECAR_BITRATE}" -bufsize "${WEBRTC_SIDECAR_BUFSIZE}" \
      -f rtsp -rtsp_transport tcp "${rtsp_url}"
    local code=$?
    set -e
    printf '[webrtc-sidecar] publisher path=%s exited status=%s; retrying in %ss at %s\n' \
      "${path}" "${code}" "${WEBRTC_SIDECAR_RESTART_SEC}" "$(date -Is)"
    sleep "${WEBRTC_SIDECAR_RESTART_SEC}"
  done
}

cleanup() {
  local status=$?
  trap - INT TERM EXIT
  if [ "${#PIDS[@]}" -gt 0 ]; then
    log "stopping ${#PIDS[@]} child process(es)"
    local i
    for ((i=${#PIDS[@]}-1; i>=0; i--)); do
      kill -INT "${PIDS[$i]}" 2>/dev/null || true
    done
    sleep 1
    for ((i=${#PIDS[@]}-1; i>=0; i--)); do
      kill -TERM "${PIDS[$i]}" 2>/dev/null || true
    done
    wait 2>/dev/null || true
  fi
  write_status stopped "" 0 || true
  exit "${status}"
}

run_sidecar() {
  require_live_tmux_context
  run_check
  rm -f "${PID_FILE}"
  write_config
  local specs=() spec source view path input_url rtsp_url publisher_log
  read_stream_specs specs
  write_status starting "" "${#specs[@]}"
  log "starting MediaMTX with ${CONFIG_FILE}"
  "${MEDIAMTX_BIN}" "${CONFIG_FILE}" > "${LOG_DIR}/mediamtx.log" 2>&1 &
  local mediamtx_pid=$!
  PIDS+=("${mediamtx_pid}")
  NAMES+=("mediamtx")
  record_process mediamtx "${mediamtx_pid}" "${LOG_DIR}/mediamtx.log"
  write_status running "${mediamtx_pid}" "${#specs[@]}"
  sleep 1
  for spec in "${specs[@]}"; do
    source="$(stream_source "${spec}")"
    view="$(stream_view "${spec}")"
    path="$(stream_path_id "${spec}")"
    input_url="$(render_input_url "${source}" "${view}")"
    rtsp_url="rtsp://127.0.0.1:${MEDIAMTX_RTSP_PORT}/${path}"
    publisher_log="${LOG_DIR}/publisher-${path}.log"
    publisher_loop "${source}" "${view}" "${path}" "${input_url}" "${rtsp_url}" > "${publisher_log}" 2>&1 &
    local publisher_pid=$!
    PIDS+=("${publisher_pid}")
    NAMES+=("publisher-${path}")
    record_process "publisher-${path}" "${publisher_pid}" "${publisher_log}"
    log "publisher-${path} pid=${publisher_pid} log=${publisher_log}"
  done
  log "running. Browser URL example: http://${WEBRTC_SIDECAR_PUBLIC_HOST}:${MEDIAMTX_WEBRTC_PORT}/$(stream_path_id "${specs[0]}")"
  trap cleanup INT TERM EXIT
  wait -n "${PIDS[@]}"
  local child_status=$?
  log "a child exited status=${child_status}; shutting down sidecar"
  exit "${child_status}"
}

status_from_files() {
  local configured=0 mediamtx_pid="" expected=0 paths="" web_port="${MEDIAMTX_WEBRTC_PORT}" rtsp_port="${MEDIAMTX_RTSP_PORT}" public_host="${WEBRTC_SIDECAR_PUBLIC_HOST}"
  if [ -f "${STATUS_FILE}" ]; then
    configured=1
    # shellcheck disable=SC1090
    source "${STATUS_FILE}"
    mediamtx_pid="${MEDIAMTX_PID:-}"
    expected="${EXPECTED_PUBLISHERS:-0}"
    paths="${STREAM_PATHS:-}"
    web_port="${MEDIAMTX_WEBRTC_PORT:-${web_port}}"
    rtsp_port="${MEDIAMTX_RTSP_PORT:-${rtsp_port}}"
    public_host="${WEBRTC_SIDECAR_PUBLIC_HOST:-${public_host}}"
  elif [ -f "${CONFIG_FILE}" ]; then
    configured=1
  fi

  local alive_publishers=0 total_publishers=0 name pid log_file mediamtx_alive=false
  if [ -f "${PID_FILE}" ]; then
    while IFS=$'\t' read -r name pid log_file; do
      [ -n "${name:-}" ] || continue
      if [ "${name}" = "mediamtx" ]; then
        alive_pid "${pid}" && mediamtx_alive=true
      elif [[ "${name}" == publisher-* ]]; then
        total_publishers=$((total_publishers + 1))
        alive_pid "${pid}" && alive_publishers=$((alive_publishers + 1))
      fi
    done < "${PID_FILE}"
  fi
  if alive_pid "${mediamtx_pid}"; then
    mediamtx_alive=true
  fi

  local reachable=false
  if [ "${mediamtx_alive}" = true ] && is_executable_cmd "${CURL_BIN}"; then
    if "${CURL_BIN}" -fsS --max-time 1 "http://127.0.0.1:${web_port}/" >/dev/null 2>&1; then
      reachable=true
    elif "${CURL_BIN}" -sS --max-time 1 "http://127.0.0.1:${web_port}/" >/dev/null 2>&1; then
      reachable=true
    fi
  fi

  local state="not_configured" exit_code=1
  if [ "${configured}" -eq 1 ]; then
    state="configured"
    if [ "${reachable}" != true ]; then
      state="mediamtx_unreachable"
    elif [ "${expected}" -gt 0 ] && [ "${alive_publishers}" -lt "${expected}" ]; then
      state="publisher_missing"
    elif [ "${alive_publishers}" -gt 0 ]; then
      state="publisher_alive"
      exit_code=0
    fi
  fi

  cat <<STATUS
SmartFactory Vision WebRTC sidecar status
  state: ${state}
  run_dir: ${RUN_DIR}
  config_file: ${CONFIG_FILE}
  mediamtx_alive: ${mediamtx_alive}
  mediamtx_http_reachable: ${reachable}
  expected_publishers: ${expected}
  alive_publishers: ${alive_publishers}/${total_publishers}
  rtsp_port: ${rtsp_port}
  webrtc_port: ${web_port}
  paths: ${paths:-<unknown>}
STATUS
  if [ -n "${paths:-}" ]; then
    local IFS=',' path
    for path in ${paths}; do
      printf '  browser: http://%s:%s/%s\n' "${public_host}" "${web_port}" "${path}"
      printf '  whep: http://%s:%s/%s/whep\n' "${public_host}" "${web_port}" "${path}"
    done
  fi
  return "${exit_code}"
}

smoke_readability() {
  status_from_files
  if ! is_executable_cmd "${FFPROBE_BIN}"; then
    echo "ERROR: ffprobe not found: ${FFPROBE_BIN}" >&2
    return 1
  fi
  local paths=""
  if [ -f "${STATUS_FILE}" ]; then
    # shellcheck disable=SC1090
    source "${STATUS_FILE}"
    paths="${STREAM_PATHS:-}"
  fi
  local first_path="${paths%%,*}"
  if [ -z "${first_path}" ]; then
    echo "ERROR: no sidecar path recorded" >&2
    return 1
  fi
  log "ffprobe RTSP readability: rtsp://127.0.0.1:${MEDIAMTX_RTSP_PORT}/${first_path}"
  "${FFPROBE_BIN}" -v error -rtsp_transport tcp -timeout 3000000 \
    -select_streams v:0 -show_entries stream=codec_name -of default=noprint_wrappers=1 \
    "rtsp://127.0.0.1:${MEDIAMTX_RTSP_PORT}/${first_path}" >/dev/null
  log "smoke ok: ${first_path} is readable via RTSP; WebRTC browser/WHEP endpoint is advertised by MediaMTX"
}

cmd="${1:-run}"
case "${cmd}" in
  run) run_sidecar ;;
  --check|check) run_check ;;
  --print-config|print-config) print_config ;;
  --status|status) status_from_files ;;
  --smoke|smoke) smoke_readability ;;
  --help|-h|help) usage ;;
  *) echo "ERROR: unknown command: ${cmd}" >&2; usage >&2; exit 2 ;;
esac
