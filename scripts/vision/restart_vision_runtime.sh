#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
PROFILE="lab-gopro-tb3-low-load"
OVERRIDE_FILE=""
DELAY_SEC="1"
RUN_ID="manual"
GIT_PULL="false"
REQUIRE_CLEAN_GIT="true"

usage() {
  cat <<USAGE
Usage: $(basename "$0") --profile lab-gopro-tb3-low-load --override-file <env-file> [--delay-sec 1] [--run-id id] [--git-pull]

Lab-only detached helper used by the AI Server operator runtime-control API.
It waits briefly so the HTTP response can return, optionally updates the current
branch with git pull --ff-only, stops the current Vision runtime, and starts the
low-load profile with SF_VISION_RUNTIME_OVERRIDE_FILE applied.

Safety boundary: this helper only restarts the local Vision runtime; it does not
start robot motion, Nav2, teleop, /cmd_vel, ROS parameter mutation, or DB writes.
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --profile)
      PROFILE="${2:-}"; shift 2 ;;
    --override-file)
      OVERRIDE_FILE="${2:-}"; shift 2 ;;
    --delay-sec)
      DELAY_SEC="${2:-}"; shift 2 ;;
    --run-id)
      RUN_ID="${2:-}"; shift 2 ;;
    --git-pull)
      GIT_PULL="true"; shift ;;
    --require-clean-git)
      REQUIRE_CLEAN_GIT="true"; shift ;;
    --allow-dirty-git)
      REQUIRE_CLEAN_GIT="false"; shift ;;
    --help|-h)
      usage; exit 0 ;;
    *)
      echo "ERROR: unknown argument: $1" >&2
      usage >&2
      exit 2 ;;
  esac
done

case "${PROFILE}" in
  low-load|lowload|lite) PROFILE="lab-gopro-tb3-low-load" ;;
  lab-gopro-tb3-low-load) ;;
  *)
    echo "ERROR: restart helper only supports lab-gopro-tb3-low-load, got: ${PROFILE}" >&2
    exit 2 ;;
esac

if [ -z "${OVERRIDE_FILE}" ] || [ ! -f "${OVERRIDE_FILE}" ]; then
  echo "ERROR: override file not found: ${OVERRIDE_FILE:-<empty>}" >&2
  exit 2
fi

case "${DELAY_SEC}" in
  ''|*[!0-9.]* )
    echo "ERROR: --delay-sec must be numeric: ${DELAY_SEC}" >&2
    exit 2 ;;
esac

cd "${ROOT_DIR}"

current_tmux_context() {
  if [ -z "${TMUX:-}" ] || ! command -v tmux >/dev/null 2>&1; then
    return 1
  fi
  if [ -n "${TMUX_PANE:-}" ]; then
    tmux display-message -p -t "${TMUX_PANE}" '#S:#I:#W' 2>/dev/null && return 0
  fi
  tmux display-message -p '#S:#I:#W' 2>/dev/null
}

tmux_pane_context() {
  local pane="$1"
  if [ -z "${pane}" ] || ! command -v tmux >/dev/null 2>&1; then
    return 1
  fi
  tmux display-message -p -t "${pane}" '#S:#I:#W' 2>/dev/null
}

preflight_tmux_context_before_destructive_steps() {
  case "${SF_VISION_TMUX_GUARD_ENABLED:-true}" in
    0|false|FALSE|no|NO|off|OFF) return 0 ;;
  esac
  local required current
  required="${SF_VISION_TMUX_REQUIRED_CONTEXT:-Smartfactory:3:Development}"
  current="$(current_tmux_context || true)"
  if [ "${current}" = "${required}" ]; then
    return 0
  fi
  cat >&2 <<ERROR
ERROR: refusing remote restart before stopping current runtime because tmux context is not ${required}.
Current context: ${current:-<not inside tmux>}
Start the laptop low-load runtime from the required tmux pane once, then retry runtime-control.
ERROR
  exit 4
}

runtime_tmux_target_pane() {
  printf '%s\n' "${SF_RUNTIME_CONTROL_TMUX_PANE:-${TMUX_PANE:-}}"
}

preflight_runtime_target_pane() {
  case "${SF_VISION_TMUX_GUARD_ENABLED:-true}" in
    0|false|FALSE|no|NO|off|OFF) return 0 ;;
  esac
  local required target target_context
  required="${SF_VISION_TMUX_REQUIRED_CONTEXT:-Smartfactory:3:Development}"
  target="$(runtime_tmux_target_pane)"
  target_context="$(tmux_pane_context "${target}" || true)"
  if [ -n "${target}" ] && [ "${target_context}" = "${required}" ]; then
    return 0
  fi
  cat >&2 <<ERROR
ERROR: refusing remote restart because target tmux pane is not in ${required}.
Target pane: ${target:-<empty>}
Target context: ${target_context:-<unavailable>}
Start the laptop low-load runtime from the required tmux pane once, then retry runtime-control.
ERROR
  exit 4
}

shell_quote() {
  printf '%q' "$1"
}

append_env_assignment() {
  local name="$1"
  if [ -n "${!name+x}" ]; then
    LAUNCH_COMMAND+=" ${name}=$(shell_quote "${!name}")"
  fi
}

build_launch_command() {
  LAUNCH_COMMAND="cd $(shell_quote "${ROOT_DIR}") && env -u VISION_STREAM_SOURCE_UPSTREAMS_JSON"
  for name in \
    SF_RUNTIME_CONTROL_ENABLED \
    SF_RUNTIME_CONTROL_TOKEN \
    SF_VISION_TMUX_GUARD_ENABLED \
    SF_VISION_TMUX_REQUIRED_CONTEXT \
    AI_SERVER_HOST \
    AI_SERVER_PORT \
    AI_SERVER_URL \
    VISION_MODEL_WORKER_ENABLED \
    VISION_MODEL_PATH \
    VISION_MODEL_TASK \
    VISION_MODEL_DEVICE \
    VISION_MODEL_IMGSZ \
    VISION_MODEL_CONF \
    VISION_MODEL_IOU \
    VISION_GATEWAY_REQUEST_TIMEOUT_SEC
  do
    append_env_assignment "${name}"
  done
  LAUNCH_COMMAND+=" SF_VISION_RUNTIME_OVERRIDE_FILE=$(shell_quote "${OVERRIDE_FILE}")"
  LAUNCH_COMMAND+=" SF_RUNTIME_CONTROL_RUN_ID=$(shell_quote "${RUN_ID}")"
  LAUNCH_COMMAND+=" ./scripts/vision/sf_vision.sh up $(shell_quote "${PROFILE}")"
}

start_runtime_in_tmux_pane() {
  local target buffer loaded
  target="$(runtime_tmux_target_pane)"
  preflight_runtime_target_pane
  build_launch_command
  buffer="sf-runtime-control-${RUN_ID}"
  tmux set-buffer -b "${buffer}" -- "${LAUNCH_COMMAND}"
  loaded="$(tmux show-buffer -b "${buffer}")"
  if [ "${loaded}" != "${LAUNCH_COMMAND}" ]; then
    echo "ERROR: tmux buffer verification failed for ${buffer}" >&2
    exit 5
  fi
  tmux send-keys -t "${target}" C-u
  tmux paste-buffer -t "${target}" -b "${buffer}" -p -d
  tmux send-keys -t "${target}" Enter
  echo "[runtime-control] pasted restart command into tmux pane ${target}"
}

preflight_tmux_context_before_destructive_steps

echo "[runtime-control] run_id=${RUN_ID} profile=${PROFILE} override=${OVERRIDE_FILE} delay=${DELAY_SEC}s git_pull=${GIT_PULL} require_clean_git=${REQUIRE_CLEAN_GIT}"
echo "[runtime-control] sleeping before restart so API response can return"
sleep "${DELAY_SEC}"

if [ "${GIT_PULL}" = "true" ]; then
  echo "[runtime-control] checking git state before pull"
  if [ "${REQUIRE_CLEAN_GIT}" = "true" ] && [ -n "$(git status --porcelain)" ]; then
    echo "ERROR: git working tree is dirty; refusing remote pull/restart" >&2
    git status --short >&2 || true
    exit 3
  fi
  echo "[runtime-control] git pull --ff-only"
  git pull --ff-only
fi

echo "[runtime-control] stopping existing Vision runtime"
./scripts/vision/sf_vision.sh down || true

echo "[runtime-control] starting ${PROFILE} with override file in the operator tmux pane"
start_runtime_in_tmux_pane
