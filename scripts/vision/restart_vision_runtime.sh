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

echo "[runtime-control] starting ${PROFILE} with override file"
# The helper is spawned by the AI Server, which itself was started by a previous
# Vision runtime. Do not let derived runtime values from that parent process
# leak into the replacement runtime: sf_vision.sh/profile defaults must
# recompute these from the selected profile plus the explicit override file.
unset VISION_STREAM_SOURCE_UPSTREAMS_JSON
export SF_VISION_RUNTIME_OVERRIDE_FILE="${OVERRIDE_FILE}"
export SF_RUNTIME_CONTROL_RUN_ID="${RUN_ID}"
exec ./scripts/vision/sf_vision.sh up "${PROFILE}"
